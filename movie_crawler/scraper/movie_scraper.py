"""
Movie scraper for 磁力熊 cilixiong.org.
"""
from __future__ import annotations

import html as html_stdlib
import logging
import re
import time
import urllib.parse
from typing import Dict, List, Optional, Tuple, Union

from bs4 import BeautifulSoup

from movie_crawler.config.paths import DOWNLOAD_PATH
from movie_crawler.config.scraper import (
    LIST_KIND_IMDB_TOP250,
    LIST_KIND_MOVIE,
    LIST_KIND_TOP250,
    REQUEST_GAP_SECONDS,
    movie_list_page_url,
)
from movie_crawler.downloader.aria2 import add_magnet_link_to_aria2
from movie_crawler.utils.common import fetch_url_with_retry
from movie_crawler.utils.database import (
    add_movie_to_database,
    check_movie_id,
    initialize_database,
)

def _element_has_card_class(classes) -> bool:
    """True if Bootstrap 'card' is present (BeautifulSoup gives str or list)."""
    if not classes:
        return False
    if isinstance(classes, str):
        tokens = classes.split()
    else:
        tokens = list(classes)
    return 'card' in tokens


def _sleep_after_response(gap_seconds: float) -> None:
    """Pace outbound requests after a successful HTTP response."""
    if gap_seconds and gap_seconds > 0:
        time.sleep(gap_seconds)


_MOVIE_DETAIL_PATH_RE = re.compile(r'/movie/\d+\.html$', re.IGNORECASE)
_INDEX_PAGE_PATH_RE = re.compile(r'/movie/index_(\d+)\.html$', re.IGNORECASE)
_TOP250_INDEX_PAGE_PATH_RE = re.compile(r'/top250/index_(\d+)\.html$', re.IGNORECASE)
_IMDB_TOP250_INDEX_PAGE_PATH_RE = re.compile(
    r'/s/imdbtop250/index_(\d+)\.html$',
    re.IGNORECASE,
)
_LIST_KIND_TO_INDEX_RE = {
    LIST_KIND_MOVIE: _INDEX_PAGE_PATH_RE,
    LIST_KIND_TOP250: _TOP250_INDEX_PAGE_PATH_RE,
    LIST_KIND_IMDB_TOP250: _IMDB_TOP250_INDEX_PAGE_PATH_RE,
}
_JIANPIAN_PATH_RE = re.compile(r'(?:^|[?&])path=([^&]+)', re.IGNORECASE)

# Sizes in torrent labels: [2.8G], 1.05 GiB, 820 MB
_LOOSE_SIZE = re.compile(
    r'(\d+(?:\.\d+)?)\s*(tib|tb|ti|gib|gb|gi|go|mb|mi|mib|m)\b',
    re.IGNORECASE,
)
_RES_HINT = re.compile(r'\b(2160p|4320p|4k|[0-9]+p)\b', re.I)
_SUBTITLE_PATTERNS = [
    ('中英双字', '中英双字'),
    ('中英字幕', '中英字幕'),
    ('国语中字', '国语中字'),
    ('简体中字', '简体中字'),
    ('中字', '中字'),
]


def _normalize_download_href(href: str) -> str:
    if not href or not href.strip():
        return ''
    raw = html_stdlib.unescape(href.strip())
    low = raw.lower()

    if low.startswith('magnet:'):
        return raw
    if low.startswith('ftp://'):
        return raw.split('&')[0]
    if low.startswith('thunder://'):
        return raw

    if low.startswith('jianpian://'):
        m = _JIANPIAN_PATH_RE.search(raw)
        if m:
            inner = urllib.parse.unquote(m.group(1))
            il = inner.lower()
            if il.startswith(('ftp://', 'magnet:', 'thunder://')):
                return inner

    if 'magnet:' in low:
        i = low.index('magnet:')
        return raw[i:]
    if 'ftp://' in low:
        i = low.index('ftp://')
        return raw[i:].split('&')[0]

    return ''


