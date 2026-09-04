"""Compaction: parquet export round trip (stdlib-free read via pyarrow).

Requires ``pyarrow`` (installed in the dev env). Verifies:
  - windows.parquet / rollups.parquet are written.
  - Read back with pyarrow: correct row counts, dtypes, and a few spot values.
  - Metadata (generated_at) is present.
  - Atomic write: destination exists, no leftover .tmp files.
  - Sparse modalities (None cells) don't break the schema.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pyarrow as pa
    import pyarrow.parquet as pq

    HAVE_PYARROW = True
except ImportError:
    HAVE_PYARROW = False

from pmbrs.compaction.parquet_writer import (
    rollups_to_rows,
    windows_to_rows,
    write_rollups_parquet,
    write_windows_parquet,
)
from pmbrs.compaction import build_rollups
from pmbrs.compaction.reader import CANONICAL_WINDOW_MS, CompactionWindow
from pmbrs.ingestion.wearable.artifact import build_window_artifact

from scripts.pmbrs_host_sync_ingest import persist_sync_batch
from pmbrs.compaction.reader import load_windows

T0 = 1_761_000_000_000
T0 = (T0 // 60_000) * 60_000


def _win(idx: int, present: dict, payloads: dict) -> CompactionWindow:
    start = T0 + idx * 60_000
    return CompactionWindow(
        artifact_id=f"wearable.win.{idx}",
        canonical_index=idx,
        start_ms=start,
        end_ms=start + 60_000,
        present={m: p for m, p in present.items()},
        coverage={m: (1.0 if p else 0.0) for m, p in present.items()},
        modality_payloads=payloads,
        device_alias="test",
    )


@unittest.skipUnless(HAVE_PYARROW, "pyarrow not installed")
class ParquetRoundTripTest(unittest.TestCase):
    def _w(self, n=5):
        wins = []
        for i in range(n):
            present = {"heart_rate": True, "hrv": i % 2 == 0}
            payloads = {"heart_rate": {"bpm": 60 + i, "bpm_min": 55, "bpm_max": 70, "bins": 10}}
            if i % 2 == 0:
                payloads["hrv"] = {"sdnn_ms": 30 + i, "rmssd_ms": 40 + i}
            wins.append(_win(i, present, payloads))
        return wins

    def _r(self, wins):
        return build_rollups(wins, spans=["5m"])

    def test_write_windows_parquet(self):
        wins = self._w(5)
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "windows.parquet"
            path = write_windows_parquet(wins, out)
            self.assertTrue(path.exists())
            table = pq.read_table(out)
            self.assertEqual(table.num_rows, 5)
            cols = set(table.column_names)
            self.assertIn("start_ms", cols)
            self.assertIn("end_ms", cols)
            self.assertIn("present_heart_rate", cols)
            self.assertIn("heart_rate_bpm", cols)
            self.assertIn("hrv_sdnn_ms", cols)
            # Only even windows have hrv -> heart_rate is non-null across all;
            # hrv_sdnn_ms is null for odd ones.
            bpm_series = table.column("heart_rate_bpm").to_pylist()
            self.assertEqual(len(bpm_series), 5)
            self.assertEqual(bpm_series[0], 60)
            hrv_series = table.column("hrv_sdnn_ms").to_pylist()
            self.assertIsNone(hrv_series[1])
            self.assertEqual(hrv_series[0], 30)
            # All heart_rate present flags are True
            flags = table.column("present_heart_rate").to_pylist()
            self.assertTrue(all(flags))
            # Metadata present
            meta = table.schema.metadata or {}
            self.assertIn(b"generated_at", meta)

    def test_write_rollups_parquet(self):
        wins = self._w(20)
        rollups = self._r(wins)
        self.assertGreaterEqual(len(rollups), 1)
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "rollups.parquet"
            path = write_rollups_parquet(rollups, out)
            self.assertTrue(path.exists())
            table = pq.read_table(out)
            self.assertEqual(table.num_rows, len(rollups))
            cols = set(table.column_names)
            for c in ("span_id", "span_seconds", "span_start_ms",
                      "windows_expected", "windows_present",
                      "coverage_heart_rate", "partial_heart_rate",
                      "agg_heart_rate_bpm"):
                self.assertIn(c, cols)
            # Spot check a known rollup row
            spans = table.column("span_seconds").to_pylist()
            self.assertTrue(all(s == 300 for s in spans))
            # Heart-rate aggregate should mean of 60..79 for 20 windows
            # All 20 are present -> bpm values are 60..79; mean ~69.5
            agg = table.column("agg_heart_rate_bpm").to_pylist()
            self.assertTrue(all(v is not None for v in agg if len(agg) > 0))
            # All hrv present for even indices (10 out of 20)
            hrv_cov = table.column("coverage_hrv").to_pylist()
            if len(hrv_cov) > 0:
                self.assertTrue(all(0.0 <= v <= 1.0 for v in hrv_cov))

    def test_no_tmp_leftover(self):
        wins = self._w(3)
        with tempfile.TemporaryDirectory() as t:
            out = Path(t) / "windows.parquet"
            write_windows_parquet(wins, out)
            leftovers = list(Path(t).glob("*.tmp"))
            self.assertEqual(leftovers, [])

    def test_empty_raises(self):
        with self.assertRaises(ValueError):
            write_windows_parquet([], Path(tempfile.gettempdir()) / "_should_not_exist.parquet")


if __name__ == "__main__":
    unittest.main()
