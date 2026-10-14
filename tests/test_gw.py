"""scripts/gw.py against a stub gateway (stdlib HTTP server, synthetic data)."""

from __future__ import annotations

import importlib.util
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "gw.py"


class Stub(BaseHTTPRequestHandler):
    def log_message(self, *a):  # quiet
        pass

    def _send(self, code: int, obj: dict) -> None:
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/readyz":
            return self._send(200, {"status": "ready"})
        ok = self.headers.get("Authorization") == "Bearer tok-viewer"
        return self._send(200 if ok else 401, {"path": self.path})

    def do_POST(self):
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        if self.path == "/api/auth/login" and data["password"] == data["username"]:
            return self._send(200, {"accessToken": f"tok-{data['username']}"})
        return self._send(400, {"seen": data})


@pytest.fixture
def gw(monkeypatch):
    srv = HTTPServer(("127.0.0.1", 0), Stub)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    spec = importlib.util.spec_from_file_location("gw_script", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    monkeypatch.setattr(mod, "BASE", f"http://127.0.0.1:{srv.server_port}")
    yield mod
    srv.shutdown()


def test_wait_token_and_call(gw, capsys):
    assert gw.main(["wait", "--timeout", "5"]) == 0
    assert gw.main(["token", "--as", "operator"]) == 0
    assert capsys.readouterr().out.strip().endswith("tok-operator")
    assert gw.main(["call", "GET", "/api/incidents", "--as", "viewer"]) == 0
    assert gw.main(["call", "GET", "/api/incidents", "--as", "operator"]) == 1
