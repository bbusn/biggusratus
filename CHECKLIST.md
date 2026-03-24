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

- [ ] `download` - Retrieve file from victim to server

  - [ ] Command class implemented
  - [ ] Handles binary files
  - [ ] Error handling for missing files
  - [ ] Progress reporting
  - [ ] Unit tests written

- [ ] `upload` - Send file from server to victim

  - [ ] Command class implemented
  - [ ] Handles binary files
  - [ ] Path validation
  - [ ] Progress reporting
  - [ ] Unit tests written

- [ ] `shell` - Open interactive shell

  - [ ] Command class implemented
  - [ ] Windows cmd.exe support
  - [ ] Linux bash support
  - [ ] Command output capture
  - [ ] Unit tests written

- [ ] `ipconfig` - Get network configuration

  - [ ] Command class implemented
  - [ ] Windows implementation
  - [ ] Linux implementation
  - [ ] Returns all interfaces
  - [ ] Unit tests written

- [ ] `screenshot` - Capture screen

  - [ ] Command class implemented
  - [ ] Uses Pillow/mss
  - [ ] Returns image data
  - [ ] Multi-monitor support
  - [ ] Unit tests written

- [ ] `keylogger` - Record keystrokes

  - [ ] Command class implemented
  - [ ] Start/stop/get actions
  - [ ] Uses pynput
  - [ ] Thread-safe logging
  - [ ] Unit tests written

- [ ] `webcam_snapshot` - Take webcam photo

  - [ ] Command class implemented
  - [ ] Uses OpenCV
  - [ ] Returns image data
  - [ ] Camera selection
  - [ ] Unit tests written

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

- [ ] OS detection implemented
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
