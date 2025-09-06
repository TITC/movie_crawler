"""
Movie and TV show renaming utilities.
"""
import os
import re
import glob
import logging
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
from openai import OpenAI

from movie_crawler.config.paths import MOVIES_DIRECTORY, DOWNLOAD_PATH, TV_SHOWS_DIRECTORY
from movie_crawler.config.services import OPENAI_API_KEY, OPENAI_BASE_URL
from movie_crawler.config.services import OPENAI_MODEL
from movie_crawler.config.files import VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS
from movie_crawler.config.files import RENAME_MAX_WORKERS, RENAME_MOVIE_WITH_YEAR


class MovieRenamer:
    """Rename movie files using AI to format filenames properly."""

    def __init__(self, source_dir=DOWNLOAD_PATH, target_dir=MOVIES_DIRECTORY,
                 api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL,
                 with_year=RENAME_MOVIE_WITH_YEAR):
        """
        Initialize the movie renamer.

        Args:
            source_dir (str): Directory containing movies to rename
            target_dir (str): Directory to move renamed movies to
            api_key (str): OpenAI API key
            base_url (str): OpenAI API base URL
            with_year (bool): Whether to include year in renamed files
        """
        self.source_dir = Path(source_dir)
        self.target_dir = Path(target_dir)
        self.api_key = api_key
        self.base_url = base_url
        self.with_year = with_year
        self.logger = logging.getLogger(__name__)

    def format_movie_name(self, original_filename):
        """
        Format a movie filename using AI.

        Args:
            original_filename (str): Original filename to format

        Returns:
            str: Formatted filename
        """
        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        # Determine what format to use based on config
        format_example = "电影名称.年份.文件格式" if self.with_year else "电影名称.文件格式"

        system_prompt = f"""接下来用户会给你一些电影名称， 希望你将其转化为 {format_example} 的格式。不要添加任何额外的信息或者描述，去掉语言和分辨率等信息，{'保留' if self.with_year else '去掉'}电影名称和年份。

                        比如：
                        [电影天堂-www.dy2018.net]狂奔蚂蚁.720p.HD国语中字.rmvb -> 狂奔蚂蚁{'如果有年份则添加年份' if self.with_year else ''}.rmvb
                        阳光电影www.ygdy8.com.查泰莱夫人的情人.2022.BD.1080P.中英双字.mkv -> 查泰莱夫人的情人{'.2022' if self.with_year else ''}.mkv
                        [电影天堂www.dy2018.net]何处献殷勤BD中英双字.mp4 -> 何处献殷勤.mp4
                        阳光电影www.ygdy8.com.宁静.BD.720p.中英双字幕.mkv -> 宁静{'.2022' if self.with_year else ''}.mkv
                        阳光电影www.ygdy8.com.搜索.BD.1080p.韩语中字.mkv -> 搜索.mkv
                        """

        try:
            completion = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": original_filename},
                ]
            )
            content = completion.choices[0].message.content

            # Validate the response to ensure it has correct format
            if len(content.split(".")) > 0:
                movie_name = content.split(".")[0]
                if len(content.split(".")) > 1:
                    # Only validate year if we're expecting it
                    if self.with_year and len(content.split(".")) > 2:
                        year = content.split(".")[1]
                        # Use regex to check if year is a 4-digit number and exists in original filename
                        if not year.isdigit() or len(year) != 4 or year not in original_filename:
                            content = movie_name + "." + content.split(".")[-1]

            self.logger.info(f"Renamed: {original_filename} -> {content}")
            return content

        except Exception as e:
            self.logger.error(f"Error formatting movie name: {e}")
            # Return original filename if formatting fails
            return original_filename

    def process_file(self, file_info):
        """
        Process a single file for renaming.

        Args:
            file_info (tuple): (filename, root_path)

        Returns:
            tuple: (original_path, new_path, success)
        """
        filename, root_path = file_info
        original_path = os.path.join(root_path, filename)

        try:
            # Check if the file has a valid video extension
            if not (any(filename.lower().endswith(ext) for ext in VIDEO_EXTENSIONS) or
                    any(filename.lower().endswith(ext) for ext in SUBTITLE_EXTENSIONS)):
                return original_path, None, False

            # Format the movie name
            formatted_name = self.format_movie_name(filename)

            # If formatting failed or didn't change anything, return
            if formatted_name == filename:
                return original_path, None, False

            # Create the new path
            new_path = os.path.join(self.target_dir, formatted_name)

            # Ensure target directory exists
            os.makedirs(self.target_dir, exist_ok=True)

            # Move and rename the file
            os.rename(original_path, new_path)

            return original_path, new_path, True

        except Exception as e:
            self.logger.error(f"Error processing file {filename}: {e}")
            return original_path, None, False

    def rename_movies_concurrently(self, max_workers=RENAME_MAX_WORKERS):
        """
        Rename movie files concurrently.

        Args:
            max_workers (int): Maximum number of worker threads

        Returns:
            int: Number of successfully renamed files
        """
        # Collect all files to process
        files_to_process = []
        for root, _, files in os.walk(self.source_dir):
            for file in files:
                if (any(file.lower().endswith(ext) for ext in VIDEO_EXTENSIONS) or
                        any(file.lower().endswith(ext) for ext in SUBTITLE_EXTENSIONS)):
                    files_to_process.append((file, root))

        if not files_to_process:
            self.logger.info(f"No media files found in {self.source_dir}")
            return 0

        self.logger.info(f"Found {len(files_to_process)} media files to process")

        # Process files concurrently
        success_count = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(self.process_file, file_info)
                       for file_info in files_to_process]

            # Track progress with tqdm
            for future in tqdm(as_completed(futures), total=len(futures), desc="Processing files"):
                try:
                    original_path, new_path, success = future.result()
                    if success:
                        success_count += 1
                        self.logger.info(f"Renamed: {original_path} -> {new_path}")
                except Exception as e:
                    self.logger.error(f"Error in worker thread: {e}")

        self.logger.info(f"Successfully renamed {success_count} of {len(files_to_process)} files")
        return success_count


