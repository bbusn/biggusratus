import json
import logging
import queue
import socket
import threading
import uuid
from typing import Any, Dict, Optional, Tuple

from common.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    HANDSHAKE_ACTION,
    PROTOCOL_VERSION,
    TEST_ACTION,
)
from common.protocol import (
    build_command,
    build_handshake_response,
    build_success_response,
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
        self._accept_thread: Optional[threading.Thread] = None
        self.selected_agent_id: Optional[str] = None
        self._response_waiters: Dict[str, "queue.Queue[Dict[str, Any]]"] = {}
        self._response_lock = threading.Lock()

    def start(self) -> None:
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.bind((self.host, self.port))
        listen_sock.listen()
        self.socket = listen_sock
        self.running = True
        self._accept_thread = threading.Thread(
            target=self._accept_connections, name="server-accept", daemon=True
        )
        self._accept_thread.start()
        bound = listen_sock.getsockname()
        logger.info(f"Server started on {bound[0]}:{bound[1]}")

    def _accept_connections(self) -> None:
        assert self.socket is not None
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
                if self.selected_agent_id == agent_id:
                    self.selected_agent_id = None
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

    def _handle_agent_incoming(
        self, client_socket: socket.socket, agent_id: str, message: Dict[str, Any]
    ) -> None:
        if message.get("type") == "response":
            rid = str(message.get("id", ""))
            with self._response_lock:
                waiter = self._response_waiters.pop(rid, None)
            if waiter is not None:
                waiter.put(message)
                return
            logger.info(f"Received response from agent {agent_id}: {message}")
            return
        if message.get("type") == "command" and message.get("action") == TEST_ACTION:
            logger.info(f"Received command from agent {agent_id}: {message}")
            req_id = str(message.get("id", ""))
            reply = build_success_response(
                req_id, TEST_ACTION, payload='{"ok":true}', message="test-ok"
            )
            send_frame(client_socket, encode_message(reply))
            return
        logger.warning(f"Unhandled message from agent {agent_id}: {message}")

    def _agent_message_loop(self, client_socket: socket.socket, agent_id: str) -> None:
        while self.running:
            raw = recv_frame(client_socket)
            message = decode_message(raw)
            self._handle_agent_incoming(client_socket, agent_id, message)

    def send_test_to_agent(self, agent_id: str) -> None:
        with self.lock:
            sock = self.agents.get(agent_id)
        if sock is None:
            logger.error(f"No such agent: {agent_id}")
            return
        cmd = build_command(TEST_ACTION, {})
        request_id = str(cmd["id"])
        waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
        with self._response_lock:
            self._response_waiters[request_id] = waiter
        try:
            send_frame(sock, encode_message(cmd))
            response = waiter.get(timeout=30.0)
            logger.info(f"Test round-trip OK from {agent_id}: {response}")
        except queue.Empty:
            logger.error(f"Timed out waiting for test response from {agent_id}")
        finally:
            with self._response_lock:
                self._response_waiters.pop(request_id, None)

    def run_interactive(self) -> None:
        print("Type 'help' for commands.")
        while self.running:
            try:
                line = input("rat> ").strip()
            except EOFError:
                break
            if not line:
                continue
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            if cmd == "help":
                print("help  list  select <agent_id>  test  quit")
            elif cmd == "list":
                with self.lock:
                    ids = list(self.agents.keys())
                if not ids:
                    print("No connected agents.")
                else:
                    for aid in ids:
                        mark = " *" if aid == self.selected_agent_id else ""
                        print(f"  {aid}{mark}")
            elif cmd == "select":
                if not arg:
                    print("Usage: select <agent_id>")
                    continue
                with self.lock:
                    if arg not in self.agents:
                        print(f"Unknown agent: {arg}")
                        continue
                    self.selected_agent_id = arg
                print(f"Selected agent {arg}")
            elif cmd == "test":
                target = self.selected_agent_id
                if target is None:
                    print("Select an agent first: select <agent_id>")
                    continue
                self.send_test_to_agent(target)
            elif cmd == "quit":
                break
            else:
                print(f"Unknown command: {cmd}")

    def stop(self) -> None:
        self.running = False
        with self.lock:
            for _, sock in list(self.agents.items()):
                try:
                    sock.close()
                except OSError:
                    pass
            self.agents.clear()
            self.selected_agent_id = None
        if self.socket:
            try:
                self.socket.close()
            except OSError:
                pass
            self.socket = None
        if self._accept_thread is not None:
            self._accept_thread.join(timeout=2.0)
            self._accept_thread = None
        logger.info("Server stopped")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    server = Server()
    try:
        server.start()
        server.run_interactive()
    except KeyboardInterrupt:
        logger.info("Interrupt received")
    finally:
        server.stop()


if __name__ == "__main__":
    main()
