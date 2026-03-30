<div align="center">

<img src="docs/images/goblin.gif" width="350" />

# BiggusRatus

</div>

Remote Administration Tool (RAT) implemented in Python. The project consists of a client, deployed on target machines, that executes commands and reports back and a server, a control center that manages multiple agents through an interactive interface.

Communication occurs via encrypted TCP sockets.

## Client

### Core

- TCP socket connection to server
- Encrypted communication (use `cryptography` library with Fernet)
- Automatic reconnection on disconnect
- Cross-platform: Windows and Linux

### Commands

| Command           | Description                         | Parameters                       | Returns                            |
| ----------------- | ----------------------------------- | -------------------------------- | ---------------------------------- |
| `help`            | Display available commands          | None                             | List of commands with descriptions |
| `download`        | Retrieve file from victim to server | `remote_path`, `local_path`      | File content or error              |
| `upload`          | Send file from server to victim     | `local_path`, `remote_path`      | Success/failure status             |
| `shell`           | Open interactive shell (bash/cmd)   | None                             | Shell session                      |
| `ipconfig`        | Get network configuration           | None                             | Network interfaces and IPs         |
| `screenshot`      | Capture screen                      | None                             | Image data (PNG/JPEG)              |
| `search`          | Search for files                    | `pattern`, `directory`           | List of matching files             |
| `hashdump`        | Extract password hashes             | None                             | SAM (Windows) or shadow (Linux)    |
| `keylogger`       | Record keystrokes                   | `action`: start/stop/get         | Logged keystrokes                  |
| `webcam_snapshot` | Take webcam photo                   | None                             | Image data                         |
| `webcam_stream`   | Stream webcam video                 | `action`: start/stop             | Video stream                       |
| `record_audio`    | Record from microphone              | `action`: start/stop, `duration` | Audio data (WAV)                   |

### Building

Build the client as a standalone binary executable:

```bash
chmod +x build-client.sh
./build-client.sh
```

The binary will be output to `dist/biggusratus-client`.

## Server

### Core

- Listen on configurable TCP port
- Accept multiple agent connections concurrently (threading or asyncio)
- Manage agent sessions (connect/disconnect tracking)
- Interactive command-line interface
- Command error handling with help display

### Commands

| Command       | Description                  |
| ------------- | ---------------------------- |
| `list`        | Show all connected agents    |
| `select <id>` | Select agent for interaction |
| `exit`        | Disconnect selected agent    |
| `quit`        | Shutdown server              |
| `help`        | Display available commands   |

### Web Interface

The server provides a web interface at `http://127.0.0.1:8080` for monitoring and managing connected agents.

### Arguments

| Argument        | Description                    | Default     |
| --------------- | ------------------------------ | ----------- |
| `--host`        | Host address to bind to        | `127.0.0.1` |
| `--port`        | TCP port for agent connections | `8443`      |
| `--web-port`    | Port for web interface         | `8080`      |
| `-v, --verbose` | Enable debug logging           | Off         |

Examples:

```bash
python -m server.server                     # Start with defaults
python -m server.server --port 9443         # Custom agent port
python -m server.server --host 0.0.0.0      # Listen on all interfaces
python -m server.server --verbose           # Enable debug logging
```

## Communication

### Format

All messages use JSON format with encryption:

```python
{
  "version": "1.0",
  "type": "command",             # command | response
  "action": "shell",             # command name for both, even if we base ourselfs on id
  "id": "uuid-1234",             # unique request ID
  "params": {},                  # only for commands
  "status": "success",           # only for response
  "error_code": null,            # only for response status error
  "data": {
    "encoding": "base64",        # or "utf-8"
    "content_type": "text/plain",
    "payload": "..."
  },

  "message": "optional human message",
  "timestamp": 1710000000.123
}
```

## Standards

### Dependencies

Use Poetry for ALL dependencies. Never use pip directly.

```bash
# Adding dependencies
poetry add cryptography
poetry add --group dev pytest

# Installing project
poetry install
```

### Logging

Always use the logging module:

```python
import logging

logger = logging.getLogger(__name__)

# Levels
logger.debug("Detailed diagnostic information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical failure")
```

### Common

Shared code or logic is in common/ folder.
Constants must be extracted to `common/constants.py`

### Conventions

Use classes for commands and major components. Use functions for utilities.

```python
# Classes - PascalCase
class DownloadCommand:
    pass

# Functions/Variables - snake_case
def download_file():
    file_path = "/tmp/file"

# Constants - UPPER_SNAKE_CASE
DEFAULT_PORT = 8443
MAX_RETRIES = 3
```

Use context managers for resources such as below

```python
with open("file.txt", "r") as f:
    content = f.read()
```

Only use f-strings for string formatting.

```python
message = f"Port: {port}"
```

### Typing

All functions must have types :

```python
from typing import Dict, List, Optional, Any

def process_command(
    command: str,
    params: Dict[str, Any],
    timeout: Optional[float] = None
) -> Dict[str, Any]:
    # Process a command and return the result.
    pass
```

### Testing

- Minimum 80% code coverage required
- All commands have unit tests
- Both success and failure scenarios are tested

Use parametrize for multiple test cases:

```python
@pytest.mark.parametrize("os_type,expected", [
    ("windows", "cmd.exe"),
    ("linux", "/bin/bash"),
])
def test_shell_command(self, os_type, expected):
    # Test shell command selection.
    result = get_shell_command(os_type)
    assert result == expected
```

### Pre-Commit

Pre-commit must be configured and used. Run before commits:

```bash
pre-commit run --all-files
```

<br><br>
