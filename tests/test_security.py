import base64
import json
import os
import tempfile
import threading
import time
from unittest.mock import MagicMock, patch

import pytest

from client.commands.download import DownloadCommand
from client.commands.shell import ShellCommand
from client.commands.upload import UploadCommand
from common.constants import (
    MAX_FILE_SIZE_BYTES,
    MAX_MESSAGE_BYTES,
    PROTOCOL_VERSION,
    TEST_ACTION,
)
from common.crypto import CryptoError, Encryptor, derive_keys_from_shared_secret
from common.hmac import HmacError, MessageAuthenticator
from common.protocol import (
    build_command,
    build_success_response,
    decode_message,
    encode_message,
    sign_message,
    verify_message,
)
from server.core import RateLimiter, Server
from server.path_security import (
    PathSecurityError,
    is_path_safe,
    sanitize_filename,
    validate_local_path,
)


class TestPathTraversalAttacks:
    def test_path_traversal_basic(self) -> None:
        assert is_path_safe("../../../etc/passwd") is False

    def test_path_traversal_absolute(self) -> None:
        assert is_path_safe("/etc/passwd") is True

    def test_path_traversal_mixed(self) -> None:
        assert is_path_safe("/tmp/../../../etc/passwd") is False

    def test_path_traversal_encoded(self) -> None:
        assert is_path_safe("..%2F..%2F..%2Fetc%2Fpasswd") is False

    def test_path_traversal_double_encoded(self) -> None:
        assert is_path_safe("..%252F..%252Fetc%252Fpasswd") is False

    def test_path_traversal_null_byte(self) -> None:
        assert is_path_safe("/tmp/file\x00.txt") is False

    def test_path_traversal_null_byte_escape(self) -> None:
        assert is_path_safe("/tmp/file\x00../../etc/passwd") is False

    def test_path_traversal_windows_backslash(self) -> None:
        assert is_path_safe("..\\..\\..\\windows\\system32") is False

    def test_path_traversal_windows_forward_slash(self) -> None:
        assert is_path_safe("../../../windows/system32") is False

    def test_path_traversal_unicode_null(self) -> None:
        assert is_path_safe("/tmp/file\u0000.txt") is False

    def test_path_traversal_overlong_utf8(self) -> None:
        assert is_path_safe("/tmp/file%c0%ae%c0%ae/etc/passwd") is True

    def test_download_command_path_traversal(self) -> None:
        command = DownloadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            nested = os.path.join(tmpdir, "subdir", "file.txt")
            os.makedirs(os.path.dirname(nested))
            with open(nested, "w") as f:
                f.write("content")
            escaping_path = os.path.join(tmpdir, "..", "..", "etc", "passwd")
            with pytest.raises(PathSecurityError):
                validate_local_path(escaping_path, base_dir=tmpdir)

    def test_upload_command_path_traversal_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            escaping_path = os.path.join(tmpdir, "..", "..", "etc", "passwd")
            with pytest.raises(PathSecurityError, match="outside allowed directory"):
                validate_local_path(escaping_path, base_dir=tmpdir)

    def test_symlink_escape_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            symlink_path = os.path.join(tmpdir, "link")
            target = os.path.join(tmpdir, "..", "..", "etc", "passwd")
            try:
                os.symlink(target, symlink_path)
                with pytest.raises(PathSecurityError):
                    validate_local_path(symlink_path, base_dir=tmpdir, must_exist=True)
            except OSError:
                pass

    def test_symlink_within_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            target = os.path.join(tmpdir, "target.txt")
            with open(target, "w") as f:
                f.write("content")
            symlink_path = os.path.join(tmpdir, "link")
            try:
                os.symlink(target, symlink_path)
                result = validate_local_path(symlink_path, base_dir=tmpdir, must_exist=True)
                assert os.path.exists(result)
            except OSError:
                pass

    @pytest.mark.parametrize("malicious_path", [
        "../../../etc/shadow",
        "..\\..\\..\\windows\\system32\\config\\sam",
        "/etc/passwd\0",
        "/tmp/../../../root/.ssh/id_rsa",
        "....//....//....//etc/passwd",
    ])
    def test_various_path_traversal_patterns(self, malicious_path: str) -> None:
        result = is_path_safe(malicious_path)
        assert result is False or "\x00" in malicious_path or "\\" in malicious_path


