# Schema Evolution Contract

## Purpose

Defines how PMBRS handles schema versions, backward compatibility, and migration semantics.

This contract is intended to preserve historical integrity while allowing derived artifacts and analytical outputs to evolve.

## Principles

- authoritative artifacts are immutable once finalized
- derived artifacts are regenerated, not rewritten
- schema version metadata is explicit and mandatory
- backward compatibility is preserved for canonical semantics
- historical lineage and auditability are never destroyed

## Required Fields

All artifacts MUST include `schema_version` as defined by `artifact_base_contract.md`.

Additionally, artifact producers SHOULD include the following when a schema change occurs:

```yaml
schema_evolution:
  previous_schema_version: string  # optional for new artifacts, required when migrating
  compatibility_level: enum(backward, forward, bidirectional, breaking)
  migration_reason: string
  deprecated_fields: list[string]
  introduced_fields: list[string]
  regeneration_strategy: enum(regenerate_derived, maintain_historical, versioned_parallel)
```

## Authoritative Artifact Immutability

Authoritative artifacts MUST NEVER be retroactively rewritten solely for schema changes.

- Raw observational records remain stable.
- User declarations and experiment artifacts remain archived with original semantics.
- Canonical windows remain fixed by the global temporal grid.

## Derived Artifact Regeneration

Derived artifacts MUST be regenerated under new schema definitions rather than mutating existing finalized artifacts.

- features, embeddings, evaluations, and summaries are re-produced with new schema versions.
- lineage MUST preserve references to both the original inputs and the regenerated outputs.
- historical artifacts remain accessible for reproducibility and audit.

## Backward Compatibility Requirements

Backward compatibility MUST be preserved for the following core semantics whenever possible:

- canonical temporal alignment
- artifact identity and content hashing
- lineage edge semantics
- provenance classification and required fields
- modality contract requirements
- authoritative artifact definitions

Breaking changes are permitted only when explicitly declared, versioned, and documented.

## Deprecation and Historical Traceability

When a schema element is deprecated:

- the deprecated version remains lineage-traceable
- downstream artifacts MUST record the schema version used
- migration paths MUST preserve historic reproducibility

## Migration Rules

- preserve historical integrity: do not rewrite finalized authoritative artifacts
- maintain deterministic lineage continuity across schema versions
- support safe subsystem replacement through explicit contract mapping
- require a documented migration strategy for any breaking schema change
- keep schema evolution orthogonal to business logic changes

## Related Contracts

- `artifact_base_contract.md`
- `artifact_lifecycle_contract.md`
- `provenance/provenance_base_contract.md`
- `execution_rules.md`
- `core_responsibility.md`
