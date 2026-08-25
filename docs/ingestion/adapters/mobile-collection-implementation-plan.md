# Mobile Collection Implementation Plan

## Purpose

This document captures the current mobile collection implementation plan for the PMBRS Android phone client and records the known gaps, failure points, and next work items.

## Current state

- The mobile app source tree exists in `mobile/app/src/main/java/com/pmbrs/mobile`.
- Core collectors and sync plumbing are present.
- The app currently supports manual capture and manual sync with trusted-network gating.
- The app also includes a scheduled background sync worker via `PMBRSSyncWorker`, with WorkManager scheduling and retry/backoff semantics.
- There are existing documentation artifacts in `docs/ingestion/adapters/mobile-collection.md`, `mobile-collection-architecture.md`, `mobile-collection-backlog.md`, and `mobile-collection-execution-checklist.md`.

## Status update

- **Completed:** scheduled sync (`PMBRSSyncWorker`), persistent last-sync diagnostics (`SyncSettings.lastSyncLog`), endpoint normalization (`normalizeSyncBaseUrl()`), low-risk collectors (`ScreenStateCollector`, `DeviceStateCollector`), DB schema updates to persist full artifact fields, deduplication and retention cleanup, and unit tests covering workers and sync paths.
- **In progress / remaining:** battery/observability validation, production endpoint/auth hardening, optional retention configurability, and formal privacy review.
- **Quick validation (from `mobile/`):**
```bash
./gradlew :app:compileDebugKotlin
./gradlew :app:testDebugUnitTest
```
- **Handoff file:** see `mobile/HANDOFF.md` for a reviewer-ready summary and checklist.

## Verified issues

1. Build validation is now working.
   - The mobile Gradle wrapper at `mobile/gradlew` now supports compilation in the Android app module.
   - `./gradlew clean :app:compileDebugKotlin --rerun-tasks --stacktrace` passes.
   - The wrapper issue appears resolved for the current workspace state, but wrapper artifacts should still be validated before wider handoff.

2. Persistence model mismatch.
   - `ArtifactEntity` includes `schemaVersion`, `deviceAlias`, and provenance metadata, but `ArtifactDatabase.kt` previously only persisted `id`, `source`, `payload`, `createdAtEpochMs`, and `synced`.
   - Payload storage was previously plain string content rather than structured JSON.
   - Current status: `ArtifactDatabase` now persists `schemaVersion`, `deviceAlias`, `provenanceMetadataJson`, and JSON-serialized payloads.

3. Sync contract mismatch.
   - `SyncApi.ArtifactPayload` previously used `id: Long`, while mobile artifacts use string IDs and the SQLite DB row ID is auto-generated.
   - `PmbrsArtifact.toArtifactPayload()` previously mapped `createdAtEpochMs` into `id`, making the payload identifier inconsistent with the artifact identity.
   - Current status: artifact IDs are now string-based, payloads serialize JSON, and provenance metadata is passed through the sync payload.

4. Collector scope is overextended for first slice.
   - `CollectorService.collectAll()` previously invoked all available collectors, including placeholder collectors:
     - `HealthDataCollector`
     - `BrowserHistoryCollector`
     - `MediaCollector`
   - These collectors currently return mock/stub payloads rather than real device data.
   - Current status: the first-slice implementation now only includes `ScreenStateCollector` and `DeviceStateCollector`; higher-risk collectors remain deferred.

5. Background collection is integrated into the startup flow.
   - `CollectorService.schedulePeriodicCollection()` is now invoked from `MainActivity.onCreate()`.
   - Periodic collection uses WorkManager to schedule repeats and preserves the first-slice low-risk collector scope.

6. Scheduled sync is implemented.
   - `PMBRSSyncWorker` now handles periodic sync delivery of pending artifacts.
   - `PMBRSSyncWorkerTest` validates success and retry behavior when the hub responds or fails.

7. Endpoint handling is in a better state.
   - `MainActivity.kt` allows editing the sync endpoint and saves it through `SyncSettings`.
   - `NetworkSyncClient.create()` validates the base URL using `normalizeSyncBaseUrl()` and rejects invalid URLs.

## Implementation plan

### Phase 1 — Restore build and validation

1. Repair the mobile Gradle wrapper
   - Validate `mobile/gradlew` script and `mobile/gradle/wrapper/gradle-wrapper.jar`.
   - Regenerate the wrapper if needed using a working Gradle installation.
   - Confirm that `./gradlew :app:assembleDebug` and `./gradlew :app:testDebugUnitTest` run successfully from `mobile/`.
   - Current status: `./gradlew clean :app:compileDebugKotlin --rerun-tasks --stacktrace` passes.
   - Current status: compile now succeeds for `:app:compileDebugKotlin`, so wrapper rebuild appears resolved.

