# Provenance Base Contract

## Purpose

Defines the canonical provenance classification and minimal fields that all provenance variants must expose.

This contract is the root of the provenance family and is extended by specialized provenance contracts.

## Required Fields

```yaml
provenance_type: enum(observational, declarative, computational, pipeline, external_import)
provenance_version: string
provenance_timestamp: timestamp
provenance_agent: string  # human or system identifier where applicable
```

## Provenance Classification

- `observational`: sensor- or ingestion-derived artifacts.
- `declarative`: user-authored or manually declared artifacts (journal, experiments, annotations).
- `computational`: model-dependent analytical artifacts (features, embeddings) that require explicit model provenance.
- `pipeline`: deterministic infrastructure or alignment pipelines that transform artifacts without introducing modeling semantics.
- `external_import`: bulk-imported records with source system metadata.

## Extension Rules

Specialized provenance contracts MUST declare additional fields appropriate to their provenance_type. When generating validators, require the base fields and then the specialized fields only when `provenance_type` matches.