class TVShowRenamer:
    """Rename TV show files to a consistent format."""

    def __init__(self, tv_dir=TV_SHOWS_DIRECTORY, api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL):
        """
        Initialize the TV show renamer.

        Args:
            tv_dir (str): Directory containing TV shows to rename
            api_key (str): OpenAI API key
            base_url (str): OpenAI API base URL
        """
        self.tv_dir = Path(tv_dir)
        self.api_key = api_key
        self.base_url = base_url
        self.logger = logging.getLogger(__name__)

    def rename_tv_show_regex(self, pattern, tv_show_name, season=1):
        """
        Rename TV show files using regex pattern matching.

        Args:
            pattern (str): Regex pattern to match filenames
            tv_show_name (str): Name of the TV show
            season (int): Season number

        Returns:
            int: Number of renamed files
        """
        renamed_count = 0
        pattern = re.compile(pattern)

        # Ensure the directory exists
        if not self.tv_dir.exists():
            self.logger.error(f"TV show directory not found: {self.tv_dir}")
            return 0

        self.logger.info(f"Renaming TV show: {tv_show_name}, Season {season}")

        # Process all files in the directory
        for filepath in sorted(glob.glob(os.path.join(self.tv_dir, "*.*"))):
            filename = os.path.basename(filepath)
            match = pattern.match(filename)

            if match:
                try:
                    episode_number = match.group(1)
                    extension = match.group(2)
                    new_filename = f'{tv_show_name}.S{season:02d}E{episode_number}{extension}'

                    # Rename the file
                    os.rename(filepath, os.path.join(self.tv_dir, new_filename))
                    self.logger.info(f"Renamed: {filename} -> {new_filename}")
                    renamed_count += 1

                except Exception as e:
                    self.logger.error(f"Error renaming file {filename}: {e}")

        self.logger.info(f"Successfully renamed {renamed_count} files for {tv_show_name}")
        return renamed_count

    def rename_tv_show_ai(self):
        """
        Rename TV show files using AI.

        Returns:
            int: Number of renamed files
        """
        renamed_count = 0

        # Ensure the directory exists
        if not self.tv_dir.exists():
            self.logger.error(f"TV show directory not found: {self.tv_dir}")
            return 0

        self.logger.info(f"Renaming TV show files in {self.tv_dir} using AI")

        client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
        )

        # Determine the TV show name from the directory name
        tv_show_name = self.tv_dir.name

        # Process all files in the directory
        for filepath in sorted(glob.glob(os.path.join(self.tv_dir, "*.*"))):
            filename = os.path.basename(filepath)

            # Skip files that are already in the correct format (SxxExx)
            if re.search(r'S\d{2}E\d{2,3}', filename):
                continue

            # Determine if this is a valid media file
            if not (any(filename.lower().endswith(ext) for ext in VIDEO_EXTENSIONS) or
                    any(filename.lower().endswith(ext) for ext in SUBTITLE_EXTENSIONS)):
                continue

            try:
                # Format the TV show name using AI
                system_prompt = f"""接下来用户会给你一些电视剧文件名称，这些文件属于"{tv_show_name}"这部剧， 希望你将其转化为 {tv_show_name}.SxxExx.文件格式 的格式。不要添加任何额外的信息或者描述，去掉语言和分辨率等信息，只保留Season和Episode信息。

                            比如：
                            [DBD-Raws][黑色五叶草][001][1080P][BDRip][HEVC-10bit][FLAC].mkv -> 黑色五叶草.S01E001.mkv
                            [DBD-Raws][黑色五叶草][001][1080P][BDRip][HEVC-10bit][FLAC].sc.ass -> 黑色五叶草.S01E001.sc.ass
                            [DBD-Raws][黑色五叶草][001][1080P][BDRip][HEVC-10bit][FLAC].tc.ass -> 黑色五叶草.S01E001.tc.ass
                            [DBD-Raws][黑色五叶草][110][1080P][BDRip][HEVC-10bit][FLAC].tc.ass -> 黑色五叶草.S01E110.tc.ass
                            """

                completion = client.chat.completions.create(
                    model=OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": filename},
                    ]
                )
                new_filename = completion.choices[0].message.content

                # If formatting didn't change anything or doesn't match expected format, continue
                if new_filename == filename or not re.search(r'S\d{2}E\d{2,3}', new_filename):
                    continue

                # Rename the file
                os.rename(filepath, os.path.join(self.tv_dir, new_filename))
                self.logger.info(f"Renamed: {filename} -> {new_filename}")
                renamed_count += 1

            except Exception as e:
                self.logger.error(f"Error renaming file {filename}: {e}")

        self.logger.info(f"Successfully renamed {renamed_count} files")
        return renamed_count
