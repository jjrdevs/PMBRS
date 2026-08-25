# Personal Mobile Telemetry Roadmap (Solo, Local-Only, Opt-In)

## Source of truth

This document is the source of truth for product intent, strategy, and decision making.

- Use this file to answer: what are we trying to achieve overall?
- Use the milestone-specific plan for the current implementation task.
- If there is a conflict between this roadmap and a milestone plan, the roadmap wins unless the milestone plan is explicitly scoped to the current work.

## Purpose

This is the working roadmap for a single-user personal telemetry project. It assumes:

- the user is the sole operator and sole data subject,
- every collection source is explicitly opt-in,
- all data is stored locally by default,
- the goal is personal analysis and pattern discovery rather than product deployment,
- local control and explicit collection boundaries are part of the operating model.

This roadmap intentionally prioritizes meaningful signals and good local analysis over broad collection or high-risk telemetry.

## Design principles

1. Local-first by default.
   - Raw and derived data stay on-device unless the user intentionally exports it.
   - Prefer SQLite, local JSON, and local CSV exports over remote storage.

2. Opt-in by signal.
   - Every telemetry source should be independently enabled or disabled.
   - Example: app usage, browser domains, coarse location, and device state are separate switches.

3. Data minimization.
   - Collect the smallest data needed to answer a concrete question.
   - Prefer summaries over raw traces whenever a summary is enough.

4. Fail closed.
   - If a permission is missing or access is restricted, the collector should skip cleanly and log the reason.
   - Never fabricate data to “fill in the gap.”

5. Treat raw logs as temporary.
   - Keep raw logs short-lived and summary-first.
   - Derived summaries are the primary analytical artifact.

6. Define analysis questions before adding collection.
   - Each signal should answer a specific question.
   - If a signal does not answer a clear question, it should not be collected.

## Operating model

This is not a public-facing app. The operating model is different from a production release:

- keep collection explicit and bounded,
- keep retention easy to review,
- avoid noisy raw logs that are hard to analyze,
- avoid accidental over-collection when a feature seems “interesting.”

The main strategy is to keep the system explicit, bounded, and easy to review.

## Phase 0 — Define the research questions

### Goal

Decide what problem the telemetry is actually trying to solve.

### Questions to answer

- Do I want to know how much time I spend in each app?
- Do I want to track my browsing by domain category?
- Do I want to understand time at home/work/other locations?
- Do I want to see how battery or network state correlates with usage?
- Do I want to inspect daily or weekly behavioral trends rather than raw events?

### Output

A short local specification with:

- the exact signal to collect,
- the data fields needed,
- the retention policy,
- the expected summary output,
- and whether raw logs are temporary or permanently kept.

### Failure points and corrections

- Failure: collecting because a signal is technically available.
  - Correction: every signal needs a concrete question and a clear reason for collection.

- Failure: no retention plan.
  - Correction: define a default retention window before rollout.

## Phase 1 — Keep the baseline telemetry stable

### Goal

Lock in the low-risk baseline as the foundation for all later analysis.

### Continue collecting

- screen state,
- battery level,
- charging status,
- connection type,
- timestamps,
- provenance metadata,
- local queue and sync status where needed.

### Recommended retention

- raw event logs: 30–90 days,
- daily summaries: 6–12 months,
- operational sync logs: 30 days.

### Why this matters

This provides the basic time-series layer without requiring sensitive collection.

### Failure points and corrections

- Failure: raw device-state logs never get summarized.
  - Correction: keep raw logs short-term and generate summary tables for long-term analysis.

- Failure: schema drift across event types.
  - Correction: keep a stable schema version and provenance metadata for each event.

## Phase 2 — Add app usage telemetry

### Goal

Capture app attention and behavioral patterns.

### Recommended signals

- app package name,
- app label,
- foreground start time,
- foreground end time,
- session duration,
- daily total by app,
- time-of-day bucket,
- optional app category label.