def _torrent_label_size_gb(label: str) -> Optional[float]:
    """Parse a crude size in GB from anchor / release title text."""
    vals: list[float] = []
    for m in _LOOSE_SIZE.finditer(label):
        try:
            n = float(m.group(1))
        except ValueError:
            continue
        u = m.group(2).lower()
        if u in ('tib', 'tb'):
            vals.append(n * 1024)
        elif u in ('gib', 'gb', 'gi', 'go'):
            vals.append(n)
        elif u in ('mib', 'mb', 'mi', 'm'):
            vals.append(n / 1024)
        else:
            vals.append(n)
    if not vals:
        return None
    return max(vals)


def _subtitle_and_resolution_from_label(label: str) -> Tuple[str, str]:
    subtitle = '未知字幕'
    resolution = '未知分辨率'
    for pat, val in _SUBTITLE_PATTERNS:
        if pat in label:
            subtitle = val
            break
    rm = _RES_HINT.search(label)
    if rm:
        resolution = rm.group(1).upper() if rm.group(1).upper() != '4K' else '4K'
    return subtitle, resolution


def detect_last_movie_list_page(
    gap_seconds: Optional[float] = None,
    list_kind: str = LIST_KIND_MOVIE,
) -> int:
    """Parse list page 1 pagination and return highest index_* page number."""
    gap = REQUEST_GAP_SECONDS if gap_seconds is None else gap_seconds
    path_re = _LIST_KIND_TO_INDEX_RE.get(list_kind, _INDEX_PAGE_PATH_RE)
    base_url = movie_list_page_url(1, list_kind=list_kind)
    html = fetch_url_with_retry(base_url)
    _sleep_after_response(gap)
    soup = BeautifulSoup(html, 'html.parser')
    numbers: list[int] = []
    for a in soup.find_all('a', href=True):
        full = urllib.parse.urljoin(base_url, a['href'])
        path = urllib.parse.urlparse(full).path
        m = path_re.search(path)
        if m:
            numbers.append(int(m.group(1)))
    return max(numbers) if numbers else 1


def _parse_mv_detail(soup: BeautifulSoup) -> Dict[str, Union[str, None]]:
    out = {
        'name': '',
        'year': '',
        'douban_rating': None,
        'aka': None,
        'release_date': None,
        'genres': None,
        'runtime_minutes': None,
        'region': None,
        'starring': None,
        'updated_at_site': None,
    }
    detail = soup.find('div', class_='mv_detail')
    if detail:
        h1 = detail.find('h1')
        if h1:
            out['name'] = h1.get_text(strip=True)

        rank_el = detail.find('span', class_='db_rank')
        if rank_el:
            out['douban_rating'] = rank_el.get_text(strip=True)

        for p in detail.find_all('p'):
            raw = p.get_text(' ', strip=True)
            if not raw:
                continue
            if raw.startswith('又名') and '：' in raw:
                out['aka'] = raw.split('：', 1)[1].strip()
            elif raw.startswith('上映日期') and '：' in raw:
                dt = raw.split('：', 1)[1].strip()
                out['release_date'] = dt
                ym = re.search(r'(19|20)\d{2}', dt)
                if ym:
                    out['year'] = ym.group(0)
            elif raw.startswith('类型') and '：' in raw:
                g = raw.split('：', 1)[1].strip()
                out['genres'] = g.replace('|', ' ').strip()
            elif raw.startswith('片长') and '：' in raw:
                lm = re.search(r'(\d+)', raw.split('：', 1)[1])
                out['runtime_minutes'] = lm.group(1) if lm else None
            elif raw.startswith('上映地区') and '：' in raw:
                out['region'] = raw.split('：', 1)[1].strip()
            elif raw.startswith('主演') and '：' in raw:
                out['starring'] = raw.split('：', 1)[1].strip()
            elif raw.startswith('最后更新') and '：' in raw:
                out['updated_at_site'] = raw.split('：', 1)[1].strip()

    if not out['name']:
        title_tag = soup.find('title')
        if title_tag:
            title_text = title_tag.get_text(strip=True)
            out['name'] = re.split(r'[-_/|]', title_text, 1)[0].strip()

    if not out['year']:
        ym = re.search(r'(19|20)\d{2}', soup.get_text('\n', strip=True))
        if ym:
            out['year'] = ym.group(0)

    return out


