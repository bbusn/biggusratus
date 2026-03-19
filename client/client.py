import logging
import socket
import time
from typing import Optional

from common.constants import (
    DEFAULT_PORT,
    MAX_RETRIES,
    RETRY_DELAY,
)

logger = logging.getLogger(__name__)

class Client:
    def __init__(self, host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False

    def connect(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.socket.connect((self.host, self.port))
            self.connected = True
            logger.info(f"Client connected to {self.host}:{self.port}")
        except ConnectionRefusedError:
            logger.error(f"Connection refused by {self.host}:{self.port}")
            self.socket.close()
            self.socket = None
            raise

    def disconnect(self) -> None:
        self.connected = False
        if self.socket:
            self.socket.close()
            self.socket = None
        logger.info("Client disconnected")

    def reconnect(self) -> None:
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info(f"Reconnection attempt {attempt}/{MAX_RETRIES}")
            try:
                self.connect()
                return
            except ConnectionRefusedError:
                if attempt < MAX_RETRIES:
                    time.sleep(RETRY_DELAY)
        logger.error("Max reconnection attempts reached")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    client = Client()
    try:
        client.connect()
    except ConnectionRefusedError:
        logger.error("Could not connect to server")


if __name__ == "__main__":
    main()