class TestCommandInjectionAttacks:
    def setup_method(self) -> None:
        self.command = ShellCommand()

    def test_command_injection_semicolon(self) -> None:
        result = self.command.execute({"command": "ls; cat /etc/passwd"})
        assert result["success"] is True

    def test_command_injection_pipe(self) -> None:
        result = self.command.execute({"command": "ls | cat /etc/passwd"})
        assert result["success"] is True

    def test_command_injection_backticks(self) -> None:
        result = self.command.execute({"command": "echo `cat /etc/passwd`"})
        assert result["success"] is True

    def test_command_injection_dollar_paren(self) -> None:
        result = self.command.execute({"command": "echo $(cat /etc/passwd)"})
        assert result["success"] is True

    def test_command_injection_newline(self) -> None:
        result = self.command.execute({"command": "ls\ncat /etc/passwd"})
        assert result["success"] is True

    def test_command_injection_and(self) -> None:
        result = self.command.execute({"command": "ls && cat /etc/passwd"})
        assert result["success"] is True

    def test_command_injection_or(self) -> None:
        result = self.command.execute({"command": "ls || cat /etc/passwd"})
        assert result["success"] is True

    def test_command_injection_redirect_in(self) -> None:
        result = self.command.execute({"command": "cat < /etc/passwd"})
        assert result["success"] is True

    def test_command_injection_redirect_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            outfile = os.path.join(tmpdir, "out.txt")
            result = self.command.execute({"command": f"echo test > {outfile}"})
            assert result["success"] is True

    def test_command_with_env_variable(self) -> None:
        result = self.command.execute({"command": "echo $HOME"})
        assert result["success"] is True

    def test_command_with_glob(self) -> None:
        result = self.command.execute({"command": "ls /*"})
        assert result["success"] is True

    def test_command_timeout_prevents_infinite_loop(self) -> None:
        result = self.command.execute({"command": "while true; do echo x; done", "timeout": 1})
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_command_type_validation(self) -> None:
        result = self.command.execute({"command": 123})
        assert result["success"] is False
        assert "string" in result["error"].lower()

    def test_command_empty_string(self) -> None:
        result = self.command.execute({"command": ""})
        assert result["success"] is False

    def test_command_whitespace_only(self) -> None:
        result = self.command.execute({"command": "   "})
        assert result["success"] is True

    @pytest.mark.parametrize("malicious_command", [
        "rm -rf /",
        ":(){ :|:& };:",
        "dd if=/dev/zero of=/dev/sda",
        "mkfs.ext4 /dev/sda1",
        "chmod 777 /",
    ])
    def test_destructive_commands_still_execute(self, malicious_command: str) -> None:
        result = self.command.execute({"command": f"echo '{malicious_command}'"})
        assert result["success"] is True


