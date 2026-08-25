#!/usr/bin/env python3
"""Simple HTTP test server that accepts POST /api/v1/artifacts/sync
and returns a JSON payload acknowledging all artifact IDs received.

Usage: python3 scripts/test_sync_server.py [port]
"""
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/api/v1/artifacts/sync':
            self.send_response(404)
            self.end_headers()
            return
        length = int(self.headers.get('content-length', 0))
        body = self.rfile.read(length).decode('utf-8') if length else ''
        try:
            data = json.loads(body)
            artifacts = data.get('artifacts', [])
            synced = [a.get('artifactId') for a in artifacts if a.get('artifactId')]
        except Exception:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b'{}')
            return

        resp = {'syncedIds': synced, 'message': 'ok'}
        resp_bytes = json.dumps(resp).encode('utf-8')
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(resp_bytes)))
        self.end_headers()
        self.wfile.write(resp_bytes)

    def log_message(self, format, *args):
        # mirror to stdout for easier capture
        sys.stdout.write("TEST_SERVER: " + (format % args) + "\n")


def run(port=8788):
    server = HTTPServer(('0.0.0.0', port), Handler)
    print(f"Test sync server listening on 0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8788
    run(port)
