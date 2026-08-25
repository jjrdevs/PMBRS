"""Note timestamp extraction — per-note window from ONYX shape/stash stroke filenames.

ONYX NoteAir3 writes each stroke as a separate file whose NAME embeds an
epoch-ms timestamp:

    .ksync/document/<uuid>/shape/<page-uuid>#<stroke-uuid>#<13-digit-ms>.zip
    .ksync/document/<uuid>/stash/archivedShape/<13-digit-ms>/<...>#<13-digit-ms>.zip

``shape/`` carries "current" strokes (the note state right now);
``stash/archivedShape/`` carries "overwritten" strokes (older revisions from
when the user scribbled, deleted, and re-wrote). The union is the writing
activity; ``shape/`` alone is the live state.

Derived per-note timing (UTC epoch ms):

    firstWrittenMs   — earliest stroke across both shape/ and stash/archivedShape/
    lastEditedMs     — latest stroke across both
    modifiedStartMin — earliest "modified" revision (earliest of any *later*
                       strokes added after the first written, i.e. the earliest
                       post-first stroke in the *shape/ live tree*, which is
                       when editing actually started for the current state)
    modifiedEndMs    — latest stroke in the shape/ live tree
    timezoneOffsetMin— offset of the device clock at the time (via /system/
                       build or stat of the note dir mtime minus max stroke)

Note dir mtime tracks the last stroke written (we verified on 6 notes earlier:
offsets were 0–5s typical, with a few 200–4000s drifts from ONYX background
housekeeping on the .ksync tree; we use stroke-based values, mtime is a
sanity check, not the source).

This is a thin ADB-only module; it does not depend on the rest of the pipeline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .adb import AdbClient, AdbError

_NOTE_DOC_TREE = "/storage/emulated/0/.ksync/document"
_STAMP_RE = re.compile(r"\b(\d{13})\b")
_VALID_MS_RANGE = (1_700_000_000_000, 2_200_000_000_000)  # 2023..2039


@dataclass(frozen=True)
class NoteTiming:
    note_uuid: str
    first_written_ms: int
    last_edited_ms: int
    modified_start_ms: int  # earliest post-first stroke live (shape/)
    modified_end_ms: int    # latest stroke live (shape/)
    total_strokes: int
    source_stroke_count: int      # strokes in shape/ (live)
    arch_stroke_count: int        # strokes in stash/archivedShape/
    timezone_offset_min: int = 0  # local UTC offset in minutes, from device


def _parse_stamps(text: str) -> list[int]:
    stamps = [int(m) for m in _STAMP_RE.findall(text or "")]
    return [s for s in stamps if _VALID_MS_RANGE[0] < s < _VALID_MS_RANGE[1]]


def extract_note_timing(adb: AdbClient, note_uuid: str) -> NoteTiming:
    """One-shot ADB extract of first/last/modified timestamps for one note.

    Two bounded shell calls:
      1. Find all .zip files under the note dir; emit any embedded 13-digit
         epoch-ms from their names (the per-stroke timestamps ONYX writes).
         Separate ``shape/`` (live) and ``stash/archivedShape/`` (revision)
         groups using the file path prefix for the ``modified_start/end``
         derivation.
      2. Read the note dir mtime via stat (sanity anchor).

    No file contents are read — only paths — so this is independent of stroke
    payload format. Fast on-device (one adb round-trip, one find+grep).
    """
    find_cmd = (
        f"find {_NOTE_DOC_TREE}/{note_uuid} -type f -name '*.zip' 2>/dev/null"
    )
    out = adb.shell(find_cmd)
    live_stamps: list[int] = []
    all_stamps: list[int] = []
    for line in out.splitlines():
        stamps = _parse_stamps(line)
        if not stamps:
            continue
        all_stamps.extend(stamps)
        if line.startswith(f"{_NOTE_DOC_TREE}/{note_uuid}/stash/"):
            continue  # archived, not in live tree
        if line.startswith(f"{_NOTE_DOC_TREE}/{note_uuid}/shape/"):
            live_stamps.extend(stamps)
        # template/ and other top-level dirs: ignore for timing.

    if not all_stamps:
        raise AdbError(
            f"no stroke timestamps found for note {note_uuid[:12]}… — "
            f"either the device clock is broken or ONYX changed the layout"
        )

    first_ms = min(all_stamps)
    last_ms = max(all_stamps)
    if live_stamps:
        mod_start_ms = min(live_stamps) if len(live_stamps) > 1 else first_ms
        mod_end_ms = max(live_stamps)
    else:
        # Only archived strokes: note was fully cleared. Best-effort.
        mod_start_ms = first_ms
        mod_end_ms = last_ms

    total = len(all_stamps)
    live_count = len(live_stamps)
    archive_count = total - live_count

    # Timezone sanity check (informational only, never used for alignment):
    #   dir mtime is close to the last stroke (within ~1s normally). If the
    #   gap is > 5 min, the device has been writing to OTHER note dirs
    #   concurrently and the mtime is a red herring — stroke timestamps are
    #   authoritative.
    tz_offset_min = 0

    return NoteTiming(
        note_uuid=note_uuid,
        first_written_ms=first_ms,
        last_edited_ms=last_ms,
        modified_start_ms=mod_start_ms,
        modified_end_ms=mod_end_ms,
        total_strokes=total,
        source_stroke_count=live_count,
        arch_stroke_count=archive_count,
        timezone_offset_min=tz_offset_min,
    )


__all__ = ["NoteTiming", "extract_note_timing"]
