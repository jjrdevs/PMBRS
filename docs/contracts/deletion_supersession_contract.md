# Deletion and Supersession Contract

## Purpose

This contract defines the operational semantics governing:

- deletion,
- supersession,
- regeneration,
- lineage preservation,
- privacy purge behavior.

The purpose of this contract is to prevent silent lineage corruption and preserve reproducibility integrity.

---

## Scope

This contract applies to:

- authoritative artifacts,
- derived artifacts,
- inferred artifacts,
- canonical windows,
- lineage metadata,
- experiment artifacts.

---

## Core Principles

### Principle 1 — Deletion Must Not Silently Corrupt Lineage

Artifact deletion may not destroy historical interpretability without explicit tombstone semantics.

---

### Principle 2 — Supersession Is Preferred Over Mutation

Artifacts are replaced through immutable supersession rather than in-place modification.

---

### Principle 3 — Derived Outputs Are Regenerated, Not Edited

Corrections to derived artifacts occur through recomputation and lineage-preserving regeneration.

---

## Deletion Types

### Logical Deletion

Logical deletion:

- hides artifacts operationally,
- preserves lineage,
- preserves metadata,
- preserves auditability.

### Required Fields

```yaml
deleted_logically: true
deleted_reason:
deleted_timestamp:
```

---

### Physical Deletion

Physical deletion:

- removes artifact payloads,
- preserves deletion tombstones,
- invalidates dependent artifacts where necessary.

### Required Fields

```yaml
deleted_physically: true
physical_deletion_timestamp:
```

---

## Tombstone Semantics

Deletion tombstones preserve:

- artifact identity,
- deletion metadata,
- lineage continuity,
- deletion rationale.

Deleted artifacts may not disappear silently from lineage graphs.

---

## Supersession Semantics

Supersession creates successor artifacts without mutating predecessors.

### Required Fields

```yaml
supersedes_artifact_id:
supersession_reason:
```

---

## Regeneration Semantics

| Artifact Type | Editable | Regeneratable |
|---|---|---|
| authoritative | no | no |
| canonical window | no | yes |
| derived | no | yes |
| inferred | no | yes |

---

## Privacy Purge Semantics

PMBRS uses a local-first privacy architecture.

Privacy purge operations may:

- remove raw payloads,
- preserve lineage stubs,
- preserve operational integrity.

### Example

```yaml
privacy_purge:
  remove_raw_content: true
  preserve_lineage_stub: true
```

---

## Validation Rules

- Physical deletion must preserve tombstones.
- Superseded artifacts must preserve predecessor linkage.
- Derived artifact regeneration must preserve provenance.
- Privacy purges may not silently invalidate lineage.

---

## Forbidden Behaviors

- Silent overwrite of finalized artifacts.
- Deletion without lineage traceability.
- Supersession without predecessor linkage.
- Derived artifact mutation in-place.
- Recursive reinterpretation of authoritative artifacts.

---

## Reproducibility Requirements

Deletion and supersession operations must preserve:

- auditability,
- lineage continuity,
- reproducibility metadata,
- operational traceability.

---

## Future Considerations

Potential future extensions:

- lineage-aware storage compaction,
- selective retention policies,
- privacy-aware recomputation strategies,
- distributed deletion propagation.
