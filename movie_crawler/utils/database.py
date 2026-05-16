"""
Database operations for movie data storage and retrieval.
"""
import sqlite3
from contextlib import contextmanager
from movie_crawler.config.paths import DB_PATH

_NEW_MOVIE_COLUMNS = (
    ('douban_rating', 'TEXT'),
    ('aka', 'TEXT'),
    ('release_date', 'TEXT'),
    ('genres', 'TEXT'),
    ('runtime_minutes', 'TEXT'),
    ('region', 'TEXT'),
    ('starring', 'TEXT'),
    ('updated_at_site', 'TEXT'),
)


@contextmanager
def get_db_connection():
    """Context manager for database connections to ensure proper closure."""
    conn = sqlite3.connect(DB_PATH)
    try:
        yield conn
    finally:
        conn.close()


def _migrate_movie_columns(cursor):
    """Add cilixiong detail columns when missing."""
    cursor.execute('PRAGMA table_info(movie)')
    existing = {row[1] for row in cursor.fetchall()}
    for col_name, col_type in _NEW_MOVIE_COLUMNS:
        if col_name not in existing:
            cursor.execute(f'ALTER TABLE movie ADD COLUMN {col_name} {col_type}')


def initialize_database():
    """Create the database schema if it doesn't exist."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS movie (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT,
                link TEXT UNIQUE,
                year TEXT,
                subtitle TEXT,
                resolution TEXT,
                added_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        _migrate_movie_columns(cursor)
        conn.commit()


def add_movie_to_database(
    name,
    link,
    year,
    subtitle,
    resolution,
    *,
    douban_rating=None,
    aka=None,
    release_date=None,
    genres=None,
    runtime_minutes=None,
    region=None,
    starring=None,
    updated_at_site=None,
):
    """
    Add a movie to the database.

    Returns:
        int or None: Database ID of the movie if successful, None otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute(
                """
                INSERT INTO movie (
                    name, link, year, subtitle, resolution,
                    douban_rating, aka, release_date, genres, runtime_minutes,
                    region, starring, updated_at_site
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    name,
                    link,
                    year,
                    subtitle,
                    resolution,
                    douban_rating,
                    aka,
                    release_date,
                    genres,
                    runtime_minutes,
                    region,
                    starring,
                    updated_at_site,
                ),
            )
            conn.commit()
            return cursor.lastrowid
        except sqlite3.IntegrityError:
            return None


def check_movie_id(name, year):
    """
    Check if a movie exists in the database by name and year.

    Returns:
        int or None: Database ID if the movie exists, None otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM movie WHERE name = ? AND year = ?", (name, year))
        result = cursor.fetchone()
        return result[0] if result else None


def find_movie_by_link(link):
    """
    Find a movie in the database by link.

    Returns:
        tuple or None: Movie data if found, None otherwise
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, name, year, subtitle, resolution,
                   douban_rating, aka, release_date, genres, runtime_minutes,
                   region, starring, updated_at_site
               FROM movie WHERE link = ?""",
            (link,),
        )
        return cursor.fetchone()


def get_all_movies():
    """
    Get all movies from the database.

    Returns:
        list: Rows (id, name, link, year, subtitle, resolution,
              douban_rating, aka, ...)
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """SELECT id, name, link, year, subtitle, resolution,
                      douban_rating, aka, release_date, genres, runtime_minutes,
                      region, starring, updated_at_site
               FROM movie"""
        )
        return cursor.fetchall()


def export_all_movie_links():
    """
    Export all movie download links.

    Returns:
        list: List of movie download links
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT link FROM movie")
        links = [row[0] for row in cursor.fetchall()]
        return links


def clear_movie_table():
    """Delete all records from the movie table."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM movie")
        conn.commit()


if __name__ == '__main__':
    initialize_database()
    print(f"Database initialized at {DB_PATH}")
    print(f"Total movies in database: {len(get_all_movies())}")