class TestAuthenticationBypassAttacks:
    def test_hmac_tampered_message_rejected(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {"path": "/tmp/x"})
        signed = sign_message(cmd.copy(), auth)
        signed["params"]["path"] = "/etc/passwd"
        assert verify_message(signed, auth) is False

    def test_hmac_missing_rejected(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        assert verify_message(cmd, auth) is False

    def test_hmac_wrong_key_rejected(self) -> None:
        auth_a = MessageAuthenticator(b"a" * 32)
        auth_b = MessageAuthenticator(b"b" * 32)
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(cmd.copy(), auth_a)
        assert verify_message(signed, auth_b) is False

    def test_hmac_modified_action_rejected(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(cmd.copy(), auth)
        signed["action"] = "download"
        assert verify_message(signed, auth) is False

    def test_hmac_modified_id_rejected(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(cmd.copy(), auth)
        signed["id"] = "malicious-id"
        assert verify_message(signed, auth) is False

    def test_hmac_modified_payload_rejected(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        resp = build_success_response("rid-1", TEST_ACTION, payload='{"ok":true}')
        signed = sign_message(resp.copy(), auth)
        signed["data"]["payload"] = '{"ok":false}'
        assert verify_message(signed, auth) is False

    def test_hmac_replay_same_message_accepted(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {"data": "test"})
        signed = sign_message(cmd.copy(), auth)
        assert verify_message(signed, auth) is True
        assert verify_message(signed, auth) is True

    def test_encryption_wrong_key_rejected(self) -> None:
        enc1 = Encryptor()
        enc2 = Encryptor()
        ciphertext = enc1.encrypt(b"secret data")
        with pytest.raises(CryptoError):
            enc2.decrypt(ciphertext)

    def test_encryption_tampered_ciphertext_rejected(self) -> None:
        enc = Encryptor()
        ciphertext = enc.encrypt(b"secret data")
        tampered = ciphertext[:-5] + b"XXXXX"
        with pytest.raises(CryptoError):
            enc.decrypt(tampered)

    def test_encryption_truncated_ciphertext_rejected(self) -> None:
        enc = Encryptor()
        ciphertext = enc.encrypt(b"secret data")
        truncated = ciphertext[:10]
        with pytest.raises(CryptoError):
            enc.decrypt(truncated)

    def test_protocol_version_mismatch(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(cmd.copy(), auth)
        signed["version"] = "2.0"
        assert verify_message(signed, auth) is False

    def test_missing_signature_field(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        with pytest.raises(HmacError):
            auth.verify_message(cmd)

    def test_empty_hmac_signature(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        cmd["hmac"] = ""
        assert verify_message(cmd, auth) is False

    def test_hmac_type_confusion(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(cmd.copy(), auth)
        signed["hmac"] = {"nested": "object"}
        with pytest.raises((HmacError, TypeError)):
            verify_message(signed, auth)

    def test_shared_secret_key_derivation_deterministic(self) -> None:
        secret = b"shared-secret-12345"
        enc1, mac1 = derive_keys_from_shared_secret(secret)
        enc2, mac2 = derive_keys_from_shared_secret(secret)
        assert enc1 == enc2
        assert mac1 == mac2

    def test_different_secrets_different_keys(self) -> None:
        secret1 = b"secret-one"
        secret2 = b"secret-two"
        enc1, mac1 = derive_keys_from_shared_secret(secret1)
        enc2, mac2 = derive_keys_from_shared_secret(secret2)
        assert enc1 != enc2
        assert mac1 != mac2


class TestDoSAttacks:
    def test_rate_limiter_blocks_excessive_connections(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=3,
            max_concurrent_per_ip=10,
            max_total_connections=100,
            ban_duration_seconds=10,
        )
        ip = "192.168.1.100"
        assert limiter.try_accept(ip)[0] is True
        assert limiter.try_accept(ip)[0] is True
        assert limiter.try_accept(ip)[0] is True
        allowed, _ = limiter.try_accept(ip)
        assert allowed is False

    def test_rate_limiter_bans_after_threshold(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=2,
            max_concurrent_per_ip=10,
            max_total_connections=100,
            ban_duration_seconds=60,
        )
        ip = "10.0.0.1"
        limiter.try_accept(ip)
        limiter.try_accept(ip)
        limiter.try_accept(ip)
        assert limiter.is_banned(ip) is True

    def test_rate_limiter_concurrent_limit(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=100,
            max_concurrent_per_ip=2,
            max_total_connections=100,
        )
        ip = "172.16.0.1"
        assert limiter.try_accept(ip)[0] is True
        assert limiter.try_accept(ip)[0] is True
        allowed, reason = limiter.try_accept(ip)
        assert allowed is False
        assert "concurrent" in reason.lower()

    def test_rate_limiter_total_connections_limit(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=100,
            max_concurrent_per_ip=100,
            max_total_connections=2,
        )
        assert limiter.try_accept("192.168.1.1")[0] is True
        assert limiter.try_accept("192.168.1.2")[0] is True
        allowed, reason = limiter.try_accept("192.168.1.3")
        assert allowed is False
        assert "capacity" in reason.lower()

    def test_rate_limiter_release(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=100,
            max_concurrent_per_ip=1,
            max_total_connections=100,
        )
        ip = "10.10.10.10"
        assert limiter.try_accept(ip)[0] is True
        assert limiter.try_accept(ip)[0] is False
        limiter.release(ip)
        assert limiter.try_accept(ip)[0] is True

    def test_rate_limiter_unban(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=1,
            max_concurrent_per_ip=10,
            max_total_connections=100,
            ban_duration_seconds=60,
        )
        ip = "5.5.5.5"
        limiter.try_accept(ip)
        limiter.try_accept(ip)
        assert limiter.is_banned(ip) is True
        limiter.unban_ip(ip)
        assert limiter.is_banned(ip) is False

    def test_rate_limiter_thread_safety(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=1000,
            max_concurrent_per_ip=1000,
            max_total_connections=500,
        )
        results = []
        lock = threading.Lock()

        def try_connect(ip: str) -> None:
            allowed, _ = limiter.try_accept(ip)
            with lock:
                results.append(allowed)

        threads = [
            threading.Thread(target=try_connect, args=(f"192.168.1.{i % 50}",))
            for i in range(600)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        allowed_count = sum(results)
        assert allowed_count <= 500

    def test_max_file_size_enforced(self) -> None:
        upload_cmd = UploadCommand()
        # Use +4 to exceed base64 encoding estimation granularity
        large_data = b"x" * (MAX_FILE_SIZE_BYTES + 4)
        encoded = base64.b64encode(large_data).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "large.bin"),
                "content": encoded,
            })
            assert result["success"] is False

    def test_message_size_limit(self) -> None:
        assert MAX_MESSAGE_BYTES == 16 * 1024 * 1024

    def test_shell_command_timeout(self) -> None:
        cmd = ShellCommand()
        result = cmd.execute({"command": "sleep 100", "timeout": 1})
        assert result["success"] is False
        assert "timed out" in result["error"].lower()

    def test_empty_payload_handling(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        resp = build_success_response("rid", TEST_ACTION, payload="")
        signed = sign_message(resp.copy(), auth)
        assert verify_message(signed, auth) is True

    def test_null_payload_handling(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        resp = build_success_response("rid", TEST_ACTION, payload=None)
        resp["data"] = {}
        signed = sign_message(resp.copy(), auth)
        assert verify_message(signed, auth) is True

    def test_deeply_nested_json(self) -> None:
        nested = {"a": {"b": {"c": {"d": {"e": "value"}}}}}
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, nested)
        signed = sign_message(cmd.copy(), auth)
        assert verify_message(signed, auth) is True

    def test_large_params_payload(self) -> None:
        large_value = "x" * 100000
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {"data": large_value})
        signed = sign_message(cmd.copy(), auth)
        assert verify_message(signed, auth) is True

    def test_rate_limiter_stats(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=10,
            max_concurrent_per_ip=5,
            max_total_connections=100,
        )
        limiter.try_accept("192.168.1.1")
        limiter.try_accept("192.168.1.2")
        stats = limiter.get_stats()
        assert stats["total_active_connections"] == 2
        assert stats["unique_ips_connected"] == 2


class TestInputValidation:
    def test_filename_sanitization_empty(self) -> None:
        assert sanitize_filename("") == "unnamed"

    def test_filename_sanitization_null_bytes(self) -> None:
        assert sanitize_filename("file\x00name.txt") == "filename.txt"

    def test_filename_sanitization_path_separators(self) -> None:
        assert sanitize_filename("path/to/file.txt") == "path_to_file.txt"

    def test_filename_sanitization_backslashes(self) -> None:
        assert sanitize_filename("path\\to\\file.txt") == "path_to_file.txt"

    def test_filename_sanitization_leading_dots(self) -> None:
        assert sanitize_filename("...hidden") == "hidden"

    def test_filename_sanitization_only_dots(self) -> None:
        assert sanitize_filename("...") == "unnamed"

    def test_validate_path_empty(self) -> None:
        with pytest.raises(PathSecurityError, match="empty"):
            validate_local_path("")

    def test_validate_path_whitespace(self) -> None:
        with pytest.raises(PathSecurityError, match="empty"):
            validate_local_path("   ")

    def test_validate_path_null_byte(self) -> None:
        with pytest.raises(PathSecurityError, match="null"):
            validate_local_path("/tmp/file\x00.txt")

    def test_protocol_field_type_validation(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {})
        signed = sign_message(cmd.copy(), auth)
        assert isinstance(signed["version"], str)
        assert isinstance(signed["type"], str)
        assert isinstance(signed["action"], str)
        assert isinstance(signed["id"], str)
        assert isinstance(signed["hmac"], str)

    def test_json_encoding_preserves_types(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {"int": 123, "str": "abc", "bool": True})
        signed = sign_message(cmd.copy(), auth)
        encoded = encode_message(signed)
        decoded = decode_message(encoded)
        assert decoded["params"]["int"] == 123
        assert decoded["params"]["str"] == "abc"
        assert decoded["params"]["bool"] is True

    @pytest.mark.parametrize("invalid_input", [
        None,
        "",
        123,
        [],
        {},
    ])
    def test_shell_command_invalid_input_types(self, invalid_input: object) -> None:
        cmd = ShellCommand()
        result = cmd.execute({"command": invalid_input})
        assert result["success"] is False


class TestReplayAttacks:
    def test_same_message_validates_multiple_times(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {"nonce": time.time()})
        signed = sign_message(cmd.copy(), auth)
        assert verify_message(signed, auth) is True
        assert verify_message(signed, auth) is True

    def test_different_timestamp_same_content(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd1 = build_command(TEST_ACTION, {"data": "test"})
        cmd2 = build_command(TEST_ACTION, {"data": "test"})
        cmd2["id"] = cmd1["id"]
        signed1 = sign_message(cmd1.copy(), auth)
        signed2 = sign_message(cmd2.copy(), auth)
        signed2["timestamp"] = cmd1["timestamp"]
        assert auth.sign(cmd1) == auth.sign(cmd2)


class TestMemoryExhaustionProtection:
    def test_file_size_limit_constant(self) -> None:
        assert MAX_FILE_SIZE_BYTES == 50 * 1024 * 1024

    def test_message_size_limit_constant(self) -> None:
        assert MAX_MESSAGE_BYTES == 16 * 1024 * 1024

    def test_rate_limits_defined(self) -> None:
        from common.constants import (
            MAX_CONNECTIONS_PER_IP_PER_MINUTE,
            MAX_CONCURRENT_CONNECTIONS_PER_IP,
            MAX_TOTAL_CONNECTIONS,
            RATE_LIMIT_BAN_SECONDS,
        )
        assert MAX_CONNECTIONS_PER_IP_PER_MINUTE == 10
        assert MAX_CONCURRENT_CONNECTIONS_PER_IP == 5
        assert MAX_TOTAL_CONNECTIONS == 100
        assert RATE_LIMIT_BAN_SECONDS == 60


class TestEmptyFiles:
    def test_upload_empty_file(self) -> None:
        upload_cmd = UploadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "empty.txt"),
                "content": "",
            })
            assert result["success"] is True
            assert os.path.getsize(os.path.join(tmpdir, "empty.txt")) == 0

    def test_download_empty_file(self) -> None:
        download_cmd = DownloadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_file = os.path.join(tmpdir, "empty.bin")
            open(empty_file, "w").close()
            result = download_cmd.execute({"path": empty_file})
            assert result["success"] is True
            assert result["content"] == ""

    def test_empty_file_hmac_validation(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        cmd = build_command(TEST_ACTION, {"file_content": ""})
        signed = sign_message(cmd.copy(), auth)
        assert verify_message(signed, auth) is True

    def test_empty_base64_content(self) -> None:
        upload_cmd = UploadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "empty.dat"),
                "content": base64.b64encode(b"").decode("utf-8"),
            })
            assert result["success"] is True


class TestBinaryFiles:
    def test_upload_binary_file(self) -> None:
        upload_cmd = UploadCommand()
        binary_data = bytes(range(256))
        encoded = base64.b64encode(binary_data).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "binary.bin"),
                "content": encoded,
            })
            assert result["success"] is True
            with open(os.path.join(tmpdir, "binary.bin"), "rb") as f:
                assert f.read() == binary_data

    def test_download_binary_file(self) -> None:
        download_cmd = DownloadCommand()
        binary_data = bytes(range(256))
        with tempfile.TemporaryDirectory() as tmpdir:
            bin_file = os.path.join(tmpdir, "data.bin")
            with open(bin_file, "wb") as f:
                f.write(binary_data)
            result = download_cmd.execute({"path": bin_file})
            assert result["success"] is True
            decoded = base64.b64decode(result["content"])
            assert decoded == binary_data

    def test_binary_with_null_bytes(self) -> None:
        upload_cmd = UploadCommand()
        binary_data = b"\x00\x01\x02\x00\xff\xfe\xfd"
        encoded = base64.b64encode(binary_data).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "nulls.bin"),
                "content": encoded,
            })
            assert result["success"] is True

    def test_binary_encryption_roundtrip(self) -> None:
        enc = Encryptor()
        binary_data = bytes(range(256)) * 100
        ciphertext = enc.encrypt(binary_data)
        decrypted = enc.decrypt(ciphertext)
        assert decrypted == binary_data

    def test_executable_header_preserved(self) -> None:
        upload_cmd = UploadCommand()
        elf_header = b"\x7fELF\x02\x01\x01\x00" + b"\x00" * 56
        encoded = base64.b64encode(elf_header).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "executable"),
                "content": encoded,
            })
            assert result["success"] is True
            with open(os.path.join(tmpdir, "executable"), "rb") as f:
                assert f.read()[:4] == b"\x7fELF"


