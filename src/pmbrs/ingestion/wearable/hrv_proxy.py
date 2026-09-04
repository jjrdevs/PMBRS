"""Tier-2 ``hrv_proxy`` — windowed variability over tier-1 HR bins (ADR-021 D1).

``hrv_proxy`` is **not** HRV. It is an adjacent-difference variability
measure computed over consecutive 60-s HR *means* (bpm). It is a
``category=inferred`` signal and MUST be labeled ``hrv_proxy`` everywhere
(never stored as ``hrv``), per ADR-021 D1.

Deterministic definition (unit-test-pinned)::

    For canonical window with index i (band B_i = [i*60s, (i+1)*60s)), the
    rolling window is the trailing 10 bins (chronological) whose start falls
    in [i*60s - 9*60s, (i+1)*60s).

        diffs  = [bpm[k] - bpm[k-1] for k in 1..(m-1)]   # m bins in window
        proxy  = sqrt( mean( d^2 for d in diffs ) )       # RMSSD-over-bpm

Units: bpm. Fewer than 2 usable bins in the rolling window -> no proxy for
that canonical window (``None``); the window is still emitted, with
``hrv_proxy`` simply absent (missingness semantics: absent != zero).
The ``bins_used`` count (< 10) is recorded on emitted windows so sparse
regions stay visible.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from bisect import bisect_left, bisect_right

from .grid import GRID_EPOCH_MS, RESOLUTION_MS

#: Rolling window length in bins (10 min at 60-s resolution).
WINDOWS_N = 10
#: Method label; pinned in artifact payloads and provenance.
METHOD = "rolling_rmssd_60s"


@dataclass(frozen=True)
class HrvProxy:
    canonical_index: int
    value_bpm: float  # root-mean-square of adjacent bpm differences
    bins_used: int
    method: str = METHOD


def compute_proxy(bpm_values: list[float]) -> float:
    """RMSSD over adjacent differences of a list of bpm values.

    Requires >= 2 values; raises ValueError otherwise (a single bin has no
    variability defined).
    """
    if len(bpm_values) < 2:
        raise ValueError("hrv_proxy requires >= 2 bins in the window")
    diffs = (bpm_values[i] - bpm_values[i - 1] for i in range(1, len(bpm_values)))
    sq_sum = sum(d * d for d in diffs)
    n = len(bpm_values) - 1
    return math.sqrt(sq_sum / n)


def _bin_starts(sorted_bins: list) -> list[int]:
    return [b.start_ms for b in sorted_bins]


def rolling_window(
    sorted_bins: list,
    canonical_index: int,
    windows_n: int = WINDOWS_N,
    _starts: list[int] | None = None,
) -> list:
    """Bins (chronological) in the rolling band ending at canonical ``i``.

    Band = [i*RES - (n-1)*RES, (i+1)*RES); only bins whose ``start_ms`` falls
    in the band are returned, in ``start_ms`` order (ties broken by end).
    ``_starts`` is an optional precomputed ``start_ms`` list matching
    ``sorted_bins`` (used by :func:`proxy_bulk`) to keep lookups O(log n).
    """
    band_start = GRID_EPOCH_MS + canonical_index * RESOLUTION_MS - (windows_n - 1) * RESOLUTION_MS
    band_end = GRID_EPOCH_MS + (canonical_index + 1) * RESOLUTION_MS
    if _starts is None:
        _starts = _bin_starts(sorted_bins)
    lo = bisect_left(_starts, band_start)
    hi = bisect_right(_starts, band_end)
    return sorted_bins[lo:hi]  # already start_ms-ordered by contract


def proxy_for_window(
    sorted_bins: list,
    canonical_index: int,
    windows_n: int = WINDOWS_N,
    _starts: list[int] | None = None,
) -> HrvProxy | None:
    """``hrv_proxy`` for canonical window ``i`` (ADR-021 D1).

    ``sorted_bins``: bin-like objects with ``bpm``/``start_ms``/``end_ms``,
    sorted by ``start_ms``. Returns ``None`` when < 2 usable bins are in band.
    """
    band = rolling_window(sorted_bins, canonical_index, windows_n, _starts=_starts)
    if len(band) < 2:
        return None
    val = compute_proxy([float(b.bpm) for b in band])
    return HrvProxy(
        canonical_index=canonical_index,
        value_bpm=val,
        bins_used=len(band),
        method=METHOD,
    )


def proxy_bulk(
    sorted_bins: list,
    indices: list[int],
    windows_n: int = WINDOWS_N,
) -> dict[int, HrvProxy]:
    """Compute :class:`HrvProxy` for many windows in one pass (O(log n) each).

    Reuses a single precomputed ``start_ms`` index so a 40k+ window run stays
    fast. Indices producing < 2 bins in band are simply omitted from the
    return dict (missingness semantics: absent != zero).
    """
    starts = _bin_starts(sorted_bins)
    out: dict[int, HrvProxy] = {}
    for i in indices:
        p = proxy_for_window(sorted_bins, i, windows_n, _starts=starts)
        if p is not None:
            out[i] = p
    return out


__all__ = [
    "WINDOWS_N",
    "METHOD",
    "HrvProxy",
    "compute_proxy",
    "rolling_window",
    "proxy_for_window",
    "proxy_bulk",
]
