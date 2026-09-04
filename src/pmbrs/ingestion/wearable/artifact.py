"""Build the canonical 9-key PMBRS raw artifact for one 60-s canonical window.

One artifact per canonical window (ADR-021 D4). Core shape is
``pmbrs.core.artifact.Artifact`` (ADR-017 D2). The payload follows
``docs/contracts/canonical_window_contract.md`` plus the ADR-021 modality
payloads. Absence == missing key / coverage 0.0 — never a zero value.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pmbrs.core.artifact import Artifact

SCHEMA_VERSION = "1.0"
PIPELINE_NAME = "wearable_canonical_window"
DEFAULT_DEVICE_ALIAS = "galaxy-watch-7"
SOURCE = "mobile"  # pinned source-dir contract -> store/raw/mobile/

#: Expected modalities on every window (for coverage / missingness).
EXPECTED_MODALITIES = ("heart_rate", "hrv_proxy", "hrv", "stress", "sleep_stage")


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%f"
    )[:-3] + "Z"


def window_block(start_ms: int, end_ms: int, index: int, timezone: str = "UTC") -> dict[str, Any]:
    return {
        "start_time": _iso(start_ms),
        "end_time": _iso(end_ms),
        "resolution_seconds": 60,
        "canonical_index": index,
        "timezone": timezone,
    }


def missingness_block(present: dict[str, bool], coverage: dict[str, float]) -> dict[str, Any]:
    missing = [m for m in EXPECTED_MODALITIES if not present.get(m, False)]
    return {
        "modality_coverage": {m: coverage.get(m, 0.0) for m in EXPECTED_MODALITIES},
        "missing_modalities": missing,
        "corruption_flags": [],
        "delayed_modalities": [],
    }


def quality_block(coverage: dict[str, float]) -> dict[str, Any]:
    vals = [c for c in coverage.values()] or [0.0]
    overall = round(sum(vals) / len(vals), 4) if vals else 0.0
    tier = "high" if overall >= 0.67 else ("medium" if overall >= 0.34 else "low")
    return {"overall_window_quality": overall, "quality_tier": tier}


def build_window_artifact(
    *,
    canonical_index: int,
    window_start_ms: int,
    window_end_ms: int,
    modalities_present: dict[str, bool],
    coverage: dict[str, float],
    modality_payloads: dict[str, Any],
    device_alias: str = DEFAULT_DEVICE_ALIAS,
    export: str = "",
    transport: str = "inbox",
    producer_version: str = "0.1",
    hrv_proxy_method: str = "",
    timezone: str = "UTC",
) -> Artifact:
    """Assemble the 9-key artifact for one canonical window.

    ``modality_payloads``: modality -> payload object (only present
    modalities; absent ones are omitted entirely).
    """
    payload: dict[str, Any] = {
        "kind": "canonical_window",
        "artifact_type": "canonical.window",
        "window": window_block(window_start_ms, window_end_ms, canonical_index, timezone),
        "modalities_present": {m: bool(modalities_present.get(m, False)) for m in EXPECTED_MODALITIES},
        "payload": {
            "modalities": dict(modality_payloads),
            "aligned_artifact_refs": [],
        },
        "missingness_metadata": missingness_block(modalities_present, coverage),
        "quality_metadata": quality_block({m: coverage.get(m, 0.0) for m in EXPECTED_MODALITIES}),
    }

    provenance: dict[str, Any] = {
        "producer": "pmbrs-wearable-producer",
        "producer_version": producer_version,
        "pipeline_name": PIPELINE_NAME,
        "transport": transport,
        "export": export,
        "device_alias": device_alias,
        "tier_labels": {
            "heart_rate": "observational",
            "hrv_proxy": "inferred",
            "hrv": "observational",
            "stress": "observational",
            "sleep_stage": "observational",
        },
        "hrv_proxy_method": hrv_proxy_method,
        "lineage": {
            "derived_from": "samsung_health_export",
            "derivation": "parse_align_project",
        },
    }

    return Artifact(
        artifact_id=f"wearable.win.{canonical_index}",
        source=SOURCE,
        payload=payload,
        created_at_epoch_ms=int(window_start_ms),
        schema_version=SCHEMA_VERSION,
        device_alias=device_alias,
        provenance_metadata_json=provenance,
        ingested_at_epoch_ms=0,  # server stamps on ingest
        ingest_status="pending",
    )


__all__ = [
    "SCHEMA_VERSION",
    "PIPELINE_NAME",
    "DEFAULT_DEVICE_ALIAS",
    "SOURCE",
    "EXPECTED_MODALITIES",
    "window_block",
    "missingness_block",
    "quality_block",
    "build_window_artifact",
]
