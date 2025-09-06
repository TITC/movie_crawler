"""
Common utility functions for the movie crawler application.
"""
import os
import random
import logging
import time
import chardet
import ssl
import urllib.request
from urllib.error import URLError, HTTPError
from datetime import datetime
from pathlib import Path
from difflib import SequenceMatcher
from movie_crawler.config.network import (
    PROXY, USER_AGENTS, REQUEST_TIMEOUT
)

from movie_crawler.config.paths import LOGS_DIR
from movie_crawler.config.scraper import MAX_RETRIES, BACKOFF_FACTOR


def setup_logging():
    """
    Set up logging configuration for the application.
    Creates a log file with the current date as the filename.
    """
    # Create log filename with current date
    current_time = datetime.now().strftime("%Y-%m-%d")
    log_file = LOGS_DIR / f"{current_time}.log"

    # Configure logging
    logging.basicConfig(
        filename=str(log_file),
        filemode='a',
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S',
        level=logging.INFO
    )

    # Also log to console
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
    logging.getLogger('').addHandler(console)

    logging.info("Logging initialized")
    return logging.getLogger()


def get_random_user_agent():
    """Get a random user agent from the list of available agents."""
    return random.choice(USER_AGENTS)


def configure_proxy():
    """Configure proxy for urllib requests."""
    proxy_handler = urllib.request.ProxyHandler(PROXY)
    opener = urllib.request.build_opener(proxy_handler)
    urllib.request.install_opener(opener)


def fetch_url_with_retry(url, use_proxy=True):
    """
    Fetch URL content with retry logic and exponential backoff.

    Args:
        url (str): URL to fetch
        use_proxy (bool): Whether to use proxy

    Returns:
        str: HTML content

    Raises:
        Exception: If fetching fails after retries
    """
    ssl._create_default_https_context = ssl._create_unverified_context

    if use_proxy:
        configure_proxy()

    headers = {'User-Agent': get_random_user_agent()}

    for i in range(MAX_RETRIES):
        try:
            req = urllib.request.Request(url, headers=headers)
            response = urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT)
            html = response.read()

            # Detect encoding and decode
            encoding = chardet.detect(html)['encoding']
            try:
                return html.decode(encoding)
            except UnicodeDecodeError:
                try:
                    return html.decode('GBK')
                except UnicodeDecodeError:
                    return html.decode('UTF-8', errors='ignore')

        except (URLError, HTTPError) as e:
            logging.warning(f"Attempt {i+1}/{MAX_RETRIES} failed: {e}")
            if i < MAX_RETRIES - 1:
                sleep_time = BACKOFF_FACTOR * (2 ** i)  # Exponential backoff
                logging.info(f"Retrying in {sleep_time} seconds...")
                time.sleep(sleep_time)
            else:
                logging.error(f"Failed to fetch URL after {MAX_RETRIES} attempts: {url}")
                raise


def ensure_directory(directory_path):
    """
    Ensure a directory exists, creating it if necessary.

    Args:
        directory_path (str or Path): Directory path to ensure exists

    Returns:
        Path: Path object for the directory
    """
    path = Path(directory_path)
    path.mkdir(parents=True, exist_ok=True)
    return path


def string_similarity(a, b):
    """
    Calculate similarity ratio between two strings.

    Args:
        a (str): First string
        b (str): Second string

    Returns:
        float: Similarity ratio between 0 and 1
    """
    return SequenceMatcher(None, a, b).ratio()
