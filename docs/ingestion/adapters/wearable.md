# Wearable Adapter Spec

## Providers (Priority Order)

| Provider | API Type | Data Available | Notes |
|---|---|---|---| Heart Rate (resting, active), HRV, sleep epochs, step count, zones, floors, ECG. ✅ Already have historical export available  
| Apple HealthKit            | iOS-only JSON/XML export   Sleep stages, heart rate, workouts, steps, oxygen saturation       🚫 Android only — skip                             ||                                   
Oura / Whoop                REST API                          Recovery scores, readiness, sleep structure, HRV          🔶 Lower priority unless device changes               

## Artifacts Produced

| Artifact Type | Fields (TBD) | Granularity |
|---|---|---|
| `wearable_event` | `provider`, `metric_type`, `value`, `unit`, `timestamp_start`, `timestamp_end`, `confidence_score`, `raw_source_hash` | Per-provider native resolution (varies: 1-min, 5-min, epoch)

## Sync Pattern

- **Incremental**: adapter tracks last sync timestamp per provider (`since` cursor)
- On failure → retry with exponential backoff up to max retries before marking window as partially missing.
- Deduplication handled via content hash on `wearable_event` (ADR-003 identity scheme).

## Alignment Contract

This adapter produces **sparse** observational signals that may be downsampled/resampled during the canonical alignment phase (`temporal` module). A raw event is never overwritten when aligned; instead, a lineage-traced canonical window references this artifact.

---

> Pending: Provider implementation selection (ADR to be written once device choice is finalized)
> Constitution Reference: §8 (Modality Model), §11 (Artifact Architecture)
