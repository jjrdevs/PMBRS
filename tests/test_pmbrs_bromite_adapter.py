import importlib.util
from pathlib import Path


def load_adapter_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "pmbrs_bromite_adapter.py"
    spec = importlib.util.spec_from_file_location("pmbrs_bromite_adapter", str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_validate_and_map_canonical_visit():
    mod = load_adapter_module()
    artifact = {
        "event_type": "browser_visit",
        "visit_id": "visit-123",
        "visit_start_ms": 1610000000000,
        "visit_end_ms": 1610000000050,
        "dwell_ms": 50,
        "provenance": {"recorded_at_ms": 1610000000000},
        "raw_content_blocked": True,
        "schema_version": "1.0",
        "source_app": "org.bromite",
        "canonical_host": "example.com",
    }

    errs = mod.validate_artifact(artifact)
    assert errs == [], f"expected no validation errors, got: {errs}"

    record = mod.to_sync_record(artifact)
    assert record["source"] == "browser"
    assert record["artifactId"] == "visit-123"
    assert record["createdAtEpochMs"] == 1610000000000


def test_validate_and_map_wrapped_mobile_shape():
    mod = load_adapter_module()
    wrapped = {
        "artifactId": "mobile-1",
        "source": "browser_metadata",
        "payload": {
            "browser_package": "org.bromite",
            "browser_name": "Bromite",
            "observed_at_ms": 1620000000000,
        },
    }

    errs = mod.validate_artifact(wrapped)
    assert errs == [], f"expected no validation errors for wrapped mobile shape, got: {errs}"

    record = mod.to_sync_record(wrapped)
    assert record["source"] == "browser"
    assert record["createdAtEpochMs"] == 1620000000000
