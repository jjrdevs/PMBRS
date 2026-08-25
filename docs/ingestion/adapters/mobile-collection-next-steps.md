# Mobile Collection Next Steps

## Purpose

This document defines the remaining work for the PMBRS Android mobile collector after the first-slice implementation is in place. It is a focused follow-up plan that tracks the completion of the remaining mobile work items identified during audit.

## Current gap summary

The first-slice mobile implementation now supports:

- compilation of `mobile/app`
- low-risk collection via `ScreenStateCollector` and `DeviceStateCollector`
- local persistence of artifacts in SQLite with schema version, device alias, and provenance fields
- JSON payload serialization and persistence of provenance metadata
- sync URL validation and normalized endpoint handling
- WorkManager-based periodic scheduling at startup
- periodic sync worker implementation for scheduled artifact delivery
- basic UI controls for manual capture and sync
- duplicate filtering by stable fingerprint at insert time
- pending queue visibility, network status display, and permission status display in the UI
- small sync log state and partial sync acknowledgement semantics with preserved pending artifacts on failure
- mocked server tests validating sync request path, payload shape, success handling, partial success, and failure preservation
- scheduled sync worker tests validating successful sync and server retry handling

The remaining work is now focused on final background diagnostics persistence, WorkManager sync policy observability, manual endpoint validation feedback, and documentation closure.

## Objective

Complete the remaining mobile work so that the phone collector is production-ready for the first PMBRS release slice and the implementation is clearly documented for handoff.

## Remaining implementation plan

### Phase 1 — Finalize sync validation

1. Confirm the periodic WorkManager sync path.
   - validate that the scheduled worker uses the same sync contract as the manual path
   - ensure scheduled sync failures preserve the pending queue
   - capture any scheduler diagnostics or retry outcomes

2. Verify the sync payload contract end-to-end.
   - confirm `SyncApi` sends artifacts to `/api/v1/artifacts/sync`
   - confirm `ArtifactPayload` includes `artifactId`, `source`, `payload`, `createdAtEpochMs`, `schemaVersion`, `deviceAlias`, and `provenanceMetadata`
   - confirm `payload` and `provenanceMetadata` are serialized JSON strings

3. Keep the sync client robust.
   - preserve pending artifacts on network or server failure
   - mark artifacts synced only for IDs returned in `syncedIds`
   - avoid retries for client-side validation failures

4. Confirm endpoint validation.
   - `normalizeSyncBaseUrl()` is used to normalize and validate URLs
   - invalid URLs should be rejected before the sync service is created
   - the UI should display clear invalid endpoint feedback

### Phase 2 — Confirm queue hygiene and retention

1. Maintain duplicate filtering.
   - keep fingerprint-based deduplication in the DB layer
   - confirm repeated screen/device state events are deduplicated by source, payload, and timestamp semantics

2. Keep retention rules in place.
   - preserve queued artifacts for a bounded retention period
   - remove artifacts older than the configured cutoff
   - verify cleanup behavior with tests

3. Review whether retention should become configurable.
   - if needed, add a user-facing retention policy option later
   - otherwise keep the default 7-day behavior for the first slice

### Phase 3 — Verify UI and observability

1. Confirm sync policy visibility.
   - show current network connection type and trusted-network gating
   - show whether manual sync is allowed under current policy

2. Confirm pending artifact visibility.
   - show pending artifact count
   - show a preview of the most recent queued artifact summary

3. Confirm permission/consent indicators.
   - display the current granted/denied state for runtime permissions
   - surface collection limitations caused by permission denial

4. Confirm last sync diagnostics.
   - show whether the last sync attempt succeeded, partially succeeded, or failed
   - include error details where available

### Phase 4 — Harden diagnostics and final edge cases

1. Add explicit diagnostics for WorkManager failures.
   - capture any worker scheduling or execution errors
   - persist the last periodic sync outcome so the UI can render it on restart

2. Review transient vs permanent failures.
   - ensure network failures are retried with backoff
   - ensure bad API responses or invalid endpoints do not trigger blind retries

3. Audit the current first-slice scope.
   - keep only low-risk collectors in the first release
   - do not add higher-risk or permission-heavy collectors until the contract is stable

### Phase 5 — Close documentation and handoff

1. Update the architecture note.
   - confirm `docs/ingestion/adapters/mobile-collection-architecture.md` matches the actual implementation and sync contract

2. Add a handoff section.
   - summarize what is implemented in the first slice
   - identify remaining risks and validation steps
   - document the workspace path and validation commands used for mobile checks

3. Reconcile the mobile docs.
   - ensure `mobile-collection-implementation-plan.md` reflects current progress and deferred scope
   - ensure `mobile-collection-backlog.md` lists only remaining work items
   - ensure `mobile-collection-execution-checklist.md` marks completed milestones and outstanding items clearly

