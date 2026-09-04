"""Canonical 60-second window grid alignment (ADR-021 D4, canonical window
contract).

The canonical grid is globally aligned to the epoch: window index ``i`` is
``[i * 60 000 ms, (i + 60) 000 ms)``. Every modality record that has a
definite start/end is attributed to the window containing its start
(boundary policy: start-inclusive), which matches the contract rule that
windows are the temporal backbone and all other resolution is a derived view.

This module is pure: given records, it returns per-window presence +
coverage. Absence is represented as coverage 0.0, never as a zero value
(missingness semantics contract).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

#: Grid resolution in ms (contract: typically 60 s).
RESOLUTION_MS = 60_000
#: Grid index 0 corresponds to 1970-01-01T00:00:00Z.
GRID_EPOCH_MS = 0


@dataclass
class GridWindow:
    """One canonical window with per-modality coverage.

    ``present`` maps modality -> present this window. ``coverage`` maps
    modality -> fraction of the window spanned by that modality's source
    records (0.0 when absent). Absent modalities have no numeric payload
    downstream; they appear only as ``False`` / ``0.0`` here.
    """

    canonical_index: int
    start_ms: int
    end_ms: int
    present: dict[str, bool] = field(default_factory=dict)
    coverage: dict[str, float] = field(default_factory=dict)
    #: modality -> record ids (source data_uuids) observed in this window
    sources: dict[str, list[str]] = field(default_factory=dict)


def window_for_ms(ts_ms: int) -> GridWindow:
    """The canonical window containing ``ts_ms``."""
    index = (ts_ms - GRID_EPOCH_MS) // RESOLUTION_MS
    start = GRID_EPOCH_MS + index * RESOLUTION_MS
    return GridWindow(
        canonical_index=int(index),
        start_ms=int(start),
        end_ms=int(start) + RESOLUTION_MS,
    )


def window_index_for_ms(ts_ms: int) -> int:
    return int((ts_ms - GRID_EPOCH_MS) // RESOLUTION_MS)


def _span_coverage(start_ms: int, end_ms: int, window: GridWindow) -> float:
    """Fraction of ``window`` overlapped by [start_ms, end_ms)."""
    lo = max(int(start_ms), window.start_ms)
    hi = min(int(end_ms), window.end_ms)
    if hi <= lo or window.end_ms <= window.start_ms:
        return 0.0
    overlap_ms = hi - lo
    return max(0.0, min(1.0, overlap_ms / (window.end_ms - window.start_ms)))


def _record_windows(start_ms: int, end_ms: int) -> list[int]:
    """Every canonical index spanned by [start_ms, end_ms)."""
    if end_ms <= start_ms:
        return [window_index_for_ms(start_ms)]
    first = window_index_for_ms(start_ms)
    last = window_index_for_ms(end_ms - 1)
    return list(range(first, last + 1))


def align_hr_bins(
    bins: Iterable,
    *,
    modality: str = "heart_rate",
) -> dict[int, GridWindow]:
    """Attribute 60-s HR bins onto the canonical grid.

    A bin whose width covers the whole window yields coverage 1.0; short
    bins (export quirk, e.g. 59-s) are scaled by overlap. Multiple bins in
    one window both count (coverage capped at 1.0).
    """
    out: dict[int, GridWindow] = {}
    for b in bins:
        for idx in _record_windows(b.start_ms, b.end_ms):
            win = out.get(idx)
            if win is None:
                win = GridWindow(
                    canonical_index=idx,
                    start_ms=GRID_EPOCH_MS + idx * RESOLUTION_MS,
                    end_ms=GRID_EPOCH_MS + (idx + 1) * RESOLUTION_MS,
                )
                out[idx] = win
            cov = max(win.coverage.get(modality, 0.0), _span_coverage(b.start_ms, b.end_ms, win))
            win.coverage[modality] = cov
            if cov > 0.0:
                win.present[modality] = True
            src = getattr(b, "data_uuid", "") or b.source_file
            if src and src not in win.sources.setdefault(modality, []):
                win.sources[modality].append(src)
    return out


def merge_windows(
    base: dict[int, GridWindow],
    extra: dict[int, GridWindow],
    *,
    modality: str | None = None,
) -> dict[int, GridWindow]:
    """Union two aligned maps (same modality), taking max coverage."""
    merged = {k: GridWindow(w.canonical_index, w.start_ms, w.end_ms, dict(w.present), dict(w.coverage), {m: list(v) for m, v in w.sources.items()}) for k, w in base.items()}
    for idx, w in extra.items():
        dst = merged.get(idx)
        if dst is None:
            merged[idx] = GridWindow(w.canonical_index, w.start_ms, w.end_ms, dict(w.present), dict(w.coverage), {m: list(v) for m, v in w.sources.items()})
            continue
        for m, flag in w.present.items():
            dst.present[m] = dst.present.get(m, False) or flag
        for m, cov in w.coverage.items():
            if cov > 0.0:
                dst.present[m] = True
            dst.coverage[m] = max(dst.coverage.get(m, 0.0), cov)
        for m, srcs in w.sources.items():
            for s in srcs:
                if s not in dst.sources.get(m, []):
                    dst.sources.setdefault(m, []).append(s)
    return merged


def align_hrv_windows(windows: Iterable, *, modality: str = "hrv") -> dict[int, GridWindow]:
    return align_recorded_windows(windows, modality=modality)


def align_recorded_windows(records: Iterable, *, modality: str) -> dict[int, GridWindow]:
    """Align any start/end-ms record (HRV / stress / sleep) onto the grid."""
    out: dict[int, GridWindow] = {}
    for rec in records:
        for idx in _record_windows(rec.start_ms, rec.end_ms):
            win = out.get(idx)
            if win is None:
                win = GridWindow(
                    canonical_index=idx,
                    start_ms=GRID_EPOCH_MS + idx * RESOLUTION_MS,
                    end_ms=GRID_EPOCH_MS + (idx + 1) * RESOLUTION_MS,
                )
                out[idx] = win
            cov = max(win.coverage.get(modality, 0.0), _span_coverage(rec.start_ms, rec.end_ms, win))
            win.coverage[modality] = cov
            if cov > 0.0:
                win.present[modality] = True
            src = getattr(rec, "data_uuid", "") or getattr(rec, "source_file", "") or getattr(rec, "sleep_id", "")
            if src and src not in win.sources.setdefault(modality, []):
                win.sources[modality].append(src)
    return out


__all__ = [
    "RESOLUTION_MS",
    "GRID_EPOCH_MS",
    "GridWindow",
    "window_for_ms",
    "window_index_for_ms",
    "align_hr_bins",
    "align_recorded_windows",
    "align_hrv_windows",
    "merge_windows",
]
