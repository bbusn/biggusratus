import threading
import time

from client.client import Client
from server.server import Server


def test_client_server_handshake() -> None:
    server = Server(host="127.0.0.1", port=0)
    server.start()

    deadline = time.monotonic() + 5.0
    while server.socket is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.socket is not None, "server failed to bind"
    port = server.socket.getsockname()[1]

    client = Client(host="127.0.0.1", port=port)
    try:
        client.connect()
        client.handshake()
    finally:
        client.disconnect()
        server.stop()


def test_test_command_roundtrip_server_to_client() -> None:
    server = Server(host="127.0.0.1", port=0)
    server.start()
    deadline = time.monotonic() + 5.0
    while server.socket is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.socket is not None
    port = server.socket.getsockname()[1]

    client = Client(host="127.0.0.1", port=port)
    recv_ready = threading.Event()

    def recv_only() -> None:
        client.connect()
        client.handshake()
        recv_ready.set()
        client._receive_loop()

    thread = threading.Thread(target=recv_only, daemon=True)
    thread.start()
    assert recv_ready.wait(timeout=5.0), "client failed to connect"

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        with server.lock:
            agent_ids = list(server.agents.keys())
        if len(agent_ids) == 1:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("agent did not register in time")

    with server.lock:
        agent_ids = list(server.agents.keys())
    server.send_test_to_agent(agent_ids[0])
    client.disconnect()
    server.stop()
    thread.join(timeout=2.0)


def test_test_command_roundtrip_client_to_server() -> None:
    server = Server(host="127.0.0.1", port=0)
    server.start()
    deadline = time.monotonic() + 5.0
    while server.socket is None and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.socket is not None
    port = server.socket.getsockname()[1]

    client = Client(host="127.0.0.1", port=port)
    recv_ready = threading.Event()

    def recv_only() -> None:
        client.connect()
        client.handshake()
        recv_ready.set()
        client._receive_loop()

    thread = threading.Thread(target=recv_only, daemon=True)
    thread.start()
    assert recv_ready.wait(timeout=5.0), "client failed to connect"

    deadline = time.monotonic() + 5.0
    while time.monotonic() < deadline:
        with server.lock:
            agent_ids = list(server.agents.keys())
        if len(agent_ids) == 1:
            break
        time.sleep(0.01)
    else:
        raise AssertionError("agent did not register in time")

    client._send_test_command()
    client.disconnect()
    server.stop()
    thread.join(timeout=2.0)
