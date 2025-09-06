"""
Check video files for integrity and retrieve download links for damaged files.
"""
import os
import subprocess
from pathlib import Path
import logging
from tqdm import tqdm
import sqlite3
from openai import OpenAI

from movie_crawler.config.paths import MOVIES_DIRECTORY, DB_PATH
from movie_crawler.config.services import OPENAI_API_KEY, OPENAI_BASE_URL, OPENAI_MODEL
from movie_crawler.config.files import VIDEO_EXTENSIONS


from movie_crawler.utils.common import string_similarity
from movie_crawler.utils.database import get_db_connection


class VideoIntegrityChecker:
    """Check video files for integrity and get download links for damaged files."""

    def __init__(self, directory=MOVIES_DIRECTORY, max_size_gb=1.0):
        """
        Initialize the video integrity checker.

        Args:
            directory (str): Directory to scan for video files
            max_size_gb (float): Maximum file size to check in GB
        """
        self.directory = Path(directory)
        self.max_size_bytes = max_size_gb * 1024 * 1024 * 1024
        self.logger = logging.getLogger(__name__)

    def check_video_integrity(self, video_path):
        """
        Check the integrity of a single video file.

        Args:
            video_path (str or Path): Path to the video file

        Returns:
            bool: True if the video is intact, False otherwise
        """
        try:
            # Use ffmpeg to check video integrity
            result = subprocess.run(
                ['ffmpeg', '-v', 'error', '-i', str(video_path), '-f', 'null', '-'],
                stderr=subprocess.PIPE,
                stdout=subprocess.PIPE
            )
            # If no error output, the video is intact
            return len(result.stderr) == 0
        except Exception as e:
            self.logger.error(f"Error checking video {video_path}: {e}")
            return False

    def scan_videos_recursive(self):
        """
        Recursively scan directory for video files and check their integrity.

        Returns:
            dict: Dictionary mapping file paths to integrity status
        """
        results = {}

        try:
            # Collect all video files
            video_files = [
                path for path in Path(self.directory).rglob('*')
                if path.is_file()
                and path.suffix.lower() in VIDEO_EXTENSIONS
                and path.stat().st_size < self.max_size_bytes
            ]

            self.logger.info(f"Found {len(video_files)} video files to check")

            # Check each file with a progress bar
            for path in tqdm(video_files, desc="Checking video integrity", unit="file"):
                file_size_mb = path.stat().st_size / (1024 * 1024)  # Convert to MB
                is_valid = self.check_video_integrity(str(path))
                results[str(path)] = is_valid

                # Log result for current file
                tqdm.write(f"Checking video: {path}")
                tqdm.write(f"File size: {file_size_mb:.2f}MB")
                tqdm.write(f"Integrity: {'OK' if is_valid else 'DAMAGED'}")
                tqdm.write("-" * 50)

        except Exception as e:
            self.logger.error(f"Error scanning directory {self.directory}: {e}")

        return results


class MovieMatcher:
    """Match damaged movies with database entries to retrieve download links."""

    def __init__(self, db_path=DB_PATH, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL):
        """
        Initialize the movie matcher.

        Args:
            db_path (str): Path to the movie database
            api_key (str): OpenAI API key
            base_url (str): OpenAI API base URL
        """
        self.db_path = db_path
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)

    def is_same_movie(self, name1, name2, year1, year2):
        """
        Use OpenAI to determine if two movie names refer to the same movie.

        Args:
            name1 (str): First movie name
            name2 (str): Second movie name
            year1 (str): First movie year
            year2 (str): Second movie year

        Returns:
            bool: True if they are the same movie, False otherwise
        """
        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        system_prompt = """你是一个电影专家，需要判断用户给出的两个电影名称是否指向同一部电影。
        只需要回答 "是" 或 "否"，不需要任何解释。

        例如：
        《数码宝贝：最后的进化》(2020) 和 《数码宝贝大冒险：最后的进化·羁绊》(2020) -> 是
        《蜘蛛侠：平行宇宙》(2018) 和 《蜘蛛侠：穿越平行宇宙》(2018) -> 是
        《流浪地球》(2019) 和 《流浪地球2》(2023) -> 否
         闻香识女人 (1992) 和 闻香识女人 (未知年份) -> 是
        """

        user_prompt = f"第一部电影：《{name1}》({year1})\n第二部电影：《{name2}》({year2})"

        try:
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ]
            )
            return completion.choices[0].message.content.strip() == "是"
        except Exception as e:
            self.logger.error(f"Error calling OpenAI API: {e}")
            # Fall back to string similarity if API call fails
            name_similarity = string_similarity(name1, name2)
            year_similarity = year1 == year2 or year1 == "未知年份" or year2 == "未知年份"
            return name_similarity > 0.8 and year_similarity

    def get_movie_links_from_db(self, damaged_movies):
        """
        Find download links for damaged movies.

        Args:
            damaged_movies (list): List of paths to damaged movie files

        Returns:
            list: List of tuples (name, year, link) for matching movies
        """
        results = []

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                # Get all movies from the database
                cursor.execute("SELECT name, year, link FROM movie")
                all_movies = cursor.fetchall()

                for movie_path in damaged_movies:
                    # Extract movie name and year from path
                    movie_dir = Path(movie_path).parent.name
                    if '(' in movie_dir and ')' in movie_dir:
                        name = movie_dir.split('(')[0].strip()
                        year = movie_dir.split('(')[1].split(')')[0].strip()

                        found = False
                        potential_matches = []

                        # Step 1: Filter potential matches by string similarity
                        for db_name, db_year, db_link in all_movies:
                            # If the year matches, calculate name similarity
                            if year == db_year:
                                similarity = string_similarity(name, db_name)
                                if similarity > 0.3:  # Adjustable threshold
                                    potential_matches.append((db_name, db_year, db_link, similarity))

                        # Sort by similarity
                        potential_matches.sort(key=lambda x: x[3], reverse=True)

                        # Step 2: Use AI to confirm the match for top candidates
                        for db_name, db_year, db_link, _ in potential_matches[:3]:  # Check top 3
                            if self.is_same_movie(name, db_name, year, db_year):
                                # Remove the damaged file
                                os.remove(movie_path)
                                results.append((db_name, db_year, db_link))
                                found = True
                                self.logger.info(f"Match found: {name} ({year}) -> {db_name} ({db_year})")
                                break

                        if not found:
                            self.logger.warning(f"No match found for: {name} ({year})")
                    else:
                        self.logger.warning(f"Could not parse movie info from path: {movie_path}")

        except Exception as e:
            self.logger.error(f"Error querying database: {e}", exc_info=True)

        return results
