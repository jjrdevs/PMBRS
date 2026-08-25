#!/usr/bin/env python3
"""Adapter: validate Bromite `browser_visit` artifacts and persist into PMBRS raw store.

Usage examples:

    python3 scripts/pmbrs_bromite_adapter.py --input docs/ingestion/adapters/examples/browser_visit_example.json

The script will validate the artifact against the JSON Schema and call
`persist_sync_batch` from `scripts.pmbrs_host_sync_ingest` to write the
artifact into the PMBRS raw root under the `browser/` source directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent.parent
SCHEMA_PATH = HERE / "docs" / "ingestion" / "schemas" / "browser_visit.schema.json"


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_artifact(artifact: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    # Preferred: use jsonschema if available
    try:
        import jsonschema  # type: ignore

        schema = load_json(SCHEMA_PATH)
        jsonschema.validate(instance=artifact, schema=schema)
        return []
    except Exception:
        # fallback to minimal checks. Accept either the canonical bromite
        # `browser_visit` schema or the legacy mobile collector shape which
        # provides `canonical_url`/`browser_package` or `browser_package`-based metadata.
        # If the artifact is a PMBRS-wrapped record with `payload`, unwrap it.
        candidate = artifact
        if isinstance(artifact, dict) and "payload" in artifact and isinstance(artifact.get("payload"), dict):
            candidate = artifact.get("payload")
        if isinstance(candidate, dict):
            # canonical schema
            if candidate.get("event_type") == "browser_visit" and candidate.get("visit_id"):
                return []
            # mobile metadata/visit shapes
            mobile_keys = {"browser_package", "browser_name", "observed_at_ms", "canonical_url", "hostname", "page_started_ms", "page_started_ms", "page_ended_ms"}
            if any(k in candidate for k in mobile_keys):
                return []
        errors.append("artifact does not match known browser_visit or mobile collector shapes")
    return errors


def to_sync_record(artifact: dict[str, Any]) -> dict[str, Any]:
    # Map a browser_visit artifact into the PMBRS sync batch item
    import uuid

    # If the input is a PMBRS-wrapped record, prefer the inner payload for
    # field extraction while preserving top-level artifact properties.
    payload = artifact.get("payload") if isinstance(artifact, dict) and artifact.get("payload") else artifact

    # prefer explicit visit_id, otherwise synthesize from available fields
    artifact_id = payload.get("visit_id") or artifact.get("artifactId") or payload.get("artifactId")
    if not artifact_id:
        # try browser_package + timestamp or canonical_url
        if payload.get("browser_package") and payload.get("observed_at_ms"):
            artifact_id = f"{payload.get('browser_package')}-{int(payload.get('observed_at_ms'))}"
        elif payload.get("canonical_url") and payload.get("visit_start_ms"):
            artifact_id = f"{hash(payload.get('canonical_url')) & 0xffffffff}-{int(payload.get('visit_start_ms'))}"
        else:
            artifact_id = str(uuid.uuid4())

    # created time: try visit_start, observed_at, provenance.recorded_at
    created_ms = (
        payload.get("visit_start_ms")
        or payload.get("visit_start")
        or payload.get("observed_at_ms")
        or (artifact.get("createdAtEpochMs") if artifact.get("createdAtEpochMs") else None)
        or (artifact.get("provenance", {}) or {}).get("recorded_at_ms")
    )
    return {
        "artifactId": artifact_id,
        "source": "browser",
        "payload": payload,
        "createdAtEpochMs": int(created_ms) if created_ms else None,
        "schemaVersion": artifact.get("schema_version", artifact.get("schemaVersion", payload.get("schema_version", "1.0"))),
        "deviceAlias": artifact.get("device_id") or artifact.get("deviceAlias") or payload.get("device_id") or payload.get("deviceAlias") or "unknown",
        "provenanceMetadataJson": artifact.get("provenance", artifact.get("provenanceMetadataJson", payload.get("provenance", {}))),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="PMBRS Bromite adapter: validate and persist browser_visit artifacts")
    parser.add_argument("--input", required=True, help="Path to JSON file containing a browser_visit artifact or JSONL of artifacts")
    parser.add_argument("--raw-root", default=None, help="Optional raw root override for PMBRS storage")
    args = parser.parse_args(argv)

    path = Path(args.input)
    if not path.exists():
        print(f"Input not found: {path}")
        return 2

    # load artifacts
    try:
        if path.suffix.lower() == ".jsonl":
            artifacts = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        else:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                artifacts = data
            else:
                artifacts = [data]
    except json.JSONDecodeError as e:
        print(f"Invalid JSON in input: {e}")
        return 3

    validated = []
    for art in artifacts:
        errs = validate_artifact(art)
        if errs:
            print("Validation errors for artifact:")
            for e in errs:
                print(" - ", e)
            continue
        validated.append(art)

    if not validated:
        print("No valid artifacts to persist.")
        return 4

    # Map to sync records
    records = [to_sync_record(a) for a in validated]

    # Import the host persist function and call it
    try:
        # Import persist_sync_batch by file path to avoid package resolution issues
        import importlib.util

        host_ingest_path = Path(__file__).resolve().parent / "pmbrs_host_sync_ingest.py"
        if not host_ingest_path.exists():
            print(f"Host ingest script not found at {host_ingest_path}")
            return 5
        spec = importlib.util.spec_from_file_location("pmbrs_host_sync_ingest", str(host_ingest_path))
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)  # type: ignore
        persist_sync_batch = getattr(module, "persist_sync_batch")

        raw_root = args.raw_root
        if raw_root is None:
            # use default inside persist_sync_batch
            written = persist_sync_batch(batch=records)
        else:
            written = persist_sync_batch(raw_root=raw_root, batch=records)

        print(f"Persisted {len(written)} artifact file(s):")
        for p in written:
            print(" -", p)
    except Exception as e:  # pragma: no cover - best-effort
        print("Failed to persist via persist_sync_batch:", e)
        return 5

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
