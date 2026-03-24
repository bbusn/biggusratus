import pytest

from common.crypto import (
    CryptoError,
    Encryptor,
    derive_keys_from_shared_secret,
    generate_key,
    key_from_string,
    key_to_string,
)


class TestGenerateKey:
    def test_generate_key_returns_bytes(self) -> None:
        key = generate_key()
        assert isinstance(key, bytes)

    def test_generate_key_returns_unique_keys(self) -> None:
        key1 = generate_key()
        key2 = generate_key()
        assert key1 != key2

    def test_generate_key_length(self) -> None:
        # Fernet keys are 44 URL-safe base64-encoded bytes
        key = generate_key()
        assert len(key) == 44


class TestKeyConversion:
    def test_key_to_string_and_back(self) -> None:
        key = generate_key()
        key_string = key_to_string(key)
        recovered = key_from_string(key_string)
        assert recovered == key

    def test_key_to_string_returns_str(self) -> None:
        key = generate_key()
        key_string = key_to_string(key)
        assert isinstance(key_string, str)

    def test_key_from_string_returns_bytes(self) -> None:
        key = generate_key()
        key_string = key_to_string(key)
        recovered = key_from_string(key_string)
        assert isinstance(recovered, bytes)


class TestEncryptor:
    def test_encryptor_init_with_key(self) -> None:
        key = generate_key()
        encryptor = Encryptor(key=key)
        assert encryptor.key == key

    def test_encryptor_init_without_key(self) -> None:
        encryptor = Encryptor()
        assert isinstance(encryptor.key, bytes)
        assert len(encryptor.key) == 44

    def test_encrypt_decrypt_roundtrip(self) -> None:
        encryptor = Encryptor()
        plaintext = b"Hello, World!"
        ciphertext = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_decrypt_string_roundtrip(self) -> None:
        encryptor = Encryptor()
        plaintext = "Hello, World!"
        ciphertext = encryptor.encrypt_string(plaintext)
        decrypted = encryptor.decrypt_to_string(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_produces_different_ciphertext(self) -> None:
        encryptor = Encryptor()
        plaintext = b"Same message"
        ct1 = encryptor.encrypt(plaintext)
        ct2 = encryptor.encrypt(plaintext)
        # Fernet includes a timestamp, so same plaintext produces different ciphertext
        assert ct1 != ct2

    def test_encrypt_empty_raises(self) -> None:
        encryptor = Encryptor()
        with pytest.raises(CryptoError, match="Cannot encrypt empty plaintext"):
            encryptor.encrypt(b"")

    def test_decrypt_empty_raises(self) -> None:
        encryptor = Encryptor()
        with pytest.raises(CryptoError, match="Cannot decrypt empty ciphertext"):
            encryptor.decrypt(b"")

    def test_decrypt_invalid_token_raises(self) -> None:
        encryptor = Encryptor()
        with pytest.raises(CryptoError, match="invalid token"):
            encryptor.decrypt(b"invalid-ciphertext")

    def test_decrypt_with_wrong_key_raises(self) -> None:
        encryptor1 = Encryptor()
        encryptor2 = Encryptor()
        ciphertext = encryptor1.encrypt(b"Secret message")
        with pytest.raises(CryptoError, match="invalid token"):
            encryptor2.decrypt(ciphertext)

    def test_shared_key_encryption(self) -> None:
        key = generate_key()
        encryptor1 = Encryptor(key=key)
        encryptor2 = Encryptor(key=key)
        plaintext = b"Shared secret"
        ciphertext = encryptor1.encrypt(plaintext)
        decrypted = encryptor2.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_unicode_string(self) -> None:
        encryptor = Encryptor()
        plaintext = "Unicode: \u00e9\u00e8\u00ea\u00eb \u4e2d\u6587"
        ciphertext = encryptor.encrypt_string(plaintext)
        decrypted = encryptor.decrypt_to_string(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_binary_data(self) -> None:
        encryptor = Encryptor()
        plaintext = bytes(range(256))
        ciphertext = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_encrypt_large_payload(self) -> None:
        encryptor = Encryptor()
        # 1 MB of data
        plaintext = b"x" * (1024 * 1024)
        ciphertext = encryptor.encrypt(plaintext)
        decrypted = encryptor.decrypt(ciphertext)
        assert decrypted == plaintext

    def test_from_shared_secret_derives_hmac_key(self) -> None:
        raw = b"\xab" * 32
        enc1, mac1 = derive_keys_from_shared_secret(raw)
        encryptor = Encryptor.from_shared_secret(raw)
        assert encryptor.key == enc1
        assert encryptor.hmac_key == mac1
        assert isinstance(encryptor.hmac_key, bytes)
        assert len(encryptor.hmac_key) == 32

    def test_from_shared_secret_roundtrip_decrypt(self) -> None:
        raw = b"\xcd" * 32
        a = Encryptor.from_shared_secret(raw)
        b = Encryptor.from_shared_secret(raw)
        ct = a.encrypt(b"payload")
        assert b.decrypt(ct) == b"payload"
