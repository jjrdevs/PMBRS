"""PMBRS artifact compaction — rollups + parquet export over canonical windows.

Reads the 60-s ``canonical_window`` artifacts from the raw store (the wearable
producer's output, ADR-021 D4) and produces two derived views:

1. **Rollup artifacts** (5 min / 30 min / 1 h / 1 day spans) written as first-class
   9-key JSON artifacts under ``<store>/rollup/`` with deterministic ids
   (``wearable.rollup.<span>s.<start_ms>``) so re-runs overwrite the same files
   (idempotent; mirrors the producer's sha-stable raw writer). They carry the
   ``aggregated_from`` lineage (docs/artifacts/specification.md:59) for every
   contributing window.
2. **Flat parquet exports** (``windows.parquet``, ``rollups.parquet``) for fast
   temporal range reads (docs/visualization/architecture.md — the SQLite range
   index's sibling requirement for batch consumers). Requires ``pyarrow``;
   ``compact()`` degrades gracefully (``parquet_ok=False``) when it is absent.

Missingness is honoured per the feature spec (docs/features/specification.md
§Rolling Aggregation): a rollup reports its per-modality ``coverage`` (share of
span windows that carried the modality) and is flagged ``partial: true`` when
that coverage drops below ``min_coverage`` (default 0.5). No zero-fills.

Public entry points:
- ``compact(...)`` — orchestrator (used by the CLI and the nightly script).
- ``reader.load_windows`` / ``rollup.build_rollups`` / ``parquet_writer.write*``.
"""

from __future__ import annotations

from .compact import CompactStats, compact
from .reader import CompactionWindow, load_windows
from .rollup import (
    DEFAULT_MIN_COVERAGE,
    DEFAULT_SPANS,
    RollupArtifact,
    build_rollups,
)

__all__ = [
    "CompactStats",
    "compact",
    "CompactionWindow",
    "load_windows",
    "DEFAULT_MIN_COVERAGE",
    "DEFAULT_SPANS",
    "RollupArtifact",
    "build_rollups",
]
