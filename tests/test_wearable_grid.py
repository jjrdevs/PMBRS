"""Unit tests for the wearable canonical-grid aligner (ADR-021 D4).

Pins the pure functions in ``pmbrs.ingestion.wearable.grid``. Coverage is
``max`` per-window overlap fraction, capped at 1.0 (a record attributes to
EVERY canonical window it spans; the docstring "multiple bins both count"
is realized as max-overlap so two half-bins in one window read 0.5).
"""
from __future__ import annotations

from pmbrs.ingestion.wearable.grid import (
    RESOLUTION_MS,
    GridWindow,
    align_hrv_windows,
    align_hr_bins,
    align_recorded_windows,
    merge_windows,
    window_for_ms,
    window_index_for_ms,
)
from pmbrs.ingestion.wearable.model import HRBin, HRVWindow


class _FakeRec:
    def __init__(self, start_ms, end_ms, src=""):
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.source_file = src


class TestWindowMath:
    def test_window_for_ms_epoch_alignment(self):
        w = window_for_ms(0)
        assert w.canonical_index == 0
        assert w.start_ms == 0
        assert w.end_ms == RESOLUTION_MS

        w = window_for_ms(30_000)
        assert w.canonical_index == 0

        w = window_for_ms(61_000)
        assert w.canonical_index == 1
        assert w.start_ms == 60_000
        assert w.end_ms == 120_000

    def test_window_index_for_ms(self):
        assert window_index_for_ms(59_999) == 0
        assert window_index_for_ms(60_000) == 1
        assert window_index_for_ms(123_456_789) == 123_456_789 // 60_000

    def test_window_contains_ts(self):
        ts = 1_800_000_000_000
        w = window_for_ms(ts)
        assert w.start_ms % RESOLUTION_MS == 0
        assert w.start_ms <= ts < w.end_ms
        assert w.canonical_index == ts // RESOLUTION_MS


class TestAlignHrBins:
    def _bin(self, start, end, data_uuid=""):
        return HRBin(start_ms=start, end_ms=end, bpm=60.0, bpm_min=50.0,
                     bpm_max=70.0, data_uuid=data_uuid, source_file="")

    def test_full_window_bin_coverage_1(self):
        out = align_hr_bins([self._bin(0, 60_000, "u1")])
        assert 0 in out
        assert out[0].coverage["heart_rate"] == 1.0
        assert out[0].present["heart_rate"] is True
        assert out[0].sources["heart_rate"] == ["u1"]

    def test_short_bin_scales_by_overlap(self):
        out = align_hr_bins([self._bin(0, 30_000, "u1")])
        assert out[0].coverage["heart_rate"] == 0.5

    def test_two_adjacent_half_bins_max_overlap(self):
        # Max-overlap (not sum): two 30-s bins each cover 50% -> 0.5 capped result.
        out = align_hr_bins([self._bin(0, 30_000), self._bin(30_000, 60_000)])
        assert out[0].coverage["heart_rate"] == 0.5

    def test_spanning_bin_attributes_to_each_window(self):
        # [30s, 90s) overlaps window 0 (50%) and window 1 (50%).
        out = align_hr_bins([self._bin(30_000, 90_000)])
        assert set(out) == {0, 1}
        assert out[0].coverage["heart_rate"] == 0.5
        assert out[1].coverage["heart_rate"] == 0.5

    def test_sources_dedup(self):
        bins = [
            self._bin(0, 60_000, "u1"),
            self._bin(0, 60_000, "u1"),
        ]
        out = align_hr_bins(bins)
        assert out[0].sources["heart_rate"] == ["u1"]

    def test_multiple_distinct_uuids_accrued(self):
        out = align_hr_bins([self._bin(0, 60_000, "a"), self._bin(0, 60_000, "b")])
        assert out[0].sources["heart_rate"] == ["a", "b"]


class TestAlignHrvWindows:
    def test_clean_3min_window_full_coverage(self):
        # [120s, 300s) == windows 2,3,4 each full.
        w = HRVWindow(start_ms=120_000, end_ms=300_000, sdnn_ms=40.0, rmssd_ms=35.0)
        out = align_hrv_windows([w])
        assert set(out) == {2, 3, 4}
        for idx in (2, 3, 4):
            assert out[idx].coverage["hrv"] == 1.0
            assert out[idx].present["hrv"] is True

    def test_hrv_modality_param(self):
        rec = HRVWindow(start_ms=90_000, end_ms=150_000, sdnn_ms=40.0, rmssd_ms=35.0)
        out = align_hrv_windows([rec])  # [90s,150s): window 1 full, window 2 full
        assert 1 in out and 2 in out

    def test_align_recorded_windows_modality_param(self):
        rec = _FakeRec(60_000, 120_000, src="sleep-1")
        out = align_recorded_windows([rec], modality="stress")
        assert out[1].present["stress"] is True
        assert out[1].coverage["stress"] == 1.0


class TestMergeWindows:
    def test_union_two_modality_maps(self):
        a = {0: GridWindow(0, 0, 60_000, {"heart_rate": True},
                           {"heart_rate": 1.0}, {"heart_rate": ["u1"]})}
        b = {0: GridWindow(0, 0, 60_000, {"hrv": True},
                          {"hrv": 0.5}, {"hrv": ["w1"]}),
             1: GridWindow(1, 60_000, 120_000, {"hrv": True},
                           {"hrv": 1.0}, {"hrv": ["w2"]})}
        merged = merge_windows(a, b)
        assert set(merged) == {0, 1}
        assert merged[0].present["heart_rate"] is True
        assert merged[0].present["hrv"] is True
        assert merged[0].sources["heart_rate"] == ["u1"]
        assert merged[0].sources["hrv"] == ["w1"]

    def test_merge_takes_max_coverage(self):
        a = {0: GridWindow(0, 0, 60_000, {"hrv": True},
                           {"hrv": 0.5}, {"hrv": ["w1"]})}
        b = {0: GridWindow(0, 0, 60_000, {"hrv": True},
                          {"hrv": 1.0}, {"hrv": ["w2"]})}
        merged = merge_windows(a, b)
        assert merged[0].coverage["hrv"] == 1.0
        assert merged[0].sources["hrv"] == ["w1", "w2"]
