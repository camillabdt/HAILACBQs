"""Verificação local do proxy usando um motor HAILA simulado em memória."""
from __future__ import annotations

import json
import sys
import threading
from functools import partial
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.request import Request, urlopen

project_root = Path(__file__).parents[1]
sys.path.insert(0, str(project_root))
from server import Handler  # noqa: E402


QUESTION = {
    "exame": "ENADE",
    "enunciado": "Questão de integração",
    "alternativas": ["A", "B", "C", "D", "E"],
    "correta": 1,
    "explicacao": "Resposta de integração",
}


class FakeMotor(BaseHTTPRequestHandler):
    def log_message(self, *_):
        return

    def reply(self, status: int, payload: dict):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            return self.reply(200, {"status": "ok", "llm_configured": True, "slm_configured": True})
        if self.path == "/requests/test-request":
            return self.reply(200, {"request": {"id": "test-request"}, "events": [], "red_flags": []})
        return self.reply(404, {"detail": "não encontrado"})

    def do_POST(self):
        size = int(self.headers.get("Content-Length", 0))
        json.loads(self.rfile.read(size) or b"{}")
        if self.path == "/requests":
            return self.reply(201, {"id": "test-request", "state": "REQUESTED"})
        if self.path == "/requests/test-request/generate":
            return self.reply(200, {
                "request_id": "test-request",
                "state": "GENERATION_COMPLETED",
                "red_flags": [],
                "version": {"id": "v1", "version_number": 1, "question": QUESTION},
            })
        return self.reply(404, {"detail": "não encontrado"})


def call(url: str, method: str = "GET", payload: dict | None = None):
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=3) as response:
        return response.status, json.load(response)


def main():
    motor = ThreadingHTTPServer(("127.0.0.1", 0), FakeMotor)
    front = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(Handler, directory=str(project_root / "public")),
    )
    front.backend = f"http://127.0.0.1:{motor.server_port}"
    for server in (motor, front):
        threading.Thread(target=server.serve_forever, daemon=True).start()

    base = f"http://127.0.0.1:{front.server_port}/api"
    assert call(base + "/health")[1]["llm_configured"] is True
    assert call(base + "/requests", "POST", {"objetivo_pedagogico": "teste"})[1]["id"] == "test-request"
    result = call(base + "/requests/test-request/generate", "POST", {})[1]
    assert result["state"] == "GENERATION_COMPLETED"
    assert len(result["version"]["question"]["alternativas"]) == 5
    assert call(base + "/requests/test-request")[1]["request"]["id"] == "test-request"

    front.shutdown()
    motor.shutdown()
    print("Integração do proxy verificada")


if __name__ == "__main__":
    main()
