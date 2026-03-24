import os
import tempfile

import pytest

from server.path_security import (
    validate_local_path,
    is_path_safe,
    sanitize_filename,
    PathSecurityError,
)


class TestValidateLocalPath:
    # Test cases for validate_local_path function.

    def test_empty_path_raises(self) -> None:
        with pytest.raises(PathSecurityError, match="empty"):
            validate_local_path("")

    def test_whitespace_path_raises(self) -> None:
        with pytest.raises(PathSecurityError, match="empty"):
            validate_local_path("   ")

    def test_null_byte_rejected(self) -> None:
        with pytest.raises(PathSecurityError, match="null bytes"):
            validate_local_path("/tmp/file\x00.txt")

    def test_relative_path_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            os.chdir(tmpdir)
            result = validate_local_path("subdir/file.txt")
            assert os.path.isabs(result)

    def test_absolute_path_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "test.txt")
            result = validate_local_path(filepath)
            assert os.path.isabs(result)

    def test_absolute_path_rejected_when_not_allowed(self) -> None:
        with pytest.raises(PathSecurityError, match="Absolute paths are not allowed"):
            validate_local_path("/tmp/file.txt", allow_absolute=False)

    def test_must_exist_true_raises_for_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            missing = os.path.join(tmpdir, "nonexistent.txt")
            with pytest.raises(PathSecurityError, match="does not exist"):
                validate_local_path(missing, must_exist=True)

    def test_must_exist_true_passes_for_existing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "existing.txt")
            with open(filepath, "w") as f:
                f.write("test")
            result = validate_local_path(filepath, must_exist=True)
            # Use os.path.samefile to compare paths (handles symlinks on macOS)
            assert os.path.samefile(result, filepath)

    def test_traversal_attack_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try to escape the base directory
            escaping_path = os.path.join(tmpdir, "..", "..", "etc", "passwd")
            with pytest.raises(PathSecurityError, match="outside allowed directory"):
                validate_local_path(escaping_path, base_dir=tmpdir)

    def test_path_within_base_dir_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            safe_path = os.path.join(tmpdir, "subdir", "file.txt")
            # Should not raise - path is within base_dir
            result = validate_local_path(safe_path, base_dir=tmpdir)
            assert os.path.isabs(result)


class TestIsPathSafe:
    # Test cases for is_path_safe function.

    def test_empty_path_not_safe(self) -> None:
        assert is_path_safe("") is False

    def test_normal_path_safe(self) -> None:
        assert is_path_safe("/tmp/file.txt") is True
        assert is_path_safe("relative/path.txt") is True

    def test_null_byte_not_safe(self) -> None:
        assert is_path_safe("/tmp/file\x00.txt") is False

    def test_double_dot_not_safe(self) -> None:
        assert is_path_safe("../etc/passwd") is False
        assert is_path_safe("/tmp/../etc/passwd") is False

    def test_double_slash_not_safe(self) -> None:
        assert is_path_safe("/tmp//file.txt") is False

    def test_double_backslash_not_safe(self) -> None:
        assert is_path_safe("C:\\\\Windows\\\\System32") is False


class TestSanitizeFilename:
    # Test cases for sanitize_filename function.

    def test_empty_returns_unnamed(self) -> None:
        assert sanitize_filename("") == "unnamed"

    def test_removes_null_bytes(self) -> None:
        assert sanitize_filename("file\x00.txt") == "file.txt"

    def test_replaces_slashes(self) -> None:
        assert sanitize_filename("path/to/file.txt") == "path_to_file.txt"

    def test_replaces_backslashes(self) -> None:
        assert sanitize_filename("path\\to\\file.txt") == "path_to_file.txt"

    def test_removes_leading_dots(self) -> None:
        assert sanitize_filename(".hidden") == "hidden"
        assert sanitize_filename("..hidden") == "hidden"

    def test_only_dots_returns_unnamed(self) -> None:
        assert sanitize_filename("...") == "unnamed"

    def test_normal_filename_unchanged(self) -> None:
        assert sanitize_filename("document.pdf") == "document.pdf"
