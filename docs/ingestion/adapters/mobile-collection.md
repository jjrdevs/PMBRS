# Mobile Collection Client Architecture (Android)

## Purpose

Provide a native Android application that turns the phone into a local observational collection device for PMBRS. The app should collect behavioral evidence locally, buffer it offline, and sync it to the PMBRS hub only when the user has opted in and the device is on a trusted network.

## Audit Summary

The existing draft is directionally correct, but it should be treated as an early concept note rather than a finalized implementation specification. The plan below turns it into a phased delivery plan with clearer scope, privacy safeguards, and acceptance criteria.

## Scope and Non-Goals

### In scope

- Android-only phone client for observational artifact capture
- Local-first buffering with delayed sync to a PMBRS instance
- Opt-in collection of low-risk behavioral signals such as screen state, battery state, boot events, and optional motion/context signals
- Generation of observational artifacts that conform to PMBRS ingestion contracts

### Out of scope

- iOS support for now
- fine-grained location tracking or continuous surveillance
- derived or inferred behavioral scoring inside the client
- real-time intervention or closed-loop control
- fully general-purpose health monitoring

## Current first-slice boundary

- Implemented: `ScreenStateCollector`, `DeviceStateCollector`, local SQLite buffering, manual/trusted-network sync gating, endpoint URL validation, JSON payload serialization, provenance metadata propagation, and startup WorkManager scheduling for periodic collection.
- Deferred: `HealthDataCollector`, `BrowserHistoryCollector`, `MediaCollector`, `AppUsageCollector`, and `GeolocationCollector`.
- The phone client is currently scoped as a low-risk observational ingestion adapter, not a general-purpose sensor or surveillance client.

## Architectural Direction

The client should behave like a replaceable ingestion adapter rather than a core PMBRS subsystem. Its role is to produce authoritative observational artifacts, not to interpret user behavior.

### High-level flow

1. Collect raw phone events locally.
2. Normalize them into PMBRS-compatible observational artifact payloads.
3. Persist them in a local on-device store.
4. Queue them for sync.
5. Transmit them to the PMBRS hub over an encrypted channel when allowed.

### Suggested app structure

- UI layer: simple settings, status, and sync controls
- Collector layer: modality-specific collectors for screen, battery, boot, and optional motion/context signals
- Storage layer: SQLite-backed local database for buffered artifacts and sync state
- Sync layer: queued delivery with retry, backoff, and deduplication
- Privacy layer: consent gating, redaction rules, retention controls, and trusted-network policy

## Operational Constraints

This work must follow the PMBRS operating model:

- default to opt-in collection
- minimize the data surface area and avoid unnecessary permissions
- avoid fine-grained location tracking by default
- keep raw artifacts local until sync succeeds
- use encrypted transport and local buffering for resilience
- preserve provenance and lineage at the artifact level

## Recommended Data Categories

| Category | Example signals | Notes |
|---|---|---|
| Screen state | screen on/off, unlock events | Low-risk behavioral proxy with minimal privacy exposure |
| Device state | battery level, charging state, boot events | Useful as contextual observational evidence |
| Motion/context | accelerometer, connectivity state | Only include if explicitly enabled and low-risk |
| Optional bridge | wearable bridge events | Only if a separate adapter is already available |

## Implementation Plan

### Phase 0 — Alignment and governance

Objectives:
- finalize the phone-client scope and confirm which modalities are in scope
- define the artifact payload shape expected by PMBRS ingestion
- identify required permissions, opt-in defaults, and retention policy

Deliverables:
- documented modality list for the phone client
- initial privacy policy configuration
- initial sync contract and endpoint assumptions

### Phase 1 — Foundation

Objectives:
- create the Android app skeleton
- establish local persistence, settings, and basic lifecycle management
- implement a minimal status UI and a first collector

Deliverables:
- app buildable on Android
- local database schema for buffered artifacts
- a first artifact emitted and persisted locally

### Phase 2 — Core collection

Objectives:
- implement collectors for screen and device-state observations
- normalize events into observational artifacts
- add local deduplication and metadata capture

Deliverables:
- screen-state and battery-state collectors
- artifact normalization path from raw event to PMBRS-compatible payload
- persisted queue of unsynced artifacts

### Phase 3 — Sync and reliability

Objectives:
- implement encrypted sync to the PMBRS hub
- support retry, backoff, and duplicate rejection
- support trusted-network or manual trigger behavior

Deliverables:
- queued sync pipeline
- successful round-trip of at least one artifact batch
- clear failure handling for offline and auth-related issues

### Phase 4 — Hardening and evaluation

Objectives:
- improve battery efficiency and reliability
- add observability for sync failures and data loss
- verify privacy defaults and retention behavior

Deliverables:
- low-impact background behavior under normal usage
- health and sync logs for troubleshooting
- documented operational procedures and user-facing settings

## Recommended Technical Stack

| Component | Recommendation | Reason |
|---|---|---|
| UI | Jetpack Compose | Native, modern, minimal UI overhead |
| Storage | SQLite via SQLiteOpenHelper | Simple, reliable offline persistence for the first slice |
| Networking | Retrofit or Ktor | Clean HTTP client support for encrypted sync |
| Transport security | TLS with mutual auth or pre-shared key | Aligns with local-first, privacy-sensitive sync |
| Payload format | JSON artifacts matching PMBRS ingestion schema | Keeps the client aligned with artifact governance |

## Open Questions

- Which modalities should be enabled by default versus opt-in-only?
- Should sync be triggered automatically on trusted Wi-Fi, manually, or both?
- Which permissions are acceptable for the initial milestone versus later expansion?
- What is the exact endpoint contract and authentication model for the PMBRS hub?

## Implementation Guidance

The best first milestone is a narrow, well-scoped version of the client: one or two collectors, local buffering, and a single reliable sync path. That keeps the work aligned with PMBRS principles and avoids overbuilding before the contract has stabilized.

> Constitution reference: §8, §15, and §16. This client is a replaceable ingestion subsystem whose job is to preserve observational evidence locally and transfer it safely when authorized.
