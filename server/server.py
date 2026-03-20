import json
import logging
import socket
import threading
import uuid
from typing import Any, Dict, Optional, Tuple

from common.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HANDSHAKE_ACTION,
    PROTOCOL_VERSION,
)
from common.protocol import (
    build_handshake_response,
    decode_message,
    encode_message,
)
from common.tcp import ProtocolError, recv_frame, send_frame

logger = logging.getLogger(__name__)


class Server:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.agents: Dict[str, socket.socket] = {}
        self.lock = threading.Lock()

    def start(self) -> None:
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.socket.bind((self.host, self.port))
        self.socket.listen()
        self.running = True
        logger.info(f"Server started on {self.host}:{self.port}")
        self._accept_connections()

    def _accept_connections(self) -> None:
        while self.running:
            try:
                client_socket, address = self.socket.accept()
                agent_id = str(uuid.uuid4())
                logger.info(
                    f"New TCP connection from {address[0]}:{address[1]} "
                    f"(agent_id={agent_id})"
                )
                with self.lock:
                    self.agents[agent_id] = client_socket
                thread = threading.Thread(
                    target=self._handle_agent,
                    args=(client_socket, address, agent_id),
                    name=f"agent-{agent_id[:8]}",
                    daemon=True,
                )
                thread.start()
            except OSError:
                break

    def _handle_agent(
        self,
        client_socket: socket.socket,
        address: Tuple[str, int],
        agent_id: str,
    ) -> None:
        try:
            self._perform_handshake(client_socket)
            logger.info(
                f"Handshake complete for agent {agent_id} "
                f"({address[0]}:{address[1]})"
            )
            self._agent_message_loop(client_socket, agent_id)
        except (
            ConnectionError,
            OSError,
            ProtocolError,
            ValueError,
            json.JSONDecodeError,
        ) as exc:
            logger.warning(
                f"Agent {agent_id} ({address[0]}:{address[1]}) disconnected: {exc}"
            )
        except Exception:
            logger.exception(
                f"Unexpected error handling agent {agent_id} "
                f"({address[0]}:{address[1]})"
            )
        finally:
            try:
                client_socket.close()
            except OSError:
                pass
            with self.lock:
                self.agents.pop(agent_id, None)
            logger.info(f"Agent session closed: {agent_id}")

    def _perform_handshake(self, client_socket: socket.socket) -> None:
        raw = recv_frame(client_socket)
        message = decode_message(raw)
        self._validate_handshake_request(message)
        request_id = str(message.get("id", ""))
        response = build_handshake_response(request_id)
        send_frame(client_socket, encode_message(response))

    @staticmethod
    def _validate_handshake_request(message: Dict[str, Any]) -> None:
        if message.get("version") != PROTOCOL_VERSION:
            raise ValueError("Invalid or unsupported protocol version")
        if message.get("type") != "command":
            raise ValueError("Handshake must be a command message")
        if message.get("action") != HANDSHAKE_ACTION:
            raise ValueError("First message must be handshake command")

    def _agent_message_loop(self, client_socket: socket.socket, agent_id: str) -> None:
        while self.running:
            raw = recv_frame(client_socket)
            message = decode_message(raw)
            logger.debug(
                f"Received from {agent_id}: type={message.get('type')} "
                f"action={message.get('action')}"
            )

    def stop(self) -> None:
        self.running = False
        with self.lock:
            for agent_id, sock in list(self.agents.items()):
                try:
                    sock.close()
                except OSError:
                    pass
            self.agents.clear()
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
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
