"""
Main entry point for the movie crawler application.
"""
import argparse
import logging
import sys
from movie_crawler.utils.common import setup_logging
from movie_crawler.scraper.movie_scraper import MovieScraper
from movie_crawler.checker.movie_checker import VideoIntegrityChecker, MovieMatcher
from movie_crawler.utils.database import initialize_database, get_all_movies, export_all_movie_links
from movie_crawler.renamer.movie_renamer import MovieRenamer, TVShowRenamer
from movie_crawler.config import paths


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Movie Crawler and Manager')

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # Scraper command
    scraper_parser = subparsers.add_parser('scrape', help='Scrape movies from DYTT8')
    scraper_parser.add_argument('--start-page', type=int, default=1, help='Starting page number')
    scraper_parser.add_argument('--end-page', type=int, default=428, help='Ending page number')
    scraper_parser.add_argument('--download', action='store_true', help='Download movies immediately')

    # Check command
    check_parser = subparsers.add_parser('check', help='Check video file integrity')
    check_parser.add_argument('--max-size', type=float, default=1.0,
                              help='Maximum file size to check in GB')
    check_parser.add_argument('--directory', type=str, default=paths.MOVIES_DIRECTORY,
                              help='Directory to scan for video files')

    # List command
    list_parser = subparsers.add_parser('list', help='List movies in database')
    list_parser.add_argument('--links-only', action='store_true',
                             help='Only list download links')

    # Initialize command
    init_parser = subparsers.add_parser('init', help='Initialize the database')

    # Rename movie command
    rename_parser = subparsers.add_parser('rename', help='Rename movie or TV show files')
    rename_parser.add_argument('--type', choices=['movie', 'tv'], default='movie',
                               help='Type of content to rename')
    rename_parser.add_argument('--source', type=str, default=paths.DOWNLOAD_PATH,
                               help='Source directory containing files to rename')
    rename_parser.add_argument('--target', type=str, default=paths.MOVIES_DIRECTORY,
                               help='Target directory for renamed files (movies only)')
    rename_parser.add_argument('--pattern', type=str,
                               help='Regex pattern for TV show renaming (regex mode only)')
    rename_parser.add_argument('--show-name', type=str,
                               help='TV show name (regex mode only)')
    rename_parser.add_argument('--season', type=int, default=1,
                               help='TV show season number (regex mode only)')
    rename_parser.add_argument('--regex', action='store_true',
                               help='Use regex mode for TV shows instead of AI')
    rename_parser.add_argument('--workers', type=int, default=10,
                               help='Number of worker threads for movie renaming')

    return parser.parse_args()


def command_scrape(args):
    """Run the movie scraper."""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting scraper from page {args.start_page} to {args.end_page}")

    scraper = MovieScraper(
        start_page=args.start_page,
        end_page=args.end_page,
        download_movies=args.download
    )
    scraper.run()


def command_check(args):
    """Run the video integrity checker."""
    logger = logging.getLogger(__name__)
    logger.info(f"Starting video integrity check in {args.directory}")

    checker = VideoIntegrityChecker(
        directory=args.directory,
        max_size_gb=args.max_size
    )
    results = checker.scan_videos_recursive()

    # Collect damaged files
    damaged_files = [path for path, is_valid in results.items() if not is_valid]

    # Print summary
    total = len(results)
    corrupted = len(damaged_files)
    logger.info("=== Scan Results Summary ===")
    logger.info(f"Total video files checked: {total}")
    logger.info(f"Intact files: {total - corrupted}")
    logger.info(f"Damaged files: {corrupted}")

    # Get download links for damaged files
    if damaged_files:
        logger.info("=== Retrieving download links for damaged files ===")
        matcher = MovieMatcher()
        movie_links = matcher.get_movie_links_from_db(damaged_files)

        if movie_links:
            logger.info(f"Found {len(movie_links)} download links")
            for name, year, link in movie_links:
                logger.info(f"Movie: {name} ({year})")
                logger.info(f"Download link: {link}")
                logger.info("-" * 50)
                print(link)  # Print to console for easy copying
        else:
            logger.info("No download links found for damaged files")


def command_list(args):
    """List movies in the database."""
    logger = logging.getLogger(__name__)

    if args.links_only:
        links = export_all_movie_links()
        for link in links:
            print(link)
        logger.info(f"Listed {len(links)} movie links")
    else:
        movies = get_all_movies()
        print(f"{'ID':<5} {'Name':<30} {'Year':<6} {'Subtitle':<15} {'Resolution':<15}")
        print("-" * 80)
        for movie in movies:
            movie_id, name, link, year, subtitle, resolution = movie
            print(f"{movie_id:<5} {name[:30]:<30} {year:<6} {subtitle:<15} {resolution:<15}")
        logger.info(f"Listed {len(movies)} movies from database")


def command_init(args):
    """Initialize the database."""
    logger = logging.getLogger(__name__)
    initialize_database()
    logger.info(f"Database initialized at {paths.DB_PATH}")


def command_rename(args):
    """Rename movie or TV show files."""
    logger = logging.getLogger(__name__)

    if args.type == 'movie':
        logger.info(f"Renaming movies from {args.source} to {args.target}")
        renamer = MovieRenamer(
            source_dir=args.source,
            target_dir=args.target
        )
        success_count = renamer.rename_movies_concurrently(max_workers=args.workers)
        print(f"Successfully renamed {success_count} movies")

    else:  # TV show
        if not args.source:
            logger.error("Source directory must be specified for TV show renaming")
            return

        if args.regex:
            if not args.pattern or not args.show_name:
                logger.error("Pattern and show name must be specified for regex TV show renaming")
                return

            logger.info(f"Renaming TV show {args.show_name} in {args.source} using regex")
            renamer = TVShowRenamer(tv_dir=args.source)
            success_count = renamer.rename_tv_show_regex(
                pattern=args.pattern,
                tv_show_name=args.show_name,
                season=args.season
            )
        else:
            logger.info(f"Renaming TV show in {args.source} using AI")
            renamer = TVShowRenamer(tv_dir=args.source)
            success_count = renamer.rename_tv_show_ai()

        print(f"Successfully renamed {success_count} TV show files")


def main():
    """Main entry point for the application."""
    args = parse_args()
    logger = setup_logging()
    logger.info(f"Movie Crawler started with command: {args.command}")

    # Execute the appropriate command
    if args.command == 'scrape':
        command_scrape(args)
    elif args.command == 'check':
        command_check(args)
    elif args.command == 'list':
        command_list(args)
    elif args.command == 'init':
        command_init(args)
    elif args.command == 'rename':
        command_rename(args)
    else:
        logger.error(f"Unknown command: {args.command}")
        print("Please specify a command: scrape, check, list, init, or rename")
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
