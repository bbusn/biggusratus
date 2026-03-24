import pytest

from client.commands.help import HelpCommand


class TestHelpCommand:
    # Test cases for HelpCommand.

    @pytest.fixture
    def command(self) -> HelpCommand:
        return HelpCommand()

    def test_name_property(self, command: HelpCommand) -> None:
        # Test that command name is 'help'.
        assert command.name == "help"

    def test_description_property(self, command: HelpCommand) -> None:
        # Test that description is returned.
        assert command.description == "Display available commands"

    def test_execute_returns_command_list(self, command: HelpCommand) -> None:
        # Test that execute returns a list of commands.
        result = command.execute({})
        assert "commands" in result
        assert isinstance(result["commands"], list)
        assert len(result["commands"]) > 0

    def test_execute_includes_help_command(self, command: HelpCommand) -> None:
        # Test that the help command is included in the output.
        result = command.execute({})
        command_names = [cmd["name"] for cmd in result["commands"]]
        assert "help" in command_names

    def test_execute_commands_have_required_fields(self, command: HelpCommand) -> None:
        # Test that each command has name and description.
        result = command.execute({})
        for cmd in result["commands"]:
            assert "name" in cmd
            assert "description" in cmd
            assert isinstance(cmd["name"], str)
            assert isinstance(cmd["description"], str)

    def test_execute_commands_with_params(self, command: HelpCommand) -> None:
        # Test that commands with params include them.
        result = command.execute({})
        commands_with_params = [
            cmd for cmd in result["commands"] if "params" in cmd
        ]
        assert len(commands_with_params) > 0
        for cmd in commands_with_params:
            assert isinstance(cmd["params"], list)

    def test_execute_ignores_params(self, command: HelpCommand) -> None:
        # Test that execute ignores any passed params.
        result1 = command.execute({})
        result2 = command.execute({"foo": "bar"})
        assert result1 == result2

    def test_all_expected_commands_present(self, command: HelpCommand) -> None:
        # Test that all expected commands are in the help output.
        expected_commands = [
            "help",
            "download",
            "upload",
            "shell",
            "ipconfig",
            "screenshot",
            "search",
            "hashdump",
            "keylogger",
            "webcam_snapshot",
            "webcam_stream",
            "record_audio",
        ]
        result = command.execute({})
        command_names = [cmd["name"] for cmd in result["commands"]]
        for expected in expected_commands:
            assert expected in command_names, f"Missing command: {expected}"
