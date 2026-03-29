# Fernet symmetric encryption for secure communication.

import base64
import logging
from typing import Optional, Tuple

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class CryptoError(Exception):
    # Raised when encryption/decryption fails.
    pass


def generate_key() -> bytes:
    # Generate a new Fernet key.
    return Fernet.generate_key()


def derive_fernet_key(raw_key: bytes) -> bytes:
    # Derive a Fernet-compatible key from raw bytes using HKDF.
    # Fernet requires a 32-byte URL-safe base64-encoded key.
    derived = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'fernet key derivation',
        backend=default_backend()
    ).derive(raw_key)
    return base64.urlsafe_b64encode(derived)


def derive_keys_from_shared_secret(shared_secret: bytes) -> Tuple[bytes, bytes]:
    # Derive separate encryption and HMAC keys from a shared secret.
    # This uses HKDF with different info parameters to generate two
    # cryptographically independent keys from the same secret.
    # Returns (encryption_key, hmac_key).
    
    # Derive encryption key (for Fernet)
    encryption_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'biggusratus encryption key',
        backend=default_backend()
    ).derive(shared_secret)
    encryption_key = base64.urlsafe_b64encode(encryption_key)
    
    # Derive HMAC key (for message authentication)
    hmac_key = HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=None,
        info=b'biggusratus hmac key',
        backend=default_backend()
    ).derive(shared_secret)
    
    return encryption_key, hmac_key


def key_to_string(key: bytes) -> str:
    # Convert a Fernet key to a URL-safe base64 string.
    return key.decode("utf-8")


def key_from_string(key_string: str) -> bytes:
    # Convert a URL-safe base64 string back to a Fernet key.
    return key_string.encode("utf-8")


class Encryptor:
    # Handles encryption/decryption using Fernet symmetric encryption.

    def __init__(
        self,
        key: Optional[bytes] = None,
        derived_from_shared_secret: bool = False,
        hmac_key: Optional[bytes] = None
    ) -> None:
        if key is None:
            key = generate_key()
        elif derived_from_shared_secret:
            # Key is a raw shared secret, derive both encryption and HMAC keys
            key, hmac_key = derive_keys_from_shared_secret(key)
        self._key = key
        self._hmac_key = hmac_key
        self._fernet = Fernet(key)
        logger.debug("Encryptor initialized")

    @classmethod
    def from_shared_secret(cls, shared_secret: bytes) -> "Encryptor":
        # Create an Encryptor from a DH shared secret.
        return cls(key=shared_secret, derived_from_shared_secret=True)

    @property
    def key(self) -> bytes:
        # Return the encryption key.
        return self._key

    @property
    def hmac_key(self) -> Optional[bytes]:
        # Return the HMAC key (if available).
        return self._hmac_key

    def encrypt(self, plaintext: bytes) -> bytes:
        # Encrypt plaintext bytes and return ciphertext.
        if not plaintext:
            raise CryptoError("Cannot encrypt empty plaintext")
        try:
            return self._fernet.encrypt(plaintext)
        except Exception as exc:
            raise CryptoError(f"Encryption failed: {exc}") from exc

    def decrypt(self, ciphertext: bytes) -> bytes:
        # Decrypt ciphertext bytes and return plaintext.
        if not ciphertext:
            raise CryptoError("Cannot decrypt empty ciphertext")
        try:
            return self._fernet.decrypt(ciphertext)
        except InvalidToken as exc:
            raise CryptoError("Decryption failed: invalid token or key") from exc
        except Exception as exc:
            raise CryptoError(f"Decryption failed: {exc}") from exc

    def encrypt_string(self, plaintext: str) -> bytes:
        # Encrypt a string and return ciphertext bytes.
        return self.encrypt(plaintext.encode("utf-8"))

    def decrypt_to_string(self, ciphertext: bytes) -> str:
        # Decrypt ciphertext bytes and return a string.
        return self.decrypt(ciphertext).decode("utf-8")
