## Purpose

Defines the canonical temporal window artifact used as PMBRS' temporal synchronization backbone. This contract aligns to `artifact_base_contract.md` and references `missingness_semantics_contract.md` for missingness semantics.

## Core Rules

- Canonical windows exist on a fixed globally aligned 60-second grid.
- Canonical windows are structural: they may exist even when all modalities are absent.
- Canonical windows preserve missingness metadata and must not conflate absence with zero.
- Canonical windows may use pipeline provenance for deterministic alignment processes.
- Canonical windows are immutable once `lifecycle_state` transitions to `finalized`.

## Required Fields (window payload)

The artifact SHOULD include an object `window` with the following fields:

```yaml
window:
  start_time: timestamp
  end_time: timestamp
  resolution_seconds: integer  # typically 60
  canonical_index: integer
  timezone: string

modalities_present: map[string]boolean

missingness_metadata:
  modality_coverage: map[string]float
  missing_modalities: list[string]
  corruption_flags: list[string]
  delayed_modalities: list[string]

quality_metadata:
  overall_window_quality: float(0.0-1.0)
  quality_tier: enum(low, medium, high)

payload:
  aligned_artifact_refs: list[string]

lineage:
  aggregated_from: list[string]
```

## References

- Missingness semantics: `missingness_semantics_contract.md`
- Artifact superclass: `artifact_base_contract.md`
- Modality contract: `modality_contract.md`
- Pipeline provenance: `provenance/pipeline_provenance_contract.md`

*** End Patch
