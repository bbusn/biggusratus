import logging
import socket
import threading
from typing import Optional

from common.constants import DEFAULT_HOST, DEFAULT_PORT

logger = logging.getLogger(__name__)


class Server:
    def __init__(
        self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT
    ) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.agents: dict[str, socket.socket] = {}
        self.lock = threading.Lock()

    def start(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen()
        self.running = True
        logger.info(f"Server started on {self.host}:{self.port}")

    def stop(self) -> None:
        self.running = False
        if self.socket:
            self.socket.close()
            self.socket = None
        logger.info("Server stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    server = Server()
    try:
        server.start()
    except KeyboardInterrupt:
        server.stop()


if __name__ == "__main__":
    main()
