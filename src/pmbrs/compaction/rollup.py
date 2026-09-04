"""Rollup: reduce canonical 60-s windows to coarser spans (5m / 30m / 1h / 1d).

Semantic contract (docs/features/specification.md §Rolling Aggregation,
docs/artifacts/specification.md ``aggregated-from`` row):

- A rollup covers an **aligned span** on the absolute grid (UTC). Spans never
  overlap; a window belongs to exactly one span per resolution.
- **No zero-fills.** A modality is only aggregated over the windows that carry
  it; the rollup reports ``modality_coverage`` = present / expected and flags
  ``partial: true`` when coverage is below ``min_coverage`` (default 0.5).
- Lineage: ``payload.payload.aggregated_from`` lists every contributing
  canonical-window artifact id (the ``aggregated-from`` rollup contract).
- Rollups are **deterministic**: id ``wearable.rollup.<secs>s.<span_start_ms>``,
  ``createdAtEpochMs`` = span start, so re-compaction overwrites the identical
  raw-store file (idempotent, mirrors the producer's writer contract ADR-021 D6).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable

from .reader import CANONICAL_WINDOW_MS, CompactionWindow, KNOWN_MODALITIES

#: Supported span resolutions (span name -> seconds). Names are stable identifiers.
SPAN_SECONDS: dict[str, int] = {
    "5m": 300,
    "30m": 1800,
    "1h": 3600,
    "1d": 86400,
}

#: Rollup spans the CLI / nightly default to (the spec's 5-min rolling feature
#: plus the day level; 30m and 1h available on request).
DEFAULT_SPANS: tuple[str, ...] = ("5m", "1h", "1d")

#: Below this per-modality coverage a rollup is flagged partial (spec §10 default).
DEFAULT_MIN_COVERAGE = 0.5

#: Raw-store destination mapping: ``persist_sync_batch``/``_source_dir`` maps
#: ``"other"`` -> the sink root itself, i.e. rollups land flat in the rollup
#: dir (no source nesting). Rollups are a derived, source-agnostic view.
ROLLUP_SOURCE = "other"
ROLLUP_SCHEMA_VERSION = "1.1"
PIPELINE_NAME = "wearable_rollup"
PRODUCER_NAME = "pmbrs-compaction"


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def _num(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    return None


def _mean(values: Iterable[float]) -> float:
    vals = [v for v in values if v is not None]
    return round(sum(vals) / len(vals), 3) if vals else 0.0


def _mean_field(windows: list[CompactionWindow], modality: str, key: str) -> float | None:
    out: list[float] = []
    for w in windows:
        if not w.present.get(modality, False):
            continue
        payload = w.modality_payloads.get(modality)
        if isinstance(payload, dict):
            v = _num(payload.get(key))
            if v is not None:
                out.append(v)
    if not out:
        return None
    return round(sum(out) / len(out), 3)


def _min_field(windows: list[CompactionWindow], modality: str, key: str) -> float | None:
    out = [
        _num(w.modality_payloads.get(modality, {}).get(key))
        for w in windows
        if w.present.get(modality, False) and isinstance(w.modality_payloads.get(modality), dict)
    ]
    out = [v for v in out if v is not None]
    return round(min(out), 3) if out else None


def _max_field(windows: list[CompactionWindow], modality: str, key: str) -> float | None:
    out = [
        _num(w.modality_payloads.get(modality, {}).get(key))
        for w in windows
        if w.present.get(modality, False) and isinstance(w.modality_payloads.get(modality), dict)
    ]
    out = [v for v in out if v is not None]
    return round(max(out), 3) if out else None


def _sum_field(windows: list[CompactionWindow], modality: str, key: str) -> int | None:
    out = [
        _num(w.modality_payloads.get(modality, {}).get(key))
        for w in windows
        if w.present.get(modality, False) and isinstance(w.modality_payloads.get(modality), dict)
    ]
    out = [v for v in out if v is not None]
    return int(round(sum(out))) if out else None


def aggregate_modality(windows: list[CompactionWindow], modality: str) -> dict[str, Any]:
    """Aggregate one modality over present windows only; {} when no window carries it."""
    present = [w for w in windows if w.present.get(modality, False)]
    if not present:
        return {}

    if modality == "heart_rate":
        stats: dict[str, Any] = {}
        m = _mean_field(present, modality, "bpm")
        if m is not None:
            stats["bpm"] = m
        mn = _min_field(present, modality, "bpm_min")
        if mn is not None:
            stats["bpm_min"] = mn
        mx = _max_field(present, modality, "bpm_max")
        if mx is not None:
            stats["bpm_max"] = mx
        bins = _sum_field(present, modality, "bins")
        if bins is not None:
            stats["bins"] = bins
        return stats

    if modality == "hrv_proxy":
        stats = {}
        m = _mean_field(present, modality, "bpm")
        if m is not None:
            stats["bpm"] = m
        return stats

    if modality == "hrv":
        stats = {}
        sdnn = _mean_field(present, modality, "sdnn_ms")
        if sdnn is not None:
            stats["sdnn_ms"] = sdnn
        rmssd = _mean_field(present, modality, "rmssd_ms")
        if rmssd is not None:
            stats["rmssd_ms"] = rmssd
        return stats

    if modality == "stress":
        stats = {}
        score = _mean_field(present, modality, "score")
        if score is not None:
            stats["score"] = score
        readings = _sum_field(present, modality, "readings")
        if readings is not None:
            stats["readings"] = readings
        return stats

    if modality == "sleep_stage":
        stats = {}
        segs = _sum_field(present, modality, "segments")
        if segs is not None:
            stats["segments"] = segs
        # Dominant stage: most frequent `dominant_stage` across windows.
        votes: dict[str, int] = {}
        for w in present:
            payload = w.modality_payloads.get(modality)
            if isinstance(payload, dict) and isinstance(payload.get("dominant_stage"), str):
                votes[payload["dominant_stage"]] = votes.get(payload["dominant_stage"], 0) + 1
        if votes:
            top = max(sorted(votes), key=lambda k: votes[k])
            stats["dominant_stage"] = top
        return stats

    # Unknown modality: passthrough of present flags only.
    return {}


def _quality_tier(overall: float) -> str:
    return "high" if overall >= 0.67 else ("medium" if overall >= 0.34 else "low")


@dataclass(frozen=True)
class RollupArtifact:
    """One aligned rollup span built from canonical windows."""

    span_id: str
    span_seconds: int
    span_start_ms: int
    span_end_ms: int
    windows_expected: int
    windows: tuple[CompactionWindow, ...]
    coverage: dict[str, float] = field(default_factory=dict)
    partial: dict[str, bool] = field(default_factory=dict)
    aggregated: dict[str, Any] = field(default_factory=dict)
    min_coverage: float = DEFAULT_MIN_COVERAGE

    @property
    def artifact_id(self) -> str:
        return f"wearable.rollup.{self.span_seconds}s.{self.span_start_ms}"

    @property
    def windows_present(self) -> int:
        return len(self.windows)

    @property
    def overall_quality(self) -> float:
        vals = [self.coverage.get(m, 0.0) for m in KNOWN_MODALITIES]
        return round(sum(vals) / len(vals), 4) if vals else 0.0

    def to_dict(self, device_alias: str, producer_version: str) -> dict[str, Any]:
        """Canonical 9-key raw-store record (the same writer contract as the producer)."""
        coverage = dict(self.coverage)
        present_flags = {m: bool(coverage.get(m, 0.0) > 0.0) for m in KNOWN_MODALITIES}
        overall = self.overall_quality
        payload: dict[str, Any] = {
            "kind": "rollup",
            "artifact_type": "canonical.rollup",
            "window": {
                "start_time": _iso(self.span_start_ms),
                "end_time": _iso(self.span_end_ms),
                "resolution_seconds": self.span_seconds,
                "span_id": self.span_id,
                "canonical_windows_expected": self.windows_expected,
            },
            "modalities_present": present_flags,
            "payload": {
                "modalities": dict(self.aggregated),
                "aggregated_from": {
                    "count": self.windows_present,
                    "artifact_ids": [w.artifact_id for w in self.windows],
                },
            },
            "missingness_metadata": {
                "modality_coverage": coverage,
                "missing_modalities": [m for m in KNOWN_MODALITIES if not coverage.get(m, 0.0)],
                "partial": dict(self.partial),
                "min_coverage": self.min_coverage,
                "corruption_flags": [],
                "delayed_modalities": [],
            },
            "quality_metadata": {
                "overall_rollup_quality": overall,
                "quality_tier": _quality_tier(overall),
            },
        }
        provenance: dict[str, Any] = {
            "producer": PRODUCER_NAME,
            "producer_version": producer_version,
            "pipeline_name": PIPELINE_NAME,
            "span_id": self.span_id,
            "min_coverage": self.min_coverage,
            "device_alias": device_alias,
            "lineage": {
                "derived_from": "wearable_canonical_window",
                "derivation": "rollup",
                "window_count": self.windows_present,
            },
        }
        return {
            "artifactId": self.artifact_id,
            "source": ROLLUP_SOURCE,
            "payload": payload,
            "createdAtEpochMs": self.span_start_ms,
            "schemaVersion": ROLLUP_SCHEMA_VERSION,
            "deviceAlias": device_alias,
            "provenanceMetadataJson": provenance,
            "ingestedAtEpochMs": 0,
            "ingestStatus": "accepted",
        }


def _resolve_span(span: str) -> tuple[str, int]:
    key = span.lower()
    # Allow raw seconds like "300" / "3600s".
    if key.isdigit():
        return f"{key}s", int(key)
    if key.endswith("s") and key[:-1].isdigit():
        return key, int(key[:-1])
    if key in SPAN_SECONDS:
        return key, SPAN_SECONDS[key]
    raise ValueError(f"unknown span {span!r}; expected one of {sorted(SPAN_SECONDS)} or '<secs>s'")


def build_rollups(
    windows: list[CompactionWindow],
    spans: Iterable[str] = DEFAULT_SPANS,
    min_coverage: float = DEFAULT_MIN_COVERAGE,
) -> list[RollupArtifact]:
    """Bucket ``windows`` into aligned spans and build one RollupArtifact each.

    A span with zero contributing windows is *omitted* (nothing to aggregate —
    an empty rollup would just be a missingness report with no stats).
    """
    resolved: list[tuple[str, int]] = [_resolve_span(s) for s in spans]

    out: list[RollupArtifact] = []
    for span_name, span_secs in resolved:
        span_ms = span_secs * 1000
        expected = max(1, span_ms // CANONICAL_WINDOW_MS)

        buckets: dict[int, list[CompactionWindow]] = {}
        for w in windows:
            bucket_start = (w.start_ms // span_ms) * span_ms
            buckets.setdefault(bucket_start, []).append(w)

        for bucket_start in sorted(buckets):
            members = sorted(buckets[bucket_start], key=lambda w: w.start_ms)
            coverage: dict[str, float] = {}
            partial: dict[str, bool] = {}
            aggregated: dict[str, Any] = {}
            for m in KNOWN_MODALITIES:
                n = sum(1 for w in members if w.present.get(m, False))
                cov = round(n / expected, 4) if expected else 0.0
                coverage[m] = cov
                stats = aggregate_modality(members, m)
                if stats:
                    aggregated[m] = stats
                # Partial: *some* data, but below the completeness bar.
                partial[m] = cov > 0.0 and cov < min_coverage
            out.append(
                RollupArtifact(
                    span_id=span_name,
                    span_seconds=span_secs,
                    span_start_ms=bucket_start,
                    span_end_ms=bucket_start + span_ms,
                    windows_expected=expected,
                    windows=tuple(members),
                    coverage=coverage,
                    partial=partial,
                    aggregated=aggregated,
                    min_coverage=min_coverage,
                )
            )
    return out


__all__ = [
    "DEFAULT_MIN_COVERAGE",
    "DEFAULT_SPANS",
    "PIPELINE_NAME",
    "PRODUCER_NAME",
    "ROLLUP_SCHEMA_VERSION",
    "ROLLUP_SOURCE",
    "SPAN_SECONDS",
    "RollupArtifact",
    "aggregate_modality",
    "build_rollups",
]
