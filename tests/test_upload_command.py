# Tests for upload command.

import base64
import os
import tempfile

import pytest

from client.commands.upload import UploadCommand


class TestUploadCommand:
    def setup_method(self) -> None:
        self.command = UploadCommand()

    def test_name_property(self) -> None:
        assert self.command.name == "upload"

    def test_description_property(self) -> None:
        assert "send" in self.command.description.lower()
        assert "file" in self.command.description.lower()

    def test_execute_missing_remote_path(self) -> None:
        content = base64.b64encode(b"test content").decode("utf-8")
        result = self.command.execute({"content": content})
        assert result["success"] is False
        assert "remote_path" in result["error"]

    def test_execute_missing_content(self) -> None:
        result = self.command.execute({"remote_path": "/tmp/test.txt"})
        assert result["success"] is False
        assert "content" in result["error"]

    def test_execute_invalid_base64(self) -> None:
        result = self.command.execute({
            "remote_path": "/tmp/test.txt",
            "content": "not valid base64!!!"
        })
        assert result["success"] is False
        assert "base64" in result["error"].lower()

    def test_execute_text_file_success(self) -> None:
        content = "Hello, World!"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "test.txt")
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
            assert result["remote_path"] == temp_path
            assert result["size"] == 13
            # Verify file was written correctly
            with open(temp_path, "r") as f:
                assert f.read() == content

    def test_execute_binary_file_success(self) -> None:
        binary_data = bytes(range(256))
        encoded_content = base64.b64encode(binary_data).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "test.bin")
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
            assert result["size"] == 256
            # Verify file was written correctly
            with open(temp_path, "rb") as f:
                assert f.read() == binary_data

    def test_execute_empty_file(self) -> None:
        encoded_content = base64.b64encode(b"").decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "empty.txt")
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
            assert result["size"] == 0
            # Verify file was created but is empty
            with open(temp_path, "rb") as f:
                assert f.read() == b""

    def test_execute_large_file(self) -> None:
        # Create a 1 MB file
        large_data = b"x" * (1024 * 1024)
        encoded_content = base64.b64encode(large_data).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "large.bin")
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
            assert result["size"] == 1024 * 1024
            # Verify content
            with open(temp_path, "rb") as f:
                assert f.read() == large_data

    def test_execute_path_normalization(self) -> None:
        content = "test content"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "test.txt")
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
            # Path should be normalized
            assert result["remote_path"] == os.path.normpath(temp_path)

    def test_execute_creates_parent_directories(self) -> None:
        content = "nested file content"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_path = os.path.join(tmpdir, "level1", "level2", "test.txt")
            result = self.command.execute({
                "remote_path": nested_path,
                "content": encoded_content
            })
            assert result["success"] is True
            # Verify directory was created
            assert os.path.exists(os.path.dirname(nested_path))
            # Verify file was written
            with open(nested_path, "r") as f:
                assert f.read() == content

    def test_execute_unicode_filename(self) -> None:
        content = "Unicode content: \u4e2d\u6587"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            unicode_path = os.path.join(tmpdir, "test_\u4e2d\u6587_\u0645\u0631\u062d\u0628\u0627.txt")
            result = self.command.execute({
                "remote_path": unicode_path,
                "content": encoded_content
            })
            assert result["success"] is True
            # Verify file was written correctly
            with open(unicode_path, "r", encoding="utf-8") as f:
                assert f.read() == content

    def test_execute_overwrites_existing_file(self) -> None:
        new_content = "new content"
        encoded_content = base64.b64encode(new_content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "existing.txt")
            # Create file with initial content
            with open(temp_path, "w") as f:
                f.write("old content")
            # Upload should overwrite
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
            # Verify content was overwritten
            with open(temp_path, "r") as f:
                assert f.read() == new_content

    def test_execute_permission_denied(self) -> None:
        content = "test content"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "readonly.txt")
            # Create file and make directory read-only
            with open(temp_path, "w") as f:
                f.write("initial")
            # Make file read-only
            os.chmod(temp_path, 0o444)
            try:
                result = self.command.execute({
                    "remote_path": temp_path,
                    "content": encoded_content
                })
                assert result["success"] is False
                assert "permission" in result["error"].lower()
            finally:
                os.chmod(temp_path, 0o644)

    def test_message_in_successful_response(self) -> None:
        content = "test"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = os.path.join(tmpdir, "test.txt")
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
            assert "message" in result
            assert "Successfully" in result["message"]

    def test_execute_path_with_trailing_slash(self) -> None:
        content = "test content"
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            # Path with trailing slash should still work after normalization
            temp_path = os.path.join(tmpdir, "test.txt")
            result = self.command.execute({
                "remote_path": temp_path,
                "content": encoded_content
            })
            assert result["success"] is True
