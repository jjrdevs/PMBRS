"""Inbox collector — reads note page PNGs from the local device-push inbox.

Implements the same collector interface as ``BooxCollector`` (adb.py) but
sources pages from ``~/.pmbrs-private/store/inbox/boox/<note_uuid>/<page>.png``
instead of pulling over ADB. Drop-in replacement in ``BooxProducer.run``.

Layout (matches the device app's upload):
    inbox/boox/
      <32-hex-note-uuid>/
        <page-id>.png          e.g. p0001.png (cover), p0002.png (page 2)

Page ordering: filename sort order (p0001 → p0002 → …). The device app
sets pageOrder=1 for the cover render; multi-page notes will use the
numeric suffix.

ADR-020 D5: "same page, same on-disk name across transports" — the artifact
fingerprint (sha256 of the PNG) is transport-agnostic, so the manifest's
``needs_ocr`` check works identically whether the page came over ADB or
the inbox.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from .adb import PngFile, png_dimensions

_UUID_RE = re.compile(r"^[0-9a-f]{32}$")


class InboxCollector:
    """Read-only enumeration of BoOX notes + renders from the local inbox.

    Drop-in for ``BooxCollector``: exposes the same methods
    (list_notes, note_dir_mtime_ms, resolve_pages, pull_page).

    ``.adb`` is deliberately absent so ``BooxProducer._adb_serial()``
    returns "" via its existing ``except AttributeError`` fallback —
    the artifact records ``transport=inbox`` cleanly.
    """

    def __init__(self, inbox_root: Path, model_name: str = "NoteAir3") -> None:
        self.inbox_root = Path(inbox_root)
        self.model_name = model_name
        self.transport_name = "inbox"  # artifact provenance (ADR-020 D5)

    def list_notes(self) -> list[str]:
        """Note UUIDs (32-hex dir names) in the inbox."""
        if not self.inbox_root.is_dir():
            return []
        entries = [e.name for e in self.inbox_root.iterdir() if e.is_dir()]
        return sorted(e for e in entries if _UUID_RE.match(e))

    def note_dir_mtime_ms(self, note_uuid: str) -> int:
        """Best-effort mtime (ms) of the most recent page in this note's inbox dir."""
        note_dir = self.inbox_root / note_uuid
        if not note_dir.is_dir():
            return 0
        pages = list(note_dir.glob("*.png"))
        if not pages:
            return 0
        try:
            return int(max(p.stat().st_mtime for p in pages) * 1000)
        except OSError:
            return 0

    def resolve_pages(self, note_uuid: str) -> list[tuple[str, str, int]]:
        """Return [(page_id, local_png_path, page_order)] for a note, sorted by order.

        page_id = "<filename>" (without extension) so the manifest key is
        stable and readable. E.g. p0001.png  →  page_id "p0001".
        """
        note_dir = self.inbox_root / note_uuid
        if not note_dir.is_dir():
            return []
        pages = sorted(note_dir.glob("*.png"), key=lambda p: p.name)
        result: list[tuple[str, str, int]] = []
        for order, p in enumerate(pages, start=1):
            result.append((p.stem, str(p), order))
        return result

    def pull_page(self, page_id: str, local_path: str, workdir: Path) -> PngFile:
        """Read a page PNG from the local inbox. No network, no ADB.

        The file is already on disk — we just copy it into the workdir
        for the producer's convenience and compute the fingerprint.
        """
        src = Path(local_path)
        if not src.is_file():
            raise FileNotFoundError(f"inbox page missing: {local_path}")
        local = workdir / f"{page_id}.png"
        local.parent.mkdir(parents=True, exist_ok=True)
        local.write_bytes(src.read_bytes())
        data = local.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        return PngFile(
            local_path=local,
            remote_rel=f"boox/inbox/{src.parent.name}/{src.name}",
            sha256=sha,
            dims=png_dimensions(data),
            size_bytes=len(data),
        )


__all__ = ["InboxCollector"]

