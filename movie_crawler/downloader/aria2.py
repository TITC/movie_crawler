"""
Aria2 RPC client for managing movie downloads.
"""
import json
import requests
import logging
import os
from pathlib import Path
from movie_crawler.config.services import ARIA2_RPC_URL, ARIA2_SECRET_TOKEN
from movie_crawler.utils.common import ensure_directory
from movie_crawler.config.paths import DOWNLOAD_PATH


class Aria2Client:
    """Client for interacting with Aria2 RPC API."""

    def __init__(self, rpc_url=ARIA2_RPC_URL, secret_token=ARIA2_SECRET_TOKEN):
        """
        Initialize Aria2 RPC client.

        Args:
            rpc_url (str): URL of the Aria2 RPC endpoint
            secret_token (str): Secret token for authorization
        """
        self.rpc_url = rpc_url
        self.secret_token = secret_token
        self.logger = logging.getLogger(__name__)

    def add_download(self, uri, output_dir, filename=None):
        """
        Add a download to Aria2.

        Args:
            uri (str): Download URI (HTTP, FTP, or magnet link)
            output_dir (str): Directory to save the downloaded file
            filename (str, optional): Name for the downloaded file

        Returns:
            dict: Response from Aria2 RPC server
        """
        # Ensure output directory exists
        ensure_directory(output_dir)

        # Prepare options
        options = {
            'dir': str(output_dir)
        }

        if filename:
            options['out'] = filename

        # Prepare RPC parameters
        params = {
            'jsonrpc': '2.0',
            'id': 'movie_crawler',
            'method': 'aria2.addUri',
            'params': [[uri], options]
        }

        # Add token if provided
        if self.secret_token:
            params['params'].insert(0, f'token:{self.secret_token}')

        return self._send_request(params)

    def get_download_status(self, gid):
        """
        Get status of a download.

        Args:
            gid (str): GID of the download

        Returns:
            dict: Status information
        """
        params = {
            'jsonrpc': '2.0',
            'id': 'movie_crawler',
            'method': 'aria2.tellStatus',
            'params': [gid]
        }

        if self.secret_token:
            params['params'].insert(0, f'token:{self.secret_token}')

        return self._send_request(params)

    def _send_request(self, params):
        """
        Send RPC request to Aria2.

        Args:
            params (dict): RPC parameters

        Returns:
            dict: Response from Aria2 RPC server

        Raises:
            Exception: If the request fails
        """
        try:
            response = requests.post(self.rpc_url, data=json.dumps(params))
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            self.logger.error(f"Aria2 RPC request failed: {e}")
            raise


def add_magnet_link_to_aria2(magnet_link, db_id, movie_name, year, download_path=DOWNLOAD_PATH):
    """
    Add a magnet link to Aria2 for downloading.

    Args:
        magnet_link (str): Magnet link URI
        db_id (int): Database ID of the movie
        movie_name (str): Name of the movie
        year (str): Release year of the movie
        download_path (str): Base directory for downloads

    Returns:
        dict: Response from Aria2 RPC server
    """
    # Create directory for the movie
    movie_dir = Path(download_path) / f"{movie_name}_{year}"

    # Add download to Aria2
    client = Aria2Client()
    return client.add_download(magnet_link, str(movie_dir), movie_name)
