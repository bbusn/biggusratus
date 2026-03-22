import json
import logging
import queue
import socket
import threading
import time
from typing import Any, Dict, Optional

from common.constants import (
    CONNECT_TIMEOUT_SEC,
    DEFAULT_CLIENT_HOST,
    DEFAULT_PORT,
    HANDSHAKE_ACTION,
    HELP_ACTION,
    RETRY_DELAY,
    TEST_ACTION,
)
from client.commands.help import HelpCommand
from common.protocol import (
    build_command,
    build_handshake_command,
    build_success_response,
    decode_message,
    encode_message,
)
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
        self._send_lock = threading.Lock()
        self._response_waiters: Dict[str, "queue.Queue[Dict[str, Any]]"] = {}
        self._response_lock = threading.Lock()
        self._commands = {
            HELP_ACTION: HelpCommand(),
        }

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
        with self._send_lock:
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

    def _handle_incoming_message(self, message: Dict[str, Any]) -> None:
        if message.get("type") == "response":
            rid = str(message.get("id", ""))
            with self._response_lock:
                waiter = self._response_waiters.pop(rid, None)
            if waiter is not None:
                waiter.put(message)
                return
            logger.info(f"Received response: {message}")
            return
        if message.get("type") == "command":
            action = message.get("action")
            logger.info(f"Received command: {message}")
            if self.socket is None:
                return
            req_id = str(message.get("id", ""))
            if action in self._commands:
                result = self._commands[action].execute(message.get("params", {}))
                import json as json_mod
                reply = build_success_response(
                    req_id,
                    action,
                    payload=json_mod.dumps(result),
                    message=f"{action}-ok",
                )
            elif action == TEST_ACTION:
                reply = build_success_response(
                    req_id, TEST_ACTION, payload='{"ok":true}', message="test-ok"
                )
            else:
                logger.warning(f"Unknown command action: {action}")
                return
            with self._send_lock:
                send_frame(self.socket, encode_message(reply))
            return
        logger.warning(f"Unhandled message: {message}")

    def _receive_loop(self) -> None:
        if self.socket is None:
            return
        try:
            while self.connected:
                raw = recv_frame(self.socket)
                message = decode_message(raw)
                self._handle_incoming_message(message)
        except (ConnectionError, OSError, ProtocolError, json.JSONDecodeError) as exc:
            logger.warning(f"Receive loop ended: {exc}")
        finally:
            self.connected = False

    def _send_test_command(self) -> None:
        if self.socket is None or not self.connected:
            logger.error("Not connected")
            return
        cmd = build_command(TEST_ACTION, {})
        request_id = str(cmd["id"])
        waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
        with self._response_lock:
            self._response_waiters[request_id] = waiter
        try:
            with self._send_lock:
                send_frame(self.socket, encode_message(cmd))
            response = waiter.get(timeout=30.0)
            logger.info(f"Test round-trip OK: {response}")
        except queue.Empty:
            logger.error("Timed out waiting for test response from server")
        finally:
            with self._response_lock:
                self._response_waiters.pop(request_id, None)

    def _input_loop(self) -> None:
        while self.connected:
            try:
                line = input("client> ").strip()
            except EOFError:
                break
            if not line:
                continue
            if line == "test":
                self._send_test_command()
            elif line in ("quit", "exit"):
                break
            else:
                logger.warning(f"Unknown input: {line}")

    def run_receive_loop(self) -> None:
        """Block processing framed messages until the connection drops."""
        self._receive_loop()

    def run_session(self) -> None:
        """Connect, handshake, then process bidirectional traffic."""
        self.connect()
        self.handshake()
        recv_thread = threading.Thread(
            target=self._receive_loop, name="client-recv", daemon=True
        )
        recv_thread.start()
        try:
            self._input_loop()
        finally:
            self.disconnect()
            recv_thread.join(timeout=2.0)

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
