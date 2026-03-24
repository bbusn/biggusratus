import sys

import pytest

from common.platform import (
    get_env_separator,
    get_home_directory,
    get_line_ending,
    get_os_info,
    get_os_type,
    get_path_separator,
    get_shell_command,
    get_temp_directory,
    is_linux,
    is_macos,
    is_windows,
    join_path,
    normalize_path,
)


class TestGetOsType:
    def test_returns_valid_os_type(self) -> None:
        result = get_os_type()
        assert result in ("windows", "linux", "darwin", "unknown")

    def test_detects_current_platform(self) -> None:
        result = get_os_type()
        platform = sys.platform.lower()
        if platform.startswith("win"):
            assert result == "windows"
        elif platform.startswith("linux"):
            assert result == "linux"
        elif platform.startswith("darwin"):
            assert result == "darwin"


class TestGetOsInfo:
    def test_returns_dict(self) -> None:
        info = get_os_info()
        assert isinstance(info, dict)

    def test_contains_os_type(self) -> None:
        info = get_os_info()
        assert "os_type" in info
        assert info["os_type"] in ("windows", "linux", "darwin", "unknown")

    def test_contains_required_fields(self) -> None:
        info = get_os_info()
        required_fields = [
            "os_type",
            "system",
            "release",
            "version",
            "machine",
            "processor",
            "python_version",
        ]
        for field in required_fields:
            assert field in info, f"Missing field: {field}"


class TestOsCheckers:
    def test_is_windows_consistency(self) -> None:
        # Should be consistent with get_os_type
        assert is_windows() == (get_os_type() == "windows")

    def test_is_linux_consistency(self) -> None:
        assert is_linux() == (get_os_type() == "linux")

    def test_is_macos_consistency(self) -> None:
        assert is_macos() == (get_os_type() == "darwin")

    def test_mutual_exclusivity(self) -> None:
        # Only one OS type should be true
        count = sum([is_windows(), is_linux(), is_macos()])
        assert count <= 1


class TestGetShellCommand:
    def test_returns_string(self) -> None:
        result = get_shell_command()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_correct_shell_for_os(self) -> None:
        shell = get_shell_command()
        if is_windows():
            assert shell == "cmd.exe"
        else:
            assert shell == "/bin/bash"


class TestGetHomeDirectory:
    def test_returns_string(self) -> None:
        result = get_home_directory()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_valid_path(self) -> None:
        import os
        home = get_home_directory()
        assert os.path.isdir(home) or home == os.path.expanduser("~")


class TestGetTempDirectory:
    def test_returns_string(self) -> None:
        result = get_temp_directory()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_returns_valid_path(self) -> None:
        import os
        temp = get_temp_directory()
        assert os.path.isdir(temp)


class TestPathSeparators:
    def test_get_path_separator(self) -> None:
        sep = get_path_separator()
        if is_windows():
            assert sep == "\\"
        else:
            assert sep == "/"

    def test_get_env_separator(self) -> None:
        sep = get_env_separator()
        if is_windows():
            assert sep == ";"
        else:
            assert sep == ":"


class TestLineEnding:
    def test_get_line_ending(self) -> None:
        ending = get_line_ending()
        if is_windows():
            assert ending == "\r\n"
        else:
            assert ending == "\n"


class TestNormalizePath:
    def test_normalizes_path(self) -> None:
        result = normalize_path("some/path")
        assert isinstance(result, str)

    def test_handles_empty_string(self) -> None:
        result = normalize_path("")
        # os.path.normpath("") returns "." on most platforms
        assert result in ("", ".")

    @pytest.mark.parametrize(
        "input_path",
        [
            "foo/bar",
            "foo\\bar",
            "./foo/bar",
            "../foo/bar",
        ],
    )
    def test_handles_various_paths(self, input_path: str) -> None:
        result = normalize_path(input_path)
        assert isinstance(result, str)


class TestJoinPath:
    def test_joins_two_parts(self) -> None:
        result = join_path("foo", "bar")
        assert "foo" in result
        assert "bar" in result

    def test_joins_multiple_parts(self) -> None:
        result = join_path("a", "b", "c", "d")
        assert "a" in result
        assert "b" in result
        assert "c" in result
        assert "d" in result

    def test_uses_correct_separator(self) -> None:
        result = join_path("foo", "bar")
        sep = get_path_separator()
        assert sep in result or result == "foo/bar" or result == "foo\\bar"

    def test_handles_empty_parts(self) -> None:
        result = join_path("", "bar")
        assert "bar" in result
