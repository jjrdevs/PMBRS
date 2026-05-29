# Artifact Lifecycle Contract

## Purpose

This contract defines the operational lifecycle states governing artifacts within PMBRS.

The purpose of this contract is to:

- preserve immutability guarantees,
- formalize regeneration semantics,
- prevent silent mutation,
- govern archival behavior,
- support lineage integrity,
- enable reproducible analytical infrastructure.

---

## Scope

This contract applies to:

- authoritative artifacts,
- derived artifacts,
- inferred artifacts,
- canonical windows,
- evaluation artifacts,
- experiment artifacts,
- lineage-tracked operational artifacts.

This contract does not apply to:

- temporary in-memory execution state,
- ephemeral UI state,
- transient runtime caches.

---

## Core Principles

### Principle 1 — Finalized Artifacts Are Immutable

Finalized authoritative artifacts may never be modified in-place.

Corrections, reinterpretations, or recomputations must occur through:

- supersession,
- regeneration,
- lineage-linked replacement artifacts.

---

### Principle 2 — Historical Lineage Must Be Preserved

Artifact lifecycle transitions must preserve historical reproducibility.

Lifecycle operations may not destroy:

- lineage continuity,
- provenance metadata,
- transformation traceability.

---

### Principle 3 — Derived Artifacts Are Reproducible, Not Canonical Truth

Derived artifacts:

- may be regenerated,
- may be superseded,
- remain model-dependent,
- are not authoritative evidence.

---

## Lifecycle States

### Allowed States

```yaml
lifecycle_state:
  - proposed
  - ingested
  - validated
  - finalized
  - superseded
  - deprecated
  - archived
  - failed
  - deleted_logical
  - deleted_physical
```

---

## Lifecycle State Definitions

| State | Meaning |
|---|---|
| PROPOSED | declared but not yet operationally accepted |
| INGESTED | entered the system but not validated |
| VALIDATED | passed schema and integrity checks |
| FINALIZED | immutable operational state |
| SUPERSEDED | replaced by newer equivalent artifact |
| DEPRECATED | retained but discouraged for future use |
| ARCHIVED | moved to cold storage |
| FAILED | invalid artifact |
| DELETED_LOGICAL | hidden operationally while preserving lineage |
| DELETED_PHYSICAL | permanently removed from storage |

---

## Allowed Lifecycle Transitions

| From | To | Allowed |
|---|---|---|
| proposed | ingested | yes |
| ingested | validated | yes |
| validated | finalized | yes |
| validated | failed | yes |
| finalized | superseded | yes |
| finalized | archived | yes |
| archived | finalized | no |
| finalized | ingested | no |
| failed | deleted_physical | yes |
| superseded | archived | yes |

---

## Mutation Rules

| Artifact Class | Mutable |
|---|---|
| authoritative artifacts | no |
| derived artifacts | no |
| inferred artifacts | no |
| caches | yes |
| indexes | yes |
| UI metadata | yes |

---

## Supersession Semantics

Supersession replaces operational preference without destroying historical artifacts.

Superseded artifacts must:

- remain lineage-accessible,
- preserve provenance,
- preserve schema integrity,
- preserve historical reproducibility.

### Required Field

```yaml
superseded_by:
```

---

## Archival Semantics

Archived artifacts:

- remain immutable,
- remain lineage-accessible,
- may be moved to cold storage,
- may not lose provenance metadata.

Archival status must not imply invalidity.

---

## Validation Rules

- FINALIZED artifacts may not transition backward.
- Derived artifacts must preserve lineage before FINALIZED transition.
- FAILED artifacts may not become FINALIZED.
- SUPERSEDED artifacts must reference successor artifacts.
- DELETED_PHYSICAL artifacts must preserve deletion tombstones.

---

## Forbidden Behaviors

- Finalized authoritative artifacts may not mutate in-place.
- Lifecycle transitions may not silently erase lineage.
- Derived artifacts may not overwrite upstream authoritative artifacts.
- Archival may not discard provenance.
- Supersession may not destroy historical reproducibility.

---

## Reproducibility Requirements

Lifecycle transitions must remain:

- lineage-traceable,
- auditable,
- versioned,
- reproducible.

All lifecycle operations affecting derived artifacts must preserve:

- upstream references,
- execution provenance,
- schema versions.

---

## Operational Notes

PMBRS intentionally uses immutable-first operational semantics.

This architecture prioritizes:

- historical reproducibility,
- epistemological integrity,
- analytical auditability,
- regeneration-based correction.

---

## Future Considerations

Potential future extensions:

- distributed archival policies,
- automated cold-storage migration,
- lineage-aware garbage collection,
- retention economics optimization.
