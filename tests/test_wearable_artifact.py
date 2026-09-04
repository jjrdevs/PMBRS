"""Pin the 9-key canonical-window artifact (ADR-021 D4 / contract).

The raw artifact is ``pmbrs.core.artifact.Artifact`` whose serialized form is
exactly ``CANONICAL_KEYS`` (9 keys). The wearable module fills the PMBRS
canonical window contract (kind/artifact_type/window/modalities_present/
payload/missingness_metadata/quality_metadata) into the ``payload`` key and
pins provenance into ``provenanceMetadataJson``.

Pins:
- ``to_dict()`` exposes exactly the 9 canonical keys
- payload carries all 7 contract sections
- coverage / missingness / quality semantics (absent == 0.0, never a value)
- provenance pins producer/transport/export/device_alias + tier labels
"""
from __future__ import annotations

import dataclasses

from pmbrs.core.artifact import CANONICAL_KEYS, Artifact
from pmbrs.ingestion.wearable.artifact import (
    EXPECTED_MODALITIES,
    build_window_artifact,
    missingness_block,
    quality_block,
)

CANONICAL_TUPLE = tuple(CANONICAL_KEYS)

# A single canonical window at 2026-08-30T12:00:00Z
START = 1759500000000  # not aligned; grid math is producer's job, not artifact's
END = START + 60000


def _make(present=None, coverage=None):
    present = present if present is not None else {"heart_rate": True, "hrv_proxy": True, "hrv": True, "stress": False, "sleep_stage": False}
    if coverage is None:
        coverage = {m: (1.0 if p else 0.0) for m, p in present.items()}
    payloads = {
        "heart_rate": {"bpm": 72.0, "bins": 1},
        "hrv_proxy": {"bpm": 71.5, "windows": 10, "method": "rmssd-of-means"},
        "hrv": {"sdnn_ms": 50.0, "rmssd_ms": 60.0, "derived_by_watch": True},
    }
    return build_window_artifact(
        canonical_index=123456,
        window_start_ms=START,
        window_end_ms=END,
        modalities_present=present,
        coverage=coverage,
        modality_payloads=payloads,
        device_alias="galaxy-watch7",
        export="export_20260830",
        transport="inbox",
        producer_version="0.1",
        hrv_proxy_method="rmssd-of-means",
        timezone="UTC",
    )


class TestCanonicalKeys:
    def test_to_dict_is_exactly_nine_keys(self):
        d = _make().to_dict()
        assert set(d.keys()) == set(CANONICAL_TUPLE)
        assert len(CANONICAL_KEYS) == 9

    def test_artifact_is_artifact_instance(self):
        a = _make()
        assert isinstance(a, Artifact)

    def test_artifact_id_is_deterministic(self):
        assert _make().artifact_id == "wearable.win.123456"
        assert _make().device_alias == "galaxy-watch7"
        assert _make().source == "mobile"


class TestPayloadContract:
    def test_all_seven_sections_present(self):
        p = _make().payload
        expected = {"kind", "artifact_type", "window", "modalities_present",
                    "payload", "missingness_metadata", "quality_metadata"}
        assert expected <= set(p.keys())
        assert p["kind"] == "canonical_window"
        assert p["artifact_type"] == "canonical.window"

    def test_window_block(self):
        w = _make().payload["window"]
        assert w["resolution_seconds"] == 60
        assert w["canonical_index"] == 123456
        assert w["timezone"] == "UTC"
        assert w["start_time"].endswith("Z")
        # 60-second span
        from datetime import datetime, timezone
        s = datetime.strptime(w["start_time"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        e = datetime.strptime(w["end_time"], "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
        assert (e - s).total_seconds() == 60

    def test_modalities_present_covers_all_expected(self):
        mp = _make().payload["modalities_present"]
        assert set(mp) == set(EXPECTED_MODALITIES)
        assert mp["heart_rate"] is True
        assert mp["sleep_stage"] is False

    def test_payload_carries_only_present_modalities(self):
        inner = _make().payload["payload"]["modalities"]
        assert set(inner) == {"heart_rate", "hrv_proxy", "hrv"}
        # absent stress/sleep keys are omitted entirely, not zero-filled
        assert "stress" not in inner
        assert "sleep_stage" not in inner

    def test_aligned_artifact_refs_is_list(self):
        assert _make().payload["payload"]["aligned_artifact_refs"] == []


class TestMissingnessAndQuality:
    def test_missing_modalities_lists_absent(self):
        mm = _make().payload["missingness_metadata"]
        assert mm["missing_modalities"] == ["stress", "sleep_stage"]
        # coverage is 1.0 for present, 0.0 for absent
        cov = mm["modality_coverage"]
        assert set(cov) == set(EXPECTED_MODALITIES)
        assert cov["heart_rate"] == 1.0
        assert cov["sleep_stage"] == 0.0
        assert mm["corruption_flags"] == []
        assert mm["delayed_modalities"] == []

    def test_quality_tier_high_for_mostly_covered(self):
        q = _make().payload["quality_metadata"]
        # 3/5 modalities covered at 1.0 -> overall 0.6
        assert abs(q["overall_window_quality"] - 0.6) < 1e-9
        assert q["quality_tier"] in {"high", "medium"}

    def test_all_modalities_gives_high_quality(self):
        present = {m: True for m in EXPECTED_MODALITIES}
        coverage = {m: 1.0 for m in EXPECTED_MODALITIES}
        q = _make(present=present, coverage=coverage).payload["quality_metadata"]
        assert q["overall_window_quality"] == 1.0
        assert q["quality_tier"] == "high"

    def test_missingness_block_is_pure_function(self):
        mm = missingness_block({"heart_rate": True}, {"heart_rate": 1.0})
        assert "stress" in mm["missing_modalities"]
        assert mm["modality_coverage"]["heart_rate"] == 1.0

    def test_quality_block_pure(self):
        assert quality_block({})["quality_tier"] == "low"


class TestProvenance:
    def test_provenance_pins_key_fields(self):
        prov = _make().provenance_metadata_json
        assert prov["producer"] == "pmbrs-wearable-producer"
        assert prov["producer_version"] == "0.1"
        assert prov["pipeline_name"] == "wearable_canonical_window"
        assert prov["transport"] == "inbox"
        assert prov["export"] == "export_20260830"
        assert prov["device_alias"] == "galaxy-watch7"
        assert prov["hrv_proxy_method"] == "rmssd-of-means"
        assert prov["lineage"]["derived_from"] == "samsung_health_export"

    def test_tier_labels_map(self):
        tl = _make().provenance_metadata_json["tier_labels"]
        assert tl["heart_rate"] == "observational"
        assert tl["hrv_proxy"] == "inferred"
        assert tl["hrv"] == "observational"

    def test_ingest_status_pending_and_zero_timestamps(self):
        a = _make()
        assert a.ingest_status == "pending"
        assert a.ingested_at_epoch_ms == 0


class TestRoundTrip:
    def test_to_dict_and_back_preserves_fields(self):
        a = _make()
        d = a.to_dict()
        b = Artifact.from_dict(d)
        assert b.artifact_id == a.artifact_id
        assert b.source == a.source
        assert b.schema_version == a.schema_version
        assert b.payload == a.payload
        assert b.provenance_metadata_json == a.provenance_metadata_json
