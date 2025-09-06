"""
Movie scraper for downloading movie information from DYTT8.
"""
import re
import urllib.parse
from bs4 import BeautifulSoup
import logging
from pathlib import Path


from movie_crawler.config.paths import DOWNLOAD_PATH
from movie_crawler.config.scraper import MOVIE_LIST_URL_TEMPLATE
from movie_crawler.utils.common import fetch_url_with_retry
from movie_crawler.utils.database import add_movie_to_database, check_movie_id, initialize_database
from movie_crawler.downloader.aria2 import add_magnet_link_to_aria2


class MovieScraper:
    """Scraper for fetching movie information from DYTT8."""

    def __init__(self, start_page=1, end_page=428, download_movies=False):
        """
        Initialize the movie scraper.

        Args:
            start_page (int): Page to start scraping from
            end_page (int): Page to end scraping at
            download_movies (bool): Whether to download movies immediately
        """
        self.start_page = start_page
        self.end_page = end_page
        self.download_movies = download_movies
        self.logger = logging.getLogger(__name__)

    def extract_movie_info(self, html, movie_url):
        """
        Extract movie information from the movie detail page HTML.

        Args:
            html (str): HTML content of the movie detail page
            movie_url (str): URL of the movie detail page

        Returns:
            tuple: (name, link, year, subtitle, resolution)
        """
        soup = BeautifulSoup(html, 'html.parser')

        # Get the full title from the page
        full_title = ""
        divs = soup.find_all('div', class_='title_all')
        for div in divs:
            if div.h1:
                full_title = div.h1.text
                break

        # If title not found in div, try header
        if not full_title:
            title_tag = soup.find('title')
            if title_tag:
                full_title = title_tag.text

        # Extract movie name from title
        name_match = re.search(r'《(.*?)》', full_title)
        name = name_match.group(1) if name_match else "未知电影名称"

        # Extract year from title
        year_match = re.search(r'(\d{4})年', full_title)
        year = year_match.group(1) if year_match else "未知年份"

        # Extract subtitle and resolution information
        subtitle_patterns = [
            ('中英双字', '中英双字'),
            ('中英字幕', '中英字幕'),
            ('国语中字', '国语中字'),
            ('BD', 'BD'),
            ('HD', 'HD')
        ]

        resolution_patterns = [
            ('1080P', '1080P'),
            ('HD', 'HD'),
            ('BD', 'BD')
        ]

        # Default values
        subtitle = "未知字幕"
        resolution = "未知分辨率"

        # Find subtitle and resolution in title
        for pattern, value in subtitle_patterns:
            if re.search(pattern, full_title):
                subtitle = value
                break

        for pattern, value in resolution_patterns:
            if re.search(pattern, full_title):
                resolution = value
                break

        # Find the download link
        link = self._extract_download_link(soup)

        return name, link, year, subtitle, resolution

    def _extract_download_link(self, soup):
        """
        Extract download link from soup object.

        Args:
            soup (BeautifulSoup): Parsed HTML

        Returns:
            str: Download link or empty string if not found
        """
        # Check regular links first
        for tag in soup.find_all('a'):
            href = tag.get('href')
            if href and (href.startswith('magnet') or href.startswith('ftp') or href.startswith('thunder')):
                return href

        # Check in zoom div if not found
        zoom_div = soup.find('div', id='Zoom')
        if zoom_div:
            for tag in zoom_div.find_all('a'):
                href = tag.get('href')
                if href and (href.startswith('magnet') or href.startswith('ftp') or href.startswith('thunder')):
                    return href

        return ""

    def scrape_movie_list_page(self, page_number):
        """
        Scrape a single movie list page.

        Args:
            page_number (int): Page number to scrape

        Returns:
            list: List of movie URLs to process
        """
        url = MOVIE_LIST_URL_TEMPLATE.format(page=page_number)
        self.logger.info(f"Scraping movie list page: {url}")

        try:
            html = fetch_url_with_retry(url)
            soup = BeautifulSoup(html, 'html.parser')

            # Find all movie links in the content area
            content_div = soup.find('div', class_='co_content8')
            if not content_div:
                self.logger.warning(f"Content div not found on page {page_number}")
                return []

            movie_links = []
            for a_tag in content_div.find_all('a'):
                href = a_tag.get('href', '')
                # Skip pagination links
                if href.startswith('list'):
                    continue

                # Build absolute URL
                movie_url = urllib.parse.urljoin(url, href)
                movie_links.append((movie_url, a_tag.text))

            self.logger.info(f"Found {len(movie_links)} movies on page {page_number}")
            return movie_links

        except Exception as e:
            self.logger.error(f"Failed to scrape page {page_number}: {e}", exc_info=True)
            return []

    def process_movie(self, movie_url, movie_title):
        """
        Process a single movie page.

        Args:
            movie_url (str): URL of the movie detail page
            movie_title (str): Title of the movie from the list page

        Returns:
            tuple: (success, movie_info)
        """
        self.logger.info(f"Processing movie: {movie_title} ({movie_url})")

        try:
            html = fetch_url_with_retry(movie_url)
            name, link, year, subtitle, resolution = self.extract_movie_info(html, movie_url)

            # Skip if we couldn't get essential information
            if name == "未知电影名称" or not link:
                self.logger.warning(f"Skipping movie with incomplete info: {movie_url}")
                return False, None

            # # Skip if movie already exists in database
            db_id = check_movie_id(name, year)
            self.logger.info(f"Checked database for movie: {name} ({year}), ID: {db_id}")

            if db_id:
                self.logger.info(f"Movie already exists in database: {name} ({year})")
            else:
                self.logger.info(f"Movie does not exist in database, adding: {name} ({year})")
                db_id = add_movie_to_database(name, link, year, subtitle, resolution)
            if self.download_movies and db_id:
                self.logger.info(f"Adding movie to Aria2 for download: {name} ({year})")
                add_magnet_link_to_aria2(link, db_id, name, year, DOWNLOAD_PATH)

            movie_info = {
                "name": name,
                "year": year,
                "subtitle": subtitle,
                "resolution": resolution,
                "link": link,
                "db_id": db_id
            }

            self.logger.info(f"Successfully processed movie: {name} ({year})")
            return True, movie_info

        except Exception as e:
            self.logger.error(f"Failed to process movie {movie_url}: {e}", exc_info=True)
            return False, None

    def run(self):
        """
        Run the scraper for the configured range of pages.

        Returns:
            int: Number of movies successfully scraped
        """
        initialize_database()
        self.logger.info(f"Starting scraper for pages {self.start_page} to {self.end_page}")

        successful_movies = 0

        for page in range(self.start_page, self.end_page + 1):
            try:
                self.logger.info(f"Processing page {page}/{self.end_page}")
                movie_links = self.scrape_movie_list_page(page)

                for movie_url, movie_title in movie_links:
                    success, _ = self.process_movie(movie_url, movie_title)
                    if success:
                        successful_movies += 1

                self.logger.info(f"Completed page {page}")

            except Exception as e:
                self.logger.error(f"Error processing page {page}: {e}", exc_info=True)
                continue

        self.logger.info(f"Scraping complete. Successfully processed {successful_movies} movies.")
        return successful_movies
