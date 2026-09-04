"""Sync / processing manifest for the wearable pipeline (ADR-021 D2/D4/D5).

Location (default): ``~/.pmbrs-private/state/wearable_sync_manifest.json``.
Mirrors ``pmbrs.ingestion.boox.manifest`` (atomic write, load/save) but keyed
by the pushed **files** rather than OCR pages, because the wearable consumer
is transport-agnostic and idempotent over
``(export, relPath, sha256)`` triples.

Shape (v1.0)
------------
{
  schemaVersion: "1.0",
  deviceAlias: "galaxy-watch7",
  exports: {
    "<export>": {
      relPath: {
        sha256: str,
        bytes: int,
        recordsEmitted: int,
        lastProcessedAtMs: int,
        status: "processed" | "empty" | "error",
        error: str,            # only when status == "error"
        windowCount: int       # canonical windows this file contributed
      }
    }
  },
  lastRunMs: int
}

``needs_processing`` gates the one-parse-pass-per-file rule (D4): a file is
re-parsed only when its sha256 is new or changed since the last recorded run.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

MANIFEST_SCHEMA = "1.0"
STATUS_PROCESSED = "processed"
STATUS_EMPTY = "empty"
STATUS_ERROR = "error"


@dataclass
class FileRecord:
    sha256: str
    bytes: int
    records_emitted: int
    last_processed_at_ms: int
    status: str
    error: str = ""
    window_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "sha256": self.sha256,
            "bytes": self.bytes,
            "recordsEmitted": self.records_emitted,
            "lastProcessedAtMs": self.last_processed_at_ms,
            "status": self.status,
            "error": self.error,
            "windowCount": self.window_count,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "FileRecord":
        return cls(
            sha256=str(d.get("sha256") or ""),
            bytes=int(d.get("bytes") or 0),
            records_emitted=int(d.get("recordsEmitted") or 0),
            last_processed_at_ms=int(d.get("lastProcessedAtMs") or 0),
            status=str(d.get("status") or STATUS_PROCESSED),
            error=str(d.get("error") or ""),
            window_count=int(d.get("windowCount") or 0),
        )


@dataclass
class FileEntry:
    rel_path: str
    sha256: str
    bytes: int
    records_emitted: int
    last_processed_at_ms: int
    status: str
    error: str = ""
    window_count: int = 0

    def record(self) -> FileRecord:
        return FileRecord(
            sha256=self.sha256,
            bytes=self.bytes,
            records_emitted=self.records_emitted,
            last_processed_at_ms=self.last_processed_at_ms,
            status=self.status,
            error=self.error,
            window_count=self.window_count,
        )

    @classmethod
    def from_dict(cls, rel: str, d: dict[str, Any]) -> "FileEntry":
        r = FileRecord.from_dict(d)
        return cls(
            rel_path=rel,
            sha256=r.sha256,
            bytes=r.bytes,
            records_emitted=r.records_emitted,
            last_processed_at_ms=r.last_processed_at_ms,
            status=r.status,
            error=r.error,
            window_count=r.window_count,
        )


@dataclass
class WearableSyncManifest:
    path: Path
    device_alias: str = "galaxy-watch7"
    #: exports -> relPath -> FileEntry
    exports: dict[str, dict[str, FileEntry]] = field(default_factory=dict)
    last_run_ms: int = 0
    schema_version: str = MANIFEST_SCHEMA

    # --- load / save -------------------------------------------------
    @classmethod
    def load(cls, path: str | Path, device_alias: str = "galaxy-watch7") -> "WearableSyncManifest":
        path = Path(path)
        if not path.exists():
            return cls(path=path, device_alias=device_alias)
        data = json.loads(path.read_text(encoding="utf-8"))
        exports: dict[str, dict[str, FileEntry]] = {}
        for ex, files in (data.get("exports") or {}).items():
            exports[ex] = {
                rel: FileEntry.from_dict(rel, d)
                for rel, d in (files or {}).items()
            }
        return cls(
            path=path,
            device_alias=str(data.get("deviceAlias") or device_alias),
            exports=exports,
            last_run_ms=int(data.get("lastRunMs") or 0),
            schema_version=str(data.get("schemaVersion") or MANIFEST_SCHEMA),
        )

    def save(self) -> None:
        payload = {
            "schemaVersion": self.schema_version,
            "deviceAlias": self.device_alias,
            "lastRunMs": self.last_run_ms,
            "exports": {
                ex: {rel: e.record().to_dict() for rel, e in files.items()}
                for ex, files in self.exports.items()
            },
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=str(self.path.parent), prefix=".wearable.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            os.replace(tmp, self.path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    # --- query helpers ------------------------------------------------
    def entry(self, export: str, rel_path: str) -> FileEntry | None:
        return (self.exports.get(export) or {}).get(rel_path)

    def needs_processing(
        self, *, export: str, rel_path: str, sha256: str, force: bool = False
    ) -> bool:
        """True when this file has never been processed or its content changed."""
        if force:
            return True
        e = self.entry(export, rel_path)
        if e is None:
            return True
        if not e.sha256:
            return True
        return e.sha256 != sha256

    def mark(self, *, export: str, rel_path: str, sha256: str,
             by: int, records: int, windows: int, status: str,
             now_ms: int, error: str = "") -> None:
        bucket = self.exports.setdefault(export, {})
        bucket[rel_path] = FileEntry(
            rel_path=rel_path,
            sha256=sha256,
            bytes=by,
            records_emitted=records,
            last_processed_at_ms=now_ms,
            status=status,
            error=error,
            window_count=windows,
        )


__all__ = [
    "MANIFEST_SCHEMA",
    "STATUS_PROCESSED",
    "STATUS_EMPTY",
    "STATUS_ERROR",
    "FileRecord",
    "FileEntry",
    "WearableSyncManifest",
]
