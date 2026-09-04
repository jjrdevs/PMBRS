"""Pin ADR-021 D1 ``hrv_proxy`` (windowed RMSSD over tier-1 HR means).

Pins:
- ``compute_proxy`` = RMSSD over adjacent diff of a list of bpm values
- ``proxy_for_window`` = trailing-10-bin band; ``None`` when < 2 bins in band
- ``proxy_bulk`` returns a dict of only the windows that have a proxy
- METHOD label is the pinned string
"""
from __future__ import annotations

import math

from pmbrs.ingestion.wearable import hrv_proxy  # noqa: F401


WINDOWS_N = hrv_proxy.WINDOWS_N
METHOD = hrv_proxy.METHOD
HrvProxy = hrv_proxy.HrvProxy
compute_proxy = hrv_proxy.compute_proxy
proxy_bulk = hrv_proxy.proxy_bulk
proxy_for_window = hrv_proxy.proxy_for_window
rolling_window = hrv_proxy.rolling_window


def _bin(start_ms, bpm=60.0):
    class _B:
        pass
    b = _B()
    b.start_ms = start_ms
    b.end_ms = start_ms + 60_000
    b.bpm = bpm
    return b


def _bins(n, start=0, bpm=60.0):
    return [_bin(start + i * 60_000, bpm) for i in range(n)]


class TestComputeProxy:
    def test_requires_at_least_two(self):
        try:
            compute_proxy([60.0])  # type: ignore[arg-type]
        except ValueError as exc:
            assert str(exc)
        else:
            raise AssertionError("expected ValueError")

    def test_constant_sequence_is_zero(self):
        assert compute_proxy([60.0, 60.0, 60.0]) == 0.0

    def test_alternating_diff(self):
        # [0, 10, 0, 10]: diffs = (10, -10, 10)  -> sqrt((100+100+100)/3)=sqrt(100)=10
        assert compute_proxy([0.0, 10.0, 0.0, 10.0]) == 10.0

    def test_symmetric_swing_5(self):
        # [60, 65, 70, 65, 60]: diffs=(5,5,-5,-5) -> sqrt(25) = 5
        assert abs(compute_proxy([60.0, 65.0, 70.0, 65.0, 60.0]) - 5.0) < 1e-9


class TestProxyForWindow:
    def test_none_when_single_bin_in_band(self):
        assert proxy_for_window(_bins(1), canonical_index=0) is None

    def test_full_10_bin_band(self):
        # 10 consecutive 60-s bins. Window 9's band is [0, 600s) — all 10 bins.
        bins = _bins(10, start=0, bpm=60.0)
        p = proxy_for_window(bins, canonical_index=9)
        assert p is not None
        assert p.canonical_index == 9
        assert p.bins_used == 10
        assert p.value_bpm == 0.0
        assert p.method == METHOD

    def test_sparse_2_bins_still_returned(self):
        # Bins at 0 and 540s. Window 9 band [0, 600s): both bins present.
        bins = [_bin(0, 60.0), _bin(540_000, 70.0)]
        p = proxy_for_window(bins, canonical_index=9)
        assert p is not None
        assert p.bins_used == 2
        assert p.value_bpm == 10.0

    def test_bins_used_reported(self):
        bins = _bins(10)
        p = proxy_for_window(bins, canonical_index=10)
        # Window 10 band [60s, 660s): bins idx 1..9 all in band -> 9 bins.
        assert p is not None
        assert p.bins_used == 9


class TestProxyBulk:


    def test_bulk_omits_windows_below_threshold(self):
        # Sparse: 3 bins. Windows 0..3 have <2 bins in their trailing-10 band
        # (band = 10 slots ending at (i+1)*60s), so they are omitted.
        bins = [_bin(0), _bin(300_000), _bin(600_000)]
        out = proxy_bulk(bins, list(range(0, 15)))
        for i in (0, 1, 2, 3):
            assert i not in out
        # Windows 4.. have >= 2 bins.
        for i in (4, 9, 14):
            assert i in out
        assert out[9].bins_used == 3

    def test_bulk_contiguous_10_bins(self):
        bins = _bins(10)
        out = proxy_bulk(bins, list(range(15)))
        # Constant bpm -> zero proxy everywhere there is a value.
        for i in range(15):
            if i in out:
                assert out[i].value_bpm == 0.0
        assert out[8].bins_used == 10
        assert out[9].bins_used == 10
        assert out[10].bins_used == 9

    def test_bulk_method_matches_method_const(self):
        out = proxy_bulk(_bins(10), [9])
        assert out[9].method == METHOD
        assert out[9].bins_used == 10
