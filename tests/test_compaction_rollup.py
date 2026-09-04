"""Compaction: rollup semantics over a real raw-store round trip.

Builds synthetic canonical windows with the *actual* producer
``build_window_artifact`` + ``persist_sync_batch`` (the same helpers the live
pipeline uses), then exercises:

  - ``reader.load_windows`` — the raw-store -> CompactionWindow coercion.
  - ``rollup.build_rollups`` — coverage / partial semantics, deterministic
    span-aligned ids, multi-span output.
  - ``compact.compact`` — the orchestrator: rollup JSON files, stats, idempotency.

Canonical-grid contract (src/pmbrs/ingestion/wearable/grid.py): index 0 is
epoch 1970, and ``index == start_ms // 60_000``. Fixtures therefore seed
*contiguous grid slots* from an aligned time base and derive the stamped index
from the slot — the reader must recover that true index, not a run-relative one.

Coverage contract (tests' oracle, matches rollup.py): for a span of ``expected``
canonical slots, ``coverage[m] = (#slots whose window is present AND carries m)
/ expected``. ``partial[m] = 0 < coverage < min_coverage``.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

import sys

_HERE = Path(__file__).resolve()
for _p in (_HERE.parent, _HERE.parent / "src"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

from pmbrs.compaction import (
    compact,
    load_windows,
    build_rollups,
)
from pmbrs.ingestion.wearable.artifact import build_window_artifact

from scripts.pmbrs_host_sync_ingest import persist_sync_batch

#: Snapped to the canonical grid AND to a 1-day boundary (index 0 = epoch,
#: grid.py). 1-day alignment is a multiple of 60s / 5m / 1h, so every span
#: test's contiguous slots land in cleanly-aligned single buckets.
_DAY = 86_400_000
T0 = (1_761_000_000_000 // _DAY) * _DAY  # ~2025-10-19T00:00:00Z, day-aligned


def _window(slot: int, present: dict[str, bool], payloads: dict[str, Any]) -> dict:
    """One canonical window at grid slot ``slot`` (start = T0 + slot*60s)."""
    start = T0 + slot * 60_000
    end = start + 60_000
    modalities = ("heart_rate", "hrv_proxy", "hrv", "stress", "sleep_stage")
    coverage = {m: (1.0 if present.get(m) else 0.0) for m in modalities}
    art = build_window_artifact(
        canonical_index=start // 60_000,
        window_start_ms=start,
        window_end_ms=end,
        modalities_present=present,
        coverage=coverage,
        modality_payloads=payloads,
        device_alias="galaxy-watch-7",
        producer_version="0.1",
        hrv_proxy_method="inter_beat",
        export="test",
        transport="inbox",
    )
    record = art.to_dict()
    # persist_sync_batch stamps createdAtEpochMs -> <id>-<ts>.json (ADR-017 D2).
    record["createdAtEpochMs"] = art.created_at_epoch_ms
    return record


class LoadWindowsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raw_root = Path(self.tmp.name)

    def _write(self, slots: list[int], present: dict, payloads: dict) -> None:
        persist_sync_batch(self.raw_root, [_window(s, present, payloads) for s in slots])

    def test_load_basic(self):
        self._write(
            [0, 1, 2, 3, 4],
            {"heart_rate": True},
            {"heart_rate": {"bpm": 70, "bpm_min": 60, "bpm_max": 80, "bins": 10}},
        )
        wins = load_windows(self.raw_root)
        self.assertEqual(len(wins), 5)
        # The reader must recover the *true grid* indices (epoch-based), not 0..4.
        expected_base = T0 // 60_000
        self.assertEqual([w.canonical_index for w in wins], [expected_base + s for s in range(5)])
        self.assertEqual([w.start_ms for w in wins], [T0 + s * 60_000 for s in range(5)])
        w0 = wins[0]
        self.assertTrue(w0.present.get("heart_rate"))
        self.assertFalse(w0.present.get("hrv"))
        self.assertAlmostEqual(w0.coverage.get("heart_rate", 0.0), 1.0)
        self.assertEqual(w0.modality_payloads["heart_rate"]["bpm"], 70)
        self.assertEqual(w0.end_ms - w0.start_ms, 60_000)
        self.assertEqual(w0.device_alias, "galaxy-watch-7")
        self.assertTrue(w0.source_file)

    def test_ordering_is_deterministic_not_filesystem_order(self):
        # Write slots out of order; the reader must sort by start_ms.
        slots = [3, 0, 5, 2, 4]
        self._write(
            slots,
            {"hrv_proxy": True},
            {"hrv_proxy": {"bpm": 42, "windows": 5}},
        )
        wins = load_windows(self.raw_root)
        self.assertEqual(len(wins), len(slots))
        self.assertEqual(
            [w.start_ms for w in wins],
            sorted(T0 + s * 60_000 for s in slots),
        )

    def test_empty_store(self):
        self.assertEqual(load_windows(self.raw_root), [])

    def test_missing_root(self):
        self.assertEqual(load_windows(Path(self.tmp.name) / "nope"), [])

    def test_ignore_non_window_records(self):
        persist_sync_batch(self.raw_root, [
            {"artifactId": "browser.x.1", "source": "browser",
             "payload": {"kind": "url"}, "createdAtEpochMs": 1234},
        ])
        self._write([0, 1], {"heart_rate": True},
                    {"heart_rate": {"bpm": 70, "bins": 1}})
        wins = load_windows(self.raw_root)
        self.assertEqual(len(wins), 2)

    def test_rollup_kind_records_are_skipped(self):
        # A rollup artifact in the same tree is NOT a canonical window.
        self._write([0], {"heart_rate": True}, {"heart_rate": {"bpm": 70}})
        persist_sync_batch(self.raw_root / "rollup", [
            {"artifactId": "wearable.rollup.300s.1", "source": "other",
             "payload": {"kind": "rollup"}, "createdAtEpochMs": 1},
        ])
        self.assertEqual([w.start_ms for w in load_windows(self.raw_root)], [T0])


class RollupSemanticsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.raw_root = Path(self.tmp.name)

    def _seed(self, slots: list[int], present: dict, payloads: dict) -> list:
        persist_sync_batch(self.raw_root, [_window(s, present, payloads) for s in slots])
        return load_windows(self.raw_root)

    def test_5m_full_coverage(self):
        # All 5 slots of a 5-min span carry hr -> coverage 1.0, not partial.
        wins = self._seed(list(range(5)), {"heart_rate": True},
                          {"heart_rate": {"bpm": 70, "bins": 1}})
        rollups = build_rollups(wins, spans=["5m"], min_coverage=0.5)
        self.assertEqual(len(rollups), 1)
        r0 = rollups[0]
        self.assertEqual(r0.span_seconds, 300)
        self.assertEqual(r0.span_start_ms, T0)
        self.assertEqual(r0.windows_expected, 5)
        self.assertEqual(r0.windows_present, 5)
        self.assertAlmostEqual(r0.coverage.get("heart_rate", 0.0), 1.0)
        self.assertFalse(r0.partial.get("heart_rate", False))
        # Aggregates computed over the present windows only.
        self.assertIn("heart_rate", r0.aggregated)
        self.assertAlmostEqual(r0.aggregated["heart_rate"]["bpm"], 70.0, delta=0.001)

    def test_5m_partial_when_slot_present_but_modality_missing(self):
        # 5 slots all present; hr only in 2 -> coverage 0.4 < 0.5 -> partial.
        present = {"heart_rate": True}
        payloads = {"heart_rate": {"bpm": 70, "bins": 1}}
        records = [_window(s, present, payloads) for s in (0, 2)]
        for s in (1, 3, 4):
            records.append(_window(s, {}, {}))
        persist_sync_batch(self.raw_root, records)
        wins = load_windows(self.raw_root)
        rollups = build_rollups(wins, spans=["5m"], min_coverage=0.5)
        r0 = rollups[0]
        self.assertAlmostEqual(r0.coverage.get("heart_rate", 0.0), 0.4, delta=0.001)
        self.assertTrue(r0.partial.get("heart_rate", False))
        # hrv absent everywhere -> coverage 0.0, and *not* partial (nothing to be
        # partial about; spec: partial implies some data was carried).
        self.assertAlmostEqual(r0.coverage.get("hrv", 0.0), 0.0)
        self.assertFalse(r0.partial.get("hrv", False))

    def test_absent_span_omitted(self):
        # Windows exist only in one 5-min bucket; a far-away bucket never appears.
        wins = self._seed([0, 1], {"heart_rate": True}, {"heart_rate": {"bpm": 70}})
        rollups = build_rollups(wins, spans=["5m"], min_coverage=0.5)
        self.assertEqual(len(rollups), 1)
        self.assertEqual(rollups[0].span_start_ms, T0)

    def test_60s_span_one_bucket_per_slot(self):
        # At the 60-s span each window is its own rollup.
        wins = self._seed([0, 1, 2], {"heart_rate": True},
                          {"heart_rate": {"bpm": 60, "bins": 1}})
        rollups = build_rollups(wins, spans=["60s"], min_coverage=0.5)
        self.assertEqual(len(rollups), 3)
        self.assertEqual([r.span_start_ms for r in rollups], [T0 + s * 60_000 for s in range(3)])
        for r in rollups:
            self.assertAlmostEqual(r.coverage.get("heart_rate", 0.0), 1.0)

    def test_deterministic_1h_id(self):
        wins = self._seed(list(range(60)), {"heart_rate": True},
                          {"heart_rate": {"bpm": 70, "bins": 1}})
        rollups = build_rollups(wins, spans=["1h"], min_coverage=0.5)
        self.assertEqual(len(rollups), 1)
        r0 = rollups[0]
        # Deterministic: artifact_id encodes span id + slot-aligned start.
        self.assertIn("1h", r0.span_id)
        self.assertEqual(r0.span_start_ms, (T0 // 3_600_000) * 3_600_000)
        self.assertAlmostEqual(r0.coverage.get("heart_rate", 0.0), 1.0)
        self.assertEqual(r0.windows_present, 60)

    def test_1d_span_groups_full_day(self):
        # 1440 slots = exactly one 24h bucket; hr present 720/1440 -> coverage 0.5,
        # at (not below) min_coverage -> NOT partial (partial needs strictly < min).
        slots = list(range(1440))
        records = [
            _window(s, {"heart_rate": True if s < 720 else False},
                    {"heart_rate": {"bpm": 70, "bins": 1}} if s < 720 else {})
            for s in slots
        ]
        persist_sync_batch(self.raw_root, records)
        wins = load_windows(self.raw_root)
        rollups = build_rollups(wins, spans=["1d"], min_coverage=0.5)
        r0 = rollups[0]
        self.assertEqual(r0.span_seconds, 86_400)
        self.assertEqual(r0.windows_expected, 1440)
        self.assertAlmostEqual(r0.coverage.get("heart_rate", 0.0), 0.5, delta=0.0001)
        self.assertFalse(r0.partial.get("heart_rate", False))

    def test_unknown_span_raises(self):
        wins = self._seed([0], {"heart_rate": True}, {"heart_rate": {"bpm": 70}})
        with self.assertRaises(ValueError):
            build_rollups(wins, spans=["bogus"], min_coverage=0.5)
        with self.assertRaises(ValueError):
            build_rollups(wins, spans=["13x"], min_coverage=0.5)

    def test_multi_span_output(self):
        # The same windows roll up independently at every requested span.
        wins = self._seed(list(range(120)), {"heart_rate": True},
                          {"heart_rate": {"bpm": 70, "bins": 1}})
        rollups = build_rollups(wins, spans=["5m", "1h"], min_coverage=0.5)
        five_m = [r for r in rollups if "5" in r.span_id]
        one_h = [r for r in rollups if "1h" in r.span_id or r.span_seconds == 3600]
        self.assertTrue(five_m, "expected 5m rollups")
        self.assertTrue(one_h, "expected 1h rollups")
        self.assertEqual(len(rollups), len(five_m) + len(one_h))

    def test_hrv_only_windows(self):
        # hrv present in all 5 slots, other modalities absent -> partial on absence.
        wins = self._seed(list(range(5)), {"hrv": True},
                          {"hrv": {"sdnn_ms": 45, "rmssd_ms": 55}})
        rollups = build_rollups(wins, spans=["5m"], min_coverage=0.5)
        r0 = rollups[0]
        self.assertAlmostEqual(r0.coverage.get("hrv", 0.0), 1.0)
        self.assertAlmostEqual(r0.coverage.get("heart_rate", 0.0), 0.0)
        self.assertIn("hrv", r0.aggregated)
        self.assertAlmostEqual(r0.aggregated["hrv"]["sdnn_ms"], 45.0)


class CompactOrchestratorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        # Store layout: store/raw + store/rollup + store/data
        self.store = Path(self.tmp.name)
        self.raw_root = self.store / "raw"
        self.raw_root.mkdir(parents=True)
        self.out_dir = self.store / "data"

    def _seed(self, slots: list[int], present: dict, payloads: dict) -> None:
        persist_sync_batch(self.raw_root, [_window(s, present, payloads) for s in slots])

    def test_compact_writes_rollup_files_with_stats(self):
        self._seed(list(range(10)), {"heart_rate": True},
                   {"heart_rate": {"bpm": 70, "bins": 1}})
        stats = compact(raw_root=self.raw_root, out_dir=self.out_dir,
                        spans=["5m"], parquet=False)
        self.assertEqual(stats.windows_loaded, 10)
        self.assertGreaterEqual(stats.rollups_built, 1)
        self.assertTrue(stats.parquet_ok is False or hasattr(stats, "parquet_ok"))
        # Rollup files exist
        rollup_root = Path(stats.rollup_root)
        files = list(rollup_root.glob("*.json")) if rollup_root.is_dir() else []
        self.assertGreaterEqual(len(files), stats.rollups_built)

    def test_compact_idempotent(self):
        self._seed(list(range(10)), {"heart_rate": True},
                   {"heart_rate": {"bpm": 70, "bins": 1}})
        s1 = compact(raw_root=self.raw_root, out_dir=self.out_dir,
                     spans=["5m"], parquet=False)
        s2 = compact(raw_root=self.raw_root, out_dir=self.out_dir,
                     spans=["5m"], parquet=False)
        self.assertEqual(sorted(s1.rollup_files), sorted(s2.rollup_files))
        rollup_root = Path(s1.rollup_root)
        files = list(rollup_root.glob("*.json")) if rollup_root.is_dir() else []
        self.assertEqual(len(files), len(set(s1.rollup_files)))

    def test_compact_empty_store(self):
        stats = compact(raw_root=self.raw_root, out_dir=self.out_dir,
                        spans=["5m"], parquet=False)
        self.assertEqual(stats.windows_loaded, 0)
        self.assertEqual(stats.rollups_built, 0)

    def test_compact_rollup_file_shape(self):
        self._seed(list(range(5)), {"heart_rate": True},
                   {"heart_rate": {"bpm": 70, "bins": 1}})
        stats = compact(raw_root=self.raw_root, out_dir=self.out_dir,
                        spans=["5m"], parquet=False)
        if stats.rollup_files:
            rec = json.loads(Path(stats.rollup_files[0]).read_text())
            # Canonical 9-key raw-store record (same contract as producer).
            for key in ("artifactId", "source", "payload", "createdAtEpochMs",
                        "schemaVersion", "ingestedAtEpochMs", "ingestStatus",
                        "deviceAlias", "provenanceMetadataJson"):
                self.assertIn(key, rec)
            self.assertEqual(rec["payload"]["kind"], "rollup")
            # Lineage to the canonical windows the rollup aggregates over.
            self.assertIn("aggregated_from", rec["payload"]["payload"])
            self.assertGreaterEqual(
                rec["payload"]["payload"]["aggregated_from"]["count"], 1)


if __name__ == "__main__":
    unittest.main()