### Design recommendations

- Prefer daily or weekly summaries over keeping every raw session forever.
- Keep raw session logs only if there is a specific reason to inspect session-level behavior.
- Expose app usage as an independent user toggle in settings.

### Recommended retention

- raw session logs: 14–30 days,
- daily top-app summaries: 6–12 months,
- per-app weekly trends: 12 months.

### Why this is the first expansion

App usage is the highest-value next signal for a personal project and is less invasive than browser history or location.

### Failure points and corrections

- Failure: retaining raw app history indefinitely.
  - Correction: create daily summaries and prune raw logs aggressively.

- Failure: ambiguous package-name treatment.
  - Correction: document whether package names are personal identifiers and keep them local-only.

- Failure: enabling usage collection without permission clarity.
  - Correction: show a simple screen explaining exactly what is being collected and why.

## Phase 3 — Add browser/domain telemetry

### Goal

Understand digital attention patterns without collecting raw content, while matching the user’s actual browser behavior: primarily Adblock Browser and occasionally Chrome.

### Recommended signals

For this project, the core browser telemetry signal is intentionally useful and locally actionable:

- browser package name,
- site hostname or domain,
- visit start time,
- visit end time,
- total dwell time per domain or tab session,
- category tags inferred from hostname and page context, such as work, social, shopping, video, news, dev, research, or unknown,
- lightweight input-field context, such as whether a form field was focused or interacted with and the general input type, without capturing the typed value,
- link or page-subcategory labels inferred from page structure or destination metadata, such as a shopping subcategory, research subtopic, or social thread cluster,
- a short optional page title when it is clearly non-sensitive and useful for differentiation.

This is intentionally not the same as raw browsing history. The project retains metadata about context and intent, not the contents of the page or the literal values entered by the user.

### Strong recommendation

For this local-only, single-user project, the allowed browser telemetry is: what site, when, how long, what category, and what kind of local context or subcategory it was associated with.

Use a metadata-first collection model:
- keep the site/domain and timing metadata,
- keep the dwell time, category label, and local intent/subcategory labels,
- keep lightweight record of input-field interaction type and general context without storing typed or submitted values,
- keep lightweight link or destination subcategory metadata when it is inferred locally from page metadata,
- avoid path-level or query-level capture,
- do not store raw page content, page text, search queries, raw form payloads, or full URLs by default,
- keep this signal strictly local and user-controlled.

This is a personal project and the relevant analytics question is not only “what site did I spend time on?” but also “what kind of context did I spend time in, and what general intent or subcategory did that visit belong to?”

### Recommended retention

- raw browser metadata: 7–14 days,
- daily browser summaries: 6–12 months,
- full URL logs or raw page text: disabled by default and only added with explicit opt-in.

### Why this is second

This is useful and personal, but it is more sensitive than app usage. The right product decision is to collect browser metadata in a narrow, readable, and summary-first way rather than raw browsing history.

### Failure points and corrections

- Failure: collecting full URLs or search strings too early.
  - Correction: keep only hostname, title, category, and local intent metadata until there is a clear reason to expand.

- Failure: discarding high-value context like input-field interaction or link subcategories.
  - Correction: retain lightweight local metadata about form interaction type and link/page subcategory classification, but never record the actual typed values or the text of the page.

- Failure: browser telemetry with no user-visible explanation.
  - Correction: document the exact scope and keep it behind a clear toggle.

- Failure: indefinite retention of browsing logs.
  - Correction: use short raw retention and summary-first storage.

- Failure: assuming a single browser API works for every browser app.
  - Correction: treat browsers as app-specific metadata sources and keep the design conservative and app-aware.

## Phase 4 — Add coarse location telemetry

### Goal

Understand where time is spent without storing a full high-precision movement trace.

### Recommended signals

- coarse place cluster or geohash,
- visit start and end time,
- coarse place category such as home, work, transit, or other,
- dwell time at each place,
- daily location summary.

