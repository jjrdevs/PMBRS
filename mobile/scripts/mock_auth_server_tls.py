#!/usr/bin/env python3
"""
TLS-enabled mock auth server for local integration testing.
Serves POST /api/v1/artifacts/sync and expects `Authorization: Bearer <token>` header.
Usage:
  ./mock_auth_server_tls.py --port 8443 --token test-token --cert cert.pem --key key.pem

If `--cert`/`--key` are omitted, a self-signed cert will be generated in a temp dir (requires `openssl`).
"""
import http.server
import socketserver
import argparse
import json
import ssl
import tempfile
import subprocess
import os
from urllib.parse import urlparse


class SyncHandler(http.server.BaseHTTPRequestHandler):
    server_version = "PMBRSMockTLS/0.1"

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

        length = int(self.headers.get('Content-Length', '0'))
        if length:
            _ = self.rfile.read(length)

        response = {'syncedIds': ['artifact-1', 'artifact-2'], 'message': 'OK'}
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode('utf-8'))

    def log_message(self, format, *args):
        print("[MockServerTLS] %s - %s" % (self.address_string(), format % args))


def gen_selfsigned(cert_path, key_path):
    cmd = [
        'openssl', 'req', '-x509', '-nodes', '-days', '365',
        '-subj', '/CN=pmbrs-mock.local',
        '-newkey', 'rsa:2048',
        '-keyout', key_path, '-out', cert_path
    ]
    subprocess.check_call(cmd)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8443)
    parser.add_argument('--token', type=str, default='test-token')
    parser.add_argument('--cert', type=str)
    parser.add_argument('--key', type=str)
    args = parser.parse_args()

    cert = args.cert
    key = args.key
    tmpdir = None
    if not cert or not key:
        tmpdir = tempfile.mkdtemp(prefix='pmbrs-mock-tls-')
        cert = os.path.join(tmpdir, 'cert.pem')
        key = os.path.join(tmpdir, 'key.pem')
        print('Generating self-signed cert (requires openssl)...')
        gen_selfsigned(cert, key)

    handler = SyncHandler
    with socketserver.TCPServer(('', args.port), handler) as httpd:
        httpd.expected_token = args.token
        # wrap socket with SSL using SSLContext
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(certfile=cert, keyfile=key)
        httpd.socket = context.wrap_socket(httpd.socket, server_side=True)
        print(f"Mock TLS auth server listening on port {args.port}; expected token='{args.token}'")
        print(f"Cert: {cert}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print('Shutting down')
            httpd.server_close()
    if tmpdir:
        pass


if __name__ == '__main__':
    main()
