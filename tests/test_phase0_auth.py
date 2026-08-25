"""Stage-3 Phase-0 auth tests (ADR-020 D2).

Two layers:

1. Token-store unit tests (issue / verify / role / revoke / permissions).
2. A live in-process HTTP server on 127.0.0.1 (random port) talking to the
   rewritten ``pmbrs_host_sync_ingest.py`` via real HTTP — this is the exact
   request path a Boox device or the phone app will use, so it doubles as the
   end-to-end verification the tunnel path will exercise (only the network hop
   differs).

Run:  python3 -m unittest tests.test_phase0_auth -v
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import socket
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "scripts" / "pmbrs_host_sync_ingest.py"


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


PNG = b"\x89PNG\r\n\x1a\n" + b"BOOXFAKEPAGE" * 32


def _put(url: str, payload: dict | None, token: str | None = None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else b""
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            body = json.loads(e.read().decode("utf-8"))
        except Exception:
            body = {"raw": str(e)}
        return e.code, body


class LiveServerMixin:
    @classmethod
    def _start(cls, tmp: Path) -> None:
        ing = _load_module("pmbrs_ingest_live_" + threading.get_ident().__str__(), SCRIPT)
        cls.ing = ing
        cls.store = ing.SyncTokenStore(tmp / "tokens.json")
        cls.boox = cls.store.issue("boox", label="noteair3", note="phase0-test")
        cls.mobile = cls.store.issue("mobile", label="testphone", note="phase0-test")
        cls.inbox = tmp / "inbox"
        cls.raw = tmp / "raw"
        cls.log = tmp / "auth.log"

        cls.handler = ing._create_handler(
            type("A", (), {}), cls.store, cls.raw, cls.inbox, cls.log
        )
        import socketserver

        class Srv(socketserver.ThreadingTCPServer):
            allow_reuse_address = True
            daemon_threads = True

        cls.srv = Srv(("127.0.0.1", 0), cls.handler)
        cls.port = cls.srv.server_address[1]
        cls.base = f"http://127.0.0.1:{cls.port}"
        cls.thread = threading.Thread(target=cls.srv.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def _stop(cls) -> None:
        if getattr(cls, "srv", None):
            cls.srv.shutdown()
            cls.srv.server_close()


# ---------------------------------------------------------------------------
# 1. Token store
# ---------------------------------------------------------------------------

class TokenStoreTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(__file__).resolve().parent / "_tmp_tokens"
        self.tmp.mkdir(exist_ok=True)
        ing = _load_module("pmbrs_ingest_tokstore", SCRIPT)
        self.ing = ing
        self.store = ing.SyncTokenStore(self.tmp / "tokens.json")

    def tearDown(self) -> None:
        import shutil

        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_issue_verify_revoke_lifecycle(self):
        rec = self.store.issue("boox", label="device-a")
        self.assertEqual(rec.role, "boox")
        self.assertEqual(self.store.verify(rec.secret).label, "device-a")  # type: ignore[union-attr]
        self.assertIsNone(self.store.verify("pmbrs_wrong"))
        self.assertIsNone(self.store.verify(""))
        self.assertTrue(self.store.revoke("device-a"))
        self.assertIsNone(self.store.verify(rec.secret))
        self.assertFalse(self.store.revoke("device-a"))  # already revoked / absent

    def test_role_bound_verification(self):
        rec = self.store.issue("mobile", label="phone-a")
        path = self.store.path
        self.assertTrue(self.ing.SyncTokenStore.verify_role(rec.secret, "mobile", path))
        self.assertFalse(self.ing.SyncTokenStore.verify_role(rec.secret, "boox", path))

    def test_token_file_permissions(self):
        self.store.issue("dev", label="perm-check")
        mode = oct(self.store.path.stat().st_mode & 0o777)
        self.assertEqual(mode, "0o600")


# ---------------------------------------------------------------------------
# 2. Live HTTP: auth matrix + both routes
# ---------------------------------------------------------------------------

class IngestAuthLiveTest(LiveServerMixin, unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(__file__).resolve().parent / "_tmp_ingest_live"
        cls.tmp.mkdir(exist_ok=True)
        cls._start(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        cls._stop()
        import shutil

        shutil.rmtree(cls.tmp, ignore_errors=True)

    # authn / authz matrix --------------------------------------------------

    def test_missing_token_is_401(self):
        code, body = _put(self.base + "/api/v1/boox/pages", {"noteUuid": "n", "pageId": "p"})
        self.assertEqual(code, 401)
        self.assertIn("Bearer", body["hint"])

    def test_malformed_header_is_401(self):
        req = urllib.request.Request(
            self.base + "/api/v1/boox/pages", data=b"{}", method="POST",
            headers={"Authorization": "NotBearer abc"},
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(ctx.exception.code, 401)

    def test_garbage_token_is_401(self):
        code, _ = _put(self.base + "/api/v1/boox/pages", None, token=f"Bearer abc")
        self.assertEqual(code, 401)

    def test_correct_role_ok(self):
        code, body = _put(
            self.base + "/api/v1/artifacts/sync",
            {"artifacts": [
                {
                    "artifactId": "phone-evt-1",
                    "source": "mobile",
                    "createdAtEpochMs": 1755790000000,
                    "payload": {"kind": "test"},
                }
            ]},
            token=self.mobile.secret,
        )
        self.assertEqual(code, 200, body)
        self.assertEqual(body["accepted"], 1)
        self.assertTrue((self.raw / "mobile" / "phone-evt-1-1755790000000.json").exists())

    def test_role_mismatch_is_403(self):
        code, body = _put(
            self.base + "/api/v1/artifacts/sync", {"artifacts": [{}]}, token=self.boox.secret
        )
        self.assertEqual(code, 403, body)
        code2, _ = _put(self.base + "/api/v1/boox/pages", {"noteUuid": "n", "pageId": "p"}, token=self.mobile.secret)
        self.assertEqual(code2, 403)

    def test_unknown_route_404_and_healthz_open(self):
        code, _ = _put(self.base + "/api/v1/never", None, token=self.boox.secret)
        self.assertEqual(code, 404)
        with urllib.request.urlopen(self.base + "/healthz", timeout=5) as r:
            self.assertEqual(r.status, 200)
            self.assertTrue(json.loads(r.read())["ok"])

    # boox page route ---------------------------------------------------------

    def test_boox_page_upload_happy_path(self):
        sha = hashlib.sha256(PNG).hexdigest()
        code, body = _put(
            self.base + "/api/v1/boox/pages",
            {
                "noteUuid": "note-live-2026-08-21",
                "pageId": "p0001",
                "pageOrder": 1,
                "sha256": sha,
                "pngB64": base64.b64encode(PNG).decode(),
            },
            token=self.boox.secret,
        )
        self.assertEqual(code, 200, body)
        expected = self.inbox / "note-live-2026-08-21" / "p0001.png"
        self.assertTrue(expected.exists())
        self.assertEqual(expected.read_bytes(), PNG)
        self.assertEqual(oct(expected.stat().st_mode & 0o777), "0o600")
        self.assertIn("note-live-2026-08-21/p0001", body["syncedIds"][0])
        self.assertEqual(body["sha256"], sha)

    def test_sha256_mismatch_refused(self):
        code, body = _put(
            self.base + "/api/v1/boox/pages",
            {
                "noteUuid": "note-badhash",
                "pageId": "p1",
                "sha256": "0" * 64,
                "pngB64": base64.b64encode(PNG).decode(),
            },
            token=self.boox.secret,
        )
        self.assertEqual(code, 400, body)
        self.assertFalse((self.inbox / "note-badhash" / "p1.png").exists())

    def test_non_png_rejected(self):
        bad = b"TEXT-FILE" * 10
        code, body = _put(
            self.base + "/api/v1/boox/pages",
            {
                "noteUuid": "n", "pageId": "p",
                "sha256": hashlib.sha256(bad).hexdigest(),
                "pngB64": base64.b64encode(bad).decode(),
            },
            token=self.boox.secret,
        )
        self.assertEqual(code, 400, body)

    def test_path_traversal_rejected(self):
        code, _ = _put(
            self.base + "/api/v1/boox/pages",
            {
                "noteUuid": "..", "pageId": "passwd",
                "sha256": hashlib.sha256(PNG).hexdigest(),
                "pngB64": base64.b64encode(PNG).decode(),
            },
            token=self.boox.secret,
        )
        self.assertEqual(code, 400)

    def test_auth_attempts_logged(self):
        # This may be the first request of the class (alphabetical order), so
        # generate one 401 and one 200 ourselves before asserting.
        _put(self.base + "/api/v1/boox/pages", {"noteUuid": "n", "pageId": "p"})  # 401 (no token)
        sha = hashlib.sha256(b"\x89PNG\r\n\x1a\nLOGCHECK").hexdigest()
        code, _ = _put(
            self.base + "/api/v1/boox/pages",
            {"noteUuid": "n", "pageId": "p", "sha256": sha,
             "pngB64": base64.b64encode(b"\x89PNG\r\n\x1a\nLOGCHECK").decode()},
            token=self.boox.secret,
        )
        assert code == 200
        lines = [json.loads(l) for l in self.log.read_text().splitlines() if l.strip()]
        events = {e["event"] for e in lines}
        self.assertIn("200", events)
        self.assertIn("401", events)
        self.assertTrue(any(e["tokenLabel"] == "noteair3" for e in lines if e["event"] == "200"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
