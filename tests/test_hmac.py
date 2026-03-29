# Tests for HMAC message authentication.

import copy

import pytest

from common.constants import TEST_ACTION
from common.crypto import Encryptor, derive_keys_from_shared_secret
from common.hmac import HmacError, MessageAuthenticator
from common.protocol import (
    build_command,
    build_success_response,
    decode_message,
    encode_message,
    sign_message,
    verify_message,
)


def _key32() -> bytes:
    return b"x" * 32


class TestMessageAuthenticatorInit:
    def test_rejects_empty_key(self) -> None:
        with pytest.raises(ValueError, match="at least 16"):
            MessageAuthenticator(b"")

    def test_rejects_short_key(self) -> None:
        with pytest.raises(ValueError, match="at least 16"):
            MessageAuthenticator(b"fifteenbytes!!!")


class TestSerializeAndSign:
    def test_nested_params_deterministic(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd1 = build_command(TEST_ACTION, {"a": 1, "nested": {"z": 1, "y": 2}})
        cmd2 = build_command(TEST_ACTION, {"nested": {"y": 2, "z": 1}, "a": 1})
        cmd2["id"] = cmd1["id"]
        cmd2["timestamp"] = cmd1["timestamp"]
        assert auth.sign(cmd1) == auth.sign(cmd2)

    def test_pipe_in_param_value_does_not_break_signing(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {"path": "a|b|c"})
        signed = auth.sign_message(copy.deepcopy(cmd))
        assert auth.verify_message(signed)

    def test_response_includes_status_and_payload(self) -> None:
        auth = MessageAuthenticator(_key32())
        resp = build_success_response("rid-1", TEST_ACTION, payload='{"ok":true}')
        signed = auth.sign_message(copy.deepcopy(resp))
        assert auth.verify_message(signed)


class TestVerifyRoundTrip:
    def test_sign_verify_command(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {"remote_path": "/tmp/x"})
        signed = sign_message(copy.deepcopy(cmd), auth)
        assert "hmac" in signed
        assert verify_message(signed, auth)

    def test_verify_message_restores_hmac_after_check(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(copy.deepcopy(cmd), auth)
        hmac_before = signed["hmac"]
        assert verify_message(signed, auth)
        assert signed["hmac"] == hmac_before

    def test_tampered_params_fails(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {"x": 1})
        signed = sign_message(copy.deepcopy(cmd), auth)
        signed["params"]["x"] = 2
        assert not verify_message(signed, auth)
        assert "hmac" in signed

    def test_tampered_hmac_fails(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(copy.deepcopy(cmd), auth)
        signed["hmac"] = "0" * 64
        assert not verify_message(signed, auth)

    def test_wrong_key_fails(self) -> None:
        auth_a = MessageAuthenticator(_key32())
        auth_b = MessageAuthenticator(b"y" * 32)
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(copy.deepcopy(cmd), auth_a)
        assert not verify_message(signed, auth_b)


class TestVerifyMessageErrors:
    def test_missing_hmac_raises(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {})
        with pytest.raises(HmacError, match="missing"):
            auth.verify_message(cmd)

    def test_protocol_verify_returns_false_when_missing_hmac(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {})
        assert not verify_message(cmd, auth)


class TestJsonWireRoundTrip:
    def test_encode_decode_preserves_verification(self) -> None:
        auth = MessageAuthenticator(_key32())
        cmd = build_command(TEST_ACTION, {"k": "v"})
        signed = sign_message(copy.deepcopy(cmd), auth)
        wire = encode_message(signed)
        restored = decode_message(wire)
        assert verify_message(restored, auth)


class TestDeriveKeysFromSharedSecret:
    def test_produces_distinct_keys(self) -> None:
        secret = b"shared-secret-bytes-here!!"
        enc, mac = derive_keys_from_shared_secret(secret)
        assert enc != mac
        assert len(mac) == 32

    def test_encryptor_from_shared_secret_matches_derive(self) -> None:
        secret = b"\x01" * 32
        enc_expected, mac_expected = derive_keys_from_shared_secret(secret)
        enc = Encryptor.from_shared_secret(secret)
        assert enc.key == enc_expected
        assert enc.hmac_key == mac_expected

    def test_different_secrets_different_mac_keys(self) -> None:
        _, mac1 = derive_keys_from_shared_secret(b"secret-one")
        _, mac2 = derive_keys_from_shared_secret(b"secret-two")
        assert mac1 != mac2
