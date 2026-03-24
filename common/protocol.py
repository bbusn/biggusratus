# JSON message helpers aligned with README communication format.

import json
import time
import uuid
from typing import Any, Dict, Optional

from common.constants import HANDSHAKE_ACTION, PROTOCOL_VERSION
from common.crypto import Encryptor, key_to_string


def encode_message(message: Dict[str, Any]) -> bytes:
    # Serialize a protocol message to UTF-8 JSON bytes.
    return json.dumps(message, separators=(",", ":")).encode("utf-8")


def decode_message(data: bytes) -> Dict[str, Any]:
    # Parse a UTF-8 JSON protocol message.
    return json.loads(data.decode("utf-8"))


def build_handshake_command(os_info: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    # Client → server first message with optional OS info.
    params = {}
    if os_info is not None:
        params["os_info"] = os_info
    return {
        "version": PROTOCOL_VERSION,
        "type": "command",
        "action": HANDSHAKE_ACTION,
        "id": str(uuid.uuid4()),
        "params": params,
        "message": None,
        "timestamp": None,
    }


def build_handshake_response(
    request_id: str, encryptor: Optional[Encryptor] = None
) -> Dict[str, Any]:
    # Server → client handshake acknowledgement with encryption key.
    key_payload = "{}"
    if encryptor is not None:
        key_payload = json.dumps({"encryption_key": key_to_string(encryptor.key)})
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
            "payload": key_payload,
        },
        "message": "connected",
        "timestamp": None,
    }


def extract_encryption_key_from_handshake(message: Dict[str, Any]) -> Optional[str]:
    # Extract encryption key from handshake response data payload.
    data = message.get("data", {})
    if not data:
        return None
    payload = data.get("payload", "{}")
    try:
        parsed = json.loads(payload)
        return parsed.get("encryption_key")
    except json.JSONDecodeError:
        return None


def extract_os_info_from_handshake(message: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    # Extract OS info from handshake command params.
    params = message.get("params", {})
    return params.get("os_info")


def build_command(
    action: str,
    params: Dict[str, Any],
    *,
    message_id: Optional[str] = None,
) -> Dict[str, Any]:
    # Build a command message (either direction on the wire).
    return {
        "version": PROTOCOL_VERSION,
        "type": "command",
        "action": action,
        "id": message_id or str(uuid.uuid4()),
        "params": params,
        "message": None,
        "timestamp": time.time(),
    }


def build_success_response(
    request_id: str,
    action: str,
    *,
    payload: str = "{}",
    encoding: str = "utf-8",
    content_type: str = "application/json",
    message: Optional[str] = None,
) -> Dict[str, Any]:
    # Build a successful response for a given command id.
    return {
        "version": PROTOCOL_VERSION,
        "type": "response",
        "action": action,
        "id": request_id,
        "status": "success",
        "error_code": None,
        "data": {
            "encoding": encoding,
            "content_type": content_type,
            "payload": payload,
        },
        "message": message,
        "timestamp": time.time(),
    }
