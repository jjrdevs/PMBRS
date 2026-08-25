# Schema Versioning and Governance Policy

## Overview

Operationalizes Constitution §17: lineage-preserving, schema-versioned artifact architecture supporting long-term reproducibility and safe evolution.

## Core Rule: Regeneration Over Rewrite

When schemas evolve across time periods:
1. Authoritative artifacts persist unchanged on disk/DB — never rewritten retroactively (except explicit user corrections).
2. Derived artifacts may be recomputed under updated schemas while preserving lineage continuity.
3. Historical artifacts remain interpretable under original schema where feasible via schema migration readers.

## Versioning Layers

| Layer | What It Versions | Scope | Bump When... |
|---|---|---|---|
| `schema` | Fields, types, constraints for each artifact_type | Per-artifact-type | Field added, removed, renamed, or type changed |
| `transformation` | Pipeline logic that produces derived artifacts (feature extraction, alignment rules) | Cross-module | Algorithm/logic version: e.g., v2 adds new HRV computation method |
| `model` | Machine learning models used for representation/evaluation | Per-model | New training run, architecture change, hyperparameter swap |
| `experiment` | Experiment definition format and evaluation methodology | Per-experiment | Outcome measures added/removed, comparison baseline strategy changes |

## Backward Compatibility Guarantees

- ✅ Schema metadata tag always present — True
- ✅ `schema_version` field on every artifact — True
- ✅ Optional fields can be added without breaking old readers (new fields marked explicit nullable/default) — True
- ❌ Optional fields removed requires deprecation window + migration path — False — this triggers a major version bump

## Migration Path Template

When schema version N is superseded by version N+1:
1. Define migration reader that maps old fields to new structure (adds defaults for newly required if needed).
2. Run `pmbrs artifacts migrate --from-version=<old> --to-version=<new>` across artifact store.
3. All prior derived artifacts remain queryable; regeneration triggered by orchestrator on next full pipeline run.
4. Old schema readers archived but not deleted (kept for historical introspection).

## Lineage Preservation During Migration

During any migration, the lineage DAG is preserved: downstream derived artifacts are re-run under new schema while original authoritative observations stay untouched. This ensures that evaluations comparing pre-migration and post-migration results can always be made — a core success criterion from §2 (Measures of Success).

---

> Constitution Reference: §17 (§§9), §11.
