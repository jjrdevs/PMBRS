# Data Minimization & Sensitive Modality Gating

## Principle

Collect only data that directly serves the platform's scientific mission: behavioral measurement, experimentation, and interpretation. Exclude modalities by default; opt in explicitly where clearly justified per §16. This is a **data minimization** rule baked into every ingestion adapter design.

The platform is not intended to become a surveillance system. Exhaustive raw surveillance artifacts are excluded by default unless they are explicitly required for a future research objective.

## Excluded Modalities (Explicit Out of Scope) ❌

| Modality | Reason for Exclusion |
|---|---|
| Full screenshot archives | Exhaustive surveillance artifact; excluded by default |
| Keystroke logging | Privacy-invasive; no behavioral signal outweighs this risk |
| Raw GPS tracking | Overly granular; zone-level context from calendar and declared events is less sensitive |

## Default Data Categories ✅ (Included Unless Explicitly Opted Out)
| Category | Modalities Included         Risk Level   Examples                         |        Observational telemetry          Wearable (HR, sleep, steps), browser activity domains               Low-Medium  Heart beats per minute at rest, time-on-page counters             |
| Declared context events      Calendar appointments, journal entries, experiment declarations       Medium     Title + calendar metadata — potentially identifiable but user-authored   ||
Inferred/derived features    Feature vectors, behavioral embeddings, regime assignments            Low           Post-hoc computation; reconstructable from authorized artifacts                         

## Gating Mechanism (Design Spec)

Every modality adapter declares a **sensitivity tier** in its config. The ingestion pipeline checks against an active `privacy_policy.yaml` before running:

```yaml
# ~/.config/pmbrs/privacy-policy.yaml example structure (TBD schema)
default_tier_allow: medium       # Default: allow up to "medium" risk modalities
opt_extra_opt_in:                # Explicit per-modality overrides below the threshold  
  - wearable_hr                   # Allow heart rate explicitly      
#    gps_zone_level               Zone-level location from calendar context (NOT raw GPS track)
```

### Gating Rules in Pipeline
1. **Adapter declares tier** → `adapter.sensitivity = low | medium | high`
2. If tier > policy threshold AND not explicitly opted-in → adapter skip with log warning (silent, no error exit for excluded modules)  
3. **Never silently collect higher-risk data without explicit approval.**

---

> **Constitution Reference**: §6–15 (§§9), §8 (Modality Gating — privacy, security). The goal is to prevent the system from becoming a surveillance tool while remaining effective as a measurement platform.
