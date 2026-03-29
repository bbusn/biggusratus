# Checklist

## Client

### Core

- [x] TCP socket connection established
- [x] Encryption implemented (Fernet)
- [x] Automatic reconnection logic
- [x] Message serialization (JSON)
- [x] Connection error handling

### Commands

- [x] `help` - Display available commands

  - [x] Command class implemented
  - [x] Returns formatted command list
  - [x] Unit tests written

- [x] `download` - Retrieve file from victim to server

  - [x] Command class implemented
  - [x] Handles binary files
  - [x] Error handling for missing files
  - [x] Progress reporting
  - [x] Unit tests written

- [x] `upload` - Send file from server to victim

  - [x] Command class implemented
  - [x] Handles binary files
  - [x] Path validation
  - [x] Progress reporting
  - [x] Unit tests written

- [x] `shell` - Open interactive shell

  - [x] Command class implemented
  - [x] Windows cmd.exe support
  - [x] Linux bash support
  - [x] Command output capture
  - [x] Unit tests written

- [x] `ipconfig` - Get network configuration

  - [x] Command class implemented
  - [x] Windows implementation
  - [x] Linux implementation
  - [x] Returns all interfaces
  - [x] Unit tests written

- [x] `screenshot` - Capture screen

  - [x] Command class implemented
  - [x] Uses Pillow/mss
  - [x] Returns image data
  - [x] Multi-monitor support
  - [x] Unit tests written

- [x] `keylogger` - Record keystrokes

  - [x] Command class implemented
  - [x] Start/stop/get actions
  - [x] Uses pynput
  - [x] Thread-safe logging
  - [x] Unit tests written

- [x] `webcam_snapshot` - Take webcam photo

  - [x] Command class implemented
  - [x] Uses OpenCV
  - [x] Returns image data
  - [x] Camera selection
  - [x] Unit tests written

- [ ] `webcam_stream` - Stream webcam video

  - [ ] Command class implemented
  - [ ] Start/stop actions
  - [ ] Uses OpenCV
  - [ ] Frame encoding
  - [ ] Unit tests written

- [ ] `record_audio` - Record from microphone

  - [ ] Command class implemented
  - [ ] Start/stop actions
  - [ ] Duration parameter
  - [ ] Uses PyAudio
  - [ ] Returns WAV data
  - [ ] Unit tests written

- [ ] `search` - Search for files

  - [ ] Command class implemented
  - [ ] Pattern matching
  - [ ] Recursive search option
  - [ ] Returns file list with paths
  - [ ] Unit tests written

- [ ] `hashdump` - Extract password hashes

  - [ ] Command class implemented
  - [ ] Windows SAM extraction
  - [ ] Linux shadow extraction
  - [ ] Privilege check
  - [ ] Unit tests written

### OS Support

- [x] OS detection implemented
- [ ] All commands work on Windows
- [ ] All commands work on Linux
- [ ] Platform-specific code paths
- [ ] Platform detection tests

## Server

### Core

- [x] TCP listener implemented
- [x] Configurable port
- [x] Multi-agent support (threading/asyncio)
- [x] Graceful shutdown
- [x] Command-line interface
- [x] Agent list display
- [x] Agent selection
- [x] Command prompt
- [x] Output formatting
- [x] Accept new connections
- [x] Handle disconnections
- [x] Reconnection support
- [x] Connection timeout handling

### Sessions

- [x] Agent session tracking
- [x] Unique session IDs
- [x] Connection timestamp
- [x] Last seen tracking
- [x] Disconnect detection
- [x] Session cleanup

### Commands

- [x] `list` - Show connected agents
- [x] `select <id>` - Select agent
- [x] `exit` - Disconnect agent
- [x] `quit` - Shutdown server
- [x] `help` - Display commands
- [x] Error handling for invalid commands
