#!/usr/bin/env bash
# Start the local mock auth server and perform a quick POST to validate integration.
# Usage: ./run_staged_sync_integration.sh [port] [token]

PORT=${1:-8080}
TOKEN=${2:-test-token}

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PY_SCRIPT="$SCRIPT_DIR/mock_auth_server.py"

if [ ! -f "$PY_SCRIPT" ]; then
  echo "mock_auth_server.py missing at $PY_SCRIPT"
  exit 1
fi

echo "Starting mock auth server on port $PORT expecting token '$TOKEN'"
python3 "$PY_SCRIPT" --port "$PORT" --token "$TOKEN" &
SERVER_PID=$!

sleep 1

URL="http://localhost:$PORT/api/v1/artifacts/sync"
PAYLOAD='[{"artifactId":"a1","source":"test","payload":"{}","createdAtEpochMs":1,"schemaVersion":"1.0","deviceAlias":"local","provenanceMetadataJson":"{}","synced":false}]'

echo "Posting test payload to $URL"
RESPONSE=$(curl -s -w "HTTPSTATUS:%{http_code}" -X POST "$URL" -H "Content-Type: application/json" -H "Authorization: Bearer $TOKEN" -d "$PAYLOAD")

HTTP_STATUS=$(echo "$RESPONSE" | tr -d '\r' | sed -e 's/.*HTTPSTATUS://')
BODY=$(echo "$RESPONSE" | sed -e 's/HTTPSTATUS:.*//')

echo "Response status: $HTTP_STATUS"
echo "Body: $BODY"

if [ "$HTTP_STATUS" != "200" ]; then
  echo "Integration check failed (status $HTTP_STATUS)"
  kill $SERVER_PID || true
  exit 2
fi

echo "Integration check succeeded." 
echo "Shutting down mock server (pid=$SERVER_PID)"
kill $SERVER_PID || true

echo "Done"
