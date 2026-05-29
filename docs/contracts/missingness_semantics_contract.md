# Missingness Semantics Contract

## Purpose

This contract defines the canonical semantics governing modality completeness, absence, uncertainty, corruption, ingestion delay, and analytical usability within PMBRS.

The purpose of this contract is to:

- preserve temporal coherence,
- prevent silent analytical contamination,
- distinguish observational absence from missing data,
- propagate uncertainty through derived artifacts,
- support reproducible multimodal analysis,
- preserve modality-specific reliability semantics.

This contract applies to:

- authoritative observational artifacts,
- canonical windows,
- modality projections,
- derived analytical artifacts,
- evaluations,
- embeddings,
- experiment comparisons.

---

## Scope

This contract governs:

- modality presence semantics,
- coverage semantics,
- confidence semantics,
- corruption semantics,
- delay semantics,
- analytical suitability semantics.

This contract does not define:

- modality-specific feature extraction,
- downstream model weighting,
- evaluation methodologies.

---

## Core Principles

### Principle 1 — Missingness Is Explicit Metadata

Missingness must never be represented implicitly through absent fields or null assumptions.

All modality incompleteness must be represented explicitly through standardized metadata.

---

### Principle 2 — Canonical Windows Exist Structurally Regardless of Completeness

Canonical windows are operational temporal infrastructure.

A window may exist even if:

- all modalities are absent,
- ingestion is delayed,
- modalities are corrupted,
- confidence is low.

Analytical suitability is distinct from structural existence.

---

### Principle 3 — Absence Is Not Equivalent to Observed Zero

The absence of observational data must never be interpreted as:

- numerical zero,
- behavioral inactivity,
- negative evidence,
- null semantic state.

---

### Principle 4 — Uncertainty Must Propagate Forward

Derived artifacts must preserve upstream uncertainty semantics.

Confidence degradation may not be discarded during transformation.

---

## Presence State Semantics

Each modality projection within a canonical window must define a presence_state.

### Allowed Values

```yaml
presence_state:
  - PRESENT
  - ABSENT
  - PARTIAL
  - DELAYED
  - CORRUPTED
  - UNKNOWN
```

---

### Definitions

| State | Meaning |
|---|---|
| PRESENT | modality data successfully available |
| ABSENT | confirmed no observational data exists |
| PARTIAL | incomplete or fragmented coverage |
| DELAYED | expected but not yet ingested |
| CORRUPTED | unusable or invalid data |
| UNKNOWN | system cannot determine modality state |

---

## Coverage Semantics

Coverage describes the proportion of expected modality coverage within the canonical window.

### Required Field

```yaml
coverage_ratio: float(0.0 - 1.0)
```

---

### Examples

| Scenario | Coverage |
|---|---|
| accelerometer available for entire window | 1.0 |
| browser telemetry for 20 seconds of 60 | 0.33 |
| no wearable data available | 0.0 |

---

## Confidence Semantics

Confidence measures reliability, not truthfulness.

Confidence is independent from:

- modality importance,
- behavioral significance,
- semantic validity.

### Required Fields

```yaml
confidence_score: float(0.0 - 1.0)
confidence_reasons:
```

---

### Example Confidence Reasons

```yaml
confidence_reasons:
  - SENSOR_NOISE
  - LOW_SAMPLE_RATE
  - CLOCK_DRIFT
  - INTERPOLATED
  - USER_DECLARED
  - PARTIAL_WINDOW
```

---

## Corruption Semantics

Corruption describes invalid or unreliable observational integrity.

### Required Field

```yaml
corruption_flags:
```

---

### Example Corruption Flags

```yaml
corruption_flags:
  - OUT_OF_RANGE
  - MALFORMED
  - INVALID_ENCODING
  - DUPLICATE_DATA
  - CLOCK_DESYNC
  - PARSE_FAILURE
```

---

## Delay Semantics

Delay semantics describe temporal differences between:

- observation,
- ingestion,
- canonical alignment.

### Required Fields

```yaml
temporal_status:
ingestion_delay_ms:
```

---

### Allowed Temporal Status Values

```yaml
temporal_status:
  - ON_TIME
  - DELAYED
  - BACKFILLED
```

---

## Analytical Suitability Semantics

Canonical windows may expose analytical suitability metadata.

### Example

```yaml
usable_for:
  embedding_generation: true
  intervention_evaluation: false
  clustering: true
  sleep_analysis: false
```

Analytical suitability metadata must not mutate authoritative observational artifacts.

---

## Validation Rules

### Required Rules

- coverage_ratio must exist for dense modalities.
- confidence_score must exist for all modality projections.
- ABSENT must not imply numerical zero.
- CORRUPTED modalities may not silently transition to PRESENT.
- DELAYED modalities must preserve original observation timestamps.
- Confidence scores may not imply causal certainty.
- Missingness metadata must remain lineage-traceable.

---

## Forbidden Behaviors

### Forbidden State Conflations

The system must never conflate:

- missingness with inactivity,
- absence with negative evidence,
- corruption with absence,
- low confidence with invalidity.

---

### Forbidden Operations

- Missing data may not silently overwrite observational evidence.
- Confidence propagation may not be discarded in derived artifacts.
- Interpolation may not modify authoritative artifacts.
- Missingness metadata may not be omitted from canonical windows.

---

## Reproducibility Requirements

All missingness metadata must be:

- versioned,
- lineage-traceable,
- reproducible,
- schema-governed.

Derived analytical outputs must preserve upstream missingness lineage.

---

## Operational Notes

PMBRS intentionally uses graded analytical suitability rather than binary validity semantics.

This reflects:

- real-world telemetry variability,
- sparse modality behavior,
- asynchronous ingestion,
- multimodal uncertainty.

---

## Future Considerations

Potential future extensions:

- modality-specific confidence calibration,
- adaptive missingness weighting,
- uncertainty-aware embeddings,
- probabilistic temporal interpolation,
- confidence-aware experiment evaluation.
