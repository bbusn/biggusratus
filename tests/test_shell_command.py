import base64
import platform

import pytest

from client.commands.shell import ShellCommand, get_shell_command


class TestGetShellCommand:
    @pytest.mark.parametrize("os_type,expected", [
        ("Windows", "cmd.exe"),
        ("Linux", "/bin/bash"),
        ("Darwin", "/bin/bash"),
    ])
    def test_shell_command_by_os(self, os_type: str, expected: str, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(platform, "system", lambda: os_type)
        result = get_shell_command()
        assert result == expected


class TestShellCommand:
    def setup_method(self) -> None:
        self.command = ShellCommand()

    def test_name_property(self) -> None:
        assert self.command.name == "shell"

    def test_description_property(self) -> None:
        assert "interactive" in self.command.description.lower()
        assert "shell" in self.command.description.lower()

    def test_execute_missing_command(self) -> None:
        result = self.command.execute({})
        assert result["success"] is False
        assert "command" in result["error"].lower()

    def test_execute_invalid_command_type(self) -> None:
        result = self.command.execute({"command": 123})
        assert result["success"] is False
        assert "command" in result["error"].lower()

    def test_execute_simple_command_success(self) -> None:
        if platform.system() == "Windows":
            cmd = "echo hello"
            expected_output = "hello"
        else:
            cmd = "echo hello"
            expected_output = "hello"

        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        assert result["encoding"] == "base64"
        assert "output" in result
        assert "return_code" in result
        assert result["return_code"] == 0

        decoded = base64.b64decode(result["output"]).decode("utf-8")
        assert expected_output in decoded

    def test_execute_command_with_exit_code(self) -> None:
        if platform.system() == "Windows":
            cmd = "exit 1"
        else:
            cmd = "exit 1"

        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        assert result["return_code"] == 1

    def test_execute_command_with_stderr(self) -> None:
        if platform.system() == "Windows":
            cmd = "dir /nonexistent_directory_12345"
        else:
            cmd = "ls /nonexistent_directory_12345"

        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        decoded = base64.b64decode(result["output"]).decode("utf-8")
        assert len(decoded) > 0
        assert result["return_code"] != 0

    def test_execute_command_with_timeout(self) -> None:
        if platform.system() == "Windows":
            cmd = "ping -n 10 127.0.0.1"
        else:
            cmd = "sleep 10"

        result = self.command.execute({"command": cmd, "timeout": 1})
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_execute_command_default_timeout(self) -> None:
        if platform.system() == "Windows":
            cmd = "echo test"
        else:
            cmd = "echo test"

        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        assert result["return_code"] == 0

    def test_execute_command_custom_timeout(self) -> None:
        if platform.system() == "Windows":
            cmd = "echo test"
        else:
            cmd = "echo test"

        result = self.command.execute({"command": cmd, "timeout": 60})
        assert result["success"] is True
        assert result["return_code"] == 0

    def test_execute_command_invalid_timeout_uses_default(self) -> None:
        if platform.system() == "Windows":
            cmd = "echo test"
        else:
            cmd = "echo test"

        result = self.command.execute({"command": cmd, "timeout": -1})
        assert result["success"] is True
        assert result["return_code"] == 0

        result = self.command.execute({"command": cmd, "timeout": "invalid"})
        assert result["success"] is True
        assert result["return_code"] == 0

    def test_execute_command_returns_shell_type(self) -> None:
        cmd = "echo test"
        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        assert "shell" in result
        if platform.system() == "Windows":
            assert result["shell"] == "cmd.exe"
        else:
            assert result["shell"] == "/bin/bash"

    def test_execute_command_message_in_response(self) -> None:
        cmd = "echo test"
        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        assert "message" in result
        assert "return code" in result["message"].lower()

    def test_execute_command_with_special_characters(self) -> None:
        if platform.system() == "Windows":
            cmd = 'echo "hello world!"'
        else:
            cmd = 'echo "hello world!"'

        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        decoded = base64.b64decode(result["output"]).decode("utf-8")
        assert "hello world" in decoded

    def test_execute_command_multiline_output(self) -> None:
        if platform.system() == "Windows":
            cmd = "echo line1 && echo line2 && echo line3"
        else:
            cmd = "echo line1; echo line2; echo line3"

        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        decoded = base64.b64decode(result["output"]).decode("utf-8")
        assert "line1" in decoded
        assert "line2" in decoded
        assert "line3" in decoded

    def test_execute_command_unicode_output(self) -> None:
        if platform.system() == "Windows":
            cmd = 'echo "Unicode: \u4e2d\u6587"'
        else:
            cmd = 'echo "Unicode: \u4e2d\u6587"'

        result = self.command.execute({"command": cmd})
        assert result["success"] is True
        decoded = base64.b64decode(result["output"]).decode("utf-8")
        assert "Unicode" in decoded
