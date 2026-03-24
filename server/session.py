# Agent session management.

import socket
import time
from typing import Any, Dict, Optional, Tuple

from common.crypto import Encryptor
from common.hmac import MessageAuthenticator


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
        self.authenticator: Optional[MessageAuthenticator] = None
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
