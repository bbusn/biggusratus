# Path security utilities to prevent path traversal attacks.

import os
from pathlib import Path
from typing import Optional


class PathSecurityError(Exception):
    # Raised when a path violates security constraints.
    pass


def validate_local_path(
    path: str,
    base_dir: Optional[str] = None,
    must_exist: bool = False,
    allow_absolute: bool = True
) -> str:
    # Validate and normalize a local file path to prevent traversal attacks.

    # Args:
    #     path: The path to validate
    #     base_dir: Optional base directory that the path must be within
    #     must_exist: If True, the path must exist on the filesystem
    #     allow_absolute: If False, absolute paths are rejected
    # Returns:
    #     The normalized absolute path
    # Raises:
    #     PathSecurityError: If the path is invalid or violates security constraints
    
    if not path or not path.strip():
        raise PathSecurityError("Path cannot be empty")

    path = path.strip()

    # Reject paths with null bytes
    if '\x00' in path:
        raise PathSecurityError("Path contains null bytes")

    # Reject absolute paths if not allowed
    if not allow_absolute and os.path.isabs(path):
        raise PathSecurityError("Absolute paths are not allowed")

    # Resolve the path to its canonical form
    try:
        resolved = Path(path).resolve()
    except OSError as e:
        raise PathSecurityError(f"Invalid path: {e}") from e

    # Check if path must exist
    if must_exist and not resolved.exists():
        raise PathSecurityError(f"Path does not exist: {path}")

    # If base_dir is specified, ensure the path is within it
    if base_dir is not None:
        try:
            base_resolved = Path(base_dir).resolve()
        except OSError as e:
            raise PathSecurityError(f"Invalid base directory: {e}") from e

        try:
            # Check if resolved path is within base_dir
            resolved.relative_to(base_resolved)
        except ValueError:
            raise PathSecurityError(
                f"Path '{path}' is outside allowed directory '{base_dir}'"
            )

    return str(resolved)


def is_path_safe(path: str) -> bool:
    # Check if a path appears safe (no obvious traversal attempts).

    # This is a quick check without filesystem access.

    # Args:
    #     path: The path to check
    # Returns:
    #     True if the path appears safe, False otherwise
    
    if not path:
        return False

    # Check for null bytes
    if '\x00' in path:
        return False

    # Check for suspicious patterns
    suspicious = ['..', '//', '\\\\']
    for pattern in suspicious:
        if pattern in path:
            return False

    return True


def sanitize_filename(filename: str) -> str:
    # Sanitize a filename by removing/replacing dangerous characters.

    # Args:
    #     filename: The filename to sanitize
    # Returns:
    #     A sanitized filename safe for filesystem use
    
    
    if not filename:
        return "unnamed"

    # Remove null bytes
    filename = filename.replace('\x00', '')

    # Replace path separators with underscores
    filename = filename.replace('/', '_').replace('\\', '_')

    # Remove leading dots (hidden files on Unix)
    while filename.startswith('.'):
        filename = filename[1:]

    # Ensure we have something left
    if not filename:
        return "unnamed"

    return filename
