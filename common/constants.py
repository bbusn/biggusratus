# Network
DEFAULT_HOST = "0.0.0.0"
DEFAULT_CLIENT_HOST = "127.0.0.1"
DEFAULT_PORT = 4444
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
# Max file size in bytes (50 MB default)
# Note: base64 encoding increases size by ~33%, so actual memory usage is higher
MAX_FILE_SIZE_BYTES = 50 * 1024 * 1024

HANDSHAKE_ACTION = "handshake"
# Temporary wire check; remove when real commands land.
TEST_ACTION = "test"
HELP_ACTION = "help"
DOWNLOAD_ACTION = "download"
UPLOAD_ACTION = "upload"

# OS Types
OS_WINDOWS = "windows"
OS_LINUX = "linux"
OS_DARWIN = "darwin"
OS_UNKNOWN = "unknown"
