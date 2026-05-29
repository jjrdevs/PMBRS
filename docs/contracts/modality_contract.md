## Purpose

Defines the structural requirements and semantic expectations for PMBRS modalities. Modalities describe the source, temporal behavior, and quality expectations of time-indexed data.

## Required Fields

Every modality definition SHOULD include:

```yaml
modality_id: string
modality_type: string  # e.g., wearable_sensor, browser_telemetry, journal_entry
modality_name: string
source_description: string
alignment_strategy: string  # deterministic alignment description
missingness_strategy: string  # how missingness is represented and handled
quality_metadata: object
uncertainty_strategy: string
category: enum(observational, declarative, subjective, inferred)
sampling_rate_hz: number?  # optional for dense modalities
expected_coverage: float?  # expected coverage ratio per canonical window
```

## Modality Categories and Semantics

- `observational`: direct sensor or ingestion sources (wearable, browser telemetry).
- `declarative`: user-authored inputs (journal, experiment declarations).
- `subjective`: self-report scales and mood ratings.
- `inferred`: model-derived modality projections.

## Dense/Sparse Modality Semantics

- Dense modalities represent continuous or high-frequency data streams and SHOULD define `sampling_rate_hz`, `expected_coverage`, and a deterministic `alignment_strategy`.
- Sparse modalities may contain intermittent or event-driven data and may omit sampling-specific metadata.
- Declarative modalities represent explicit user declarations or narrative content and SHOULD document their own temporal semantics rather than assume fixed sampling.
- Inferred modalities are produced by computation and SHOULD include provenance references, uncertainty strategy, and any upstream modality dependencies.

## Additional Guidance

- Dense modalities SHOULD provide `sampling_rate_hz` and `expected_coverage`.
- Sparse or declarative modalities MAY omit sampling-related fields.
- Modality definitions MUST document `alignment_strategy` used to project data onto canonical windows.

*** End Patch
