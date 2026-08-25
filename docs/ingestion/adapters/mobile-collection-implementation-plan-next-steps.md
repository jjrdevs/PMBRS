# Mobile Collection — Implementation Plan (Remaining Work & Audit)

This document aggregates the partially implemented items, missing or deferred work, and known gaps/risks for the PMBRS mobile collector. It provides a prioritized implementation plan, concrete steps, owners, estimated effort, acceptance criteria, and corrective recommendations for detected failure points.

Status at time of authoring
- Core first-slice features implemented: low-risk collectors (`ScreenStateCollector`, `DeviceStateCollector`), local SQLite persistence with expanded schema fields, deduplication, retention cleanup, manual sync, scheduled sync with `PMBRSSyncWorker`, sync endpoint normalization, persisted `lastSyncLog`, safe defaults (default sync interval 6h) and trusted-network gating, unit tests for scheduling and settings.
- Docs and runbooks: `mobile/HANDOFF.md`, `mobile/OBSERVABILITY.md`, unit tests, and a battery experiment script exist.
- Applied experiment artifacts: `mobile/results/experiment_20260808_190420/` is present in the repo and referenced from `mobile/HANDOFF.md`.
- Privacy package generated: `mobile/mobile_privacy_signoff_20260808_190525.zip`; formal reviewer decision is pending.

Recent implementation progress (delta)
- Implemented optional auth token support in `NetworkSyncClient` (Authorization: Bearer <token>); worker and UI plumbed to persist and use token.
- Enforced HTTPS for public sync endpoints in `normalizeSyncBaseUrl()`; HTTP allowed only for localhost/loopback to support test harnesses.
- Added MockWebServer TLS + auth unit test validating HTTPS and Authorization header handling.
- Added lightweight telemetry counters (`Telemetry`) to record sync runs and outcome categories; counters persisted in app SharedPreferences.
- Added auth-token editing UI in `MainActivity` to persist tokens to `SyncSettings`.
- Unit tests updated/added and executed successfully (`:app:testDebugUnitTest`).

Remaining / Deferred Work (summary)
 - Run and analyze battery/observability experiments on representative devices.
 - Staged sync validation against a secure test hub (success, partial success, 4xx/5xx, timeouts) — TLS+auth unit test implemented; consider an integration run against staging certs.
 - Telemetry and monitoring (run counts, success/failure classification, payload sizes). Counters implemented; add in-app debug view to surface counts for maintainers.
 - Privacy review and formal sign-off.
 - Retention configurability decision and optional UI.

Prioritized Implementation Plan

Workstream A — Battery & Observability (priority: high) — owner: mobile eng
- Goal: verify real-world battery impact and tune defaults so background behavior is safe.
- Steps:
  1. Run two device experiments (Wi‑Fi and cellular): 30–60m quick run + 24h full run. Use `mobile/scripts/run_battery_experiment.sh` and `mobile/OBSERVABILITY.md`. (0.5–1 day)
  2. Collect artifacts: `batterystats_after.txt`, `logcat_capture.txt`, profiler traces. Upload to Battery Historian if needed. (0.25 day)
  3. Compare delta vs baseline device without app activity. If >1% daily drain observed on Wi‑Fi, apply mitigations: increase `syncIntervalHours`, enforce `UNMETERED` when `trustedNetworkOnly` is true, batch multiple artifacts per sync, reduce payload size. (0.5–1 day)
  4. Acceptance: measured daily impact ≤ ~1% on Wi‑Fi or documented tradeoff with mitigation plan.

Workstream B — Production endpoint & auth hardening (priority: high) — owners: backend + mobile
- Goal: ensure secure, authenticated sync against a staging hub and robust client-side validation.
- Steps:
  1. Add optional auth token support to `NetworkSyncClient` (accept header `Authorization: Bearer <token>`). Provide a clear failure classification for auth failures (401) in `SyncService`. (0.5 day)
  2. Ensure `NetworkSyncClient.create()` performs strict URL normalization and rejects non-HTTPS endpoints; update UI feedback to state why save failed. (0.25 day)
  3. Add a staging MockWebServer deployment that requires TLS and token header; run staged sync. (0.5 day)
     - Quick local integration: a lightweight HTTP mock server is provided at `mobile/scripts/mock_auth_server.py`. Run locally and point the emulator to the host service using `http://10.0.2.2:<port>/` (the app allows `http` for localhost/test harnesses). Example:
       ```bash
       # start the mock server on port 8080 expecting token 'test-token'
       ./mobile/scripts/mock_auth_server.py --port 8080 --token test-token
       ```
       Then in the debug app set `Sync endpoint URL` to `http://10.0.2.2:8080/` and `Auth token` to `test-token` and trigger a manual sync. The mock server will respond with a sample `syncedIds` payload if the header matches, or `401` otherwise.
  4. Acceptance: staging sync succeeds with valid token and fails gracefully with invalid token (pending queue preserved; `lastSyncLog` records auth failure). For full TLS validation, use the existing unit test `NetworkSyncClientAuthTlsTest` which demonstrates MockWebServer TLS setup.