2. Confirm current mobile module configuration
   - Ensure `mobile/build.gradle` and `mobile/settings.gradle` align with the Android plugin and Kotlin versions.
   - Confirm `mobile/app/build.gradle` uses the right Kotlin and Compose versions.

### Phase 2 — Fix persistence and artifact model

1. Normalize `ArtifactEntity` and DB schema.
   - Persist `schemaVersion` and `deviceAlias` in SQLite.
   - Add explicit JSON payload handling rather than `payload.toString()`.
   - Update `ArtifactDao` to preserve all artifact fields.

2. Ensure model conversions are consistent.
   - Review `PmbrsArtifact.toArtifactPayload()` and `toEntity()`.
   - Confirm the fields saved to DB match the fields sent to sync.

3. Add tests for DB persistence.
   - Verify insertion and retrieval round-trip for full artifact records.
   - Verify pending artifact selection and sync marking.

### Phase 3 — Fix sync contract and artifact identity

1. Align artifact ID types.
   - Decide whether the sync contract should use `String` artifact IDs or stable numeric IDs.
   - Make `SyncApi.ArtifactPayload` match the chosen artifact identifier type.

2. Improve sync request payload.
   - Send JSON-serialized artifact payloads and explicit provenance fields if required.
   - Avoid sending raw `payload.toString()` values.

3. Harden sync behavior.
   - Only mark artifacts synced when the server returns confirmed synced IDs.
   - Preserve pending artifacts on partial or total failure.
   - Add retry logging and error classification.

4. Add API validation.
   - Validate the sync base URL before building Retrofit.
   - Provide a clear UI error if the endpoint is invalid.

### Phase 4 — Narrow collector scope for the first slice

1. Restrict the first delivery to low-risk collectors.
   - Keep:
     - `ScreenStateCollector`
     - `DeviceStateCollector`
   - Optionally keep `BatteryLevelCollector` if it is separate from device-state.

2. Defer higher-risk or placeholder collectors.
   - Remove or disable in the first slice:
     - `HealthDataCollector`
     - `BrowserHistoryCollector`
     - `MediaCollector`
     - `AppUsageCollector` and `GeolocationCollector` until permissions are clarified.

3. Simplify collector orchestration.
   - Update `CollectorService.collectAll()` to include only the approved first-slice collectors.
   - Preserve failure isolation so one collector failure does not cancel all collection.
   - Current status: `CollectorService` already uses only `ScreenStateCollector` and `DeviceStateCollector`.

4. Verify provenance metadata.
   - Ensure every emitted artifact includes device alias, artifact type, and source device ID.

### Phase 5 — Improve UI/UX and sync controls

1. Expose sync policy clearly.
   - Show whether sync is manual only or trusted-network gated.
   - Show current network state and why sync is blocked.

2. Add endpoint validation and save feedback.
   - Validate the base URL format in the UI.
   - Confirm save success or show validation error.

3. Show queue observability.
   - Display pending artifact count and last sync result.
   - Show a readable preview of stored artifacts.

4. Add permission status display if needed.
   - If collectors require permissions, show which permissions are granted or denied.

### Phase 6 — Document the first-slice boundaries and known gaps

1. Update or add doc sections in:
   - `docs/ingestion/adapters/mobile-collection.md`
   - `docs/ingestion/adapters/mobile-collection-architecture.md`
   - `docs/ingestion/adapters/mobile-collection-backlog.md`
   - `docs/ingestion/adapters/mobile-collection-execution-checklist.md`

2. Capture the current boundary explicitly.
   - State which collectors are implemented and which are stubbed.
   - State the current sync contract assumptions.
   - State the current build status and blocker.

3. Add a handoff note for the next developer.
   - Include the exact workspace path: `mobile/`.
   - Include the failing command and wrapper issue.
   - Include the artifact model mismatch and sync contract mismatch.

## Known risk areas

- Gradle wrapper failure: if `mobile/gradlew` remains broken, the code cannot be built or validated locally.
- Artifact identity mismatch: if the sync endpoint receives wrong ID types, sync will fail or duplicate artifacts may be created.
- Payload serialization mismatch: stringified maps are not reliable artifact payloads and are hard to parse.
- Stubbed collectors: placeholder collectors can mask the true implementation risk if they remain in the first slice.
- Background collection confusion: periodic collection exists in code but has no UI or lifecycle integration.
- Endpoint validation is now integrated: `normalizeSyncBaseUrl()` is used to reject invalid sync URLs before `NetworkSyncClient` is created.

## Acceptance criteria for the first slice

- The mobile app builds successfully in `mobile/`.
- The app persists at least one low-risk artifact to SQLite.
- The app can send pending artifacts to a sync endpoint using a validated payload shape.
- The sync endpoint contract uses stable artifact IDs and JSON payloads.
- The app only uses non-sensitive collectors for the first release.
- The docs describe the implemented scope and remaining gaps clearly.
