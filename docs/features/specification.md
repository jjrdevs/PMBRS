# Feature Extraction Pipeline — Specification

## Purpose

Transform aligned canonical windows into behavioral feature vectors that serve as the input representation for downstream representation learning and evaluation models.

This is a **batch-first** operation per Constitution §5: features are computed over historical data in scheduled batch runs, not real-time streaming.

## Input/Output Contract

| Direction | Artifact Type                                               | Description                                                    |
|-----------|-------------------------------------------------------------|----------------------------------------------------------------|
| input     | `canonical_window`, `modality_alignment_mapping`, `missingness_mask` | Aligned temporal backbone with coverage info                   |
| output    | `feature_vector`                                            | Numerical/symbolic features computed per window or rolling horizon |

## Feature Categories (by Modality)

### Wearable Features

| Feature                    | Units         | Notes                                                                    |
|----------------------------|---------------|--------------------------------------------------------------------------|
| Heart rate mean/median/std per window    | BPM     | Dense signal — high confidence within covered windows                     |
| HRV (RMSSD, SDNN)           | ms            | Computed from inter-beat interval series; requires minimum N beats        |
| Sleep stage probabilities   | [0-1]         | If epoch-level data available for this window's time range                |
| Step count / cadence         | steps/min     | Sparse event — alignment strategy: hold-last or zero-fill? (TBD)          |
| Activity zone minutes       | min           | Moderate-intensity, vigorous-intensity zones                              |

### Browser/Digital Activity Features

| Feature              | Units   | Notes                                                  |
|----------------------|---------|--------------------------------------------------------|
| Distinct domain count per window    | —      | Proxy for switching activity                           |
| Mean time-on-domain                 | seconds | Requires sub-window granularity                        |
| Daytime vs nighttime active flag    | boolean | Contextual overlay from temporal position              |
| Screen activity proxy            | boolean | Binary on/off during this 60s period       |

### Calendar/Context Features (Sparse)

| Feature              | Type          | Notes                                   |
|----------------------|---------------|-----------------------------------------|
| Scheduled event present    | boolean       | Binary: any calendar event overlaps this window |
| Event category tags         | array[string]  | Meeting / personal / work / other       |

## Rolling / Window Aggregation Features

In addition to per-window features, rolling windows provide temporal context:

- `rolling_mean(window_size=5min)`: 5-consecutive-canonical-windows average for wearable metrics
- **Averaging over missing regions**: explicitly excluded. Rolling aggregates drop windows below minimum coverage threshold; result marked as partial if coverage drops below defined minimum (TBD per §10).

---

**Pending ADRs:** ADR-008: Sparse-to-Dense Alignment Rules, ADR-009: Feature Extraction Windowing & Incremental Reprocessing Strategy.
