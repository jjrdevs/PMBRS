"""PMBRS artifact primitives (core layer).

Implements the raw artifact record shape documented in
``docs/storage/architecture.md`` and written by ``scripts/pmbrs_host_sync_ingest.py``:

    artifactId, source, payload, createdAtEpochMs, schemaVersion,
    deviceAlias, provenanceMetadataJson, ingestedAtEpochMs, ingestStatus

Per ADR-017 D2 the raw layer is **one JSON object per file** (plain JSON,
stdlib only — no SQLite / JSONL in this phase). ``StorageAdapter``
(``pmbrs.core.storage``) is the single consumer-facing interface over these
artifacts; downstream modules never open store files directly
(``docs/module-contracts.md``).

Note on the on-disk sample files: the 5 placeholder ``sample.json`` artifacts
under ``~/.pmbrs-private/store/raw/<source>/`` use an earlier snake_case
variant of the shape (``artifact_id``, ``created_at`` ISO-8601,
``schema_version`` plus an extra ``artifact_type`` field). The parser below
accepts **both** shapes and normalizes to the canonical record so the store
remains readable by the adapter. ``strict_validate`` reports whether a raw
mapping carries all canonical keys.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

#: The canonical on-disk record keys, in canonical order.
#: (docs/storage/architecture.md — "Artifact Record Shape (raw layer)")
CANONICAL_KEYS: tuple[str, ...] = (
    "artifactId",
    "source",
    "payload",
    "createdAtEpochMs",
    "schemaVersion",
    "deviceAlias",
    "provenanceMetadataJson",
    "ingestedAtEpochMs",
    "ingestStatus",
)

#: snake_case/legacy keys seen in the on-disk sample artifacts and early
#: draft docs, mapped to their canonical counterparts. ``created_at`` is an
#: ISO-8601 timestamp, not an integer epoch.
LEGACY_KEY_MAP: dict[str, str] = {
    "artifact_id": "artifactId",
    "created_at": "createdAtEpochMs",
    "schema_version": "schemaVersion",
}


def strict_validate(data: Mapping[str, Any]) -> list[str]:
    """Return the list of canonical record keys **missing** from ``data``.

    An empty list means the mapping carries the full documented raw-record
    shape. Keys present but not canonical are *not* reported here (unknown
    extensions are preserved via :attr:`Artifact.extras`).
    """
    if not isinstance(data, Mapping):
        raise TypeError(f"expected a mapping, got {type(data).__name__}")
    return [key for key in CANONICAL_KEYS if key not in data]


def _to_epoch_ms(value: Any) -> int:
    """Coerce a timestamp (int/float/numeric string/ISO-8601 string) to epoch ms."""
    if isinstance(value, bool):
        raise TypeError(f"invalid epoch-ms value: {value!r}")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        try:
            return int(float(text))
        except ValueError:
            pass
        try:
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError as exc:
            raise TypeError(f"invalid timestamp for epoch-ms coercion: {value!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return int(parsed.timestamp() * 1000)
    raise TypeError(f"invalid epoch-ms value: {value!r}")


@dataclass
class Artifact:
    """One PMBRS raw-layer artifact (the 9-field documented record shape).

    ``extras`` preserves any non-canonical keys (e.g. the legacy
    ``artifact_type`` field in the on-disk samples) so ``to_dict()`` is a
    lossless round-trip back to the on-disk JSON.
    """

    artifact_id: str
    source: str
    payload: dict[str, Any]
    created_at_epoch_ms: int
    schema_version: str
    device_alias: str
    provenance_metadata_json: Any
    ingested_at_epoch_ms: int
    ingest_status: str
    extras: dict[str, Any] = field(default_factory=dict)

    # -- (de)serialization ---------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return the canonical on-disk record shape (canonical keys first,
        then any preserved extra keys)."""
        data: dict[str, Any] = {
            "artifactId": self.artifact_id,
            "source": self.source,
            "payload": self.payload,
            "createdAtEpochMs": int(self.created_at_epoch_ms),
            "schemaVersion": self.schema_version,
            "deviceAlias": self.device_alias,
            "provenanceMetadataJson": self.provenance_metadata_json,
            "ingestedAtEpochMs": int(self.ingested_at_epoch_ms),
            "ingestStatus": self.ingest_status,
        }
        data.update(self.extras)
        return data

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Artifact":
        """Parse either the canonical or the legacy sample artifact shape.

        Both shapes are normalized to the canonical record so the adapter can
        consume the store uniformly. Non-canonical keys are preserved in
        :attr:`Artifact.extras` for lossless round-trips.
        """
        if not isinstance(data, Mapping):
            raise TypeError(f"expected a mapping, got {type(data).__name__}")

        legacy = any(key in data for key in LEGACY_KEY_MAP)
        raw: dict[str, Any]
        if legacy:
            # snake_case / early-draft keys -> canonical; keep the rest as-is.
            raw = {LEGACY_KEY_MAP.get(key, key): value for key, value in data.items()}
        else:
            raw = dict(data)

        payload = raw.get("payload")
        if payload is None:
            payload = {}
        if not isinstance(payload, Mapping):
            raise TypeError(f"payload must be an object, got {type(payload).__name__}")

        # Normalize creation timestamp to integer epoch-ms (accepts int, float,
        # numeric string, or ISO-8601 string as in the legacy samples).
        if "createdAtEpochMs" in raw:
            raw["createdAtEpochMs"] = _to_epoch_ms(raw["createdAtEpochMs"])
        else:
            raise KeyError("artifact is missing 'createdAtEpochMs'")

        created_ms = int(raw["createdAtEpochMs"])

        # Ingest timestamp: fall back to creation time when the record
        # predates the field (legacy samples) or omits it.
        if "ingestedAtEpochMs" in raw:
            raw["ingestedAtEpochMs"] = _to_epoch_ms(raw["ingestedAtEpochMs"])
        else:
            raw["ingestedAtEpochMs"] = created_ms

        # Documented fallbacks for fields a raw record may omit.
        raw.setdefault("schemaVersion", "1.0")
        raw.setdefault("deviceAlias", "unknown")
        raw.setdefault("ingestStatus", "accepted")

        provenance = raw.get("provenanceMetadataJson")
        if provenance is None:
            provenance = {}
        elif isinstance(provenance, str):
            try:
                provenance = json.loads(provenance)
            except (ValueError, TypeError):
                provenance = None  # keep raw string if it is not valid JSON

        # Preserve any non-canonical keys (e.g. legacy 'artifact_type') so that
        # to_dict() round-trips the original on-disk record faithfully.
        extras = {k: v for k, v in raw.items() if k not in CANONICAL_KEYS}

        return cls(
            artifact_id=str(raw["artifactId"]),
            source=str(raw["source"]),
            payload=dict(payload),
            created_at_epoch_ms=created_ms,
            schema_version=str(raw["schemaVersion"]),
            device_alias=str(raw["deviceAlias"]),
            provenance_metadata_json=provenance,
            ingested_at_epoch_ms=int(raw["ingestedAtEpochMs"]),
            ingest_status=str(raw["ingestStatus"]),
            extras=extras,
        )

    @classmethod
    def from_file(cls, path: str | Path) -> "Artifact":
        """Load one artifact JSON file from the store."""
        with Path(path).open("r", encoding="utf-8") as fh:
            return cls.from_dict(json.load(fh))


@dataclass(frozen=True)
class LineageEdge:
    """One edge in the artifact lineage DAG (``derive_from``, module contract).

    ``parent_ids`` → upstream (authoritative) artifacts; ``child_id`` is the
    derived artifact produced by ``module``.
    """

    child_id: str
    parent_ids: tuple[str, ...]
    edge_type: str = "derived"
    module: str | None = None
    created_at_epoch_ms: int = 0
