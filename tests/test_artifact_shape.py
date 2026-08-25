"""Shape tests for the raw-layer artifact record.

READ-ONLY: these tests load the five real sample artifacts under
``~/.pmbrs-private/store/raw/<source>/sample.json``. They never write to the
real store.

The on-disk samples use the earlier snake_case draft shape; ADR-017 D2 pins
the canonical nine-key camelCase record. Both must parse to a well-formed
``Artifact``; ``strict_validate`` enumerates which canonical keys each raw
record is missing.
"""

from __future__ import annotations

import json
from pathlib import Path

from pmbrs.core.artifact import CANONICAL_KEYS, Artifact, strict_validate

REAL_RAW_ROOT = Path("/home/jjrdev/.pmbrs-private/store/raw")
SOURCES = ("browser", "desktop", "journal", "mobile", "other")


def _iter_real_samples():
    for source in SOURCES:
        path = REAL_RAW_ROOT / source / "sample.json"
        yield source, path


def test_all_real_samples_exist():
    for source, path in _iter_real_samples():
        assert path.is_file(), f"expected real sample at {path} (source={source})"


def test_each_real_sample_is_valid_json():
    for source, path in _iter_real_samples():
        data = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(data, dict), f"{source}: sample must be a JSON object"


def test_each_real_sample_parses_to_well_formed_artifact():
    for source, path in _iter_real_samples():
        artifact = Artifact.from_file(path)
        assert artifact.source == source
        assert artifact.artifact_id == "demo-mobile-1"
        assert artifact.payload.get("kind") == source
        assert artifact.created_at_epoch_ms > 0
        assert artifact.schema_version
        assert artifact.device_alias
        assert artifact.ingested_at_epoch_ms >= 0
        assert artifact.ingest_status


def test_strict_validator_lists_all_eight_plus_documented_keys():
    """Each real sample record is validated against the full canonical key set.

    The samples carry ``source`` and ``payload`` under canonical names but
    predate the remaining documented fields, so ``strict_validate`` must
    report exactly the canonical keys each sample lacks (7 of 9) and — after
    parsing — every sample normalizes to a record with all 9 keys present.
    """
    for source, path in _iter_real_samples():
        data = json.loads(path.read_text(encoding="utf-8"))
        missing = strict_validate(data)
        assert missing == [
            "artifactId",
            "createdAtEpochMs",
            "schemaVersion",
            "deviceAlias",
            "provenanceMetadataJson",
            "ingestedAtEpochMs",
            "ingestStatus",
        ], f"{source}: missing={missing}"
        assert len(CANONICAL_KEYS) == 9
        assert set(missing) == {
            "artifactId",
            "createdAtEpochMs",
            "schemaVersion",
            "deviceAlias",
            "provenanceMetadataJson",
            "ingestedAtEpochMs",
            "ingestStatus",
        }
        # Post-parse, the adapter sees the complete documented record.
        assert strict_validate(Artifact.from_dict(data).to_dict()) == []


def test_strict_validator_passes_for_canonical_record():
    canonical = {
        "artifactId": "a1",
        "source": "mobile",
        "payload": {"kind": "mobile"},
        "createdAtEpochMs": 1720000000000,
        "schemaVersion": "1.0",
        "deviceAlias": "pixel-7",
        "provenanceMetadataJson": {},
        "ingestedAtEpochMs": 1720000000123,
        "ingestStatus": "accepted",
    }
    assert strict_validate(canonical) == []
    artifact = Artifact.from_dict(canonical)
    assert artifact.to_dict()["artifactId"] == "a1"


def test_legacy_sample_round_trips_losslessly():
    path = REAL_RAW_ROOT / "browser" / "sample.json"
    original = json.loads(path.read_text(encoding="utf-8"))
    artifact = Artifact.from_file(path)
    restored = artifact.to_dict()
    # Preserve both canonical fields (defaults applied) and the legacy extras.
    assert restored["source"] == original["source"]
    assert restored["payload"] == original["payload"]
    assert restored["artifact_type"] == original["artifact_type"]
    assert strict_validate(restored) == []  # now carries the full canonical shape
