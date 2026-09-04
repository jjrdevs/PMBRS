"""Pin the pure parser functions in ``pmbrs.ingestion.wearable.parsers``.

Real export shapes (captured from the adb-pulled ``/tmp/pmbrs_export``):

* HR bin JSON  -> array of
  ``{heart_rate, heart_rate_max, heart_rate_min, start_time, end_time}``
* HRV JSON     -> array of
  ``{start_time, end_time, sdnn, rmssd}``   (values already in ms)

Pins: field mapping, malformed-record skipping, corrupt-timestamp filtering,
and the rel_path dispatch of ``parse_file``.
"""
from __future__ import annotations

import json

from pmbrs.ingestion.wearable import parsers as P
from pmbrs.ingestion.wearable.model import HRBin, HRVWindow


def _hr_json(*recs: dict) -> str:
    return json.dumps(list(recs))


class TestIterHrBins:
    def test_maps_real_shape(self):
        payload = [
            {
                "heart_rate": 87.0,
                "heart_rate_max": 91.0,
                "heart_rate_min": 85.0,
                "start_time": 1787709540000,
                "end_time": 1787709599000,
            }
        ]
        out = list(P.iter_hr_bins(payload, source_file="x"))
        assert len(out) == 1
        b = out[0]
        assert isinstance(b, HRBin)
        assert b.bpm == 87.0
        assert b.bpm_min == 85.0
        assert b.bpm_max == 91.0
        assert b.start_ms == 1787709540000
        assert b.end_ms == 1787709599000
        assert b.source_file == "x"

    def test_skips_records_missing_required_fields(self):
        payload = [
            {"start_time": 1, "end_time": 2},          # no heart_rate
            {"heart_rate": 60.0},                       # no times
            "not-a-dict",                               # wrong type
            {"heart_rate": 72.0, "start_time": 10, "end_time": 20},
        ]
        out = list(P.iter_hr_bins(payload))
        assert len(out) == 1
        assert out[0].bpm == 72.0

    def test_defaults_min_max_to_zero(self):
        out = list(P.iter_hr_bins([{"heart_rate": 60.0, "start_time": 10, "end_time": 20}]))
        assert out[0].bpm_min == 0.0
        assert out[0].bpm_max == 0.0

    def test_empty_payload(self):
        assert list(P.iter_hr_bins([])) == []
        assert list(P.iter_hr_bins(None)) == []


class TestIterHrvWindows:
    def test_maps_real_shape(self):
        payload = [
            {"start_time": 1787350667259, "end_time": 1787350967512,
             "sdnn": 53.980747, "rmssd": 60.412968}
        ]
        out = list(P.iter_hrv_windows(payload, source_file="y"))
        assert len(out) == 1
        w = out[0]
        assert isinstance(w, HRVWindow)
        assert w.sdnn_ms == 53.980747
        assert w.rmssd_ms == 60.412968
        assert w.start_ms == 1787350667259
        assert w.end_ms == 1787350967512
        assert w.source_file == "y"

    def test_drops_corrupt_timestamps(self):
        payload = [
            {"start_time": 0, "end_time": 100, "sdnn": 1, "rmssd": 1},   # start<=0
            {"start_time": 200, "end_time": 100, "sdnn": 1, "rmssd": 1},  # end<start
            {"start_time": 100, "end_time": 200, "sdnn": 1, "rmssd": 1},  # ok
            {"start_time": 100, "end_time": 200, "rmssd": 1},            # no sdnn
        ]
        out = list(P.iter_hrv_windows(payload))
        assert len(out) == 1
        assert out[0].start_ms == 100

    def test_empty_payload(self):
        assert list(P.iter_hrv_windows([])) == []


class TestParseHrJson:
    def test_end_to_end(self):
        text = _hr_json({"heart_rate": 61.0, "start_time": 1000, "end_time": 2000})
        out = P.parse_hr_json(text, rel_path="r")
        assert len(out) == 1
        assert out[0].bpm == 61.0

    def test_rejects_invalid_json(self):
        try:
            P.parse_hr_json("{not json", rel_path="r")
        except (ValueError, json.JSONDecodeError):
            return
        raise AssertionError("expected a parse error")


class TestParseFileDispatch:
    def test_hr_json_dir_routes_to_hrbins(self):
        rel = "com.samsung.shealth.tracker.heart_rate/9/abc.json"
        text = _hr_json({"heart_rate": 60.0, "start_time": 1000, "end_time": 2000})
        out = P.parse_file(rel, text)
        assert all(isinstance(r, HRBin) for r in out)
        assert len(out) == 1

    def test_hrv_dir_routes_to_hrvwindows(self):
        # canonical rel_path layout: <shard>/<file>.json
        rel = "com.samsung.health.hrv/shard-x/file.hrv.json"
        text = json.dumps([{"start_time": 100, "end_time": 200,
                            "sdnn": 12.0, "rmssd": 20.0}])
        out = P.parse_file(rel, text)
        assert all(isinstance(r, HRVWindow) for r in out)

    def test_hr_csv_is_a_silent_mirror(self):
        # hr.csv carries the same data as the JSON shards -> dispatched to [].
        assert P.parse_file(P.HR_CSV, "start_time\n1\n") == []

    def test_unknown_file_raises(self):
        try:
            P.parse_file("mystery.bin", "x")
        except ValueError:
            return
        raise AssertionError("expected ValueError for unknown file")


class TestDiscoverExportFiles:
    def test_no_dir_returns_empty(self, tmp_path):
        assert P.discover_export_files(tmp_path / "does-not-exist") == []

    def test_maps_hr_bins_alias_to_canonical_relpath(self, tmp_path):
        alias = tmp_path / "hr_bins" / "9"
        alias.mkdir(parents=True)
        f = alias / "uuid.com.samsung.health.heart_rate.binning_data.json"
        f.write_text("[]", encoding="utf-8")
        pairs = P.discover_export_files(tmp_path)
        assert len(pairs) == 1
        rel, path = pairs[0]
        assert rel == "com.samsung.shealth.tracker.heart_rate/9/" + f.name
        assert path.is_file()

    def test_discovers_top_level_csvs(self, tmp_path):
        for name in ("hr.csv", "stress.csv", "sleep.csv", "sleep_stage.csv"):
            (tmp_path / name).write_text("", encoding="utf-8")
        rels = {rel for rel, _ in P.discover_export_files(tmp_path)}
        assert rels == {"hr.csv", "stress.csv", "sleep.csv", "sleep_stage.csv"}


import pytest  # noqa: E402  (conftest ensures it; keep import for clarity)
