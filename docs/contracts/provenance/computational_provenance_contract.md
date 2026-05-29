# Computational Provenance Contract

## Purpose

Provenance schema for computationally-derived artifacts. Extends `provenance_base_contract.md`.

## Extends

`provenance_base_contract.md`

## Applicability

These fields MUST be present when `provenance_type` is `computational`.

## Required Fields

```yaml
provenance_type: computational
provenance_version: string
provenance_timestamp: timestamp
provenance_agent: string
model_name: string
model_version: string
feature_config: object
execution_environment: object
input_artifact_refs: list[string]
random_seed: number
parameter_hash: string
execution_timestamp: timestamp
software_version: string
``` 

## Notes

- The execution- and environment-specific fields are required only for computational provenance.
- For deterministic infrastructure processes that do not require model semantics, use `pipeline` provenance instead of `computational` provenance.
- Fields that are expected to vary across runs (e.g., execution_timestamp) are excluded from content hash scope by default.
