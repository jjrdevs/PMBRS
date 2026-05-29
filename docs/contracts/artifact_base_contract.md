## Purpose

Defines the canonical artifact superclass used across PMBRS. This contract is the authoritative schema that examples and downstream validators MUST follow.

## Required Fields (canonical)

Every artifact MUST include the following top-level fields unless a narrower contract explicitly overrides them:

```yaml
artifact_id: string  # UUID v4
artifact_type: string
artifact_class: enum(authoritative, derived, inferred, canonical, experiment, feature, embedding)
authority_level: enum(authoritative, operational, derived)
lifecycle_state: enum(proposed, ingested, validated, finalized, superseded, deprecated, archived, failed, deleted_logical, deleted_physical)
schema_version: string
created_at: timestamp
content_hash: string  # algorithm specified by content_hash_algorithm
content_hash_algorithm: string
hash_scope_version: string
lineage:
  derived_from: list[string]
  observed_from: list[string]
  aggregated_from: list[string]
  referenced_by: list[string]
provenance: object
canonical_time_refs: list[string]
modality_refs: list[string]
payload: object
```

`canonical_time_refs` and `modality_refs` are required but MAY be empty lists when not applicable to a given artifact type.

The nested `lineage` structure replaces older flat `lineage_refs` patterns and supports explicit edge types.

## Artifact Identity and Content Hashing

Artifacts use UUIDs for operational identity and content hashes for reproducibility, equivalence detection, and lineage integrity.

### Content Hash Specification

- **Algorithm:** SHA-256 (hex digest). Field: `content_hash_algorithm` = "sha256".
- **Serialization:** Canonical JSON serialization (JCS-style: UTF-8, sorted object keys, no insignificant whitespace, deterministic number formatting). Implementations SHOULD follow the JSON Canonicalization Scheme (RFC 8785 or equivalent).
- **Input:** The canonical serialization of authoritative artifact metadata only, including:
  - `artifact_type`
  - `artifact_class`
  - `authority_level`
  - `schema_version`
  - `payload`
  - `lineage`
  - `provenance` (excluding provenance fields explicitly marked mutable)
  - `canonical_time_refs`
- **Exclusions:** Timestamps except `created_at`, operational metadata, and mutable cache fields MUST be excluded from the content hash scope. These include: `lifecycle_state`, ingestion timestamps, `execution_timestamp`, and other environment-derived fields that are expected to differ across regenerations.
- **Purpose:** `content_hash` enables deduplication, equivalence checking, and lineage integrity validation.

Field examples and canonicalization rules MUST be applied consistently by any code generator.

## Field-Level Invariants (Required)

Every field declared in a contract MUST define:

- type
- required/optional status
- validation rule (format, range, or constraint)
- semantic meaning
- null/missing behavior, if applicable

For example:

- `artifact_id`: UUID v4, required, immutable, no nulls.
- `content_hash`: SHA-256 over canonical JSON serialization, required, no nulls.
- `start_time` / `end_time`: timestamps, required when present, must satisfy `start_time < end_time`.

Field-level invariants are mandatory for all contracts and are the schema-level constraints that prevent implicit model guessing.

## Artifact Constraints

All artifacts MUST:

- be schema-valid according to their `artifact_type` and `schema_version`.
- expose explicit `lineage` as shown above.
- include a `provenance` object consistent with the provenance base contract.
- remain immutable after `FINALIZED` unless superseded via the lifecycle semantics defined in the lifecycle contract.

