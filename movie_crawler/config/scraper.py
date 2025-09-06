"""
爬虫相关配置设置
"""

# Scraping settings
BASE_URL = 'https://www.dytt8.com'
MOVIE_LIST_URL_TEMPLATE = f'{BASE_URL}/html/gndy/dyzz/list_23_{{page}}.html'

# Scraping retry settings
MAX_RETRIES = 5
BACKOFF_FACTOR = 1  # Base factor for exponential backoff
