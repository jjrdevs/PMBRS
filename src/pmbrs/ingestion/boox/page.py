"""Data types for the BoOX note ingestion pipeline."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NoteDir:
    """One BoOX note directory on the device."""

    note_uuid: str
    remote_path: str       # /storage/emulated/0/.ksync/document/<uuid>
    mtime_ms: int = 0      # filesystem mtime (device time); 0 = unknown


@dataclass(frozen=True)
class PageRef:
    """One resolved rendered page belonging to a note.

    For the cover fallback (Stage 1 default, single-page notes):
        source    = "cover"
        page_id   = <note-uuid>
        png_rel   = ".noteCache/thumbnail/<uuid>.png"

    For page-dir pages (multi-page notes):
        source    = "page"
        page_id   = <page-dir 32-hex id>
        png_rel   = ".noteCache/thumbnail/page/<pageid>/<hash>.png"
    """

    note_uuid: str
    page_id: str
    page_order: int        # 1-based ordinal position within the note
    png_rel: str           # relative to /storage/emulated/0/
    png_bytes: int = 0
    png_sha256: str = ""
    png_dims: tuple[int, int] = (0, 0)
    source: str = "cover"  # "cover" | "page"
