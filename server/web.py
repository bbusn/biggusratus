import json
import logging
import mimetypes
import os
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.core import Server

logger = logging.getLogger(__name__)
_server_instance: "Server" = None
_templates_dir = os.path.join(os.path.dirname(__file__), "web", "templates")
_static_dir = os.path.join(os.path.dirname(__file__), "web", "static")


def set_server(server: "Server") -> None:
    global _server_instance
    _server_instance = server


class WebHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        logger.debug("%s - %s", self.address_string(), format % args)

    def _send_json(self, data: dict, status: int = 200):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, filepath: str):
        mime_type, _ = mimetypes.guess_type(filepath)
        if mime_type is None:
            mime_type = "application/octet-stream"
        try:
            with open(filepath, "rb") as f:
                content = f.read()
            self.send_response(200)
            self.send_header("Content-Type", mime_type)
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)
        except FileNotFoundError:
            self.send_error(404)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._send_file(os.path.join(_templates_dir, "index.html"))
        elif self.path == "/api/agents":
            self._serve_agents()
        elif self.path.startswith("/static/"):
            filepath = os.path.join(_static_dir, self.path[8:])
            self._send_file(filepath)
        else:
            self.send_error(404)

    def _serve_agents(self):
        if _server_instance is None:
            self._send_json({"agents": []})
            return
        with _server_instance.lock:
            agents = []
            for session in _server_instance.sessions.values():
                agents.append({
                    "id": session.agent_id[:8],
                    "ip": session.address[0],
                    "port": session.address[1],
                    "os": session.os_type or "unknown",
                    "uptime": session.session_duration,
                    "idle": session.idle_time,
                })
        self._send_json({"agents": agents})


def start_web_server(host: str, port: int, server: "Server") -> HTTPServer:
    set_server(server)
    httpd = HTTPServer((host, port), WebHandler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.1), daemon=True)
    thread.start()
    logger.info(f"Web interface started on http://{host}:{port}")
    return httpd
