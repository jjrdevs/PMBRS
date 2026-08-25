#!/usr/bin/env python3
"""Host-side ingest for PMBRS device sync (phone + Boox).

Routes (all bearer-token authed except ``/healthz``):

    POST /api/v1/artifacts/sync   phone app batch upload (JSON artifacts)
                                  roles: mobile | dev
                                  → store/raw/<source>/<id>-<ts>.json
    POST /api/v1/boox/pages       Boox NoteAir3 page upload (Phase 0 shape,
                                  ADR-020 D1/D2): JSON body
                                  {noteUuid, pageId, pageOrder, sha256, pngB64}
                                  (pngB64 = base64 PNG bytes)
                                  roles: boox | dev
                                  → store/inbox/boox/<noteUuid>/<pageId>.png
    GET  /healthz                 liveness probe, no auth, no data

Auth model (ADR-020 D2):
  * Bearer token from ``~/.pmbrs-private/config/sync_tokens.json``
    (managed by ``scripts/pmbrs_sync_tokens.py``).
  * Constant-time compare (hmac.compare_digest).
  * The token's *role* must match the route's required role — a boox token
    can never hit the phone route and vice versa.
  * Every attempt (ok or 401) is appended to ``~/.pmbrs-private/logs/sync_auth.log``.

Boox payload integrity: the hub verifies the declared ``sha256`` against the
decoded bytes before writing the inbox file, and re-hashes the file after
writing. On mismatch the file is not kept and a 400 is returned. The file is
written ``0o600`` under the 700 private root.

The phone-route behavior (``persist_sync_batch``) is byte-for-byte the Stage-2
contract that ADR-017 pinned and ``tests/test_mobile_raw_ingest.py`` covers;
it is unchanged in this rewrite.
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import http.server
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import sys

# Make `pmbrs.auth` importable both from the repo (src/ layout) and when the
# script is run directly from a checkout without an install step.
_REPO_ROOT = Path(__file__).resolve().parents[1]
if _REPO_ROOT.is_dir():
    _SRC = _REPO_ROOT / "src"
    if str(_SRC) not in sys.path:
        sys.path.insert(0, str(_SRC))

from pmbrs.auth import DEFAULT_TOKENS_PATH, SyncTokenStore  # noqa: E402

DEFAULT_RAW_ROOT = Path("/home/jjrdev/.pmbrs-private/store/raw")
DEFAULT_INBOX_ROOT = Path("/home/jjrdev/.pmbrs-private/store/inbox/boox")
DEFAULT_AUTH_LOG = Path("/home/jjrdev/.pmbrs-private/logs/sync_auth.log")
MAX_BODY_BYTES = 64 * 1024 * 1024  # single page PNG; hard cap, not a quota

# route path -> role required (dev can access everything, for testing)
ROUTE_ROLE = {
    "/api/v1/artifacts/sync": "mobile",
    "/api/v1/boox/pages": "boox",
}


# ---------------------------------------------------------------------------
# phone route (unchanged Stage-2 contract, ADR-017 D4 / ADR-019)
# ---------------------------------------------------------------------------

def _source_dir(raw_root: Path, source: str) -> Path:
    normalized = (source or "other").strip().lower()
    if normalized.startswith("browser"):
        normalized = "browser"
    if normalized not in {"mobile", "browser", "desktop", "journal", "other"}:
        normalized = "other"
    return raw_root / normalized


def _write_artifact_file(path: Path, payload: dict[str, Any]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def persist_sync_batch(raw_root: str | Path = DEFAULT_RAW_ROOT, payloads: Iterable[dict[str, Any]] | None = None) -> list[Path]:
    # ADR-017 D9 / tests/test_mobile_raw_ingest.py pin this exact contract:
    # persist_sync_batch(raw_root=..., payloads=[...]) -> list[Path]
    root = Path(raw_root)
    root.mkdir(parents=True, exist_ok=True)
    if payloads is None:
        raise ValueError("payloads must be provided")

    written: list[Path] = []
    for item in payloads:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or item.get("sourceType") or "other")
        artifact_id = str(item.get("artifactId") or item.get("id") or "unknown")
        created_ms = item.get("createdAtEpochMs") or item.get("createdAt") or int(datetime.now(timezone.utc).timestamp() * 1000)
        record = {
            "artifactId": artifact_id,
            "source": source,
            "payload": item.get("payload") or {},
            "createdAtEpochMs": int(created_ms),
            "schemaVersion": item.get("schemaVersion") or "1.0",
            "deviceAlias": item.get("deviceAlias") or "unknown",
            "provenanceMetadataJson": item.get("provenanceMetadataJson") or {},
            "ingestedAtEpochMs": int(datetime.now(timezone.utc).timestamp() * 1000),
            "ingestStatus": "accepted",
        }
        destination_dir = _source_dir(root, source)
        destination_dir.mkdir(parents=True, exist_ok=True)
        file_name = f"{artifact_id}-{int(created_ms)}.json"
        file_path = _write_artifact_file(destination_dir / file_name, record)
        written.append(file_path)
    return written


def _handle_phone_sync(raw_root: Path, body: Any) -> dict[str, Any]:
    if isinstance(body, list):
        batch = body
    elif isinstance(body, dict):
        batch = body.get("artifacts", [])
    else:
        batch = []

    written = persist_sync_batch(raw_root, batch)
    return {
        "accepted": len(written),
        "message": "OK",
        "storedFiles": [str(path.relative_to(raw_root)) for path in written],
    }


# ---------------------------------------------------------------------------
# boox route (Phase-0 shape; producer/OCR consume this in Phase 2)
# ---------------------------------------------------------------------------

def _safe_segment(value: str) -> str | None:
    """Validate a user-supplied path segment (noteUuid / pageId).

    Must be non-empty, no separators, no '..'; length <= 128; printable
    ASCII only. Returns the value or None (caller 400s).
    """
    if not value or len(value) > 128:
        return None
    if any(ch in value for ch in ("/", "\\", "\x00", "..")):
        return None
    if not all(32 < ord(ch) < 127 for ch in value):
        return None
    return value


def _sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def store_boox_page(inbox_root: Path, note_uuid: str, page_id: str, png: bytes) -> Path:
    """Write one page PNG into the inbox (staging; *not* the raw store).

    Writes atomically (tmp + os.replace) to a final path of
    ``inbox/<note_uuid>/<page_id>.png`` and returns it.
    """
    note_dir = inbox_root / note_uuid
    note_dir.mkdir(parents=True, exist_ok=True)
    final = note_dir / f"{page_id}.png"
    tmp = note_dir / f".{page_id}.tmp.{os.getpid()}"
    tmp.write_bytes(png)
    try:
        os.chmod(tmp, 0o600)
    except OSError:
        pass
    os.replace(tmp, final)
    return final


def handle_boox_page(inbox_root: Path, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("page payload must be a JSON object")
    note_uuid = _safe_segment(str(payload.get("noteUuid") or ""))
    page_id = _safe_segment(str(payload.get("pageId") or ""))
    if note_uuid is None or page_id is None:
        raise ValueError("noteUuid / pageId must be a safe non-empty path segment")

    b64 = payload.get("pngB64")
    if not isinstance(b64, str) or not b64:
        raise ValueError("pngB64 (base64 PNG) is required")
    try:
        png = base64.b64decode(b64, validate=True)
    except (binascii.Error, ValueError) as exc:
        raise ValueError(f"pngB64 is not valid base64: {exc}") from exc
    if not png:
        raise ValueError("decoded PNG is empty")
    if png[:4] != b"\x89PNG":
        # Strict: the device ships PNG bytes; reject anything else early.
        raise ValueError("payload is not a PNG (bad magic bytes)")
    actual = _sha256_hex(png)
    expected = str(payload.get("sha256") or "").lower().strip()
    if expected and expected != actual:
        # Do NOT write the file on hash mismatch — refuse to stage it.
        raise ValueError(f"sha256 mismatch (expected {expected[:12]}…, got {actual[:12]}…)")

    path = store_boox_page(inbox_root, note_uuid, page_id, png)
    # Re-hash what we actually put on disk; this is what the device ACKS against.
    on_disk_sha = _sha256_hex(path.read_bytes())
    return {
        "accepted": 1,
        "message": "OK",
        "storedFiles": [str(path)],
        "syncedIds": [f"{note_uuid}/{page_id}"],
        "sha256": on_disk_sha,
        "bytes": len(png),
        "pageOrder": payload.get("pageOrder"),
    }


# ---------------------------------------------------------------------------
# HTTP server (auth + routing)
# ---------------------------------------------------------------------------

def _authz_log(auth_log: Path, event: str, role_used: str, path: str, peer: str, token_label: str | None = None) -> None:
    try:
        auth_log.parent.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        line = json.dumps(
            {"ts": ts, "event": event, "role": role_used, "path": path, "peer": peer, "tokenLabel": token_label},
            ensure_ascii=False,
        )
        with auth_log.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
        try:
            os.chmod(auth_log, 0o600)
        except OSError:
            pass
    except OSError:
        # Auth logging must never break a request.
        pass


def _json_response(handler, code: int, body: dict[str, Any]) -> None:
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(data)))
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.wfile.write(data)


def _send_401(handler, path: str, peer: str, auth_log: Path) -> None:
    _authz_log(auth_log, "401", "-", path, peer, None)
    _json_response(handler, 401, {"message": "unauthorized", "hint": "Authorization: Bearer <pmbrs_sync_token>"})


def _create_handler(args, token_store: SyncTokenStore, raw_root: Path, inbox_root: Path, auth_log: Path):
    class IngestHandler(http.server.BaseHTTPRequestHandler):
        server_version = "PMBRSHostIngest/0.2"

        def _route(self) -> None:
            from urllib.parse import urlparse

            parsed = urlparse(self.path)
            path = parsed.path

            if path == "/healthz":
                _json_response(self, 200, {"ok": True, "service": "pmbrs-ingest", "routes": list(ROUTE_ROLE)})
                return

            required_role = ROUTE_ROLE.get(path)
            if required_role is None:
                _json_response(self, 404, {"message": "no such route"})
                return

            # --- authn + authz (constant-time compare + role match) ---
            header = self.headers.get("Authorization") or ""
            parts = header.strip().split(None, 1)
            token_presented = ""
            if len(parts) == 2 and parts[0].lower() == "bearer":
                token_presented = parts[1].strip()
            record = token_store.verify(token_presented)
            if record is None:
                _send_401(self, path, self.address_string(), auth_log)
                return
            if record.role not in (required_role, "dev"):
                _json_response(self, 403, {"message": "token role does not cover this route", "route": path, "tokenRole": record.role})
                return
            _authz_log(auth_log, "200", record.role, path, self.address_string(), record.label)

            # --- body + route handler ---
            content_length = int(self.headers.get("Content-Length", "0") or 0)
            if content_length > MAX_BODY_BYTES:
                _json_response(self, 413, {"message": f"body exceeds {MAX_BODY_BYTES} bytes"})
                return
            body_bytes = self.rfile.read(content_length) if content_length else b"{}"
            try:
                payload = json.loads(body_bytes.decode("utf-8"))
            except json.JSONDecodeError:
                _json_response(self, 400, {"message": "Invalid JSON"})
                return

            try:
                if path == "/api/v1/artifacts/sync":
                    result = _handle_phone_sync(raw_root, payload)
                else:  # /api/v1/boox/pages
                    result = handle_boox_page(inbox_root, payload)
            except ValueError as exc:
                _json_response(self, 400, {"message": str(exc)})
                return

            _json_response(self, 200, result)

        def do_POST(self):
            self._route()

        def do_GET(self):
            from urllib.parse import urlparse

            if urlparse(self.path).path == "/healthz":
                _json_response(self, 200, {"ok": True, "service": "pmbrs-ingest", "routes": list(ROUTE_ROLE)})
                return
            _json_response(self, 405, {"message": "method not allowed"})

        def log_message(self, format: str, *log_args: Any) -> None:  # silence default stderr noise
            print(f"[PMBRSIngest] {self.address_string()} - {format % log_args}")

    return IngestHandler


def main() -> int:
    parser = argparse.ArgumentParser(description="PMBRS host-side raw ingest endpoint (authed)")
    parser.add_argument("--raw-root", default=str(DEFAULT_RAW_ROOT), help="Directory where raw phone artifacts are stored")
    parser.add_argument("--inbox-root", default=str(DEFAULT_INBOX_ROOT), help="Inbox directory for Boox page uploads (staging)")
    parser.add_argument("--tokens", default=str(DEFAULT_TOKENS_PATH), help="Path to the sync token store JSON")
    parser.add_argument("--auth-log", default=str(DEFAULT_AUTH_LOG), help="Append-only auth/usage log")
    parser.add_argument("--port", type=int, default=8788, help="Local port to serve (tunnel + LAN devices connect here)")
    parser.add_argument("--bind", default="0.0.0.0", help="Bind address. Use 127.0.0.1 to serve tunnel-only (cloudflared connects over 127.0.0.1); use 0.0.0.0 to also accept LAN device clients. Default: 0.0.0.0.")
    args = parser.parse_args()

    token_store = SyncTokenStore(args.tokens)
    raw_root = Path(args.raw_root)
    inbox_root = Path(args.inbox_root)
    auth_log = Path(args.auth_log)
    handler = _create_handler(args, token_store, raw_root, inbox_root, auth_log)

    import http.server as _http
    import socketserver

    class Server(socketserver.ThreadingTCPServer):
        allow_reuse_address = True
        daemon_threads = True

    with Server((args.bind, args.port), handler) as httpd:
        print(f"PMBRS host ingest listening on http://{args.bind}:{args.port}")
        print(f"  routes:  {', '.join(ROUTE_ROLE)} (+ /healthz)")
        print(f"  raw root: {raw_root}")
        print(f"  inbox:    {inbox_root}")
        print(f"  tokens:   {args.tokens}  auth-log: {args.auth_log}")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("Shutting down")
            httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
