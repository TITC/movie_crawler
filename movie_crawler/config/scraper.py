"""
爬虫相关配置设置
"""

# Scraping settings（磁力熊 电影列表）
BASE_URL = 'https://www.cilixiong.org'
MOVIE_LIST_BASE = f'{BASE_URL}/movie'


def movie_list_page_url(page: int) -> str:
    """列表页：第 1 页为 index.html，第 n 页为 index_n.html。"""
    if page < 1:
        raise ValueError(f'page must be >= 1, got {page}')
    if page == 1:
        return f'{MOVIE_LIST_BASE}/index.html'
    return f'{MOVIE_LIST_BASE}/index_{page}.html'


# Scraping retry settings
MAX_RETRIES = 5
BACKOFF_FACTOR = 1  # Base factor for exponential backoff

# 两次成功请求之间的休眠（秒）。适当增大可减轻源站 520 / 429 / 502 等临时错误；设为 0 关闭。
REQUEST_GAP_SECONDS = 1.0

# 重试时若遇到以下 HTTP 状态码，在指数退避之外再额外加上若干秒的「冷静期」（与 REQUEST_GAP 同量级）
HTTP_COOLDOWN_STATUSES = frozenset({429, 500, 502, 503, 520, 521, 522, 523, 524})
HTTP_COOLDOWN_EXTRA_SECONDS = 3.0
