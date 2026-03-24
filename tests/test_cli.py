import sys
from unittest.mock import patch

import pytest

from server.output import OutputFormatter
from server.session import AgentSession
from server.core import Server
from server.server import parse_args


class TestOutputFormatter:
    # Test cases for OutputFormatter.

    def test_format_duration_seconds(self) -> None:
        assert OutputFormatter.format_duration(30) == "30s"
        assert OutputFormatter.format_duration(59) == "59s"
        assert OutputFormatter.format_duration(0.5) == "0s"

    def test_format_duration_minutes(self) -> None:
        assert OutputFormatter.format_duration(60) == "1.0m"
        assert OutputFormatter.format_duration(120) == "2.0m"
        assert OutputFormatter.format_duration(90) == "1.5m"

    def test_format_duration_hours(self) -> None:
        assert OutputFormatter.format_duration(3600) == "1.0h"
        assert OutputFormatter.format_duration(7200) == "2.0h"

    def test_format_session_table_empty(self) -> None:
        result = OutputFormatter.format_session_table([])
        assert result == "No connected agents."

    def test_format_session_table_with_sessions(self) -> None:
        sessions = [
            AgentSession("test-id-1", ("192.168.1.1", 12345)),
            AgentSession("test-id-2", ("192.168.1.2", 54321)),
        ]
        result = OutputFormatter.format_session_table(sessions)

        assert "test-id-..." in result
        assert "192.168.1.1:12345" in result
        assert "192.168.1.2:54321" in result
        assert "Address" in result
        assert "Duration" in result
        assert "Idle" in result

    def test_format_session_table_with_selected(self) -> None:
        sessions = [AgentSession("test-id-1", ("192.168.1.1", 12345))]
        result = OutputFormatter.format_session_table(sessions, selected_id="test-id-1")
        assert "*test-id-..." in result

    def test_format_session_table_without_selected(self) -> None:
        sessions = [AgentSession("test-id-1", ("192.168.1.1", 12345))]
        result = OutputFormatter.format_session_table(sessions, selected_id="other-id")
        assert " test-id-..." in result

    def test_info_output(self, capsys: pytest.CaptureFixture) -> None:
        with patch("server.output.datetime") as mock_datetime:
            mock_datetime.now().strftime.return_value = "12:00:00"
            OutputFormatter.info("Test message")
            captured = capsys.readouterr()
            assert "[12:00:00] Test message" in captured.out

    def test_error_output(self, capsys: pytest.CaptureFixture) -> None:
        with patch("server.output.datetime") as mock_datetime:
            mock_datetime.now().strftime.return_value = "12:00:00"
            OutputFormatter.error("Error message")
            captured = capsys.readouterr()
            assert "[12:00:00] [!] Error message" in captured.err

    def test_success_output(self, capsys: pytest.CaptureFixture) -> None:
        with patch("server.output.datetime") as mock_datetime:
            mock_datetime.now().strftime.return_value = "12:00:00"
            OutputFormatter.success("Success message")
            captured = capsys.readouterr()
            assert "[12:00:00] [+] Success message" in captured.out

    def test_warning_output(self, capsys: pytest.CaptureFixture) -> None:
        with patch("server.output.datetime") as mock_datetime:
            mock_datetime.now().strftime.return_value = "12:00:00"
            OutputFormatter.warning("Warning message")
            captured = capsys.readouterr()
            assert "[12:00:00] [?] Warning message" in captured.out


class TestArgParse:
    # Test cases for argparse functionality.

    def test_server_parse_args_defaults(self) -> None:
        with patch("sys.argv", ["server"]):
            args = parse_args()
            assert args.host == "0.0.0.0"
            assert args.port == 8443
            assert args.verbose is False

    def test_server_parse_args_custom(self) -> None:
        with patch("sys.argv", ["server", "--host", "127.0.0.1", "--port", "8443", "-v"]):
            args = parse_args()
            assert args.host == "127.0.0.1"
            assert args.port == 8443
            assert args.verbose is True

    def test_client_parse_args_defaults(self) -> None:
        from client.client import parse_args as client_parse_args
        with patch("sys.argv", ["client"]):
            args = client_parse_args()
            assert args.host == "127.0.0.1"
            assert args.port == 8443
            assert args.verbose is False

    def test_client_parse_args_custom(self) -> None:
        from client.client import parse_args as client_parse_args
        with patch("sys.argv", ["client", "--host", "192.168.1.100", "--port", "9999", "--verbose"]):
            args = client_parse_args()
            assert args.host == "192.168.1.100"
            assert args.port == 9999
            assert args.verbose is True


class TestServerPrompt:
    # Test cases for server prompt generation.

    def test_prompt_no_sessions(self) -> None:
        server = Server()
        prompt = server._get_prompt()
        assert prompt == "biggusRatus[0]> "

    def test_prompt_with_sessions(self) -> None:
        server = Server()
        server.sessions["test-id"] = AgentSession("test-id", ("127.0.0.1", 12345))
        prompt = server._get_prompt()
        assert prompt == "biggusRatus[1]> "

    def test_prompt_with_selection(self) -> None:
        server = Server()
        server.sessions["test-id-12345678"] = AgentSession("test-id-12345678", ("127.0.0.1", 12345))
        server.selected_agent_id = "test-id-12345678"
        prompt = server._get_prompt()
        assert prompt == "biggusRatus[test-id-]> "