### Strong recommendation

Avoid a continuous raw GPS trace in the default flow.

### Recommended retention

- raw coarse location points: 7–30 days,
- place summaries: 6–12 months,
- full traces: only for explicit need and not as the default.

### Why this is last

Location is the most identifying signal and should be treated with care even in a personal project.

### Failure points and corrections

- Failure: precise GPS tracking by default.
  - Correction: start with coarse place clustering and only collect exact coordinates with explicit opt-in.

- Failure: assuming local-only means low risk.
  - Correction: implement a reviewable retention plan and a raw-vs-summary split.

- Failure: long raw movement history without a strong reason.
  - Correction: default to summaries and make raw traces temporary and explicit.

## Phase 5 — Build the derived analysis layer

### Goal

Transform raw logs into useful summaries and trends.

### Recommended outputs

- daily app usage totals,
- time-of-day summaries,
- weekly browsing category summaries,
- place-frequency summaries,
- battery/network correlations,
- screen-state versus usage correlations.

### Design recommendation

Store summaries as a first-class data model alongside raw storage. Summaries should be the main artifact for analysis.

### Failure points and corrections

- Failure: relying only on raw logs for analysis.
  - Correction: add summary tables and aggregated views to reduce noise and retention pressure.

- Failure: schema churn in analysis scripts.
  - Correction: version every event type and keep schema changes explicit.

## Phase 6 — Export, review, and cleanup

### Goal

Keep the system manageable over time.

### Export formats

- JSON for raw structured events,
- CSV for summaries and daily analysis,
- notebook, dashboard, or script-based local review.

### Review cadence

- weekly: review storage growth and data quality,
- monthly: review which signals are still worth keeping,
- quarterly: prune raw logs and confirm retention windows.

### Failure points and corrections

- Failure: no periodic review.
  - Correction: schedule monthly cleanup and review of all retained raw data.

- Failure: raw logs accumulate because summaries are not generated.
  - Correction: run summary generation on a schedule and prune old raw logs automatically.

## Recommended rollout order for a solo user

1. Baseline device state and screen state
2. App usage telemetry
3. Browser/domain telemetry
4. Coarse location telemetry
5. Derived summaries and local dashboards
6. Optional raw traces only when there is a specific need

This order maximizes analytical value while keeping the most personal and sensitive data behind explicit opt-in boundaries.

## Implementation guardrails

### Local-only policy

- Keep all data on-device.
- Default to summaries rather than raw traces.
- Keep raw logs short-lived.

### Consent policy

- Every new signal must be opt-in.
- The app should explain what is being collected and why.

### Retention policy

- Raw logs are temporary.
- Summaries are the long-lived analysis layer.
- The user should be able to clear or prune all data easily.

### Security policy

- Keep data local and encrypted at rest if feasible.
- Avoid cloud sync unless the user explicitly decides to export or sync it.

## Concrete next milestone

### Milestone: app usage telemetry as the first rich signal

#### Goal

Introduce a single high-value collector that answers the most important personal question: how do I spend my time in apps?

#### Scope

- add an independent app usage toggle,
- gate on `PACKAGE_USAGE_STATS`,
- collect app package, session window, and duration,
- write local raw session events,
- generate daily summaries,
- prune raw logs after a short retention window,
- allow the user to clear all telemetry.

#### Acceptance criteria

- app usage collection is opt-in,
- permission denial is handled cleanly,
- raw logs are explicit and temporary,
- daily summaries exist and are the primary artifact,
- the app stores everything locally,
- the user can review and clear telemetry easily.

## Concrete next milestone: a separate instrumented browser app feeding PMBRS

### Goal

Build a separate, standalone mobile browser app that records page-level telemetry locally and emits PMBRS-compatible artifacts for later ingestion into PMBRS. The browser app is not the PMBRS app itself; it is a dedicated telemetry collector that sends data to PMBRS through a defined ingestion boundary.

