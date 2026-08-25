# Evaluation Artifact Contract

## Purpose

Defines evaluation artifacts as first-class derived artifacts used to validate artifact integrity, representation quality, experiment usefulness, and system performance.

Evaluation artifacts are not raw observations. They are explicitly derived outputs with reproducible lineage, uncertainty metadata, and comparison baselines.

## Scope

This contract applies to artifacts whose primary role is evaluation and validation. Typical use cases include:

- behavioral experiment outcome evaluation
- canonical alignment quality assessment
- representation quality metrics for embeddings/features
- system integrity evaluation for ingestion and modality coverage
- human assessment utility and interpretability scoring

## Required Fields

Evaluation artifacts MUST include the canonical artifact superclass fields from `artifact_base_contract.md`, plus the following evaluation-specific fields:

```yaml
evaluated_target_refs: list[string]
metric_outputs:
  - metric_name: string
    metric_value: number|string|object
    metric_units: string
    metric_description: string
    confidence_score: number  # optional, 0.0-1.0
    uncertainty_estimate: object  # optional
comparison_baselines: list[
  type: enum(baseline, control, historical, expected)
  reference_artifact_ref: string
  description: string
]
dataset_scope_refs: list[string]
modality_scope_refs: list[string]
configuration_snapshot: object
execution_provenance: object
uncertainty_estimates: object
interpretability_metadata: object
```

## Semantics

- `evaluated_target_refs` MUST reference the artifact(s) under evaluation.
- `metric_outputs` MUST capture quantitatively measurable evaluation outcomes and may include qualitative metadata.
- `comparison_baselines` MUST preserve the context used to judge evaluation results.
- `dataset_scope_refs` and `modality_scope_refs` MUST describe the data bounds used to compute the evaluation.
- `configuration_snapshot` MUST record model, pipeline, or analysis configuration state that produced the evaluation artifact.
- `execution_provenance` MUST include the specialized provenance contract appropriate to the artifact’s generation method.
- `uncertainty_estimates` MUST make uncertainty explicit rather than implicit.
- `interpretability_metadata` SHOULD capture whether the evaluation artifact is human-meaningful and how it should be interpreted.

## Properties

Evaluation artifacts MUST be:

- derived: `artifact_class` MUST be `derived` or `experiment`
- lineage-traceable: `lineage.derived_from` or `lineage.aggregated_from` MUST exist
- reproducible: input references and configuration must be explicit
- versioned: `schema_version` MUST be set
- non-destructive: evaluation artifacts MAY NOT overwrite authoritative evidence

## Forbidden Behaviors

- Evaluation artifacts MUST NOT be treated as authoritative observational evidence.
- Evaluation artifacts MUST NOT hide comparison baselines or dataset scope.
- Evaluation artifacts MUST NOT omit uncertainty metadata when confidence is material.
- Evaluation artifacts MUST NOT mix inference provenance with declarative or observational provenance incorrectly.

## Related Contracts

- `artifact_base_contract.md`
- `provenance/provenance_base_contract.md`
- `provenance/computational_provenance_contract.md`
- `experiment_declaration_contract.md`
- `schema_evolution_contract.md`
