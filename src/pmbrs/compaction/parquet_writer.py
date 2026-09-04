"""Flat parquet exports of canonical windows and rollups (fast range reads).

The visualization architecture (docs/visualization/architecture.md) asks for
fast temporal range reads; the SQLite range index serves interactive queries,
and these flat files serve batch consumers (pandas/polars, ML feature builds,
ad-hoc dashboards) without a database dependency.

Layout (one table per artifact kind, one row per artifact):

``windows.parquet`` columns:
  canonical_index, start_ms, end_ms, start_iso, end_iso
  present_<m> (bool, one per known modality)
  cov_<m>    (float, modality coverage for that window)
  <m>_<field> (flattened numeric modalities; e.g. heart_rate_bpm)
  artifact_id, device_alias

``rollups.parquet`` columns:
  span_id, span_seconds, span_start_ms, span_end_ms, span_start_iso, span_end_iso
  windows_expected, windows_present
  coverage_<m> (float), partial_<m> (bool)
  agg_<m>_<field> (numeric rollup stats)
  artifact_id, device_alias

Both tables carry a ``generated_at`` metadata key at the file level (pyarrow
schema metadata), so downstream can tell which compaction run produced them.
Files are rewritten atomically (tmp + rename) so a reader never sees a partial.

Requires ``pyarrow``. When it is absent the compact() orchestrator skips the
parquet step and reports ``parquet_ok=False`` (graceful degradation) — the
rollup JSON artifacts are the source of truth.
"""

from __future__ import annotations

import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

from .reader import CompactionWindow, KNOWN_MODALITIES
from .rollup import RollupArtifact

_PARQUET_FLAT_FIELDS: dict[str, tuple[str, ...]] = {
    "heart_rate": ("bpm", "bpm_min", "bpm_max", "bins"),
    "hrv_proxy": ("bpm", "windows"),
    "hrv": ("sdnn_ms", "rmssd_ms"),
    "stress": ("score", "readings"),
    "sleep_stage": ("segments",),
}


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _atomic_write(path: Path, data: bytes) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
        os.replace(tmp, path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return path


def windows_to_rows(windows: Sequence[CompactionWindow]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for w in windows:
        row: dict[str, Any] = {
            "canonical_index": w.canonical_index,
            "start_ms": w.start_ms,
            "end_ms": w.end_ms,
            "start_iso": _iso(w.start_ms),
            "end_iso": _iso(w.end_ms),
            "artifact_id": w.artifact_id,
            "device_alias": w.device_alias,
        }
        for m in KNOWN_MODALITIES:
            present = bool(w.present.get(m, False))
            row[f"present_{m}"] = present
            row[f"cov_{m}"] = float(w.coverage.get(m, 0.0) if present else 0.0)
            if present:
                payload = w.modality_payloads.get(m)
                if isinstance(payload, dict):
                    for f in _PARQUET_FLAT_FIELDS.get(m, ()):
                        row[f"{m}_{f}"] = payload.get(f)
                    if m == "sleep_stage":
                        row["sleep_stage_dominant_stage"] = (
                            str(payload.get("dominant_stage")) if payload.get("dominant_stage") is not None else None
                        )
        rows.append(row)
    return rows


def rollups_to_rows(rollups: Sequence[RollupArtifact]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for r in rollups:
        row: dict[str, Any] = {
            "span_id": r.span_id,
            "span_seconds": r.span_seconds,
            "span_start_ms": r.span_start_ms,
            "span_end_ms": r.span_end_ms,
            "span_start_iso": _iso(r.span_start_ms),
            "span_end_iso": _iso(r.span_end_ms),
            "windows_expected": r.windows_expected,
            "windows_present": r.windows_present,
            "artifact_id": r.artifact_id,
        }
        for m in KNOWN_MODALITIES:
            coverage = float(r.coverage.get(m, 0.0))
            row[f"coverage_{m}"] = coverage
            row[f"partial_{m}"] = bool(r.partial.get(m, coverage > 0.0 and coverage < r.min_coverage))
            stats = r.aggregated.get(m)
            if isinstance(stats, dict):
                for f, v in stats.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        row[f"agg_{m}_{f}"] = v
                    elif m == "sleep_stage" and f == "dominant_stage":
                        row[f"agg_{m}_{f}"] = str(v)
        rows.append(row)
    return rows


def _write_parquet(rows: list[dict[str, Any]], path: Path, label: str) -> Path:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError as exc:  # pragma: no cover - exercised by graceful path
        raise RuntimeError("pyarrow is required for parquet export") from exc

    if not rows:
        raise ValueError(f"no {label} rows to export")

    # Build the table preserving dict-key order stability: collect all keys in
    # first-seen order, null-fill missing values across rows (sparse modalities
    # are expected — a window without stress must not break the schema).
    columns: list[str] = []
    for row in rows:
        for key in row:
            if key not in columns:
                columns.append(key)
    data = {col: [row.get(col) for row in rows] for col in columns}

    table = pa.table(data)
    metadata = {
        "generated_at": _now_iso().encode("utf-8"),
        "producer": b"pmbrs-compaction",
        "label": label.encode("utf-8"),
    }
    table = table.replace_schema_metadata(metadata)

    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, compression="snappy")
    buf = sink.getvalue()
    return _atomic_write(path, bytes(buf))


def write_windows_parquet(windows: Sequence[CompactionWindow], out_path: str | Path) -> Path:
    return _write_parquet(windows_to_rows(windows), Path(out_path), "windows")


def write_rollups_parquet(rollups: Sequence[RollupArtifact], out_path: str | Path) -> Path:
    return _write_parquet(rollups_to_rows(rollups), Path(out_path), "rollups")


__all__ = [
    "windows_to_rows",
    "rollups_to_rows",
    "write_windows_parquet",
    "write_rollups_parquet",
]
