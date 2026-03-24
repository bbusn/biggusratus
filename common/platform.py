# Platform and OS detection utilities.

import logging
import platform
import sys
from typing import Tuple

logger = logging.getLogger(__name__)


def get_os_type() -> str:
    # Detect the current operating system type.
    # Returns: "windows", "linux", "darwin", or "unknown"
    os_name = sys.platform.lower()
    if os_name.startswith("win"):
        return "windows"
    elif os_name.startswith("linux"):
        return "linux"
    elif os_name.startswith("darwin"):
        return "darwin"
    return "unknown"


def get_os_info() -> dict:
    # Get detailed OS information.
    return {
        "os_type": get_os_type(),
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python_version": platform.python_version(),
    }


def is_windows() -> bool:
    # Check if running on Windows.
    return get_os_type() == "windows"


def is_linux() -> bool:
    # Check if running on Linux.
    return get_os_type() == "linux"


def is_macos() -> bool:
    # Check if running on macOS.
    return get_os_type() == "darwin"


def get_shell_command() -> str:
    # Get the appropriate shell command for the current OS.
    if is_windows():
        return "cmd.exe"
    return "/bin/bash"


def get_home_directory() -> str:
    # Get the current user's home directory.
    import os
    return os.path.expanduser("~")


def get_temp_directory() -> str:
    # Get the appropriate temp directory for the current OS.
    import tempfile
    return tempfile.gettempdir()


def get_path_separator() -> str:
    # Get the path separator for the current OS.
    import os
    return os.sep


def get_line_ending() -> str:
    # Get the line ending for the current OS.
    return "\r\n" if is_windows() else "\n"


def get_env_separator() -> str:
    # Get the environment variable path separator.
    import os
    return os.pathsep


def normalize_path(path: str) -> str:
    # Normalize a file path for the current OS.
    import os
    return os.path.normpath(path)


def join_path(*parts: str) -> str:
    # Join path components using the OS-appropriate separator.
    import os
    return os.path.join(*parts)
