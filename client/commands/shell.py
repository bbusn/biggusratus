import base64
import logging
import platform
import subprocess
from typing import Any, Dict

from client.commands.base import BaseCommand

logger = logging.getLogger(__name__)


def get_shell_command() -> str:
    if platform.system() == "Windows":
        return "cmd.exe"
    return "/bin/bash"


class ShellCommand(BaseCommand):

    @property
    def name(self) -> str:
        return "shell"

    @property
    def description(self) -> str:
        return "Open interactive shell (bash/cmd)"

    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        command = params.get("command")
        if not command:
            return self._error_response("Missing required parameter: command")

        if not isinstance(command, str):
            return self._error_response("Invalid parameter: command must be a string")

        timeout = params.get("timeout", 30)
        if not isinstance(timeout, (int, float)) or timeout <= 0:
            timeout = 30

        try:
            shell_executable = get_shell_command()
            logger.info(f"Executing shell command: {command}")

            result = subprocess.run(
                command,
                shell=True,
                executable=shell_executable,
                capture_output=True,
                timeout=timeout,
            )

            stdout = result.stdout.decode("utf-8", errors="replace")
            stderr = result.stderr.decode("utf-8", errors="replace")
            return_code = result.returncode

            combined_output = stdout
            if stderr:
                if combined_output:
                    combined_output += "\n"
                combined_output += stderr

            encoded_output = base64.b64encode(combined_output.encode("utf-8")).decode("utf-8")

            logger.info(f"Shell command completed with return code: {return_code}")

            return {
                "success": True,
                "output": encoded_output,
                "encoding": "base64",
                "return_code": return_code,
                "shell": shell_executable,
                "message": f"Command executed with return code {return_code}",
            }

        except subprocess.TimeoutExpired:
            logger.warning(f"Shell command timed out after {timeout} seconds")
            return self._error_response(f"Command timed out after {timeout} seconds")
        except Exception as e:
            logger.error(f"Error executing shell command: {e}")
            return self._error_response(f"Failed to execute command: {e}")

    def _error_response(self, message: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": message,
        }
