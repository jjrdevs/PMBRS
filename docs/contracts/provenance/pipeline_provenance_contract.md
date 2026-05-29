# Pipeline Provenance Contract

## Purpose

Describes provenance semantics for deterministic infrastructure and alignment pipelines that transform artifacts without introducing explicit model semantics.

## Extends

`provenance_base_contract.md`

## Applicability

These fields MUST be present when `provenance_type` is `pipeline`.

## Required Fields

```yaml
provenance_type: pipeline
provenance_version: string
provenance_timestamp: timestamp
provenance_agent: string
pipeline_name: string
pipeline_version: string
execution_environment: string
execution_timestamp: timestamp
software_version: string
input_artifact_refs: list[string]
```

## Notes

- Pipeline provenance is intended for deterministic artifact transformation and alignment processes such as canonical window builders.
- Fields like `parameter_hash` and `random_seed` are intentionally omitted because they are not required for deterministic pipeline provenance.