def _gather_magnet_anchors(soup: BeautifulSoup) -> List[Tuple[str, str]]:
    block = soup.find('div', class_='mv_down')
    roots = [block] if block else []
    roots.append(soup)
    seen = set()
    out: List[Tuple[str, str]] = []
    for root in roots:
        if root is None:
            continue
        for tag in root.find_all('a', href=True):
            magnet = _normalize_download_href(tag.get('href') or '')
            if not magnet.lower().startswith('magnet:'):
                continue
            if magnet in seen:
                continue
            seen.add(magnet)
            label = tag.get_text(' ', strip=True)
            out.append((magnet, label))
    return out


def _pick_largest_magnet(candidates: List[Tuple[str, str]]) -> Tuple[str, str]:
    if not candidates:
        return '', ''
    scored = []
    for magnet, label in candidates:
        sz = _torrent_label_size_gb(label)
        scored.append((sz if sz is not None else -1.0, magnet, label))
    scored.sort(key=lambda x: x[0], reverse=True)
    if scored[0][0] < 0:
        return candidates[0]
    top = scored[0][0]
    for s, magnet, label in scored:
        if s == top:
            return magnet, label
    return candidates[0]


class MovieScraper:
    """Scraper for cilixiong.org movie list and detail pages."""

    def __init__(
        self,
        start_page=1,
        end_page=None,
        download_movies=False,
        request_gap_seconds=None,
        list_kind: str = LIST_KIND_MOVIE,
    ):
        """
        Args:
            start_page (int): First list page index.
            end_page (Optional[int]): Last page; if None, resolved at run() via detect_last_movie_list_page().
            download_movies (bool): Queue magnets in Aria2 when True.
            request_gap_seconds (Optional[float]): Seconds to sleep after each successful HTTP fetch;
                None uses config scraper.REQUEST_GAP_SECONDS (set to 0 to disable pacing).
            list_kind (str): ``movie``（默认 /movie/）、``top250``（豆瓣）或 ``imdbtop250``（/s/imdbtop250/）。
        """
        self.start_page = start_page
        self.end_page = end_page
        self.download_movies = download_movies
        self.list_kind = list_kind
        self.request_gap_seconds = (
            REQUEST_GAP_SECONDS if request_gap_seconds is None else float(request_gap_seconds)
        )
        self.logger = logging.getLogger(__name__)
        if self.request_gap_seconds > 0:
            self.logger.info(
                'Pacing: sleeping %.2fs after each HTTP response (--request-gap overrides config/scraper.REQUEST_GAP_SECONDS)',
                self.request_gap_seconds,
            )
        elif request_gap_seconds is not None and self.request_gap_seconds <= 0:
            self.logger.info('Pacing: disabled (--request-gap 0 or non-positive)')

    def _request_gap(self) -> None:
        _sleep_after_response(self.request_gap_seconds)

    def extract_movie_info(self, html: str, _movie_url: str) -> Tuple[Optional[Dict], Optional[str]]:
        """
        Extract movie dict from detail HTML.

        Returns:
            (meta, None) on success; meta has keys: name, link, year, subtitle, resolution,
            douban_rating, aka, release_date, genres, runtime_minutes, region, starring, updated_at_site.
            (None, reason) when the page should be skipped, with a short Chinese explanation.
        """
        soup = BeautifulSoup(html, 'html.parser')
        meta = _parse_mv_detail(soup)
        name = (meta['name'] or '').strip()

        magnets = _gather_magnet_anchors(soup)
        magnet, torrent_label = _pick_largest_magnet(magnets)
        link = magnet
        subtitle, resolution = _subtitle_and_resolution_from_label(torrent_label)

        meta['subtitle'] = subtitle
        meta['resolution'] = resolution
        meta['link'] = link

        skip_parts: List[str] = []
        if not name:
            skip_parts.append(
                '未解析到影片标题（div.mv_detail 内 h1 与 <title> 均未得到有效片名）'
            )
        if not link:
            skip_parts.append(
                f'未找到 magnet 磁力链接（'
                f'页面中共收集到 {len(magnets)} 个 magnet 锚点；'
                f'若仅有 FTP/迅雷/剪辑等格式则不会入库）'
            )
        if skip_parts:
            return None, '；'.join(skip_parts)
        return meta, None

    def scrape_movie_list_page(self, page_number):
        url = movie_list_page_url(page_number, list_kind=self.list_kind)
        self.logger.info(f"Scraping movie list page: {url}")

        try:
            html = fetch_url_with_retry(url)
            self._request_gap()
            soup = BeautifulSoup(html, 'html.parser')

            seen_urls = set()
            movie_links = []

            for card in soup.find_all('div', class_=_element_has_card_class):
                a_tag = card.find('a', href=_MOVIE_DETAIL_PATH_RE)
                if not a_tag or not a_tag.get('href'):
                    inner = card.find('a', href=True)
                    if inner:
                        path = urllib.parse.urlparse(
                            urllib.parse.urljoin(url, inner['href'])
                        ).path
                        if _MOVIE_DETAIL_PATH_RE.search(path):
                            a_tag = inner
                if not a_tag:
                    continue
                href = a_tag.get('href', '')
                movie_url = urllib.parse.urljoin(url, href)
                if movie_url in seen_urls:
                    continue
                path = urllib.parse.urlparse(movie_url).path
                if not _MOVIE_DETAIL_PATH_RE.search(path):
                    continue

                card_body = card.find('div', class_='card-body')
                title_el = card_body.find(('h2', 'h3', 'h4')) if card_body else None
                title_text = ''
                if title_el:
                    title_text = title_el.get_text(strip=True)
                if not title_text:
                    title_text = a_tag.get_text(' ', strip=True)

                seen_urls.add(movie_url)
                movie_links.append((movie_url, title_text))

            self.logger.info(f"Found {len(movie_links)} movies on page {page_number}")
            return movie_links

        except Exception as e:
            self.logger.error(f"Failed to scrape page {page_number}: {e}", exc_info=True)
            return []

    def process_movie(self, movie_url: str, movie_title: str):
        self.logger.info(f"Processing movie: {movie_title} ({movie_url})")

        try:
            html = fetch_url_with_retry(movie_url)
            self._request_gap()
            info, skip_reason = self.extract_movie_info(html, movie_url)

            if not info:
                detail = skip_reason or '原因未知（extract_movie_info 返回空且无说明）'
                self.logger.warning(
                    'Skipping movie with incomplete info: %s — %s',
                    movie_url,
                    detail,
                )
                return False, None

            name = info['name']
            link = info['link']
            year = info.get('year') or '未知年份'
            subtitle = info['subtitle']
            resolution = info['resolution']

            db_id = check_movie_id(name, year)
            self.logger.info(f"Checked database for movie: {name} ({year}), ID: {db_id}")

            if db_id:
                self.logger.info(f"Movie already exists in database: {name} ({year})")
            else:
                self.logger.info(f"Movie does not exist in database, adding: {name} ({year})")
                db_id = add_movie_to_database(
                    name,
                    link,
                    year,
                    subtitle,
                    resolution,
                    douban_rating=info.get('douban_rating'),
                    aka=info.get('aka'),
                    release_date=info.get('release_date'),
                    genres=info.get('genres'),
                    runtime_minutes=info.get('runtime_minutes'),
                    region=info.get('region'),
                    starring=info.get('starring'),
                    updated_at_site=info.get('updated_at_site'),
                )
            if self.download_movies and db_id:
                self.logger.info(f"Adding movie to Aria2 for download: {name} ({year})")
                add_magnet_link_to_aria2(link, db_id, name, year, DOWNLOAD_PATH)

            movie_info = {
                'name': name,
                'year': year,
                'subtitle': subtitle,
                'resolution': resolution,
                'link': link,
                'db_id': db_id,
            }

            self.logger.info(f"Successfully processed movie: {name} ({year})")
            return True, movie_info

        except Exception as e:
            self.logger.error(f"Failed to process movie {movie_url}: {e}", exc_info=True)
            return False, None

    def run(self):
        initialize_database()
        end = self.end_page
        if end is None:
            self.logger.info("Detecting last list page from page 1…")
            end = detect_last_movie_list_page(
                self.request_gap_seconds, list_kind=self.list_kind
            )
            self.logger.info(f"Using last page: {end}")
        self.end_page = end

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
