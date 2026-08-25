# Bromite Browser Foundation Plan

## Decision

Use Bromite as the real browser foundation for the PMBRS browser telemetry effort.

This is intentionally not a custom WebView shell. The current custom browser app remains a prototype only and should not become the long-term product direction.

## Alignment with the roadmap

This plan follows the phased roadmap in the source-of-truth document and keeps the PMBRS browser work aligned with the documented guardrails:

- browser collected data stays local-first,
- browser telemetry is opt-in,
- PMBRS remains downstream from the browser,
- raw browser metadata stays minimal and temporary,
- summaries are the main analytical artifact.

## Phase 1 — Stabilize the browser foundation

### Goal

Establish Bromite as the browser base and ensure we can build and run it on the device.

### Deliverables

- Bromite source checked out or forked under a project-managed workspace,
- Android build path validated,
- device install verified,
- browser baseline confirmed on the physical device,
- PMBRS browser telemetry work scoped as an instrumentation layer rather than a replacement browser.

### Required actions

1. Clone or fork Bromite upstream.
2. Validate the Android build prerequisites.
3. Build the arm64 release APK.
4. Install it on the physical device.
5. Confirm the browser loads pages and behaves as a real browser.

### Acceptance criteria

- Bromite runs on the device,
- the app is a real browser foundation rather than a WebView stub,
- the project team can state clearly that PMBRS is not replacing the browser.

## Phase 2 — Instrument browser page telemetry

### Goal

Capture page-level metadata without collecting raw page content or query strings.

### Scope

- canonical URL or hostname,
- page title (truncated),
- start and end timestamps,
- dwell time,
- category label,
- provenance metadata,
- schema version,
- deduplication for redirects and reloads.

### Required guardrails

- no full page content,
- no URL query strings,
- no raw search terms,
- no path-level collection by default,
- no storage of full page text unless explicitly opted in.

### Acceptance criteria

- each valid page visit becomes one PMBRS-compatible browser artifact,
- duplicates are suppressed,
- empty/error pages are skipped,
- the output is summary-first by default.

## Phase 3 — Add the PMBRS logging pipeline

### Goal

Connect Bromite instrumentation to the PMBRS artifact model without mixing browser logic into the PMBRS app itself.

### Required work

- versioned browser artifact schema,
- browser event taxonomy,
- local artifact generation,
- PMBRS local ingest validation,
- browser queue visibility,
- local-only storage before sync,
- summaries and browser review screens.

### PMBRS boundary

Bromite is the source of browser truth. PMBRS is the downstream analysis and local review layer.

### Acceptance criteria

- browser page events appear as PMBRS artifact records,
- local queue behavior is visible,
- browser metadata remains distinct from the rest of the app data,
- the ingest boundary is explicit and versioned.

## Phase 4 — Privacy and retention controls

### Goal

Keep the browser telemetry bounded and reviewable.

### Default policy

- raw browser metadata retained for a short window only,
- daily or weekly summaries retained longer,
- full URL logs disabled by default,
- browser logging toggled by explicit user choice,
- manual clear/delete support available.

### Acceptance criteria

- user can disable browser telemetry without impacting other PMBRS data,
- deletion works cleanly,
- retention windows are enforced,
- clear explanation is shown to the user before collection starts.

## Phase 5 — Minimal browser parity for real use

### Goal

Make the Bromite-based browser usable enough to validate actual user behavior without adding product bloat.

### Minimal useful features

- address bar,
- back/forward/reload,
- homepage or new-tab behavior,
- safe URL handling,
- stable page loading,
- simple history or nav state.

### Acceptance criteria

- the browser is stable enough for actual browsing,
- the instrumentation does not interfere with page loading,
- the app is still clearly a telemetry-sensitive browser, not a generic product browser.

## Phase 6 — Evaluate whether the browser foundation is sufficient

### Decision rule

Keep Bromite as the browser foundation unless it is clearly insufficient for the intended telemetry use.

### Proceed with Bromite when

- the browser works reliably on-device,
- the telemetry is useful and local-only,
- the user can inspect and prune data,
- the PMBRS artifact path is stable.

### Re-evaluate only if

- Bromite does not provide the needed browser instrumentation,
- the feature set is insufficient for real testing,
- the telemetry needs stronger browser integration than the stock fork provides.

## Phase 7 — End-to-end validation on device

### Goal

Prove the complete path works on the physical device.

### Test flow

1. Open Bromite on-device.
2. Browse a few pages.
3. Confirm page metadata is logged.
4. Confirm browser artifacts are written locally.
5. Confirm PMBRS sees them as queued or stored artifacts.
6. Confirm summary generation works.
7. Confirm delete and retention behavior works.
8. Confirm sync/local-first behavior still works when network is unavailable.

### Acceptance criteria

- the browser logs page metadata on device,
- PMBRS accepts and stores browser artifacts,
- local queue state is correct,
- the user can review and prune browser data,
- no broad raw data is retained beyond the policy.

## Current implementation status

- Bromite is already verified installable on the connected Android device.
- The current custom WebView browser remains a prototype and should not be the long-term browser foundation.
- The next project step is to pivot fully onto Bromite and begin the instrumentation path described above.

## Immediate next step

Create a real Bromite-based implementation branch or workspace and begin instrumenting the browser with the metadata-only PMBRS contract described in this plan.
