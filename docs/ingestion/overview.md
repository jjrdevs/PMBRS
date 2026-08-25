# Ingestion Subsystem — Overview

## Purpose

The ingestion subsystem is responsible for pulling raw observational data from external providers and writing **authoritative artifacts** to the artifact store. It never interprets or infers — it captures, validates schema compliance, and preserves lineage roots.

The subsystem exists to support structured measurement and evidence collection rather than behavioral optimization, surveillance, or autonomous intervention. It should preserve the original observational evidence as faithfully as possible while keeping the data local and privacy-preserving.

## Adapter Contract

Every modality adapter implements a minimal interface:

```python
class ModalityAdapter(Protocol):
    """All ingestion adapters must provide these methods."""
    
    name: str                           # Unique identifier (e.g., "fitbit", "browser_history")
    
    def fetch(self, since: datetime) -> list[dict]: ...   # Pull raw data from provider
    def normalize(self, raw: dict) -> Artifact: ...        # Map to canonical artifact schema
    def health_check(self) -> bool: ...                     # Can we reach the provider?
```

### Constraints (from Constitution §8)
- Adapters produce **observational artifacts** only — never derived or inferred types.
- Each adapter declares which modality category it belongs to: `observational`, `objective`, or `inferred`.
- Provider credentials are isolated per adapter; no cross-contamination between adapters.
- Higher-risk modalities must be gated by explicit privacy policy checks and excluded by default unless the user opts in.

## Modality Catalog (Planned)

| Adapter | Category | Data Provided | Priority |
|---|---|---|---|
| Wearable API adapter (`wearable`) | Observational       heart rate, sleep stages, steps, activity bouts, stress markers | 🔴 High — core behavioral signal |
| Browser telemetry (`browser`)         # Activity tracking, history logs | 🔴 High — rich digital behavior trace    || Mobile client direct export  | Observational  sensor sync (accelerometer, GPS, etc.)      🟡 Medium — Android only, native collection                | Calendar sync (`calendar_provider`) | Declared            Events: appointments, meetings, scheduled context          | 🟢 Low — contextual overlay                          |
| Journal/manual entry (`journal`)       # Subjective             Text entries, mood ratings, freeform notes                                    | 🟡 Medium — subjective but intentional                               |

## Known Implementation Notes (Android Collection):
- **Platform**: Android only (Kotlin + Ktor / Exposed or SQLite via Room) for native mobile collection.
- Android client runs as `observational` artifact writer → syncs back to local PMBRS instance periodically via encrypted channel (local-first: LAN sync during home network availability).

---

> **Constitution Reference**: §5–8 (Ingestion role), §8 (Modality Model)