### Current state

- PMBRS already has a working local artifact model, local ingest, sync policy, and dashboard UI.
- The app can collect app and device metadata and persist it locally.
- A minimal custom browser telemetry activity exists as a proof of concept using Android `WebView`.
- The project does not yet have a standalone browser app with address bar, navigation controls, a real telemetry pipeline, and a clean PMBRS handoff protocol.

### Important reality check

This is not a feature addition to the PMBRS app itself. It is a separate Android app with its own runtime, UI, and data flow.

The browser app should:

- record browser page metadata at the browser boundary,
- store artifacts locally first,
- expose a PMBRS-compatible export or ingest path,
- remain independent from the PMBRS UI and data model unless explicitly transferred,
- treat PMBRS as a downstream consumer, not as part of the same app process.

The PMBRS app should:

- accept browser-generated artifacts through a defined ingestion contract,
- validate schema and provenance metadata,
- store them in the same local artifact model as other PMBRS signals,
- keep browser data separate in review and summarization until the user chooses to merge it.

This is not a clone of Adblock Browser and it should not be described as one until the project has either:

- a real browser-engine integration, or
- a stable, reviewed custom browser build that is functionally sufficient for the user’s telemetry goals.

Android `WebView` is useful for metadata logging, but it is not the same as a full independent browser engine. It cannot capture the full browser internals, extension model, or all browsing behaviors that a dedicated browser project would provide.

### Ingestion contract boundary

The browser app and PMBRS app must agree on a clear boundary before implementation starts.

Required contract elements:

- artifact schema version,
- event-type taxonomy,
- timestamp format and timezone behavior,
- canonical URL or hostname rules,
- provenance fields such as app_id, device_id, and collection source,
- secure local transfer method, such as a local HTTP endpoint, shared file export, or explicit manual import,
- explicit data minimization rules for path/query handling,
- reviewable retention and delete behavior at both ends.

See the Bromite → PMBRS ingest contract: [Bromite → PMBRS Ingest Contract](docs/ingestion/adapters/bromite-pmbrs-ingest-contract.md)

#### Failure: no ingestion contract between the two apps

- Risk: PMBRS accepts malformed or mismatched browser artifacts, causing silent data loss or bad summaries.
- Mitigation: define a versioned schema and validate every ingest before it is persisted.

### Objectives

The end-state is a separate instrumented browser app that follows the same design pattern:

- browser as the source of truth for page metadata,
- local-first raw storage inside the browser app,
- opt-in logging,
- summary-first analytics,
- explicit review and deletion controls,
- a clean PMBRS handoff through a defined artifact or ingest interface,
- clear separation between browser functionality and PMBRS processing.

### Known failure points and mitigations

#### Failure: treating WebView as equivalent to a fully instrumented browser

- Risk: it does not provide the same behavior, extension model, or deep browser instrumentation as a full browser engine.
- Mitigation: explicitly scope the project to “instrumented browser shell” rather than “full Adblock Browser clone” until parity is demonstrated.

#### Failure: duplicate page events from redirects, reloads, and repeated navigation

- Risk: a single page load can create multiple navigation callbacks, especially for redirects or dynamic page transitions.
- Mitigation: canonicalize URLs, suppress duplicate events within a short time window, and emit one visit record per canonical page session.

#### Failure: page title and URL noise from blank, error, or interstitial pages

- Risk: blank or error pages can generate misleading telemetry.
- Mitigation: ignore blank pages, protocol-only URLs, and failed loads; only keep records with valid domain and page metadata.

#### Failure: over-collecting browsing data beyond the local-only design

- Risk: storing full URL paths, query strings, or page content can violate the project boundary and create unnecessary privacy exposure.
- Mitigation: default to hostname-level and title-level records, keep path/query out of storage unless the user explicitly opts in.

#### Failure: browser telemetry becomes a fake signal if the user exits the app or uses another browser

