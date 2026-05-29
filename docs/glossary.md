## Artifact

A structured object produced, consumed, stored, transformed, or referenced within PMBRS.

Artifacts are the formal communication and persistence units of the system and exist independently of specific subsystems or storage mechanisms.

Artifacts may be:
- authoritative,
- derived,
- inferred,
- immutable,
- reproducible,
- transient,
depending on epistemological and operational role.

## Authoritative Artifact

An artifact treated as irreducible historical evidence within PMBRS.

Authoritative artifacts:
- originate from direct observation, user declaration, or user authorship,
- are immutable once finalized,
- are never overwritten by downstream interpretations,
- form the permanent source-of-truth layer of the system.

Examples:
- wearable telemetry
- journal entries
- calendar events
- intervention declarations
- browser activity records

## Derived Artifact

An artifact produced through computational transformation of upstream artifacts.

Derived artifacts:
- are reproducible,
- are model-dependent,
- may be regenerated,
- are not authoritative,
- must preserve explicit lineage to upstream artifacts.

Examples:
- features
- embeddings
- sentiment scores
- behavioral clusters
- evaluation metrics

## Inferred Artifact

A probabilistic derived artifact representing a hypothesis rather than directly observed evidence.

Inferred artifacts:
- carry uncertainty,
- are never treated as ground truth,
- must preserve confidence metadata,
- must remain lineage-traceable.

Examples:
- inferred walking session
- inferred sleep disruption
- inferred stress regime

## Canonical Window

A globally aligned fixed-duration temporal container used as the operational synchronization backbone of PMBRS.

Canonical windows:
- exist structurally regardless of modality completeness,
- align all modalities onto a shared temporal reference system,
- are operational infrastructure rather than interpretive outputs,
- preserve missingness and uncertainty metadata.

## Modality

A structured time-indexed information source aligned to the canonical temporal system through modality-specific transformation rules.

Modalities are categorized by epistemological role rather than semantic equivalence.

Examples:
- observational modalities
- declarative modalities
- subjective modalities
- inferred modalities

## Observational Modality

A modality derived from directly measured behavioral or environmental signals.

Examples:
- heart rate
- accelerometer data
- app usage
- GPS movement

## Subjective Modality

A modality representing self-authored or self-reported internal interpretation, emotion, reflection, or experience.

Examples:
- journal entries
- mood ratings
- annotations
- experiment reflections

## Lineage

The explicit directed dependency structure describing how artifacts were produced from upstream artifacts and transformations.

Lineage must preserve:
- upstream references,
- transformation identity,
- execution configuration,
- model versions,
- environment provenance.

## Provenance

Metadata describing the origin, execution context, and transformation conditions associated with artifact creation.

Provenance includes:
- creator identity,
- ingestion source,
- model version,
- parameter configuration,
- execution environment,
- timestamps.

## Reproducibility

The ability to regenerate equivalent derived artifacts from authoritative upstream artifacts using preserved lineage and execution provenance.

## Interpretability

The requirement that user-facing conclusions remain traceable to observable evidence, transformation lineage, and statistically supported associations rather than opaque model assertions.

## Semantic Leakage

The contamination of observational behavioral representations by subjective or interpretive artifacts in ways that compromise interpretability, reproducibility, or epistemological separation.

## Experiment

A structured behavioral intervention declaration with explicit temporal scope, contextual scope, intervention metadata, and evaluation linkage intended to support reproducible behavioral comparison.

## Missingness

Explicit metadata describing absent, delayed, corrupted, incomplete, or low-confidence modality coverage within canonical windows.

# Forbidden Semantic Conflations

Authoritative ≠ true
Derived ≠ invalid
Inference ≠ observation
Correlation ≠ causation
Canonical ≠ authoritative
Missing ≠ zero
Interpretation ≠ evidence