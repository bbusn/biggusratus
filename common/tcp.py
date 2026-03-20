"""Length-prefixed TCP framing for reliable message boundaries on a stream."""

import socket

from common.constants import LENGTH_PREFIX_BYTES, MAX_MESSAGE_BYTES


class ProtocolError(Exception):
    """Raised when a peer violates framing or size limits."""


def recv_exact(sock: socket.socket, num_bytes: int) -> bytes:
    """Read exactly ``num_bytes`` from ``sock`` or raise on EOF / error."""
    chunks: list[bytes] = []
    received = 0
    while received < num_bytes:
        chunk = sock.recv(num_bytes - received)
        if not chunk:
            raise ConnectionError(
                f"Connection closed while reading ({received}/{num_bytes} bytes)"
            )
        chunks.append(chunk)
        received += len(chunk)
    return b"".join(chunks)


def send_frame(sock: socket.socket, payload: bytes) -> None:
    """Send a length-prefixed frame (big-endian ``LENGTH_PREFIX_BYTES``)."""
    if len(payload) > MAX_MESSAGE_BYTES:
        raise ValueError(
            f"Payload length {len(payload)} exceeds MAX_MESSAGE_BYTES "
            f"({MAX_MESSAGE_BYTES})"
        )
    length = len(payload).to_bytes(LENGTH_PREFIX_BYTES, "big")
    sock.sendall(length + payload)


def recv_frame(sock: socket.socket) -> bytes:
    """Receive one length-prefixed frame."""
    prefix = recv_exact(sock, LENGTH_PREFIX_BYTES)
    length = int.from_bytes(prefix, "big")
    if length > MAX_MESSAGE_BYTES:
        raise ProtocolError(
            f"Peer announced frame length {length} (max {MAX_MESSAGE_BYTES})"
        )
    return recv_exact(sock, length)