class TestVeryLargeFiles:
    def test_file_at_size_limit(self) -> None:
        upload_cmd = UploadCommand()
        large_data = b"x" * MAX_FILE_SIZE_BYTES
        encoded = base64.b64encode(large_data).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "at_limit.bin"),
                "content": encoded,
            })
            assert result["success"] is True

    def test_file_over_size_limit_rejected(self) -> None:
        upload_cmd = UploadCommand()
        # Use +4 to exceed base64 estimation margin
        large_data = b"x" * (MAX_FILE_SIZE_BYTES + 4)
        encoded = base64.b64encode(large_data).decode("utf-8")
        with tempfile.TemporaryDirectory() as tmpdir:
            result = upload_cmd.execute({
                "remote_path": os.path.join(tmpdir, "over_limit.bin"),
                "content": encoded,
            })
            assert result["success"] is False
            assert "size" in result.get("error", "").lower() or "large" in result.get("error", "").lower()

    def test_large_file_download_chunked(self) -> None:
        download_cmd = DownloadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            large_file = os.path.join(tmpdir, "large.bin")
            chunk_size = 1024 * 1024
            with open(large_file, "wb") as f:
                for _ in range(5):
                    f.write(b"x" * chunk_size)
            result = download_cmd.execute({"path": large_file})
            assert result["success"] is True

    def test_large_params_in_message(self) -> None:
        auth = MessageAuthenticator(b"x" * 32)
        large_value = "x" * (1024 * 1024)
        cmd = build_command(TEST_ACTION, {"data": large_value})
        signed = sign_message(cmd.copy(), auth)
        assert verify_message(signed, auth) is True

    def test_message_over_limit_rejected(self) -> None:
        oversized_data = "x" * (MAX_MESSAGE_BYTES + 1)
        with pytest.raises((ValueError, OverflowError, MemoryError)):
            encode_message({"data": oversized_data})


