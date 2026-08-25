"""Sync manifest — idempotency across producer runs (ADR-019 D5).

Location (default): ``~/.pmbrs-private/state/boox_sync_manifest.json``
(per ``config/external_data_policy.json`` state_root). Written atomically so a
crash mid-run never produces a half-updated manifest.

Shape (v1.0)
------------
{
  schemaVersion: "1.0",
  deviceSerial: "4EF2D7E9",
  notes: {
    "<note-uuid>": {
      noteDirMtimeMs: int,
      pageCount: int,
      pages: [
        {
          pageId: str,
          pageOrder: int,
          source: "cover" | "page",
          pngRelPath: str,
          pngSha256: str,
          pngDims: [w, h],
          lastOcrAtMs: int,
          lastOcrEngine: str,
          lastArtifactId: str,
          blank: bool
        }
      ]
    }
  },
  lastRunMs: int
}
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


MANIFEST_SCHEMA = "1.0"


@dataclass
class PageRecord:
    page_id: str
    page_order: int
    source: str
    png_rel_path: str
    png_sha256: str
    png_dims: tuple[int, int]
    last_ocr_at_ms: int = 0
    last_ocr_engine: str = ""
    last_artifact_id: str = ""
    blank: bool = False

    def to_dict(self) -> dict[str, Any]:
        d = {
            "pageId": self.page_id,
            "pageOrder": self.page_order,
            "source": self.source,
            "pngRelPath": self.png_rel_path,
            "pngSha256": self.png_sha256,
            "pngDims": list(self.png_dims),
            "lastOcrAtMs": self.last_ocr_at_ms,
            "lastOcrEngine": self.last_ocr_engine,
            "lastArtifactId": self.last_artifact_id,
            "blank": self.blank,
        }
        return d

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PageRecord":
        dims = d.get("pngDims") or [0, 0]
        return cls(
            page_id=str(d.get("pageId") or ""),
            page_order=int(d.get("pageOrder") or 0),
            source=str(d.get("source") or "cover"),
            png_rel_path=str(d.get("pngRelPath") or ""),
            png_sha256=str(d.get("pngSha256") or ""),
            png_dims=(int(dims[0]), int(dims[1])) if len(dims) >= 2 else (0, 0),
            last_ocr_at_ms=int(d.get("lastOcrAtMs") or 0),
            last_ocr_engine=str(d.get("lastOcrEngine") or ""),
            last_artifact_id=str(d.get("lastArtifactId") or ""),
            blank=bool(d.get("blank") or False),
        )


@dataclass
class NoteRecord:
    note_uuid: str
    note_dir_mtime_ms: int = 0
    pages: list[PageRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "noteDirMtimeMs": self.note_dir_mtime_ms,
            "pageCount": len(self.pages),
            "pages": [p.to_dict() for p in self.pages],
        }

    @classmethod
    def from_dict(cls, uuid: str, d: dict[str, Any]) -> "NoteRecord":
        pages = [PageRecord.from_dict(p) for p in (d.get("pages") or [])]
        return cls(
            note_uuid=uuid,
            note_dir_mtime_ms=int(d.get("noteDirMtimeMs") or 0),
            pages=pages,
        )


@dataclass
class BooxSyncManifest:
    manifest_path: Path
    device_serial: str = ""
    notes: dict[str, NoteRecord] = field(default_factory=dict)
    last_run_ms: int = 0
    schema_version: str = MANIFEST_SCHEMA

    # --- load / save --------------------------------------------

    @classmethod
    def load(cls, path: str | Path, device_serial: str = "") -> "BooxSyncManifest":
        path = Path(path)
        if not path.exists():
            return cls(manifest_path=path, device_serial=device_serial)
        data = json.loads(path.read_text(encoding="utf-8"))
        notes = {
            uuid: NoteRecord.from_dict(uuid, d)
            for uuid, d in (data.get("notes") or {}).items()
        }
        return cls(
            manifest_path=path,
            device_serial=str(data.get("deviceSerial") or device_serial),
            notes=notes,
            last_run_ms=int(data.get("lastRunMs") or 0),
            schema_version=str(data.get("schemaVersion") or MANIFEST_SCHEMA),
        )

    def save(self) -> None:
        payload = {
            "schemaVersion": self.schema_version,
            "deviceSerial": self.device_serial,
            "lastRunMs": self.last_run_ms,
            "notes": {uuid: rec.to_dict() for uuid, rec in self.notes.items()},
        }
        target = self.manifest_path
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: temp file in the same dir, then replace.
        fd, tmp_name = tempfile.mkstemp(dir=str(target.parent), prefix=".manifest.", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
            os.replace(tmp_name, target)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    # --- query helpers -------------------------------------------

    def page_record(self, note_uuid: str, page_id: str) -> PageRecord | None:
        note = self.notes.get(note_uuid)
        if not note:
            return None
        for p in note.pages:
            if p.page_id == page_id:
                return p
        return None

    def needs_ocr(
        self,
        note_uuid: str,
        page_id: str,
        png_sha256: str,
        force: bool = False,
    ) -> bool:
        """Decide whether a page needs re-OCR.

        A page is re-worked when:
          - it has never been OCR'd (no record), OR
          - ``force`` is set, OR
          - its PNG changed (sha256 differs from the recorded hash), OR
          - the recorded text was empty and it was not a blank page
            (previous OCR failed).
        """
        if force:
            return True
        rec = self.page_record(note_uuid, page_id)
        if rec is None:
            return True
        if rec.png_sha256 and rec.png_sha256 != png_sha256:
            return True
        if rec.last_artifact_id == "" and not rec.blank:
            return True  # prior attempt did not produce an artifact
        return False


__all__ = [
    "MANIFEST_SCHEMA",
    "PageRecord",
    "NoteRecord",
    "BooxSyncManifest",
]
