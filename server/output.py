# Output formatting utilities for the server CLI.

import sys
from datetime import datetime
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from server.session import AgentSession


class OutputFormatter:
    # Handles formatted output for the server CLI.

    @staticmethod
    def timestamp() -> str:
        # Return current timestamp string.
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def info(message: str) -> None:
        # Print an info message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] {message}")

    @staticmethod
    def error(message: str) -> None:
        # Print an error message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] [!] {message}", file=sys.stderr)

    @staticmethod
    def success(message: str) -> None:
        # Print a success message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] [+] {message}")

    @staticmethod
    def warning(message: str) -> None:
        # Print a warning message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] [?] {message}")

    @staticmethod
    def format_duration(seconds: float) -> str:
        # Format duration in human-readable format.
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    @staticmethod
    def format_session_table(
        sessions: list, selected_id: Optional[str] = None
    ) -> str:
        # Format sessions as a table.
        if not sessions:
            return "No connected agents."

        header = f"{'ID':<37} {'Address':<21} {'OS':<8} {'Duration':<10} {'Idle':<10} {'Status':<8}"
        lines = [header, "-" * len(header)]

        for session in sessions:
            session_id = session.agent_id
            address = f"{session.address[0]}:{session.address[1]}"
            os_type = (session.os_type or "unknown")[:7]
            duration = OutputFormatter.format_duration(session.session_duration)
            idle = OutputFormatter.format_duration(session.idle_time)
            status = "active" if session.idle_time < 30 else "idle"

            marker = "* " if session.agent_id == selected_id else "  "
            line = f"{marker}{session_id:<35} {address:<21} {os_type:<8} {duration:<10} {idle:<10} {status:<8}"
            lines.append(line)

        return "\n".join(lines)