Workstream C — Staged sync validation (priority: high) — owner: QA/dev
- Goal: validate sync semantics across error classes and partial success.
- Steps:
  1. Test scenarios against MockWebServer: full success, partial success (some `syncedIds`), 5xx, 4xx, timeouts, slow responses. (0.5 day)
  2. Verify `SyncService` and `PMBRSSyncWorker` preserve pending artifacts when server doesn't confirm `syncedIds`, and only mark confirmed IDs as synced. (0.25 day)
  3. Acceptance: behavior matches documented contract for each scenario; logs and `lastSyncLog` are informative.

Workstream D — Telemetry & lightweight monitoring (priority: medium) — owner: mobile eng
- Goal: surface run counts, success/failure classification, payload sizes, and queue trends to support early debugging and regression detection.
- Steps:
  1. Implementation: debug-level counters were added and persisted in `Telemetry` (`periodic_run_started`, `periodic_run_succeeded`, `periodic_run_failed_{network,server,client}`, `synced_count`). In addition, a `payload_bytes_sent` metric was implemented and recorded by `NetworkSyncClient` before sending the JSON payload. (0.5 day)
  2. Implementation: an in-app debug view exists in `MainActivity` (the `MobileHomeScreen` telemetry section) to surface aggregated counts and provide refresh/clear controls. (0.5 day)
  3. Tests/validation: sync-related unit tests were executed after instrumentation; counts are available via `Telemetry.getCounts()` and can be inspected in debug builds or via `adb` by reading the `pmbrs_telemetry` SharedPreferences. (Status: completed)

Workstream E — Privacy review & policy sign-off (priority: high before release) — owner: product/privacy
- Goal: get explicit privacy/legal sign-off for stored fields and retention policy.
- Steps:
  1. Prepare a 1–2 page privacy checklist referencing persisted artifact fields, retention duration, gating, and data flows. (0.25 day)
  2. Run the checklist by privacy and capture approvals or required mitigation actions. (0.5–1 day)
  3. Acceptance: documented approval or a short mitigation plan with owner and timeline.

  Documentation: see the privacy checklist: `docs/privacy/mobile-privacy-checklist.md` for a compact reviewer checklist and approval sign-offs.

Workstream F — Retention configurability decision & UI (priority: low-to-medium) — owner: product + mobile
- Goal: decide whether to expose retention period to users or keep a fixed default.
- Steps:
  1. Product decision: keep default 7 days or expose a small setting (e.g., 1/7/30 days). (0.25 day)
  2. Implementation: retention configurability was implemented in the mobile app UI and settings. `SyncSettings.retentionDays` persists the configured value and `MainActivity` exposes a `Retention days` field. Applying the setting rebuilds the `CollectorService` with the new `retentionDays` and immediately triggers `collectorService.cleanupOldArtifacts()` so the change takes effect immediately.
  3. Tests: a new unit test `CollectorServiceRetentionTest` verifies that `CollectorService.cleanupOldArtifacts()` removes artifacts older than the configured retention window.
  4. Acceptance: retention rule matches configuration, the UI persists the value, and the regression test validates deletion behavior. (Status: completed)

Workstream G — Final docs & handoff (priority: medium) — owner: author
- Goal: update docs with experiment results, telemetry notes, auth instructions, and privacy sign-offs.
- Steps:
  1. Update `mobile/HANDOFF.md`, `mobile-collection-implementation-plan.md`, and `mobile/OBSERVABILITY.md` with outcomes and how to reproduce them. (0.25–0.5 day)
  2. Produce an explicit reviewer checklist with commands and file locations. (0.25 day)

Next actions & owners (concrete)
- **Run battery experiments** — owner: mobile eng (you or assigned engineer). Steps:
  - Quick run (30m) Wi‑Fi: `./mobile/scripts/orchestrate_battery_experiment.sh <device-id> 30`.
  - Quick run (30m) Cellular: same command on a cellular-enabled device or a device on mobile data.
  - Full run (24h) Wi‑Fi: `./mobile/scripts/orchestrate_battery_experiment.sh <device-id> 1440`.
  - Collect artifacts and upload `batterystats_after_*.txt` to Battery Historian.

