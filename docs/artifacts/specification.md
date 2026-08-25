# Artifact Architecture — Specification

## Overview

PMBRS uses an immutable-first, lineage-centric artifact architecture where all subsystems communicate exclusively through formally defined artifacts. This document operationalizes Constitution §11 and ADR-003.

## Artifact Definition

An artifact is any structured object produced, consumed, stored, transformed, or referenced within PMBRS. Every artifact contains:

| Field | Type | Description |
|---|---|---|
| `artifact_id` | UUID / content hash | Globally unique identifier (split point TBD in ADR-003) |
| `artifact_type` | string | Enum value identifying the kind (e.g., `wearable_event`, `canonical_window`) |
| `created_at` | ISO-8601 UTC | Creation timestamp — never retroactively changed |
| `lineage_refs` | list[ArtifactRef] | Upstream artifact IDs this was derived from |
| `schema_version` | semver string (e.g., `1.2.0`) | Schema version for backward compatibility checks |
| `config_ref` | URI or hash | Points to configuration snapshot used during creation |
| `modality_refs` | list[str] | Which modalities this artifact pertains to |
| `provenance` | ProvenanceRecord | Who/what produced this, when, under which environment |

## Artifact Types (Exhaustive Catalog — see schema-catalog.md)

### Observational Artifacts (Authoritative, Immutable, Append-Only)
- `wearable_event`, `browser_event`, `mobile_log_event`, `calendar_event`, `journal_chunk`
- These are **lineage roots** — irreducible historical evidence that is never modified in place.

### Canonical Structural Artifacts (Operationally Authoritative, Immutable)
- `canonical_window`, `modality_alignment_mapping`, `window_modality_coverage`, `missingness_mask`
- Globally referenced operational infrastructure. Reproducible from upstream observational data.

### Derived Analytical Artifacts (Non-Authoritative, Versioned, Replaceable)
- `feature_vector`, `behavioral_embedding`, `clustering_result`, `inferred_behavioral_event`
- Lineage-dependent, reproducible, replaceable. Superseded rather than overwritten on regeneration.

### Semantic/Interpretive Artifacts (Probabilistic, Non-Deterministic)
- `llm_summary`, `semantic_label`, `sentiment_analysis`, `behavioral_explanation`
- Must never overwrite upstream observational evidence. Highly version-sensitive to LLM model used.

### Experimental Artifacts (Lineage-Linked, Temporally Scoped)
- `experiment_definition`, `intervention_declaration`, `comparison_cohort`, `evaluation_report`
- Partially authoritative for user-declared interventions; derived analytics around experiments are non-authoritative per Constitution §13.

## Identity Model (Pending ADR-003)

Hybrid strategy to be decided:
- **Content hash**: For reproducible artifacts where hash provides deduplication + integrity verification
- **UUID**: For transient/execution objects, user-declared entries, non-deterministic outputs
- The split point between these two regimes is the core question ADR-003 resolves.

## Lineage Model

Directed acyclic graph with edge types:

| Edge Type | Meaning | Example |
|---|---|---|
| `derived-from` | Computed from upstream artifact(s) | Feature vector derived-from canonical window |
| `observed-from` | Captured via adapter/provider | Wearable event observed-from Fitbit API |
| `aggregated-from` | Rollup of multiple same-type artifacts | Daily summary aggregated-from 1440 canonical windows |
| `referenced-by` | Cited but not transformed by | Experiment definition referenced-by evaluation report |

**Mandatory** for all derived and interpretive artifacts. Must identify: upstream inputs, producing subsystem, execution timestamp, configuration snapshot, model version, dependency versions, code revision/environment snapshot.

## Immutability Rules

| Mutable | Immutable |
|---|---|
| Caches, indexes, temporary processing state, UI convenience metadata, orchestration state | Raw observational evidence, journal entries, experiment declarations, canonical windows, derived analytical outputs — never modified in place; supersession creates new artifacts. |

## Lifecycle States (Operational Metadata Only)

`proposed` -> `validated` -> `finalized` / `deprecated` / `superseded` / `archived` / `failed`

**Note**: State transitions do NOT imply mutability of artifact content. They track operational status only.

---

> Constitution Reference: §11 (Artifact Architecture), §12 (Lineage-Centric Reproducibility), §17 (Schema Versioning)
