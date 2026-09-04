"""Compact orchestrator: raw canonical windows -> rollups (JSON) + parquet.

Pipeline (all deterministic, all idempotent on re-run):

1. Read canonical windows from ``raw_root/<source>/`` (the producer's sink).
2. Build rollups for each requested span (5m/1h/1d by default).
3. Write rollups as 9-key artifacts under ``rollup_root`` (default
   ``<store>/rollup``; written via ``persist_sync_batch`` so the on-disk
   contract is the same as the phone/producer raw store). Deterministic ids
   mean a re-run overwrites the identical file — no duplication churn.
4. Write flat ``windows.parquet`` and ``rollups.parquet`` under ``out_dir``.

The producer chain (ADR-021) has already done parsing, binning, dedup, and
HRV; compaction is a pure derivation over the accepted windows, so it never
rewrites the raw store and never needs the inbox.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

from .parquet_writer import (
    write_rollups_parquet,
    write_windows_parquet,
)
from .reader import CompactionWindow, load_windows
from .rollup import (
    DEFAULT_MIN_COVERAGE,
    DEFAULT_SPANS,
    PIPELINE_NAME,
    PRODUCER_NAME,
    RollupArtifact,
    build_rollups,
)

#: Where the wearable producer writes canonical windows under the raw store.
DEFAULT_SOURCE = "mobile"

#: Rollup sink directory name (sibling of raw sources).
ROLLUP_DIR = "rollup"

#: Producer version stamp for provenance (bump on schema changes).
PRODUCER_VERSION = "compaction-1.0"


@dataclass
class CompactStats:
    """Result summary returned by :func:`compact` (also serialized by the CLI)."""

    windows_loaded: int = 0
    span_ids: list[str] = field(default_factory=list)
    rollups_built: int = 0
    rollup_files: list[str] = field(default_factory=list)
    rollup_root: str = ""
    windows_parquet: str = ""
    rollups_parquet: str = ""
    parquet_ok: bool = False
    partial_rollups: int = 0
    source: str = DEFAULT_SOURCE

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": True,
            "pipeline": PIPELINE_NAME,
            "source": self.source,
            "windows_loaded": self.windows_loaded,
            "spans": sorted(self.span_ids),
            "rollups_built": self.rollups_built,
            "partial_rollups": self.partial_rollups,
            "rollup_root": self.rollup_root,
            "rollup_files": self.rollup_files,
            "parquet": {
                "ok": self.parquet_ok,
                "windows_parquet": self.windows_parquet,
                "rollups_parquet": self.rollups_parquet,
            },
        }


def _default_rollup_root(raw_root: Path, source: str) -> Path:
    # raw_root is the raw store (…/store/raw); rollups live in …/store/rollup.
    return raw_root.parent / ROLLUP_DIR


def compact(
    raw_root: str | Path,
    out_dir: str | Path | None = None,
    spans: Iterable[str] = DEFAULT_SPANS,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
    source: str = DEFAULT_SOURCE,
    rollup_root: str | Path | None = None,
    device_alias: str = "",
    parquet: bool = True,
) -> CompactStats:
    """Run the full compaction pipeline over the raw store under ``raw_root``.

    ``raw_root`` is the raw store root (``~/.pmbrs-private/store/raw``). Windows
    come from ``raw_root/<source>/``; rollups are written to ``rollup_root``
    (default ``raw_root.parent / "rollup"``); parquet goes to ``out_dir``
    (default ``raw_root.parent / "data"``).

    Returns a :class:`CompactStats`. Does not raise on empty store (returns
    zeroed stats) — a device with no data is a valid, common state.
    """
    spans = tuple(spans)
    raw_root = Path(raw_root)
    rollup_root = Path(rollup_root) if rollup_root else _default_rollup_root(raw_root, source)
    out_dir = Path(out_dir) if out_dir else raw_root.parent / "data"

    stats = CompactStats(source=source, rollup_root=str(rollup_root))

    windows: list[CompactionWindow] = load_windows(raw_root, source=source)
    stats.windows_loaded = len(windows)
    if not windows:
        return stats

    rollups: list[RollupArtifact] = build_rollups(windows, spans=spans, min_coverage=min_coverage)
    stats.span_ids = sorted({r.span_id for r in rollups})
    stats.rollups_built = len(rollups)
    stats.partial_rollups = sum(1 for r in rollups if any(r.partial.values()))

    device_alias = device_alias or _infer_device_alias(windows)

    # 1) Rollup JSON artifacts (same writer contract as the producer's sink).
    if rollups:
        payloads = [r.to_dict(device_alias, PRODUCER_VERSION) for r in rollups]
        written = _persist(rollup_root, payloads)
        stats.rollup_files = [str(p) for p in written]

    # 2) Parquet exports (graceful degradation if pyarrow is missing).
    if parquet:
        try:
            stats.windows_parquet = str(write_windows_parquet(windows, out_dir / "windows.parquet"))
            if rollups:
                stats.rollups_parquet = str(write_rollups_parquet(rollups, out_dir / "rollups.parquet"))
            stats.parquet_ok = True
        except Exception:  # noqa: BLE001 - deliberate: never kill the rollup path
            stats.parquet_ok = False

    return stats


def _infer_device_alias(windows: list[CompactionWindow]) -> str:
    for w in windows:
        if w.device_alias:
            return w.device_alias
    return "unknown"


def _persist(rollup_root: Path, payloads: list[dict[str, Any]]) -> list[Path]:
    """Write rollup payloads as first-class raw-store records in a **flat** sink.

    The contract matches ``persist_sync_batch`` (ADR-017 D2 ``<id>-<createdMs>.json``),
    but written directly to the rollup root rather than a ``source/`` subdir:
    rollups are a derived, source-agnostic *view* of canonical windows, not new
    source data, so the ADR-017 D3 ``<source>/`` partition (which exists for
    *source* artifacts) does not apply. Idempotent: deterministic ids mean a
    re-run overwrites the identical file.
    """
    import json

    rollup_root.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for item in payloads:
        aid = str(item.get("artifactId") or "rollup")
        created = int(item.get("createdAtEpochMs") or 0)
        path = rollup_root / f"{aid}-{created}.json"
        path.write_text(json.dumps(item, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        out.append(path)
    return out


__all__ = [
    "DEFAULT_SOURCE",
    "PRODUCER_VERSION",
    "ROLLUP_DIR",
    "CompactStats",
    "compact",
]