- Risk: the app only logs what happens inside the instrumented browser shell.
- Mitigation: document clearly that this is a dedicated PMBRS browser app, not a universal browser-history collector.

#### Failure: the browser app is treated as if it were the PMBRS app

- Risk: the project blurs the functional boundary and creates hidden coupling between telemetry collection and analysis.
- Mitigation: keep the browser app and PMBRS app separate in code, deployment, and documentation, and define an explicit import boundary.

### Phase 1 — Stabilize the browser shell

#### Scope

- create a dedicated browser activity with a visible URL bar,
- support load, reload, back, forward, and stop,
- add a homepage and simple navigation flow,
- keep the app focused on PMBRS browser telemetry rather than as a generic app launcher,
- ensure page lifecycle events are captured in a consistent, testable way.

#### Deliverables

- user-visible browser UI,
- navigation lifecycle hooks,
- browser session state tracking,
- safe handling of blank, failed, and repeated page loads,
- a clean separation between browser behavior and PMBRS logging.

#### Acceptance criteria

- the user can open a page inside the app,
- page loading works reliably on-device,
- page lifecycle callbacks fire consistently,
- the app records a session start and finish without requiring another app to expose data,
- the app can be clearly described as a dedicated PMBRS browser shell rather than a generic browser.

### Phase 2 — Instrument browser page telemetry

#### Scope

- track page navigation start and finish,
- extract canonical domain and hostname,
- capture a lightweight page title,
- calculate dwell time per page or per domain,
- normalize category labels such as work, news, shopping, social, dev, video, or unknown,
- record only metadata needed for later analysis.

#### Required signals

- canonical URL or hostname,
- page title,
- start timestamp,
- end timestamp,
- dwell time in milliseconds,
- category label,
- local intent or subcategory label inferred from page metadata,
- input-field interaction context such as field type and whether the field was focused or submitted, without the typed value,
- browser session metadata,
- provenance and schema version.

#### Strong recommendation

- default to hostname-level and title-level logging,
- avoid full path and query capture by default,
- keep raw browsing metadata short-lived,
- generate daily or weekly summaries for analysis,
- deduplicate by canonical page identity and short session window.

#### Acceptance criteria

- every valid page visit results in a PMBRS artifact record,
- each record contains timestamp, domain, and dwell metadata,
- duplicate redirects and reload artifacts are filtered,
- the app can review raw page events locally,
- summaries can be generated without retaining full page traces forever.

### Phase 3 — Add a real PMBRS logging pipeline

#### Scope

- write browser page events into the same artifact database used by the rest of PMBRS,
- add queue state for unsynced browser events,
- support local-only storage before export or sync,
- keep browser data in the same provenance model as app usage and device state,
- create a visible browser section in the PMBRS dashboard and review screens.

#### Required work

- artifact schema versioning,
- event-type tags for browser pages,
- clean conversion from browser events to PMBRS artifacts,
- explicit retention and pruning logic,
- review UI for local browser metadata summary,
- clear local queue diagnostics so app state is trustworthy.

#### Acceptance criteria

- browser artifacts appear alongside other local PMBRS events,
- queued versus sent counts are visible in the app,
- the user can inspect historical browser metadata without opening raw database files,
- browser event writes are visible in the local queue before any sync attempt.

### Phase 4 — Add privacy and retention controls

#### Scope

- create a dedicated browser telemetry toggle,
- add review-and-delete functionality,
- implement retention windows for raw browser metadata,
- provide a domain summary mode and a raw log mode,
- build a fallback where browser events are excluded if the user turns logging off.

#### Default policy

- raw browser metadata: short retention, such as 7–14 days,
- domain summaries: longer retention,
- full raw URL logs: disabled unless explicit opt-in,
- all data remains local by default,
- a manual clear function must remove all retained browser artifacts and summaries.

#### Acceptance criteria