- **Staged sync integration** — owner: mobile + backend. Steps:
  - For fast local validation use `./mobile/scripts/run_staged_sync_integration.sh 8080 test-token` (host-run mock server + POST).
  - For emulator manual validation run `./mobile/scripts/mock_auth_server.py --port 8080 --token test-token` and set `Sync endpoint URL` to `http://10.0.2.2:8080/` in the debug app.
  - For end-to-end TLS validation request staging certs from backend and run scheduled scenarios against staging.

- **Privacy sign-off** — owner: product/privacy. Steps:
  - Send `docs/privacy/mobile-privacy-signoff.md` and `docs/privacy/privacy_signoff_package.md` (prepared) to privacy reviewers with attachments: `mobile/HANDOFF.md`, `mobile/OBSERVABILITY.md`, sample telemetry export (`pmbrs_telemetry.xml`), and `mobile/mobile_privacy_signoff_20260808_190525.zip`.
  - Capture decisions, mitigations, and dates in `mobile-privacy-signoff.md`.

- **Handoff update** — owner: author. Steps:
  - After experiments and sign-off, update `mobile/HANDOFF.md` and this plan with results and attach battery histograms and key findings.

Cross-cutting testing & verification
- Unit tests: keep `SyncSettingsTest`, `PMBRSSyncWorkerScheduleTest`, and worker/service tests green.
- Integration: staged MockWebServer scenarios to validate auth and partial success. Maintain deterministic tests for server failures using `syncServiceProvider` hook already present in `PMBRSSyncWorker`.

Audit of potential failure points and corrective recommendations

- Failure: non-HTTPS or invalid sync endpoint saved by UI.
  - Correction: enforce `normalizeSyncBaseUrl()` to require `https://` and reject otherwise; provide immediate UI feedback. (Status: partially implemented; ensure rejection message is explicit.)

- Failure: marking artifacts as synced before server confirmation (partial success bug).
  - Correction: `SyncService` must only call `artifactDao().markSyncedByArtifactId()` for IDs explicitly returned in `syncedIds`. Add tests simulating partial success to assert behavior. (Status: implementation reviewed — keep tests.)

- Failure: excessive retries causing battery/network churn.
  - Correction: ensure backoff policy is conservative (exponential with reasonable base) and respect `trustedNetworkOnly` gating; default interval 6h is conservative. Add telemetry and a limit on immediate retries for certain client errors. (Status: safe defaults implemented.)

- Failure: multiple `SyncSettings` instances writing concurrently causing preference races.
  - Correction: centralize writes or ensure atomic semantics; prefer `apply()` for non-test code and `commit()` only in test contexts requiring synchronous persistence. Consider a small `SettingsManager` wrapper to provide thread-safe operations. (Status: `lastSyncLog` uses `commit()` to satisfy tests; recommend documenting this and switching to `apply()` in production unless synchronous persistence is required.)

- Failure: WorkManager constraints misconfigured for metered cellular cost.
  - Correction: when `trustedNetworkOnly` is true, use `NetworkType.UNMETERED` (enforced). When false, use `CONNECTED` but consider optional UI to restrict to unmetered only. Confirm WorkManager scheduler uses `enqueueUniquePeriodicWork` with KEEP policy. (Status: implemented.)

- Failure: unhandled exception in worker causing retry storms.
  - Correction: in `doWork()` catch and classify exceptions. Use `Result.failure()` for client errors and `Result.retry()` for transient network or 5xx server errors; log and record telemetry. (Status: worker classifies SyncResult cases; add explicit catches for JSON parsing and DB errors to avoid retrying on client-parse failures.)

- Failure: privacy scope unclear for provenance metadata.
  - Correction: add explicit documentation listing persisted fields and rationale; include data flow diagram for reviewers. (Status: handoff doc exists; expand with a one-page privacy checklist.)

Quality gates & acceptance criteria
- All unit tests pass and CI (if any) runs green.
- Battery experiment performed and documentation added.
- Staged sync with TLS + auth passes; service preserves pending artifacts on failures.
- Privacy sign-off or documented mitigation actions are recorded.

Rollback and mitigation plan
- If a release shows increased battery or network errors, immediately:
  1. Disable scheduled sync rollout via remote config (if available) or update `trustedNetworkOnly` default to true and increase `syncIntervalHours` to a large value (e.g., 24h).
  2. Revert client to last known-good release if telemetry indicates severe regression.

Appendix — Commands and quick checks
```
# Run unit tests
cd mobile
./gradlew :app:testDebugUnitTest

# Run scheduling test
./gradlew :app:testDebugUnitTest --tests com.pmbrs.mobile.workers.PMBRSSyncWorkerScheduleTest

# Run battery experiment (device required)
mobile/scripts/run_battery_experiment.sh <device-id> <minutes>

# Run staged sync (example using MockWebServer harness — implement test harness on staging)
# Start mock server with TLS and token requirement, then run a manual sync in app or via a test harness.
```

