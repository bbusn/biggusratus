# HMAC-based message authentication for command integrity.

import hashlib
import hmac
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class HmacError(Exception):
    # Raised when HMAC verification fails.
    pass


class MessageAuthenticator:
    # Handles HMAC signing and verification for message integrity.

    def __init__(self, hmac_key: bytes) -> None:
        if not hmac_key or len(hmac_key) < 16:
            raise ValueError("HMAC key must be at least 16 bytes")
        self._hmac_key = hmac_key
        logger.debug("MessageAuthenticator initialized")

    @staticmethod
    def _serialize_for_signing(message: Dict[str, Any]) -> bytes:
        # Canonical JSON over signed fields only (excludes hmac, timestamp, message).
        # sort_keys gives stable ordering for nested dicts (e.g. command params).
        signed: Dict[str, Any] = {}
        for key in ("version", "type", "action", "id", "status", "error_code"):
            if key in message and message[key] is not None:
                signed[key] = message[key]
        if "params" in message and message["params"] is not None:
            signed["params"] = message["params"]
        data = message.get("data")
        if isinstance(data, dict) and "payload" in data:
            signed["payload"] = data["payload"]
        return json.dumps(signed, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def sign(self, message: Dict[str, Any]) -> str:
        # Generate an HMAC signature for the message.
        # Returns a hex-encoded signature string.
        data = self._serialize_for_signing(message)
        signature = hmac.new(self._hmac_key, data, hashlib.sha256).hexdigest()
        return signature

    def verify(self, message: Dict[str, Any], expected_hmac: Optional[str] = None) -> bool:
        # Verify the HMAC signature of a message.
        # If expected_hmac is provided, verify against it.
        # Otherwise, look for 'hmac' field in the message.
        if expected_hmac is None:
            expected_hmac = message.get("hmac")
            if expected_hmac is None:
                raise HmacError("Message has no HMAC signature to verify")

        data = self._serialize_for_signing(message)
        computed = hmac.new(self._hmac_key, data, hashlib.sha256).hexdigest()

        # Use constant-time comparison to prevent timing attacks
        if not hmac.compare_digest(computed, expected_hmac):
            logger.warning("HMAC verification failed")
            return False

        return True

    def sign_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        # Add HMAC signature to a message and return it.
        # The message is modified in place and returned.
        message["hmac"] = self.sign(message)
        return message

    def verify_message(self, message: Dict[str, Any]) -> bool:
        # Verify a message that contains its own HMAC signature.
        # Raises HmacError if the signature is missing. Always restores "hmac"
        # on the dict after verification so callers keep a consistent message.
        if "hmac" not in message:
            raise HmacError("Message missing HMAC signature")

        stored_hmac = message.pop("hmac")
        try:
            return self.verify(message, stored_hmac)
        finally:
            message["hmac"] = stored_hmac
