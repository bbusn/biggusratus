import threading
import time

from client.client import Client
from server.server import Server


def test_client_server_handshake() -> None:
    server = Server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.start, daemon=True)
    thread.start()

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

    thread.join(timeout=2.0)
    assert not thread.is_alive()
