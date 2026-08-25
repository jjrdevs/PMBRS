#!/usr/bin/env bash
# Start TLS mock auth server for local testing and run a quick curl check
# Usage: ./run_staged_tls_integration.sh <port> <token> [cert.pem key.pem]

PORT=${1:-8443}
TOKEN=${2:-test-token}
CERT=${3:-}
KEY=${4:-}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$SCRIPT_DIR/mock_auth_server_tls.py"

if [ -n "$CERT" ] && [ -n "$KEY" ]; then
  echo "Starting TLS mock server with provided cert/key"
  python3 "$PY" --port "$PORT" --token "$TOKEN" --cert "$CERT" --key "$KEY" &
else
  echo "Starting TLS mock server with self-signed cert (requires openssl)"
  python3 "$PY" --port "$PORT" --token "$TOKEN" &
fi

PID=$!
sleep 1

echo "Server started (PID=$PID). Quick health check using curl (insecure)"
curl -k -X POST https://localhost:$PORT/api/v1/artifacts/sync -H "Authorization: Bearer $TOKEN" -d '{}' -v || true

echo "To test from emulator, you may need to add the cert as a trusted CA or use a debug build that disables certificate validation."

echo "Server PID: $PID"
echo "To stop: kill $PID"

*** End Patch