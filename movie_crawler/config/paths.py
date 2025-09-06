"""
路径相关配置设置
"""
from pathlib import Path

# Base paths
# Get the project root directory (two levels up from this file)
BASE_DIR = Path(__file__).parents[2].absolute()
LOGS_DIR = BASE_DIR / 'logs'
DB_DIR = BASE_DIR / 'db'
DB_PATH = DB_DIR / 'movie.db'

# Ensure directories exist
LOGS_DIR.mkdir(parents=True, exist_ok=True)
DB_DIR.mkdir(parents=True, exist_ok=True)

# Media directories
DOWNLOAD_PATH = '/mnt/20240403/media/Downloads/'
MOVIES_DIRECTORY = '/mnt/20240403/media/电影'
TV_SHOWS_DIRECTORY = '/mnt/20230127/media/Anime'  # TV节目目录
