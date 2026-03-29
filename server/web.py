import json
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from server.core import Server

logger = logging.getLogger(__name__)
_server_instance: "Server" = None


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

    def _send_html(self, html: str, status: int = 200):
        body = html.encode()
        self.send_response(status)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "/index.html":
            self._serve_index()
        elif self.path == "/api/agents":
            self._serve_agents()
        else:
            self.send_error(404)

    def _serve_index(self):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>BiggusRatus - Agents</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0f172a; color: #e2e8f0; min-height: 100vh; }
        .container { max-width: 1200px; margin: 0 auto; padding: 2rem; }
        h1 { font-size: 1.5rem; font-weight: 600; margin-bottom: 1.5rem; color: #f8fafc; }
        table { width: 100%; border-collapse: collapse; background: #1e293b; border-radius: 8px; overflow: hidden; }
        th, td { padding: 0.875rem 1rem; text-align: left; border-bottom: 1px solid #334155; }
        th { background: #334155; font-weight: 600; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.05em; color: #94a3b8; }
        tr:hover { background: #273449; }
        .mono { font-family: 'SF Mono', Monaco, 'Courier New', monospace; font-size: 0.875rem; }
        .badge { display: inline-block; padding: 0.25rem 0.5rem; border-radius: 4px; font-size: 0.75rem; font-weight: 500; }
        .badge-linux { background: #1d4ed8; color: #fff; }
        .badge-windows { background: #7c3aed; color: #fff; }
        .badge-darwin { background: #059669; color: #fff; }
        .badge-unknown { background: #475569; color: #fff; }
        .status { display: flex; align-items: center; gap: 0.5rem; }
        .status-dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; animation: pulse 2s infinite; }
        @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
        .empty { text-align: center; padding: 3rem; color: #64748b; }
        .refresh-btn { background: #3b82f6; color: #fff; border: none; padding: 0.5rem 1rem; border-radius: 6px; cursor: pointer; font-size: 0.875rem; margin-bottom: 1rem; }
        .refresh-btn:hover { background: #2563eb; }
    </style>
</head>
<body>
    <div class="container">
        <h1>Connected Agents</h1>
        <button class="refresh-btn" onclick="loadAgents()">Refresh</button>
        <table>
            <thead>
                <tr>
                    <th>Status</th>
                    <th>Agent ID</th>
                    <th>IP Address</th>
                    <th>OS</th>
                    <th>Connected</th>
                    <th>Last Seen</th>
                </tr>
            </thead>
            <tbody id="agents-body"></tbody>
        </table>
    </div>
    <script>
        function formatDuration(seconds) {
            if (seconds < 60) return Math.floor(seconds) + 's';
            if (seconds < 3600) return Math.floor(seconds / 60) + 'm ' + Math.floor(seconds % 60) + 's';
            return Math.floor(seconds / 3600) + 'h ' + Math.floor((seconds % 3600) / 60) + 'm';
        }
        function loadAgents() {
            fetch('/api/agents')
                .then(r => r.json())
                .then(data => {
                    const tbody = document.getElementById('agents-body');
                    if (data.agents.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="6" class="empty">No agents connected</td></tr>';
                        return;
                    }
                    tbody.innerHTML = data.agents.map(a => `
                        <tr>
                            <td><div class="status"><span class="status-dot"></span>Online</div></td>
                            <td class="mono">${a.id}</td>
                            <td class="mono">${a.ip}</td>
                            <td><span class="badge badge-${a.os}">${a.os}</span></td>
                            <td>${formatDuration(a.uptime)}</td>
                            <td>${formatDuration(a.idle)} ago</td>
                        </tr>
                    `).join('');
                });
        }
        loadAgents();
        setInterval(loadAgents, 5000);
    </script>
</body>
</html>"""
        self._send_html(html)

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
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    logger.info(f"Web interface started on http://{host}:{port}")
    return httpd
