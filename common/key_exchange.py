# Elliptic Curve Diffie-Hellman (ECDH) key exchange for secure encryption key derivation.

import logging
from typing import Tuple

from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.backends import default_backend

logger = logging.getLogger(__name__)


class KeyExchangeError(Exception):
    # Raised when key exchange fails.
    pass


def generate_ecdh_keypair() -> Tuple[bytes, bytes]:
    # Generate an ECDH key pair using SECP384R1 curve.

    # Returns:
    #    Tuple of (private_key_bytes, public_key_bytes) in PEM format
    
    try:
        private_key = ec.generate_private_key(ec.SECP384R1(), default_backend())
        public_key = private_key.public_key()

        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )

        return private_bytes, public_bytes
    except Exception as exc:
        raise KeyExchangeError(f"Failed to generate ECDH keypair: {exc}") from exc


def compute_shared_key(private_key_bytes: bytes, peer_public_key_bytes: bytes) -> bytes:
    # Compute shared secret using ECDH private key and peer's public key.

    # Args:
    #     private_key_bytes: Our private key in PEM format
    #     peer_public_key_bytes: Peer's public key in PEM format

    # Returns:
    #     Derived 32-byte key suitable for Fernet
    
    try:
        # Load our private key
        private_key = serialization.load_pem_private_key(
            private_key_bytes,
            password=None,
            backend=default_backend()
        )

        # Load peer's public key
        peer_public_key = serialization.load_pem_public_key(
            peer_public_key_bytes,
            backend=default_backend()
        )

        # Perform ECDH key exchange
        shared_secret = private_key.exchange(ec.ECDH(), peer_public_key)

        # Derive a 32-byte key using HKDF
        derived_key = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=b'biggusratus encryption key',
            backend=default_backend()
        ).derive(shared_secret)

        return derived_key
    except Exception as exc:
        raise KeyExchangeError(f"Failed to compute shared key: {exc}") from exc


class ECDHExchange:
    # Manages an Elliptic Curve Diffie-Hellman key exchange session.

    def __init__(self) -> None:
        self._private_key_bytes: bytes = b""
        self._public_key_bytes: bytes = b""
        self._generated = False

    def generate_keypair(self) -> bytes:
        # Generate a new ECDH keypair and return the public key.

        # Returns:
        #     Public key bytes in PEM format
        
        self._private_key_bytes, self._public_key_bytes = generate_ecdh_keypair()
        self._generated = True
        logger.debug("ECDH keypair generated")
        return self._public_key_bytes

    def compute_shared_key(self, peer_public_key_bytes: bytes) -> bytes:
        # Compute shared key using peer's public key.

        # Args:
        #     peer_public_key_bytes: Peer's public key in PEM format

        # Returns:
        #     Derived 32-byte key suitable for Fernet
        
        if not self._generated:
            raise KeyExchangeError("Must generate keypair first")

        shared_key = compute_shared_key(self._private_key_bytes, peer_public_key_bytes)
        logger.debug("Shared key computed")
        return shared_key

    @property
    def public_key(self) -> bytes:
        # Return our public key.
        if not self._generated:
            raise KeyExchangeError("Must generate keypair first")
        return self._public_key_bytes