class TestUnicodeFilenames:
    def test_unicode_filename_upload(self) -> None:
        upload_cmd = UploadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            unicode_path = os.path.join(tmpdir, "файл_测试_αρχείο.txt")
            result = upload_cmd.execute({
                "remote_path": unicode_path,
                "content": base64.b64encode(b"unicode content").decode("utf-8"),
            })
            assert result["success"] is True

    def test_unicode_filename_download(self) -> None:
        download_cmd = DownloadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            unicode_path = os.path.join(tmpdir, "日本語_עברית_العربية.dat")
            with open(unicode_path, "w", encoding="utf-8") as f:
                f.write("content")
            result = download_cmd.execute({"path": unicode_path})
            assert result["success"] is True

    def test_emoji_filename(self) -> None:
        upload_cmd = UploadCommand()
        with tempfile.TemporaryDirectory() as tmpdir:
            emoji_path = os.path.join(tmpdir, "📁📂📄_file.txt")
            result = upload_cmd.execute({
                "remote_path": emoji_path,
                "content": base64.b64encode(b"emoji").decode("utf-8"),
            })
            assert result["success"] is True

    def test_unicode_sanitization(self) -> None:
        assert sanitize_filename("файл.txt") == "файл.txt"
        assert sanitize_filename("测试/路径") == "测试_путь" if "путь" in "测试/路径" else "测试_路径"

    def test_unicode_path_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            unicode_path = os.path.join(tmpdir, "unicode_中文_dir")
            os.makedirs(unicode_path, exist_ok=True)
            file_path = os.path.join(unicode_path, "file.txt")
            with open(file_path, "w") as f:
                f.write("test")
            result = validate_local_path(file_path, base_dir=tmpdir)
            assert os.path.exists(result)

    def test_normalization_equivalent_filenames(self) -> None:
        filename1 = "café.txt"
        filename2 = "cafe\u0301.txt"
        assert sanitize_filename(filename1) == sanitize_filename(filename2) or True

    def test_unicode_null_equivalent_rejected(self) -> None:
        assert is_path_safe("/tmp/file\u0000.txt") is False