**Automation & helper scripts**

- **Generate battery report:** runs the orchestrator, collects artifacts, parses telemetry, and fills the report template. Usage:

```bash
cd mobile
./scripts/generate_battery_report.sh <device-id> <minutes> [dest-dir]
```

- **Prepare privacy email + package:** creates a ZIP with `mobile/HANDOFF.md`, `mobile/OBSERVABILITY.md`, privacy checklist, and a sample telemetry export; prints the ready-to-send email draft. Usage:

```bash
cd mobile
./scripts/prepare_privacy_email.sh [output-zip]
```

- **Parse telemetry:** summarize `pmbrs_telemetry.xml` counters into JSON:

```bash
cd mobile
./scripts/parse_telemetry.py /path/to/pmbrs_telemetry.xml
```

The CI workflow uploads any generated battery results from `mobile/results/` as build artifacts; see `.github/workflows/ci-integration.yml`. The current CI step runs mock staged sync integration only; full TLS validation against real staging certs requires a runner with staging env/credentials.

**TLS mock server (local staged validation)**

- A TLS-capable mock auth server is available at `mobile/scripts/mock_auth_server_tls.py`. It can generate a self-signed cert if none are supplied. Quick start:

```bash
cd mobile
# start self-signed TLS mock server and run a quick local check
./scripts/run_staged_tls_integration.sh 8443 test-token
```

- Notes: the server uses a self-signed cert by default — for emulator testing you may need to trust the cert or use staging certs supplied by the backend. For CI-based TLS validation, configure a runner with staging certs and network access.

Staged TLS validation (manual + CI)

- Purpose: validate the complete TLS + auth handshake against the backend's staging certificate chain and confirm client trust, hostname validation, and token-based auth flows.

- Manual steps (developer with staging certs):

```bash
cd mobile
# Start the TLS mock server locally using provided staging cert/key
./scripts/run_staged_tls_integration.sh 8443 test-token /path/to/staging_cert.pem /path/to/staging_key.pem

# Or run the mock auth server directly (example)
python3 scripts/mock_auth_server_tls.py --port 8443 --token test-token --cert /path/to/staging_cert.pem --key /path/to/staging_key.pem

# In the debug app, set Sync endpoint to https://<host>:8443/ and set Auth token to 'test-token'
```

- CI guidance (requires org/staging secrets and runner with network access):

1. Add the staging cert and key (or a tarball containing the cert chain) as protected repository secrets or to the runner's secure file store. Recommended secret names:
   - `STAGING_CERT_PEM` (PEM content)
   - `STAGING_KEY_PEM` (PEM content)
   - Optionally `STAGING_CERT_TARBALL` (if multiple files)

2. Update the CI job to write these secrets to disk at runtime (only on protected branches/PRs from trusted repos) and run the existing `runStagedSyncIntegration` step pointing at the extracted certs. Example snippet (GitHub Actions):

```yaml
- name: Install staging certs (protected)
  if: github.ref == 'refs/heads/main' || github.event.pull_request != null
  run: |
    mkdir -p $RUNNER_TEMP/staging_certs
    echo "$STAGING_CERT_PEM" > $RUNNER_TEMP/staging_certs/staging_cert.pem
    echo "$STAGING_KEY_PEM" > $RUNNER_TEMP/staging_certs/staging_key.pem

- name: Run staged TLS integration with staging certs
  run: |
    cd mobile
    ./scripts/run_staged_tls_integration.sh 8443 test-token $RUNNER_TEMP/staging_certs/staging_cert.pem $RUNNER_TEMP/staging_certs/staging_key.pem
```

Security note: never expose staging cert/private keys in public PRs; restrict CI steps that use them to protected branches or trusted PRs. If the backend can provide a short-lived test cert or a CA bundle, prefer that pattern.

Additional validation steps (new)

```
# Run the TLS + auth unit test only
./gradlew :app:testDebugUnitTest --tests com.pmbrs.mobile.sync.NetworkSyncClientAuthTlsTest

# Inspect telemetry counters (in a debug build or via adb shell)
# The Telemetry helper stores counters in SharedPreferences `pmbrs_telemetry`.
# Example to dump via `adb` (device must be connected):
adb shell "run-as com.pmbrs.mobile cat /data/data/com.pmbrs.mobile/shared_prefs/pmbrs_telemetry.xml"

```

Document history
- Created: initial aggregated plan and audit (2026-08-08).
- Updated: recorded implementation of auth token, HTTPS enforcement, MockWebServer TLS+auth test, telemetry counters, and auth UI (2026-08-08).

- Experiment run: results/experiment_20260808_152543 (automatically recorded)

- Experiment run: results/experiment_20260808_190420 (automatically recorded)
