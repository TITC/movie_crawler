# Movie Crawler

Movie Crawler 是一个Python应用程序，用于从电影天堂网站(DYTT8)爬取电影信息并下载电影资源。该应用程序还可以检查本地视频文件的完整性，并为损坏的文件找到替代下载链接。

## 功能特点

- 爬取电影天堂网站的电影信息
- 将电影信息存储到SQLite数据库中
- 使用Aria2下载电影（支持磁力链接、FTP和迅雷链接）
- 检查电影文件完整性
- 使用AI模型匹配损坏的电影文件并找到替代下载链接
- 使用AI模型批量重命名电影和电视剧文件
- 命令行界面，方便操作

## 系统要求

- Python 3.7+
- FFmpeg（用于视频完整性检查）
- Aria2（用于下载功能）

## 安装

1. 克隆仓库：

```bash
git clone https://github.com/yourusername/movie_crawler.git
cd movie_crawler
```

2. 安装依赖：

```bash
pip install -r requirements.txt
```

3. 初始化数据库：

```bash
python -m movie_crawler init
```

## 配置

所有配置选项都位于 `movie_crawler/config/` 目录中。您可以根据需要修改以下设置：

- `paths.py`：路径配置（下载目录、电影目录、数据库路径等）
- `network.py`：网络配置（代理服务器设置等）
- `services.py`：服务配置（Aria2 RPC设置、AI接口设置等）
- `scraper.py`：爬虫配置（爬取设置、请求参数等）
- `files.py`：文件处理配置

## 使用方法

### 爬取电影信息

```bash
# 默认爬取所有页面(1-428)
python -m movie_crawler scrape

# 指定页面范围
python -m movie_crawler scrape --start-page 1 --end-page 10

# 爬取并立即下载电影
python -m movie_crawler scrape --download
```

### 检查视频文件完整性

```bash
# 检查默认目录中的视频文件
python -m movie_crawler check

# 指定目录和最大文件大小
python -m movie_crawler check --directory /path/to/movies --max-size 2.5
```

### 列出数据库中的电影

```bash
# 列出所有电影信息
python -m movie_crawler list

# 仅列出下载链接
python -m movie_crawler list --links-only
```

### 重命名电影和电视剧文件

```bash
# 重命名电影文件（使用AI整理格式）
python -m movie_crawler rename --type movie --source /path/to/downloads --target /path/to/movies

# 使用AI重命名电视剧文件
python -m movie_crawler rename --type tv --source /path/to/tv_show

# 使用正则表达式重命名电视剧文件（针对特定格式）
python -m movie_crawler rename --type tv --source /path/to/tv_show --regex \
    --pattern "^\[DBD-Raws\]\[家庭教师\]\[(\d+)\].*?(\..+)$" \
    --show-name "家庭教师" --season 1
```

## 项目结构

```
movie_crawler/
├── LICENSE                   # 许可证文件
├── README.md                 # 项目文档
├── requirements.txt          # 项目依赖
├── pyproject.toml           # Python 项目配置文件
├── movie_crawler/            # 主包目录
│   ├── __init__.py           # 包初始化文件
│   ├── __main__.py           # 主入口点
│   ├── config/               # 配置模块
│   │   ├── __init__.py
│   │   ├── files.py          # 文件处理配置
│   │   ├── network.py        # 网络配置
│   │   ├── paths.py          # 路径配置
│   │   ├── scraper.py        # 爬虫配置
│   │   └── services.py       # 服务配置
│   ├── utils/                # 工具模块
│   │   ├── __init__.py
│   │   ├── common.py         # 通用工具函数
│   │   └── database.py       # 数据库操作
│   ├── scraper/              # 爬虫模块
│   │   ├── __init__.py
│   │   └── movie_scraper.py  # 电影爬虫
│   ├── checker/              # 检查模块
│   │   ├── __init__.py
│   │   └── movie_checker.py  # 视频完整性检查
│   ├── downloader/           # 下载模块
│   │   ├── __init__.py
│   │   └── aria2.py          # Aria2下载器
│   └── renamer/              # 重命名模块
│       ├── __init__.py
│       └── movie_renamer.py  # 电影和电视剧重命名
├── db/                       # 数据库目录
│   └── movie.db              # SQLite数据库文件
├── logs/                     # 日志目录
    └── *.log                 # 日志文件

```

## 更新记录

### 1.0.0 (2024-04-xx)
- 项目重构，改进代码结构和模块化
- 增加了模块化设计，使用包层次结构
- 明确的职责分离：核心、爬虫、检查、下载、重命名和工具模块
- 添加了命令行界面
- 添加了AI驱动的电影和电视剧重命名功能
- 改进了日志记录和错误处理
- 集中配置管理
- 增加了更全面的文档

## 许可证

此项目采用MIT许可证 - 详情请参阅LICENSE文件。