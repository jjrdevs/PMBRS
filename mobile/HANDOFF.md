# PMBRS Mobile Collector — Handoff Notes

This file summarizes what was implemented in the first delivery slice, where to find important code, how to validate the build/tests, and the known remaining risks.

## Implemented (first slice)
- Low-risk collectors: `ScreenStateCollector`, `DeviceStateCollector`.
- Local persistence in SQLite with full artifact fields: `schemaVersion`, `deviceAlias`, `provenanceMetadata`.
- Fingerprint-based deduplication at insert and retention cleanup (7-day default).
- Manual sync and scheduled sync via WorkManager:
  - Manual path: `SyncService` invoked from UI (`MainActivity.kt`).
  - Scheduled path: `PMBRSSyncWorker` (periodic delivery, retry/backoff semantics).
- Sync client: `NetworkSyncClient` with `normalizeSyncBaseUrl()` validation and `SyncApi` contract to `/api/v1/artifacts/sync`.
- Last-sync diagnostics persisted to `SyncSettings.lastSyncLog` and surfaced in UI.
- Unit tests for DB, sync client, `SyncService`, and `PMBRSSyncWorker` (success + failure behaviors).

## Workspace pointers
- UI and entry: `mobile/app/src/main/java/com/pmbrs/mobile/MainActivity.kt`
- Collectors: `mobile/app/src/main/java/com/pmbrs/mobile/collectors/`
- DB + DAO: `mobile/app/src/main/java/com/pmbrs/mobile/data/ArtifactDatabase.kt`
- Sync: `mobile/app/src/main/java/com/pmbrs/mobile/sync/` (includes `NetworkSyncClient`, `SyncService`, `SyncApi`)
- Workers: `mobile/app/src/main/java/com/pmbrs/mobile/workers/PMBRSSyncWorker.kt`, `PMBRSWorker.kt`
- Tests: `mobile/app/src/test/java/com/pmbrs/mobile/`

## Quick validation (from workspace `mobile/`)
```bash
./gradlew :app:compileDebugKotlin
./gradlew :app:testDebugUnitTest
# Or run a focused worker test
./gradlew :app:testDebugUnitTest --tests com.pmbrs.mobile.workers.PMBRSSyncWorkerTest
```

## Known risks / next validation work
- Battery and background impact: run extended instrumentation or manual device trials.
- Production endpoint/auth: implement and validate TLS/auth, and load tests against the hub.
- Optional: expose retention policy as user-configurable if required by product.

## Quick helpers added
- `mobile/scripts/mock_auth_server.py`: lightweight mock auth server for local staged-sync testing (enforces `Authorization: Bearer <token>` for `/api/v1/artifacts/sync`).
- `mobile/scripts/run_staged_sync_integration.sh`: starts the mock server, POSTs a sample payload, and validates the response.
- `mobile/scripts/orchestrate_battery_experiment.sh`: wrapper that runs `run_battery_experiment.sh` and `collect_battery_results.sh` and stores artifacts in a timestamped `results/` folder.

## Reviewer checklist
- [ ] Build and run app locally (`:app:assembleDebug`)
- [ ] Run unit tests (`:app:testDebugUnitTest`)
- [ ] Validate a full sync round-trip against a test hub (MockWebServer or staging)
- [ ] Confirm privacy defaults and retention expectations with policy owners

---

Contact: mobile maintainer (see repository CONTRIBUTORS) for walkthrough or follow-up actions.

## Results and follow-up actions

- Experiment artifacts from `results/experiment_20260808_190420/` have been applied; for future runs add a filled results file to `mobile/results/<timestamp>/battery_report.md` and copy a summary into `mobile/EXPERIMENT_RESULTS_TEMPLATE.md`.
- Record privacy review decision in `mobile-privacy-signoff.md` at repository root (or update `docs/privacy/mobile-privacy-signoff.md` with reviewer signature and date).
- Privacy package generated: `mobile/mobile_privacy_signoff_20260808_190525.zip`; send with `docs/privacy/privacy_email_draft.md`. Reviewer decision is pending.
- CI will upload any `mobile/results/**` artifacts for review; post the artifact link in the PR discussion. The current workflow runs mock staged sync integration only; full TLS validation against staging certs requires a runner with staging env/credentials.

Recommended next steps for reviewers
- Run the battery quick-run for Wi‑Fi and Cellular and attach `battery_report.md` to the PR.
- Confirm privacy checklist and sign-off before merging to main.

- Experiment artifacts have already been applied from `results/experiment_20260808_152543` to `results/experiment_20260808_190420`.
- Record privacy review decision in `mobile-privacy-signoff.md` and attach `mobile/mobile_privacy_signoff_*.zip`.
- For staged TLS validation, use `mobile/scripts/run_staged_tls_integration.sh 8443 test-token` or request staging certs from backend; real staging cert validation remains pending.

- Experiment report: results/experiment_20260808_190420/battery_report.md
- Telemetry summary: results/experiment_20260808_190420/telemetry_summary.json
