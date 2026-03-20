import socket

import pytest

from common.constants import LENGTH_PREFIX_BYTES, MAX_MESSAGE_BYTES
from common.tcp import ProtocolError, recv_exact, recv_frame, send_frame


def test_recv_exact_reads_full_payload() -> None:
    a, b = socket.socketpair()
    try:
        a.sendall(b"hello")
        assert recv_exact(b, 5) == b"hello"
    finally:
        a.close()
        b.close()


def test_recv_exact_raises_on_early_close() -> None:
    a, b = socket.socketpair()
    try:
        a.close()
        with pytest.raises(ConnectionError):
            recv_exact(b, 1)
    finally:
        b.close()


def test_send_frame_recv_frame_roundtrip() -> None:
    a, b = socket.socketpair()
    try:
        payload = b'{"type":"ping"}'
        send_frame(a, payload)
        assert recv_frame(b) == payload
    finally:
        a.close()
        b.close()


def test_recv_frame_rejects_oversized_length() -> None:
    a, b = socket.socketpair()
    try:
        bad_length = (MAX_MESSAGE_BYTES + 1).to_bytes(LENGTH_PREFIX_BYTES, "big")
        a.sendall(bad_length)
        with pytest.raises(ProtocolError):
            recv_frame(b)
    finally:
        a.close()
        b.close()


def test_send_frame_rejects_oversized_payload() -> None:
    a, b = socket.socketpair()
    try:
        with pytest.raises(ValueError):
            send_frame(a, b"x" * (MAX_MESSAGE_BYTES + 1))
    finally:
        a.close()
        b.close()
