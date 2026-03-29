import os
import subprocess
from typing import Any, Dict
from unittest.mock import MagicMock, mock_open, patch

import pytest

from client.commands.hashdump import HashdumpCommand


class TestHashdumpCommand:
    def setup_method(self) -> None:
        self.command = HashdumpCommand()

    def test_name_property(self) -> None:
        assert self.command.name == "hashdump"

    def test_description_property(self) -> None:
        assert "hash" in self.command.description.lower()

    @patch("platform.system")
    def test_execute_windows_with_privileges(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Windows"

        with patch.object(self.command, "_is_windows_admin", return_value=True):
            with patch.object(self.command, "_extract_windows_sam") as mock_extract:
                mock_extract.return_value = {
                    "success": True,
                    "os": "windows",
                    "hashes": [{"username": "Administrator", "ntlm_hash": "abc123"}],
                    "count": 1,
                    "message": "Extracted 1 password hashes from SAM",
                }

                result = self.command.execute({})

                assert result["success"] is True
                assert result["os"] == "windows"
                mock_extract.assert_called_once()

    @patch("platform.system")
    def test_execute_linux_with_privileges(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Linux"

        with patch.object(self.command, "_is_linux_root", return_value=True):
            with patch.object(self.command, "_extract_linux_shadow") as mock_extract:
                mock_extract.return_value = {
                    "success": True,
                    "os": "linux",
                    "hashes": [{"username": "root", "hash": "$6$xxx"}],
                    "count": 1,
                    "message": "Extracted 1 password hashes from shadow file",
                }

                result = self.command.execute({})

                assert result["success"] is True
                assert result["os"] == "linux"
                mock_extract.assert_called_once()

    @patch("platform.system")
    def test_execute_windows_without_privileges(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Windows"

        with patch.object(self.command, "_is_windows_admin", return_value=False):
            result = self.command.execute({})

            assert result["success"] is False
            assert "Administrator" in result["error"]

    @patch("platform.system")
    def test_execute_linux_without_privileges(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Linux"

        with patch.object(self.command, "_is_linux_root", return_value=False):
            result = self.command.execute({})

            assert result["success"] is False
            assert "Root" in result["error"]

    @patch("platform.system")
    def test_execute_unsupported_os(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Darwin"

        result = self.command.execute({})

        assert result["success"] is False
        assert "Unsupported" in result["error"]

    def test_is_windows_admin_true(self) -> None:
        with patch.object(self.command, "_is_windows_admin", return_value=True):
            result = self.command._is_windows_admin()
            assert result is True

    def test_is_windows_admin_false(self) -> None:
        with patch.object(self.command, "_is_windows_admin", return_value=False):
            result = self.command._is_windows_admin()
            assert result is False

    def test_is_windows_admin_exception(self) -> None:
        with patch.object(self.command, "_is_windows_admin", return_value=False):
            result = self.command._is_windows_admin()
            assert result is False

    def test_is_linux_root_true(self) -> None:
        with patch("os.geteuid", return_value=0):
            result = self.command._is_linux_root()
            assert result is True

    def test_is_linux_root_false(self) -> None:
        with patch("os.geteuid", return_value=1000):
            result = self.command._is_linux_root()
            assert result is False

    @patch("os.path.exists")
    def test_extract_linux_shadow_file_not_found(self, mock_exists: MagicMock) -> None:
        mock_exists.return_value = False

        result = self.command._extract_linux_shadow()

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_extract_linux_shadow_success(self, mock_file: MagicMock, mock_exists: MagicMock) -> None:
        mock_exists.return_value = True

        shadow_content = """root:$6$rounds=5000$salt$hash:18000:0:99999:7:::
nobody:*:18000:0:99999:7:::
user:$5$salt$hash:18000:0:99999:7:::
daemon:!:18000:0:99999:7:::
bin:!!:18000:0:99999:7:::
# comment line
"""
        mock_file.return_value.__enter__.return_value.__iter__ = lambda self: iter(shadow_content.split("\n"))

        result = self.command._extract_linux_shadow()

        assert result["success"] is True
        assert result["os"] == "linux"
        assert result["count"] == 2
        assert len(result["hashes"]) == 2

        usernames = [h["username"] for h in result["hashes"]]
        assert "root" in usernames
        assert "user" in usernames
        assert "nobody" not in usernames

    @patch("os.path.exists")
    @patch("builtins.open", side_effect=PermissionError("Permission denied"))
    def test_extract_linux_shadow_permission_denied(
        self, mock_file: MagicMock, mock_exists: MagicMock
    ) -> None:
        mock_exists.return_value = True

        result = self.command._extract_linux_shadow()

        assert result["success"] is False
        assert "permission" in result["error"].lower()

    @patch("os.path.exists")
    @patch("builtins.open", side_effect=Exception("Read error"))
    def test_extract_linux_shadow_exception(self, mock_file: MagicMock, mock_exists: MagicMock) -> None:
        mock_exists.return_value = True

        result = self.command._extract_linux_shadow()

        assert result["success"] is False
        assert "Read error" in result["error"]

    def test_identify_hash_type_sha512(self) -> None:
        hash_value = "$6$rounds=5000$salt$hash"
        result = self.command._identify_hash_type(hash_value)
        assert result == "SHA-512"

    def test_identify_hash_type_sha256(self) -> None:
        hash_value = "$5$salt$hash"
        result = self.command._identify_hash_type(hash_value)
        assert result == "SHA-256"

    def test_identify_hash_type_blowfish_b(self) -> None:
        hash_value = "$2b$salt$hash"
        result = self.command._identify_hash_type(hash_value)
        assert result == "Blowfish"

    def test_identify_hash_type_blowfish_y(self) -> None:
        hash_value = "$2y$salt$hash"
        result = self.command._identify_hash_type(hash_value)
        assert result == "Blowfish"

    def test_identify_hash_type_md5(self) -> None:
        hash_value = "$1$salt$hash"
        result = self.command._identify_hash_type(hash_value)
        assert result == "MD5"

    def test_identify_hash_type_des(self) -> None:
        hash_value = "$$abc123"
        result = self.command._identify_hash_type(hash_value)
        assert result == "DES"

    def test_identify_hash_type_unknown(self) -> None:
        hash_value = "unknownhashformat"
        result = self.command._identify_hash_type(hash_value)
        assert result == "Unknown"

    @patch.object(HashdumpCommand, "_read_registry_sam")
    @patch.object(HashdumpCommand, "_read_registry_system")
    @patch.object(HashdumpCommand, "_parse_sam_hashes")
    def test_extract_windows_sam_success(
        self,
        mock_parse: MagicMock,
        mock_system: MagicMock,
        mock_sam: MagicMock,
    ) -> None:
        mock_sam.return_value = b"sam_data"
        mock_system.return_value = b"system_data"
        mock_parse.return_value = [
            {"username": "Administrator", "lm_hash": "lm", "ntlm_hash": "ntlm", "type": "NTLM"}
        ]

        result = self.command._extract_windows_sam()

        assert result["success"] is True
        assert result["os"] == "windows"
        assert result["count"] == 1
        assert len(result["hashes"]) == 1

    @patch.object(HashdumpCommand, "_read_registry_sam", return_value=b"")
    @patch.object(HashdumpCommand, "_read_registry_system", return_value=b"system_data")
    def test_extract_windows_sam_no_sam_data(
        self, mock_system: MagicMock, mock_sam: MagicMock
    ) -> None:
        result = self.command._extract_windows_sam()

        assert result["success"] is False
        assert "Failed to read SAM" in result["error"]

    @patch.object(HashdumpCommand, "_read_registry_sam", return_value=b"sam_data")
    @patch.object(HashdumpCommand, "_read_registry_system", return_value=b"")
    def test_extract_windows_sam_no_system_data(
        self, mock_system: MagicMock, mock_sam: MagicMock
    ) -> None:
        result = self.command._extract_windows_sam()

        assert result["success"] is False
        assert "Failed to read SAM or SYSTEM" in result["error"]

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data=b"sam_data")
    @patch("os.remove")
    def test_read_registry_sam_success(
        self, mock_remove: MagicMock, mock_file: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        result = self.command._read_registry_sam()

        assert result == b"sam_data"
        mock_run.assert_called_once()
        mock_remove.assert_called_once_with("SAM.tmp")

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "reg", stderr="Error"))
    def test_read_registry_sam_error(self, mock_run: MagicMock) -> None:
        result = self.command._read_registry_sam()

        assert result == b""

    @patch("subprocess.run", side_effect=Exception("Unexpected error"))
    def test_read_registry_sam_exception(self, mock_run: MagicMock) -> None:
        result = self.command._read_registry_sam()

        assert result == b""

    @patch("subprocess.run")
    @patch("builtins.open", new_callable=mock_open, read_data=b"system_data")
    @patch("os.remove")
    def test_read_registry_system_success(
        self, mock_remove: MagicMock, mock_file: MagicMock, mock_run: MagicMock
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0)

        result = self.command._read_registry_system()

        assert result == b"system_data"
        mock_run.assert_called_once()
        mock_remove.assert_called_once_with("SYSTEM.tmp")

    @patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "reg", stderr="Error"))
    def test_read_registry_system_error(self, mock_run: MagicMock) -> None:
        result = self.command._read_registry_system()

        assert result == b""

    @patch("subprocess.run")
    def test_parse_sam_hashes_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(
            stdout="HKEY_LOCAL_MACHINE\\SAM\\SAM\\Domains\\Account\\Users\\Names\\Administrator\n"
            "HKEY_LOCAL_MACHINE\\SAM\\SAM\\Domains\\Account\\Users\\Names\\Guest\n",
            returncode=0,
        )

        result = self.command._parse_sam_hashes(b"sam", b"system")

        assert len(result) == 2
        usernames = [h["username"] for h in result]
        assert "Administrator" in usernames
        assert "Guest" in usernames

    @patch("subprocess.run", side_effect=Exception("Error"))
    def test_parse_sam_hashes_exception(self, mock_run: MagicMock) -> None:
        result = self.command._parse_sam_hashes(b"sam", b"system")

        assert result == []

    def test_error_response(self) -> None:
        result = self.command._error_response("Test error message")

        assert result["success"] is False
        assert result["error"] == "Test error message"
        assert result["hashes"] == []
        assert result["count"] == 0

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_extract_linux_shadow_empty_lines(self, mock_file: MagicMock, mock_exists: MagicMock) -> None:
        mock_exists.return_value = True

        shadow_content = """
root:$6$salt$hash:18000:0:99999:7:::

nobody:*:18000:0:99999:7:::

"""
        mock_file.return_value.__enter__.return_value.__iter__ = lambda self: iter(shadow_content.split("\n"))

        result = self.command._extract_linux_shadow()

        assert result["success"] is True
        assert result["count"] == 1

    @patch("os.path.exists")
    @patch("builtins.open", new_callable=mock_open)
    def test_extract_linux_shadow_locked_accounts(self, mock_file: MagicMock, mock_exists: MagicMock) -> None:
        mock_exists.return_value = True

        shadow_content = """root:$6$salt$hash:18000:0:99999:7:::
nobody:*:18000:0:99999:7:::
daemon:!:18000:0:99999:7:::
mail:!!:18000:0:99999:7:::
test:!!*:18000:0:99999:7:::
user:$5$salt$hash:18000:0:99999:7:::
"""
        mock_file.return_value.__enter__.return_value.__iter__ = lambda self: iter(shadow_content.split("\n"))

        result = self.command._extract_linux_shadow()

        assert result["success"] is True
        assert result["count"] == 2
        usernames = [h["username"] for h in result["hashes"]]
        assert "root" in usernames
        assert "user" in usernames