## Acceptance criteria for remaining work

- The manual and scheduled sync paths are validated against the same server contract.
- Duplicate artifacts are filtered before insertion and pending queue hygiene is maintained.
- The mobile UI exposes sync policy, pending queue state, permission state, and last-sync diagnostics.
- Failure modes preserve pending data and do not silently drop unacknowledged artifacts.
- Documentation describes the implemented scope, remaining risks, and next validation requirements clearly.

## Notes

This document is scoped to the final delivery work after the first-slice implementation. It is a handoff-focused follow-up plan, not a redefinition of the original first-slice scope.

## Handoff Summary

**Implemented in this slice:**
- Low-risk collectors: `ScreenStateCollector` and `DeviceStateCollector`.
- Local persistence of full artifact fields (`schemaVersion`, `deviceAlias`, provenance).
- Deduplication by fingerprint at insert time and retention cleanup (7-day default).
- Manual and scheduled sync paths using `SyncService` and `PMBRSSyncWorker` (WorkManager).
- Sync payload shape and endpoint validation via `normalizeSyncBaseUrl()` and `NetworkSyncClient`.
- Persistent last-sync diagnostics persisted in `SyncSettings.lastSyncLog` and surfaced in the UI.
- Unit tests covering DB persistence, sync client, `SyncService` behavior, and `PMBRSSyncWorker` success/failure paths.

**Remaining risks & next validations:**
- Battery and background-impact profiling under real-world conditions (instrumentation/usage trials).
- Authentication and production endpoint hardening (TLS, auth, rate-limiting tests).
- User-facing retention configurability (if product requires it later).

**Quick validation commands (run from `mobile/`):**
```
./gradlew :app:compileDebugKotlin
./gradlew :app:testDebugUnitTest --tests com.pmbrs.mobile.workers.PMBRSSyncWorkerTest
```

**Workspace pointers for handoff:**
- App entry and UI: `mobile/app/src/main/java/com/pmbrs/mobile/MainActivity.kt`
- Collectors: `mobile/app/src/main/java/com/pmbrs/mobile/collectors/` (screen/device)
- DB + DAO: `mobile/app/src/main/java/com/pmbrs/mobile/data/ArtifactDatabase.kt`
- Sync and client: `mobile/app/src/main/java/com/pmbrs/mobile/sync/` (includes `NetworkSyncClient`, `SyncService`, `SyncApi`)
- Workers: `mobile/app/src/main/java/com/pmbrs/mobile/workers/PMBRSSyncWorker.kt` and `PMBRSWorker.kt`
- Tests: `mobile/app/src/test/java/com/pmbrs/mobile/` (worker, sync, data tests)

## Validation: Battery & Observability

Purpose: provide a short, repeatable validation plan to measure background battery impact and visibility into periodic sync behavior.

1. Baseline and scenario measurement
    - Reset battery stats on a test device/emulator:
       ```bash
       adb devices
       adb -s <device-id> shell dumpsys batterystats --reset
       ```
    - Run a realistic scenario (idle background for N minutes, periodic sync enabled) for 10–30 minutes.
    - Capture post-run stats:
       ```bash
       adb -s <device-id> shell dumpsys batterystats > batterystats_after.txt
       ```
    - Optionally upload the captured output to Battery Historian for timeline analysis.

2. WorkManager & sync tracing
    - Collect `logcat` output while a periodic sync runs and filter for the app tag and `WorkManager`:
       ```bash
       adb -s <device-id> logcat --clear
       adb -s <device-id> logcat | grep -E "PMBRS|PMBRSSyncWorker|WorkManager|SyncService"
       ```
    - Verify `PMBRSSyncWorker` run timestamps and `SyncSettings.lastSyncLog` entries after each scheduled run.
    - Use Android Studio's `Profiler` -> `Energy` and `Network` tabs to confirm sync durations and network payload sizes.

3. Observability checklist
    - Confirm `lastSyncLog` shows outcome (success / partial / failure) after scheduled runs and is visible in UI on restart.
    - Verify pending-queue count does not decrease on failed syncs and that `synced` marking only occurs for confirmed IDs.
    - Collect `WorkManager` work info for debugging (use an in-app debug view or REPL):
       ```kotlin
       WorkManager.getInstance(context).getWorkInfosByTag("pmbrs_sync")
       ```

4. Repeatable experiments
    - Run the same scenario with `trusted-network` toggled to verify gating behavior.
    - Run with the server stubbed to return partial successes to validate pending-preservation semantics.

Recording results: store captured `batterystats_after.txt`, `logcat` snapshots, and profiler traces in the review folder for the delivery ticket.

If you'd like, I can also generate a short `HANDOFF.md` in `mobile/` summarizing these points for reviewers.
