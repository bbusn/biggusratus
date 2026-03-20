import json
import logging
import socket
import time
from typing import Any, Dict, Optional

from common.constants import (
    CONNECT_TIMEOUT_SEC,
    DEFAULT_CLIENT_HOST,
    DEFAULT_PORT,
    HANDSHAKE_ACTION,
    RETRY_DELAY,
)
from common.protocol import build_handshake_command, decode_message, encode_message
from common.tcp import ProtocolError, recv_frame, send_frame

logger = logging.getLogger(__name__)


class Client:
    def __init__(
        self, host: str = DEFAULT_CLIENT_HOST, port: int = DEFAULT_PORT
    ) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.connected = False

    def connect(self) -> None:
        if self.socket is not None:
            self.disconnect()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.settimeout(CONNECT_TIMEOUT_SEC)
        try:
            sock.connect((self.host, self.port))
        except (ConnectionRefusedError, OSError) as exc:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {exc}")
            sock.close()
            raise
        sock.settimeout(None)
        self.socket = sock
        self.connected = True
        logger.info(f"TCP connection established to {self.host}:{self.port}")

    def handshake(self) -> None:
        if self.socket is None:
            raise RuntimeError("Cannot handshake: not connected")
        command = build_handshake_command()
        send_frame(self.socket, encode_message(command))
        raw = recv_frame(self.socket)
        response = decode_message(raw)
        self._validate_handshake_response(response, command["id"])
        logger.info("Handshake completed with server")

    @staticmethod
    def _validate_handshake_response(
        message: Dict[str, Any], expected_request_id: str
    ) -> None:
        if message.get("type") != "response":
            raise ValueError("Handshake reply must be a response message")
        if message.get("action") != HANDSHAKE_ACTION:
            raise ValueError("Invalid handshake response action")
        if message.get("id") != expected_request_id:
            raise ValueError("Handshake response id mismatch")
        if message.get("status") != "success":
            raise ValueError("Handshake rejected by server")

    def run_receive_loop(self) -> None:
        """Block processing framed messages until the connection drops."""
        if self.socket is None:
            raise RuntimeError("Cannot receive: not connected")
        while self.connected:
            raw = recv_frame(self.socket)
            message = decode_message(raw)
            logger.debug(
                f"Received message type={message.get('type')} "
                f"action={message.get('action')}"
            )

    def run_session(self) -> None:
        """Connect, handshake, then process inbound traffic."""
        self.connect()
        self.handshake()
        self.run_receive_loop()

    def disconnect(self) -> None:
        self.connected = False
        if self.socket:
            try:
                self.socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None
        logger.info("Client disconnected")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    client = Client()
    while True:
        try:
            client.run_session()
        except KeyboardInterrupt:
            client.disconnect()
            logger.info("Client shutting down")
            break
        except (ConnectionRefusedError, ConnectionError, OSError) as exc:
            logger.warning(f"Connection lost or failed: {exc}")
            client.disconnect()
            time.sleep(RETRY_DELAY)
        except (ProtocolError, ValueError, json.JSONDecodeError) as exc:
            logger.error(f"Protocol error: {exc}")
            client.disconnect()
            time.sleep(RETRY_DELAY)


if __name__ == "__main__":
    main()
