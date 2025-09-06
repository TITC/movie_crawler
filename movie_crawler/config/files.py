"""
文件处理相关配置设置
"""

# Video file extensions for checking and renaming
VIDEO_EXTENSIONS = ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.rmvb')
SUBTITLE_EXTENSIONS = ('.srt', '.ass', '.ssa', '.sub', '.idx', '.tc.ass', '.sc.ass')

# Renamer settings
RENAME_MAX_WORKERS = 10  # 最大并行重命名工作线程数
RENAME_MOVIE_WITH_YEAR = True  # 重命名电影时是否包含年份
