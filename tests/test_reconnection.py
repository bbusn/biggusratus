import socket
import threading
import time

import pytest

from client.client import Client
from common.constants import (
    CONNECT_TIMEOUT_SEC,
    MAX_RETRIES,
    RETRY_BACKOFF_FACTOR,
    RETRY_DELAY,
    RETRY_DELAY_MAX,
)
from server.server import AgentSession, Server


class TestClientReconnection:
    # Test cases for client reconnection logic.

    @pytest.fixture
    def client(self) -> Client:
        return Client()

    def test_initial_retry_count(self, client: Client) -> None:
        # Test that initial retry count is zero.
        assert client._retry_count == 0

    def test_reset_retry_count(self, client: Client) -> None:
        # Test that retry count can be reset.
        client._retry_count = 5
        client._reset_retry_count()
        assert client._retry_count == 0

    def test_increment_retry(self, client: Client) -> None:
        # Test retry count increment.
        assert client._increment_retry() == 1
        assert client._retry_count == 1
        assert client._increment_retry() == 2
        assert client._retry_count == 2

    def test_calculate_backoff_first_attempt(self, client: Client) -> None:
        # Test backoff calculation for first attempt.
        backoff = client._calculate_backoff(0)
        assert RETRY_DELAY <= backoff <= RETRY_DELAY * 1.1

    def test_calculate_backoff_increases(self, client: Client) -> None:
        # Test that backoff increases with attempts.
        backoff_0 = client._calculate_backoff(0)
        backoff_1 = client._calculate_backoff(1)
        backoff_2 = client._calculate_backoff(2)
        assert backoff_1 > backoff_0
        assert backoff_2 > backoff_1

    def test_calculate_backoff_max(self, client: Client) -> None:
        # Test that backoff doesn't exceed max.
        backoff = client._calculate_backoff(100)
        assert backoff <= RETRY_DELAY_MAX * 1.1

    def test_shutdown_flag(self, client: Client) -> None:
        # Test that shutdown flag prevents reconnection.
        assert client._shutdown is False
        client.shutdown()
        assert client._shutdown is True

    def test_connect_raises_on_refused(self, client: Client) -> None:
        # Test that connect raises ConnectionRefusedError when server not running.
        with pytest.raises((ConnectionRefusedError, OSError)):
            client.connect()


class TestAgentSession:
    # Test cases for AgentSession.

    def test_session_creation(self) -> None:
        # Test session is created with correct attributes.
        session = AgentSession("test-id", ("127.0.0.1", 12345))
        assert session.agent_id == "test-id"
        assert session.address == ("127.0.0.1", 12345)
        assert session.socket is None
        assert session.reconnect_count == 0

    def test_update_last_seen(self) -> None:
        # Test that update_last_seen updates the timestamp.
        session = AgentSession("test-id", ("127.0.0.1", 12345))
        initial_last_seen = session.last_seen
        time.sleep(0.1)
        session.update_last_seen()
        assert session.last_seen > initial_last_seen

    def test_session_duration(self) -> None:
        # Test session duration calculation.
        session = AgentSession("test-id", ("127.0.0.1", 12345))
        time.sleep(0.1)
        assert session.session_duration >= 0.1

    def test_idle_time(self) -> None:
        # Test idle time calculation.
        session = AgentSession("test-id", ("127.0.0.1", 12345))
        time.sleep(0.1)
        assert session.idle_time >= 0.1


class TestServerSessions:
    # Test cases for server session management.

    @pytest.fixture
    def server(self) -> Server:
        return Server(port=0)

    def test_server_starts_with_empty_sessions(self, server: Server) -> None:
        # Test that server starts with no sessions.
        assert server.sessions == {}
        server.start()
        assert server.sessions == {}
        server.stop()

    def test_server_stop_clears_sessions(self, server: Server) -> None:
        # Test that stop clears all sessions.
        server.start()
        server.sessions["test"] = AgentSession("test", ("127.0.0.1", 12345))
        server.stop()
        assert server.sessions == {}


class TestIntegration:
    # Integration tests for reconnection.

    def test_client_server_connection_with_timeout(self) -> None:
        # Test that client connects to server with timeout handling.
        server = Server(port=0)
        server.start()
        port = server.socket.getsockname()[1] if server.socket else 0

        client = Client(port=port)

        try:
            client.connect()
            assert client.connected is True
            assert client._retry_count == 0
        finally:
            client.disconnect()
            server.stop()

    def test_client_retry_after_disconnect(self) -> None:
        # Test that client can retry after disconnect.
        server = Server(port=0)
        server.start()
        port = server.socket.getsockname()[1] if server.socket else 0

        client = Client(port=port)

        try:
            client.connect()
            assert client.connected is True
            client.disconnect()
            assert client.connected is False
            client.connect()
            assert client.connected is True
        finally:
            client.disconnect()
            server.stop()

    def test_client_backoff_after_failure(self) -> None:
        # Test that client backoff increases after connection failures.
        client = Client()
        initial_backoff = client._calculate_backoff(0)

        for i in range(3):
            client._increment_retry()

        later_backoff = client._calculate_backoff(3)
        assert later_backoff > initial_backoff
