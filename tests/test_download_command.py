import base64
import os
import tempfile

import pytest

from client.commands.download import DownloadCommand


class TestDownloadCommand:
    def setup_method(self) -> None:
        self.command = DownloadCommand()

    def test_name_property(self) -> None:
        assert self.command.name == "download"

    def test_description_property(self) -> None:
        assert "retrieve" in self.command.description.lower()
        assert "file" in self.command.description.lower()

    def test_execute_missing_remote_path(self) -> None:
        result = self.command.execute({})
        assert result["success"] is False
        assert "remote_path" in result["error"]

    def test_execute_file_not_found(self) -> None:
        result = self.command.execute({"remote_path": "/nonexistent/path/file.txt"})
        assert result["success"] is False
        assert "not found" in result["error"].lower()

    def test_execute_directory_not_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            result = self.command.execute({"remote_path": tmpdir})
            assert result["success"] is False
            assert "not a file" in result["error"].lower()

    def test_execute_text_file_success(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("Hello, World!")
            temp_path = f.name
        try:
            result = self.command.execute({"remote_path": temp_path})
            assert result["success"] is True
            assert result["remote_path"] == temp_path
            assert result["encoding"] == "base64"
            assert "content" in result
            # Verify content
            decoded = base64.b64decode(result["content"]).decode("utf-8")
            assert decoded == "Hello, World!"
            assert result["size"] == 13
        finally:
            os.unlink(temp_path)

    def test_execute_binary_file_success(self) -> None:
        binary_data = bytes(range(256))
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".bin", delete=False) as f:
            f.write(binary_data)
            temp_path = f.name
        try:
            result = self.command.execute({"remote_path": temp_path})
            assert result["success"] is True
            assert result["encoding"] == "base64"
            # Verify content
            decoded = base64.b64decode(result["content"])
            assert decoded == binary_data
            assert result["size"] == 256
        finally:
            os.unlink(temp_path)

    def test_execute_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".empty", delete=False) as f:
            temp_path = f.name
        try:
            result = self.command.execute({"remote_path": temp_path})
            assert result["success"] is True
            assert result["size"] == 0
            assert result["content"] == ""  # base64 of empty bytes
        finally:
            os.unlink(temp_path)

    def test_execute_large_file(self) -> None:
        # Create a 1 MB file
        large_data = b"x" * (1024 * 1024)
        with tempfile.NamedTemporaryFile(mode="wb", suffix=".large", delete=False) as f:
            f.write(large_data)
            temp_path = f.name
        try:
            result = self.command.execute({"remote_path": temp_path})
            assert result["success"] is True
            assert result["size"] == 1024 * 1024
            # Verify content
            decoded = base64.b64decode(result["content"])
            assert decoded == large_data
        finally:
            os.unlink(temp_path)

    def test_execute_path_normalization(self) -> None:
        # Test that path is normalized (no traversal attacks)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_path = f.name
        try:
            result = self.command.execute({"remote_path": temp_path})
            assert result["success"] is True
            # Path should be normalized
            assert result["remote_path"] == os.path.normpath(temp_path)
        finally:
            os.unlink(temp_path)

    def test_execute_unicode_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            unicode_path = os.path.join(tmpdir, "test_\u4e2d\u6587_\u0645\u0631\u062d\u0628\u0627.txt")
            with open(unicode_path, "w", encoding="utf-8") as f:
                f.write("Unicode content: \u4e2d\u6587")
            result = self.command.execute({"remote_path": unicode_path})
            assert result["success"] is True
            decoded = base64.b64decode(result["content"]).decode("utf-8")
            assert "Unicode content" in decoded

    def test_execute_permission_denied(self, monkeypatch: pytest.MonkeyPatch) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("secret content")
            temp_path = f.name
        try:
            # Make file unreadable
            os.chmod(temp_path, 0o000)
            result = self.command.execute({"remote_path": temp_path})
            assert result["success"] is False
            assert "permission" in result["error"].lower()
        finally:
            os.chmod(temp_path, 0o644)
            os.unlink(temp_path)

    def test_message_in_successful_response(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test")
            temp_path = f.name
        try:
            result = self.command.execute({"remote_path": temp_path})
            assert result["success"] is True
            assert "message" in result
            assert "Successfully" in result["message"]
        finally:
            os.unlink(temp_path)
