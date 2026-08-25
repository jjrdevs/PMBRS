"""Journal enrichment — attach note-time + canonical-window alignment to a
cleaned ``raw/journal/boox.*.json`` record in place.

Why in place: one canonical record per (note, page) is a hard
downstream-invariant (``docs/storage/architecture.md`` §Lineage +
``pmbrs/core/storage.py`` ``StorageAdapter``). A fresh record per enrich
pass would create a lineage-fanout with no parent edge. In-place updates
keep ``artifactId`` + ``createdAtEpochMs`` stable — the record identity
survives; only the extension (``payload.noteTemporal``) is added.

Fields added (all inside ``payload`` to keep top-level 9-key canonical
shape intact — ``Artifact.extras`` preserves non-canonical top-level but
we want the extension visible in the payload where consumers naturally
look):

    noteTemporal: {
      firstWrittenMs    int,   # earliest stroke across shape/ + stash/
      lastEditedMs      int,   # latest stroke across shape/ + stash/
      modifiedStartMs   int,   # earliest post-first stroke in live shape/
      modifiedEndMs     int,   # latest stroke in live shape/
      durationSec       int,   # last_edited - first_written
      totalStrokes      int,
      liveStrokes       int,   # shape/ (current note state)
      archivedStrokes   int,   # stash/archivedShape/ (overwritten revisions)
      timezoneOffsetMin int,   # informational only
    }
    canonicalWindowGrid: {
      gridSeconds       int,   # 60
      anchor            str,   # "epoch" (provisional pending ADR-002)
      anchorNote        str,   # rationale, so the ADR can be cited later
      firstWindowIndex  int,   # floor(firstWrittenMs / 60_000)
      lastWindowIndex   int,   # floor(lastEditedMs   / 60_000)
      windowsCovered    int,   # last - first + 1
    }

Provenance additions:
    timestampSource          = "onyx-ksync-stroke-filenames"
    timestampExtractedAtMs   = extract time, epoch ms
    temporalEnriched         = True
    temporalExtractorVersion = "1.0"

The function is idempotent: running it twice on the same record produces
the same result (timestamps are device data; grid index is a pure
function of the timestamps; provenance fields are overwritten to the
current extract time).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .note_timestamps import NoteTiming

TEMPORAL_EXTRACTOR_VERSION = "1.0"
GRID_SECONDS = 60
GRID_ANCHOR = "epoch"  # provisional — ADR-002 is TBD on this choice
GRID_ANCHOR_NOTE = (
    "Provisional epoch-aligned 60s grid per docs/temporal/specification.md; "
    "ADR-002 (canonical window anchor) is unresolved. The index math is "
    "pure arithmetic so the ADR can be applied as a one-line transform "
    "when it lands (epoch ↔ midnight-local is a shift of the index by a "
    "per-day offset, no re-derivation)."
)


def apply_note_temporal(
    record: dict[str, Any],
    timing: NoteTiming,
    *,
    temporal_extracted_at_ms: int,
) -> dict[str, Any]:
    """Return a copy of ``record`` with the temporal + grid block attached.

    Does not mutate the input (so callers can keep the pre-enrich version
    for a diff / audit log if they want one).
    """
    out: dict[str, Any] = json.loads(json.dumps(record))  # deep-copy

    # -- 1. payload.noteTemporal ---------------------------------------------
    payload = out.get("payload")
    if not isinstance(payload, dict):
        raise ValueError(f"record has no dict payload (got {type(payload).__name__})")
    duration_sec = max(0, (timing.last_edited_ms - timing.first_written_ms) // 1000)
    payload["noteTemporal"] = {
        "firstWrittenMs": timing.first_written_ms,
        "lastEditedMs": timing.last_edited_ms,
        "modifiedStartMs": timing.modified_start_ms,
        "modifiedEndMs": timing.modified_end_ms,
        "durationSec": duration_sec,
        "totalStrokes": timing.total_strokes,
        "liveStrokes": timing.source_stroke_count,
        "archivedStrokes": timing.arch_stroke_count,
        "timezoneOffsetMin": timing.timezone_offset_min,
        # Device-local convenience (same clock that generated the strokes):
        "firstWrittenISO": _iso(timing.first_written_ms),
        "lastEditedISO": _iso(timing.last_edited_ms),
        "modifiedStartISO": _iso(timing.modified_start_ms),
        "modifiedEndISO": _iso(timing.modified_end_ms),
    }

    # -- 2. payload.canonicalWindowGrid --------------------------------------
    first_idx = timing.first_written_ms // (GRID_SECONDS * 1000)
    last_idx = timing.last_edited_ms // (GRID_SECONDS * 1000)
    payload["canonicalWindowGrid"] = {
        "gridSeconds": GRID_SECONDS,
        "anchor": GRID_ANCHOR,
        "anchorNote": GRID_ANCHOR_NOTE,
        "firstWindowIndex": int(first_idx),
        "lastWindowIndex": int(last_idx),
        "windowsCovered": int(last_idx - first_idx + 1),
        # Explicit UTC window boundaries so downstream doesn't need to
        # re-derive the index↔UTC relationship:
        "firstWindowStartMsUtc": int(first_idx * GRID_SECONDS * 1000),
        "lastWindowEndMsUtc": int((last_idx + 1) * GRID_SECONDS * 1000),
    }

    # -- 3. provenance additions ----------------------------------------------
    prov = out.get("provenanceMetadataJson")
    if prov is None:
        prov = {}
    elif isinstance(prov, str):
        try:
            prov = json.loads(prov)
        except (ValueError, TypeError):
            prov = {}
    if not isinstance(prov, dict):
        prov = {"_raw": prov}
    prov["timestampSource"] = "onyx-ksync-stroke-filenames"
    prov["timestampExtractedAtMs"] = temporal_extracted_at_ms
    prov["temporalEnriched"] = True
    prov["temporalExtractorVersion"] = TEMPORAL_EXTRACTOR_VERSION
    # Keep the rest of the provenance intact; only the three above added/overwritten.
    out["provenanceMetadataJson"] = prov
    return out


def _iso(ms: int) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def enrich_record_in_place(path: Path, record: dict[str, Any], timing: NoteTiming, *, now_ms: int) -> Path:
    """Write the enriched record back to ``path`` atomically (same filename =
    stable artifact identity — see module docstring on why in-place)."""
    enriched = apply_note_temporal(record, timing, temporal_extracted_at_ms=now_ms)
    tmp = path.with_name(path.name + ".enrich-tmp")
    tmp.write_text(json.dumps(enriched, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    path.replace(tmp) if False else tmp.replace(path)  # atomic on POSIX
    return path


__all__ = [
    "apply_note_temporal",
    "enrich_record_in_place",
    "TEMPORAL_EXTRACTOR_VERSION",
    "GRID_SECONDS",
    "GRID_ANCHOR",
]
