"""ADR-021 route smoke (task 10b): live HTTP contract for the wearable push.

Boots ``scripts/pmbrs_host_sync_ingest.py`` on an ephemeral 127.0.0.1 port,
waits for ``/healthz``, then asserts the exact contract the phone relies on:

  * valid push         -> 200, 0o600 on disk, declared sha256 == stored sha256
  * hash mismatch      -> 400, path NOT created
  * path traversal     -> 400, nothing written outside the inbox
  * disallowed relPath -> 400 (non-wearable file)
  * wrong-role token   -> 403
  * missing token      -> 401
  * unknown route      -> 404
  * re-push same file  -> 200, in-place overwrite, still 0o600
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import json
import os
import stat
import subprocess
import sys
import time
from pathlib import Path

_REPO = Path("/home/jjrdev/workspace/pmbrs")
sys.path.insert(0, str(_REPO / "src"))
sys.path.insert(0, str(_REPO))

import pytest

TOKEN_FILE = Path.home() / ".pmbrs-private" / "config" / "sync_tokens.json"

VALID_REL_PATH = "com.samsung.shealth.tracker.heart_rate/3/valid-test.binning.json"
VALID_DATA = json.dumps([{"start_time": 1704067200000, "end_time": 1704067260000,
                          "heart_rate": 72, "heart_rate_min": 68, "heart_rate_max": 76}]).encode()
HASH_MISMATCH_PATH = "com.samsung.health.hrv/0/bad-hash.json"
TRAVERSAL_REL_PATH = "com.samsung.shealth.tracker.heart_rate/../../etc/evil.json"


def _pick(role: str) -> str:
    for t in json.loads(TOKEN_FILE.read_text())["tokens"]:
        if t.get("role") == role:
            return t["secret"]
    raise AssertionError(f"no {role} token in {TOKEN_FILE}")


MOBILE = _pick("mobile")
OTHER = _pick("boox")  # different role -> must be rejected on the wearable route


def _free_port() -> int:
    import socket
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def _post(port: int, path: str, body: bytes, token: str | None):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=15)
    hdrs = {"Content-Type": "application/json"}
    if token:
        hdrs["Authorization"] = f"Bearer {token}"
    c.request("POST", path, body=body, headers=hdrs)
    r = c.getresponse()
    data = r.read()
    c.close()
    return r.status, data


def _payload(rel_path: str, data: bytes, sha: str | None = None) -> bytes:
    return json.dumps({
        "relPath": rel_path,
        "sha256": sha if sha is not None else hashlib.sha256(data).hexdigest(),
        "b64": base64.b64encode(data).decode("ascii"),
    }).encode("ascii")


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    """Run the real ingest server on an ephemeral port; yield (port, inbox_root)."""
    inbox = tmp_path_factory.mktemp("wear_inbox")
    port = _free_port()
    proc = subprocess.Popen(
        [sys.executable, "scripts/pmbrs_host_sync_ingest.py",
         "--port", str(port), "--bind", "127.0.0.1",
         "--wearable-inbox-root", str(inbox)],
        cwd=str(_REPO), stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    deadline = time.time() + 10
    up = False
    while time.time() < deadline:
        if proc.poll() is not None:
            out = ""
            try:
                out = proc.stdout.read().decode(errors="replace") if proc.stdout else ""
            except Exception:  # noqa: BLE001
                pass
            raise AssertionError(f"server died at startup:\n{out}")
        try:
            c = http.client.HTTPConnection("127.0.0.1", port, timeout=1)
            c.request("GET", "/healthz")
            r = c.getresponse()
            r.read()
            c.close()
            up = True
            break
        except OSError:
            time.sleep(0.2)
    assert up, "server did not become ready"
    yield port, inbox
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def test_valid_push_ok_0600_sha_match(server):
    port, inbox = server
    status, data = _post(port, "/api/v1/wearable/files", _payload(VALID_REL_PATH, VALID_DATA), MOBILE)
    body = json.loads(data)
    assert status == 200, body
    assert body["sha256"] == hashlib.sha256(VALID_DATA).hexdigest()
    stored = inbox / VALID_REL_PATH
    assert stored.is_file()
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600
    assert stored.read_bytes() == VALID_DATA


def test_hash_mismatch_400_not_stored(server):
    port, inbox = server
    status, data = _post(port, "/api/v1/wearable/files",
                         _payload(HASH_MISMATCH_PATH, b"xyz", sha="0" * 64), MOBILE)
    assert status == 400, data
    assert "sha256" in data.decode()
    assert not (inbox / HASH_MISMATCH_PATH).exists()


def test_path_traversal_400(server):
    port, inbox = server
    status, data = _post(port, "/api/v1/wearable/files", _payload(TRAVERSAL_REL_PATH, b"n"), MOBILE)
    assert status == 400, data
    assert not Path("/etc/evil.json").exists()


def test_disallowed_relpath_400(server):
    port, inbox = server
    status, data = _post(port, "/api/v1/wearable/files", _payload("arbitrary/e.json", b"x"), MOBILE)
    assert status == 400, data
    assert not (inbox / "arbitrary" / "e.json").exists()


def test_wrong_role_token_403(server):
    port, inbox = server
    status, data = _post(port, "/api/v1/wearable/files", _payload(VALID_REL_PATH, VALID_DATA), OTHER)
    assert status == 403, data
    assert "role" in data.decode()


def test_missing_token_401(server):
    port, inbox = server
    status, data = _post(port, "/api/v1/wearable/files", _payload(VALID_REL_PATH, VALID_DATA), None)
    assert status == 401, data


def test_unknown_route_404(server):
    port, inbox = server
    status, data = _post(port, "/api/v1/nope", _payload(VALID_REL_PATH, VALID_DATA), MOBILE)
    assert status == 404, data


def test_idempotent_repush_same_file(server):
    port, inbox = server
    for _ in range(2):
        status, data = _post(port, "/api/v1/wearable/files", _payload(VALID_REL_PATH, VALID_DATA), MOBILE)
        assert status == 200, data
    stored = inbox / VALID_REL_PATH
    assert stored.is_file()
    assert stat.S_IMODE(stored.stat().st_mode) == 0o600
    assert stored.read_bytes() == VALID_DATA
