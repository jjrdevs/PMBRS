"""PMBRS sync-token management (Phase 0 of Stage-3, ADR-020 D2).

Tokens are the only credential that lets a device (Boox NoteAir3, future phone)
push data to the hub's ingest endpoint. Design rules from ADR-020:

- A token is bound to exactly one **device role** (``boox`` today; ``mobile``
  reserved for the phone app). Roles are never shared.
- Tokens live **outside the repo**, under ``~/.pmbrs-private/config/sync_tokens.json``.
- Compare with ``hmac.compare_digest`` — constant-time, no timing oracle.
- Every auth attempt (success or failure) is logged with the acting token
  label so leaks / brute-force can be spotted in the service log.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_TOKENS_PATH = Path.home() / ".pmbrs-private" / "config" / "sync_tokens.json"

TOKEN_PREFIX = "pmbrs"
TOKEN_BYTES = 32  # 256 bits


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


@dataclass(frozen=True)
class TokenRecord:
    """One issued (not revoked) token."""

    label: str
    role: str
    secret: str
    created_at: str
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "role": self.role,
            "secret": self.secret,
            "note": self.note,
            "created_at": self.created_at,
        }


class SyncTokenStore:
    """JSON-file-backed store of sync bearer tokens.

    The file layout (versioned so future migrations don't break it):

    .. code-block:: json

        {
          "schema": "pmbrs.sync-tokens/1",
          "tokens": [ {label, role, secret, note, created_at} ],
          "revoked": [ {label, role, secret, revoked_at} ]
        }

    Concurrency is not expected (single hub process); ``load``/``save`` are
    plain read-modify-write with ``os.replace`` for atomicity on save.
    """

    SCHEMA = "pmbrs.sync-tokens/1"

    def __init__(self, path: str | Path = DEFAULT_TOKENS_PATH):
        self.path = Path(path)

    # -- lifecycle -------------------------------------------------------

    def issue(self, role: str, label: str | None = None, note: str = "") -> TokenRecord:
        """Issue a new token for ``role`` and persist it.

        Returns the full record including the secret (this is the only time
        the secret is exposed to the caller; after that it is only matched,
        never displayed — see `show` for the redacted view).
        """
        if role not in {"boox", "mobile", "dev"}:
            raise ValueError(f"unknown token role: {role!r} (expected boox|mobile|dev)")
        label = (label or role).strip() or role
        data = self._load()
        record = TokenRecord(
            label=label,
            role=role,
            secret=f"{TOKEN_PREFIX}_{secrets.token_urlsafe(TOKEN_BYTES)}",
            created_at=_utcnow_iso(),
            note=note,
        )
        data["tokens"].append(record.to_dict())
        self._save(data)
        return record

    def revoke(self, label: str) -> bool:
        """Move a token from active to revoked. Returns True if it was active."""
        data = self._load()
        for i, tok in enumerate(data["tokens"]):
            if tok["label"] == label:
                tok["revoked_at"] = _utcnow_iso()
                data["revoked"].append(tok)
                data["tokens"].pop(i)
                self._save(data)
                return True
        return False

    # -- verification ----------------------------------------------------

    def verify(self, presented: str) -> TokenRecord | None:
        """Constant-time match of a presented bearer token against active tokens.

        Compares UTF-8 bytes so non-ASCII input cannot raise
        ``TypeError`` from ``hmac.compare_digest`` (which is only defined for
        ASCII ``str`` or ``bytes``); such input simply fails to match and
        yields 401 instead of a 500.
        """
        if not presented:
            return None
        presented_b = presented.encode("utf-8")
        for tok in self._load().get("tokens", []):
            if hmac.compare_digest(tok.get("secret", "").encode("utf-8"), presented_b):
                return TokenRecord(
                    label=tok["label"],
                    role=tok["role"],
                    secret=tok["secret"],
                    created_at=tok.get("created_at", ""),
                    note=tok.get("note", ""),
                )
        return None

    @staticmethod
    def verify_role(presented: str, required_role: str, path: str | Path = DEFAULT_TOKENS_PATH) -> bool:
        """Verify token AND that its role matches. Used by the ingest handler."""
        rec = SyncTokenStore(path).verify(presented)
        return rec is not None and rec.role == required_role

    # -- introspection ---------------------------------------------------

    def list_active(self) -> list[dict[str, Any]]:
        return [self._redact(t) for t in self._load().get("tokens", [])]

    @staticmethod
    def _redact(tok: dict[str, Any]) -> dict[str, Any]:
        secret = tok.get("secret", "")
        prefix = secret[:9] if len(secret) >= 9 else secret
        return {
            **{k: v for k, v in tok.items() if k != "secret"},
            "secret": f"{prefix}…({len(secret)} chars)",
            "sha256_12": hashlib.sha256(secret.encode()).hexdigest()[:12],
        }

    # -- plumbing --------------------------------------------------------

    def _load(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"schema": self.SCHEMA, "tokens": [], "revoked": []}
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw.setdefault("tokens", [])
        raw.setdefault("revoked", [])
        return raw

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, self.path)
        try:
            self.path.chmod(0o600)
        except OSError:
            pass
