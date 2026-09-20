"""Interface local e proxy restrito para a API HAILA existente."""
import argparse
import json
import os
import re
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/api/'):
            return self.proxy()
        return super().do_GET()

    def do_POST(self):
        return self.proxy()

    def proxy(self):
        path = self.path.removeprefix('/api')
        allowed = (self.command == 'GET' and re.fullmatch(r'/health|/requests/[\w-]+', path)) or (self.command == 'POST' and re.fullmatch(r'/requests|/requests/[\w-]+/generate', path))
        if not self.path.startswith('/api/') or not allowed:
            return self.send_error(404)
        size = int(self.headers.get('Content-Length', 0))
        if size > 65536:
            return self.send_error(413)
        body = self.rfile.read(size) if self.command == 'POST' else None
        try:
            request = Request(self.server.backend + path, data=body, method=self.command, headers={'Content-Type': 'application/json'})
            with urlopen(request, timeout=1800 if path.endswith('/generate') else 10) as response:
                self.reply(response.status, response.read())
        except HTTPError as exc:
            self.reply(exc.code, exc.read())
        except (URLError, TimeoutError, OSError):
            self.reply(503, json.dumps({'detail': 'Não foi possível acessar o motor HAILA. Verifique se a API está em execução.'}).encode())

    def end_headers(self):
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Referrer-Policy', 'no-referrer')
        self.send_header('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        super().end_headers()

    def reply(self, status, data):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=int(os.getenv('HAILA_FRONT_PORT', '4173')))
    parser.add_argument('--backend', default=os.getenv('HAILA_API_URL', 'http://127.0.0.1:8000'))
    args = parser.parse_args()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), partial(Handler, directory=str(Path(__file__).parent / 'public')))
    server.backend = args.backend.rstrip('/')
    print(f'HAILA Studio: http://127.0.0.1:{args.port}', flush=True)
    print(f'Motor HAILA: {server.backend}', flush=True)
    server.serve_forever()
