"""Manifest seeder — rebuild sync-manifest state from already-ingested artifacts.

The journal store under ``~/.pmbrs-private/store/raw/journal/`` is the source
of truth for what has already been OCR'd + committed. On a cold start (or after
a ``/tmp`` workdir wipe), the manifest is empty and the producer would naively
re-OCR everything. :func:`seed_manifest_from_store` walks the existing ``boox.*.json``
artifacts and reconstructs the ``last_artifact_id`` / ``png_sha256`` /
``png_dims`` fields the producer checks in ``needs_ocr``, so a follow-up run
skips pages already committed.

Blank pages are *not* recoverable from the store (they intentionally produce
no artifact). That's acceptable: they will be re-OCR'd once and re-marked as
blank. The cost of one extra OCR pass on a handful of blank pages is far
less than re-OCR-ing the 16 notes we already have text for.
"""
from __future__ import annotations

import glob
import json
from pathlib import Path

from .manifest import BooxSyncManifest, NoteRecord, PageRecord


def seed_manifest_from_store(
    manifest_path: str | Path,
    raw_root: str | Path = "/home/jjrdev/.pmbrs-private/store/raw",
    *,
    device_serial: str = "",
) -> BooxSyncManifest:
    """Return a manifest pre-populated from the journal artifacts in the store.

    Idempotent: running this twice with the same store state produces the same
    manifest. The result is **not** saved by this function — the caller decides.
    Pass ``manifest_path`` to :func:`BooxSyncManifest.save` if/when you want to
    persist it.
    """
    manifest = BooxSyncManifest.load(manifest_path, device_serial=device_serial)
    raw_journal = Path(raw_root) / "journal"
    boox_files = sorted(glob.glob(str(raw_journal / "boox.*.json")))

    ingested_in_run = 0
    for path in boox_files:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if data.get("ingestStatus") != "accepted":
            continue
        payload = data.get("payload") or {}
        note_uuid = str(payload.get("noteUuid") or "")
        if not note_uuid:
            continue
        page_image = payload.get("pageImage") or {}
        dims = list(page_image.get("dimensions") or [0, 0])
        if len(dims) < 2:
            dims = [0, 0]
        artifact_id = str(data.get("artifactId") or "")
        ocr_engine = str(payload.get("ocrEngine") or "")
        ingested_ms = int(data.get("ingestedAtEpochMs") or data.get("createdAtEpochMs") or 0)

        note_rec = manifest.notes.get(note_uuid)
        if note_rec is None:
            note_rec = NoteRecord(note_uuid=note_uuid)
            manifest.notes[note_uuid] = note_rec

        # Replace (not duplicate) a page with the same id, if present.
        # The BOOX producer uses `page_id = note_uuid` for the single cover page
        # (single-page notes are the common case in Stage 1); see `producer.py` and
        # `BooxCollector.resolve_pages`.
        page_id = note_uuid
        existing = next((p for p in note_rec.pages if p.page_id == page_id), None)
        if existing is None:
            existing = PageRecord(
                page_id=page_id,
                page_order=int(payload.get("pageOrder") or 1),
                source=str(payload.get("source") or "cover"),
                png_rel_path=str(payload.get("sourcePath") or ""),
                png_sha256="",
                png_dims=(0, 0),
            )
            note_rec.pages.append(existing)
        existing.page_order = int(payload.get("pageOrder") or 1)
        existing.source = str(payload.get("source") or existing.source)
        existing.png_rel_path = str(payload.get("sourcePath") or existing.png_rel_path)
        existing.png_sha256 = str(page_image.get("sha256") or "")
        existing.png_dims = (int(dims[0]), int(dims[1]))
        existing.last_ocr_at_ms = int(ingested_ms)
        existing.last_ocr_engine = ocr_engine
        existing.last_artifact_id = artifact_id
        existing.blank = False
        ingested_in_run += 1

    return manifest


__all__ = ["seed_manifest_from_store"]
