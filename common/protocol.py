"""JSON message helpers aligned with README communication format (pre-encryption)."""

import json
import uuid
from typing import Any, Dict

from common.constants import HANDSHAKE_ACTION, PROTOCOL_VERSION


def encode_message(message: Dict[str, Any]) -> bytes:
    """Serialize a protocol message to UTF-8 JSON bytes."""
    return json.dumps(message, separators=(",", ":")).encode("utf-8")


def decode_message(data: bytes) -> Dict[str, Any]:
    """Parse a UTF-8 JSON protocol message."""
    return json.loads(data.decode("utf-8"))


def build_handshake_command() -> Dict[str, Any]:
    """Client → server first message."""
    return {
        "version": PROTOCOL_VERSION,
        "type": "command",
        "action": HANDSHAKE_ACTION,
        "id": str(uuid.uuid4()),
        "params": {},
        "message": None,
        "timestamp": None,
    }


def build_handshake_response(request_id: str) -> Dict[str, Any]:
    """Server → client handshake acknowledgement."""
    return {
        "version": PROTOCOL_VERSION,
        "type": "response",
        "action": HANDSHAKE_ACTION,
        "id": request_id,
        "status": "success",
        "error_code": None,
        "data": {
            "encoding": "utf-8",
            "content_type": "application/json",
            "payload": "{}",
        },
        "message": "connected",
        "timestamp": None,
    }