- the user can disable browser logging without affecting unrelated PMBRS features,
- the app can prune browser logs cleanly,
- the user can see why a page event was stored or discarded,
- the browser toggle has a visible state in the UI and is persisted across app restarts.

### Phase 5 — Add browser parity features needed for real use

#### Scope

- tabs or a simple multi-page experience,
- bookmarking or homepage support,
- history list,
- safe URL handling,
- basic domain blocking or filtering if desired,
- clear separation between browser functionality and PMBRS instrumentation.

#### Goal

Make the browser usable enough to test real user behavior without overpromising Adblock parity.

#### Acceptance criteria

- page loading and navigation feel stable,
- browser controls are usable without reducing telemetry quality,
- the minimal feature set is sufficient to test actual user behavior,
- the user understands that this is a telemetry-focused browser shell, not a full third-party browser replacement.

### Phase 6 — Evaluation against the browser-engine decision

#### Option A: stay on an instrumented WebView-based browser

Use this path when:

- the app already compiles and runs reliably,
- the logging model meets the personal-telemetry goals,
- the browser UI is sufficient for the user’s purposes,
- the goal is a narrow, local-only browser instrumented for telemetry rather than feature parity with a full browser.

#### Option B: move to a forked Chromium-based browser project

Use this path only when:

- the WebView path is insufficient for the required functionality,
- the user needs more realistic browser behavior,
- the telemetry needs deeper integration into browser internals,
- there is enough engineering time to maintain and document a full forked browser build.

#### Decision rule

Do not fork a full browser codebase before the WebView-based version is proven useful. Build the minimal instrumented browser first, validate the logging pipeline end-to-end, and only then decide whether a larger fork is worth the cost.

### Phase 7 — End-to-end validation on device

#### Scope

- test the browser on the physical Android device,
- verify page loads produce PMBRS artifacts,
- confirm local queue behavior,
- check sync fallback modes,
- verify the app still stores data locally when the network is unavailable,
- confirm browser event summaries are visible in the dashboard,
- test clear/delete flows and retention cleanup,
- validate that the browser shell behaves as expected under real navigation and reload patterns.

#### Acceptance criteria

- the browser logs page metadata on device,
- artifacts appear in the local PMBRS queue and summary screens,
- the user can inspect and prune them,
- the local-first sync path still works,
- realistic browser usage does not generate junk or duplicate events beyond the deduplication policy.

### Exit criteria for the browser milestone

The project is ready to treat the browser as a production-relevant component when all of the following are true:

- browser page events are emitted as first-class PMBRS artifacts,
- the browser is the source of page metadata rather than a reading of another app,
- raw page metadata remains local and short-lived,
- summary views are the primary analysis artifact,
- the user can review, clear, and control logging explicitly,
- the app behaves like a usable browser shell rather than a stub demo,
- the project documentation clearly states the scope boundary: this is an instrumented browser shell, not a full cloned Adblock Browser.

## Android-specific constraints to respect

1. App usage access is not a normal runtime permission.
   - `PACKAGE_USAGE_STATS` is typically granted by the user through system settings.
   - It can also be revoked by the user or the OS.
   - Collector logic must fail gracefully when access is not available.

2. Browser APIs differ widely by browser and Android version.
   - Do not assume a single cross-browser API.
   - Prefer domain-level summaries over rich browser logs.

3. Background collection is subject to OS limits.
   - Do not assume continuous collection of usage or location is always available.
   - Treat these as opportunistic and scheduled, not guaranteed.

4. Local-only is not the same as risk-free.
   - Even local personal data can be sensitive.
   - Retention and summarization are non-optional.

## Final recommendation

For a solo personal project, the right path is not “collect everything.” It is:

- baseline telemetry,
- app usage,
- domain-level browser telemetry,
- coarse location only after that,
- summary-first storage and local review,
- optional raw traces only when explicitly justified.

That sequence keeps the system useful, reviewable, and manageable while aligning with the user’s personal, local-only, opt-in goals.
