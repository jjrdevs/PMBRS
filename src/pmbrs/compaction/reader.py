"""Read canonical 60-s window artifacts from the PMBRS raw store.

The raw store is one JSON object per file (``<artifactId>-<createdAtMs>.json``,
ADR-017 D2). We scan ``<raw_root>/mobile/`` (the wearable producer's source)
and return :class:`CompactionWindow` rows for every ``canonical_window``
artifact. Other sources and non-window payloads are skipped so the reader is
safe to point at any of the producer's sink roots.

No pyarrow / pandas required here — pure stdlib (json + pathlib), so compaction
stays usable on a bare interpreter even if the parquet backend is absent.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

#: Canonical window resolution (ADR-021 D4: one artifact per 60-s grid cell).
CANONICAL_WINDOW_MS = 60_000


def _parse_iso_ms(value: Any) -> int | None:
    """Parse an ISO-8601 timestamp (e.g. ``2026-08-30T03:05:00.000Z``) to ms."""
    if not isinstance(value, str):
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return int(parsed.timestamp() * 1000)

#: Sources the wearable producer writes under (see ``build_window_artifact``):
#: the source-dir contract pins ``mobile`` -> ``store/raw/mobile/``.
WINDOW_SOURCE_DIR = "mobile"
WINDOW_KIND = "canonical_window"

#: Modalities we know how to reduce in a rollup (the wearable set, ADR-021 D5).
KNOWN_MODALITIES = ("heart_rate", "hrv_proxy", "hrv", "stress", "sleep_stage")


@dataclass(frozen=True)
class CompactionWindow:
    """One 60-s canonical window, flattened for rollup / parquet.

    ``start_ms`` / ``end_ms`` are the window bounds (epoch ms, tz-naive on the
    grid — the producer aligns to the absolute 60-s grid, ADR-021).
    ``present`` mirrors ``payload.modalities_present`` and ``coverage`` mirrors
    ``payload.missingness_metadata.modality_coverage``. ``modality_payloads``
    is the raw ``payload.payload.modalities`` dict (only present modalities).
    """

    artifact_id: str
    canonical_index: int
    start_ms: int
    end_ms: int
    present: dict[str, bool] = field(default_factory=dict)
    coverage: dict[str, float] = field(default_factory=dict)
    modality_payloads: dict[str, Any] = field(default_factory=dict)
    device_alias: str = ""
    source_file: str = ""

    def present_modalities(self) -> tuple[str, ...]:
        return tuple(m for m in KNOWN_MODALITIES if self.present.get(m, False))


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _artifact_to_window(record: dict[str, Any], source_file: str) -> CompactionWindow | None:
    """Coerce one raw-store record into a :class:`CompactionWindow`, or None.

    Returns None when the record is not a wearable canonical window (any
    modality set), so callers can feed mixed source dirs without filtering.
    """
    payload = record.get("payload")
    if not isinstance(payload, dict) or payload.get("kind") != WINDOW_KIND:
        return None

    window = payload.get("window") or {}

    # The window block carries ISO-8601 ``start_time``/``end_time`` strings
    # (see ``build_window_artifact.window_block``); accept the epoch-ms
    # aliases as a forward-compat escape hatch. ``created_at`` is stamped with
    # the window's start by the producer, so it is a sane last-resort fallback.
    start_ms = _as_int(window.get("startEpochMs") or window.get("start_ms"), default=0)
    end_ms = _as_int(window.get("endEpochMs") or window.get("end_ms"), default=0)
    if start_ms <= 0:
        start_ms = _parse_iso_ms(window.get("start_time")) or 0
    if end_ms <= 0:
        end_ms = _parse_iso_ms(window.get("end_time")) or 0
    if end_ms <= start_ms:
        end_ms = start_ms + CANONICAL_WINDOW_MS
    if start_ms <= 0:
        return None

    index = _as_int(window.get("canonical_index"), default=0)
    if index <= 0:
        # The index is a deterministic function of the grid cell; derive it
        # when the producer did not stamp it (never trust a 0/sentinel value).
        index = start_ms // CANONICAL_WINDOW_MS

    present = payload.get("modalities_present") or {}
    missingness = payload.get("missingness_metadata") or {}
    coverage = missingness.get("modality_coverage") or {}
    inner = payload.get("payload") or {}
    modalities = inner.get("modalities") or {}

    return CompactionWindow(
        artifact_id=str(record.get("artifactId") or ""),
        canonical_index=index,
        start_ms=start_ms,
        end_ms=end_ms,
        present={str(k): bool(v) for k, v in present.items()},
        coverage={str(k): float(v) for k, v in coverage.items()},
        modality_payloads=modalities,
        device_alias=str(record.get("deviceAlias") or ""),
        source_file=source_file,
    )


def iter_store_records(raw_root: str | Path, source: str = WINDOW_SOURCE_DIR) -> Iterable[tuple[dict[str, Any], str]]:
    """Yield ``(record, relative_path)`` for every JSON file under
    ``raw_root/<source>/``. Skips unreadable/partial files silently (the
    producer writes atomically, but a crash mid-run must not break a rollup).
    """
    root = Path(raw_root)
    if not root.is_dir():
        return
    src_dir = root / source
    if not src_dir.is_dir():
        src_dir = root  # allow pointing directly at a source dir
    for path in sorted(src_dir.rglob("*.json")):
        if not path.is_file():
            continue
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        yield record, str(path)


def load_windows(raw_root: str | Path, source: str = WINDOW_SOURCE_DIR) -> list[CompactionWindow]:
    """Load every wearable canonical window under ``raw_root``.

    ``raw_root`` may be the store root (``.../store/raw``) — the source dir is
    appended automatically — or a source dir already (``.../store/raw/mobile``).
    Deterministically ordered by ``(start_ms, artifact_id)``.
    """
    windows: list[CompactionWindow] = []
    for record, rel in iter_store_records(raw_root, source=source):
        window = _artifact_to_window(record, rel)
        if window is not None:
            windows.append(window)
    windows.sort(key=lambda w: (w.start_ms, w.artifact_id))
    return windows


__all__ = [
    "CompactionWindow",
    "KNOWN_MODALITIES",
    "WINDOW_SOURCE_DIR",
    "load_windows",
    "iter_store_records",
]