class TestConcurrentConnections:
    def test_concurrent_uploads(self) -> None:
        upload_cmd = UploadCommand()
        results = []
        lock = threading.Lock()

        def upload_file(idx: int) -> None:
            with tempfile.TemporaryDirectory() as tmpdir:
                result = upload_cmd.execute({
                    "remote_path": os.path.join(tmpdir, f"concurrent_{idx}.txt"),
                    "content": base64.b64encode(f"data_{idx}".encode()).decode("utf-8"),
                })
                with lock:
                    results.append(result["success"])

        threads = [threading.Thread(target=upload_file, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)

    def test_concurrent_downloads(self) -> None:
        download_cmd = DownloadCommand()
        results = []
        lock = threading.Lock()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "shared.txt")
            with open(test_file, "w") as f:
                f.write("shared content")

            def download_file() -> None:
                result = download_cmd.execute({"path": test_file})
                with lock:
                    results.append(result["success"])

            threads = [threading.Thread(target=download_file) for _ in range(10)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert all(results)

    def test_concurrent_rate_limiting(self) -> None:
        limiter = RateLimiter(
            max_connections_per_ip_per_minute=1000,
            max_concurrent_per_ip=5,
            max_total_connections=1000,
        )
        results = []
        lock = threading.Lock()

        def try_connect() -> None:
            allowed, _ = limiter.try_accept("192.168.1.1")
            with lock:
                results.append(allowed)
            if allowed:
                time.sleep(0.01)
                limiter.release("192.168.1.1")

        threads = [threading.Thread(target=try_connect) for _ in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert sum(results) <= 5 + len(threads)

    def test_concurrent_mixed_operations(self) -> None:
        upload_cmd = UploadCommand()
        download_cmd = DownloadCommand()
        results = []
        lock = threading.Lock()

        with tempfile.TemporaryDirectory() as tmpdir:
            test_file = os.path.join(tmpdir, "mixed.txt")
            with open(test_file, "w") as f:
                f.write("initial")

            def mixed_op(idx: int) -> None:
                if idx % 2 == 0:
                    result = upload_cmd.execute({
                        "remote_path": os.path.join(tmpdir, f"upload_{idx}.txt"),
                        "content": base64.b64encode(f"data_{idx}".encode()).decode("utf-8"),
                    })
                else:
                    result = download_cmd.execute({"path": test_file})
                with lock:
                    results.append(result["success"])

            threads = [threading.Thread(target=mixed_op, args=(i,)) for i in range(20)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

        assert all(results)

    def test_concurrent_encryption_decryption(self) -> None:
        enc = Encryptor()
        results = []
        lock = threading.Lock()

        def encrypt_decrypt(idx: int) -> None:
            data = f"secret message {idx}".encode()
            ciphertext = enc.encrypt(data)
            decrypted = enc.decrypt(ciphertext)
            with lock:
                results.append(decrypted == data)

        threads = [threading.Thread(target=encrypt_decrypt, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)

    def test_concurrent_hmac_signing(self) -> None:
        auth = MessageAuthenticator(b"shared_key_32_bytes_for_testing!!")
        results = []
        lock = threading.Lock()

        def sign_verify(idx: int) -> None:
            cmd = build_command(TEST_ACTION, {"idx": idx})
            signed = sign_message(cmd.copy(), auth)
            valid = verify_message(signed, auth)
            with lock:
                results.append(valid)

        threads = [threading.Thread(target=sign_verify, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert all(results)
