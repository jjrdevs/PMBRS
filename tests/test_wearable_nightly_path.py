"""Regression test for `_resolve_raw_dir` (Step 3 nightly wiring).

The nightly producer writes canonical windows to `<store>/raw/mobile/`
(mirroring the boox convention where `--raw-root` is the STORE root).
Compaction (`compact(raw_root=...)`) then reads from `<store>/raw/mobile/`
via `load_windows`. Both share a single `raw_dir = _resolve_raw_dir(store)`.

Before the fix, `raw_dir` was passed as the bare store root, causing:
  * `compact`'s defaults to resolve rollup/parquet to `store.parent` (wrong level), and
  * the reader's fallback path to potentially scan unrelated sources.

These tests lock the `_resolve_raw_dir` contract and the idempotent `/raw` path
so a regression (removing the append, or double-appending) is immediately caught.
"""
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

# Load the nightly script as a module (it is a script, not a package).
_NIGHTLY_PATH = ROOT / "scripts" / "pmbrs_wearable_nightly.py"
_spec = importlib.util.spec_from_file_location("pmbrs_wearable_nightly", _NIGHTLY_PATH)
assert _spec is not None and _spec.loader is not None  # path is a known-good existing file
nightly = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = nightly
_spec.loader.exec_module(nightly)

_resolve_raw_dir = nightly._resolve_raw_dir


# ── Unit tests for _resolve_raw_dir ────────────────────────────────────────────

def test_resolve_appends_raw():
    """Bare store root gets /raw appended (the core fix)."""
    out = _resolve_raw_dir("/home/user/.pmbrs-private/store")
    assert out == "/home/user/.pmbrs-private/store/raw", out


def test_resolve_idempotent_already_raw():
    """A path already ending in /raw is returned unchanged."""
    out = _resolve_raw_dir("/home/user/.pmbrs-private/store/raw")
    assert out == "/home/user/.pmbrs-private/store/raw", out


def test_resolve_trailing_slash_stripped():
    """Trailing slash is stripped before appending /raw."""
    out = _resolve_raw_dir("/home/user/.pmbrs-private/store/")
    assert out == "/home/user/.pmbrs-private/store/raw", out


def test_resolve_already_raw_with_trailing_slash():
    """Already /raw with trailing slash: strip slash, path already ends in /raw."""
    out = _resolve_raw_dir("/home/user/.pmbrs-private/store/raw/")
    assert out == "/home/user/.pmbrs-private/store/raw", out


def test_resolve_double_raw_not_appended():
    """Guard against accidentally appending /raw twice."""
    assert not _resolve_raw_dir("/a/b/raw").endswith("raw/raw")
    assert not _resolve_raw_dir("/a/b").endswith("raw/raw")


# ── Integration: producer sink and compact reader resolve to the same tree ────

def test_producer_and_compact_share_raw_tree(tmp_path):
    """The raw_dir passed to both producer and compact points at the same tree:
    <store>/raw/mobile/ — windows written there are found by load_windows."""
    store = tmp_path / "store"
    # Simulate what the producer would write (via LocalIngestClient with raw_dir).
    raw_dir = _resolve_raw_dir(str(store))
    mobile_dir = Path(raw_dir) / "mobile"
    mobile_dir.mkdir(parents=True, exist_ok=True)
    # One minimal canonical_window artifact (the reader requires kind + window block).
    window_artifact = {
        "artifactId": "wearable.win.29000000-1000",
        "source": "mobile",
        "payload": {
            "kind": "canonical_window",
            "artifact_type": "canonical.window",
            "window": {
                "start_time": "2025-07-05T00:00:00.000Z",
                "end_time": "2025-07-05T00:01:00.000Z",
                "resolution_seconds": 60,
                "canonical_index": 29000000,
            },
            "modalities_present": {"heart_rate": True, "hrv_proxy": False,
                                   "hrv": False, "stress": False, "sleep_stage": False},
            "payload": {
                "modalities": {
                    "heart_rate": {"bpm": 72.5, "bpm_min": 65, "bpm_max": 80, "bins": 3}
                }
            },
            "missingness_metadata": {
                "modality_coverage": {"heart_rate": 1.0, "hrv_proxy": 0.0,
                                      "hrv": 0.0, "stress": 0.0, "sleep_stage": 0.0},
                "missing_modalities": ["hrv_proxy", "hrv", "stress", "sleep_stage"],
            },
            "quality_metadata": {"overall": 0.2},
        },
        "createdAtEpochMs": 1000,
        "schemaVersion": "1.1",
        "deviceAlias": "galaxy-watch7",
        "provenanceMetadataJson": {"producer": "pmbrs"},
        "ingestedAtEpochMs": 0,
        "ingestStatus": "accepted",
    }
    (mobile_dir / "wearable.win.29000000-1000.json").write_text(
        json.dumps(window_artifact, indent=2))

    # compact(raw_root=raw_dir) must find the window.
    from pmbrs.compaction import compact, load_windows
    windows = load_windows(raw_dir)
    assert len(windows) == 1, f"expected 1 window, got {len(windows)}"

    stats = compact(
        raw_root=raw_dir,
        spans=["1h"],
        min_coverage=0.1,
        source="mobile",
    )
    assert stats.windows_loaded == 1, f"compact loaded {stats.windows_loaded}"
    assert stats.rollups_built >= 1, f"expected ≥1 rollup, got {stats.rollups_built}"

    # Rollup file must be in the expected place: <store>/ (rollup_root default).
    rollup_dir = Path(raw_dir).parent  # = <store>
    rollup_files = list(rollup_dir.rglob("*.json"))
    assert rollup_files, f"no rollup JSON files found under {rollup_dir}"
    # Spot-check the rollup content.
    rec = json.loads(rollup_files[0].read_text())
    assert rec["payload"]["modalities_present"].get("heart_rate") is True
    assert "heart_rate" in rec["payload"]["payload"]["modalities"]
