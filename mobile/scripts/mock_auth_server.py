#!/usr/bin/env python3
"""
Simple mock auth server for local integration testing.
Serves POST /api/v1/artifacts/sync and expects `Authorization: Bearer <token>` header.
Usage:
  ./mock_auth_server.py --port 8080 --token test-token

For Android emulator, point the app sync base URL to http://10.0.2.2:8080/
Set the auth token in the app UI to the same token.
"""

import http.server
import socketserver
import argparse
import json
from urllib.parse import urlparse

class SyncHandler(http.server.BaseHTTPRequestHandler):
    server_version = "PMBRSMock/0.1"

    def do_POST(self):
        parsed = urlparse(self.path)
        if parsed.path != '/api/v1/artifacts/sync':
            self.send_response(404)
            self.end_headers()
            return

        auth = self.headers.get('Authorization')
        expected = f"Bearer {self.server.expected_token}"
        if auth != expected:
            self.send_response(401)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            body = {'message': 'Unauthorized'}
            self.wfile.write(json.dumps(body).encode('utf-8'))
            return

        # Read and ignore body content; respond with a simple syncedIds list
        length = int(self.headers.get('Content-Length', '0'))
        if length:
            _ = self.rfile.read(length)

        response = {'syncedIds': ['artifact-1', 'artifact-2'], 'message': 'OK'}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        # Keep logs concise
        print("[MockServer] %s - %s" % (self.address_string(), format % args))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8080)
    parser.add_argument('--token', type=str, default='test-token')
    args = parser.parse_args()

    handler = SyncHandler
    with socketserver.TCPServer(("", args.port), handler) as httpd:
        httpd.expected_token = args.token
        print(f"Mock auth server listening on port {args.port}; expected token='{args.token}'")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down")
            httpd.server_close()

if __name__ == '__main__':
    main()
