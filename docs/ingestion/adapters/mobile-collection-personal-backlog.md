# Personal Mobile Telemetry Backlog

## Purpose

This file is the full development backlog for the personal telemetry project. It is intentionally broader than the active milestone plan and should be used as the working queue of future work.

## Source-of-truth hierarchy

1. `mobile-collection-personal-roadmap.md` — strategy and direction
2. `mobile-collection-app-usage-plan.md` — current implementation milestone
3. `mobile-collection-personal-backlog.md` — all planned work across phases
4. `README.md` — index and navigation for the folder

## Core rule

- Roadmap answers "what are we trying to achieve?"
- The active milestone plan answers "what are we building next?"
- The backlog answers "what is left after this?"

## Backlog phases

## Phase 1 — Baseline telemetry hardening

### Goal

Keep the current low-risk system stable and well-structured.

### Tasks

- keep the baseline collectors active and stable,
- maintain schema versioning and provenance metadata,
- retain raw device-state logs for a short window,
- generate daily summaries for battery, connectivity, and screen-state trends,
- review local storage growth monthly,
- ensure fail-closed behavior on permission failure.

### Acceptance criteria

- baseline telemetry remains useful,
- daily summaries are generated,
- local retention is bounded,
- raw logs are short-lived and summarized.

## Phase 2 — App usage telemetry

### Goal

Add the first rich personal signal.

### Tasks

- add per-signal app usage toggle,
- gate on `PACKAGE_USAGE_STATS`,
- query usage stats for defined time windows,
- normalize usage events to session records,
- persist raw app session artifacts locally,
- generate daily app summaries,
- prune raw app logs after retention window,
- surface app usage permission status in UI,
- allow user to clear local app telemetry.

### Acceptance criteria

- app usage is opt-in,
- permission denial fails gracefully,
- local summaries exist for daily analysis,
- raw logs are temporary,
- feature remains local-only.

## Phase 3 — Browser/domain telemetry

### Goal

Understand browsing patterns without collecting raw content, while matching the user’s actual browser behavior: primarily Adblock Browser and occasionally Chrome.

### Tasks

- define browser/domain telemetry as a separate opt-in signal,
- restrict to browser package + hostname + page title metadata by default,
- avoid raw URLs, path capture, search strings, and page content,
- classify domains by category when useful (work, social, shopping, video, news, dev, unknown),
- keep raw browser metadata short-lived,
- generate daily browser summaries,
- review whether browser telemetry adds meaningful analysis value,
- keep the implementation conservative and local-only.

### Acceptance criteria

- no raw page content or full URL tracking by default,
- domain and title metadata are the main output,
- category tagging is lightweight and explainable,
- the user has a clear explanation of what is being collected,
- the feature remains summary-first and local-only.

## Phase 4 — Coarse location telemetry

### Goal

Track place patterns without storing a continuous high-precision movement trace.

### Tasks

- define a coarse location model with place clusters or geohashes,
- keep raw traces temporary and optional,
- use home/work/transit/other labels when useful,
- generate location dwell summaries by day,
- review whether exact coordinates are necessary,
- keep location behind an explicit user toggle.

### Acceptance criteria

- location uses coarse place clusters by default,
- exact raw traces are not default,
- time-at-place summaries are the main artifact,
- retention and cleanup are explicit.

## Phase 5 — Derived analytics and review layer

### Goal

Turn raw logs into high-value local insights.

### Tasks

- build daily totals and trend views,
- correlate app usage with battery and network state,
- correlate screen-state and app-state patterns,
- build weekly summary exports,
- produce local CSV/JSON exports for personal analysis,
- design a monthly review and cleanup loop.

### Acceptance criteria

- daily summaries and trend views are available,
- analysis is based on summaries and not raw logs alone,
- export format is easy to inspect and analyze locally,
- storage remains manageable.

## Phase 6 — Local data hygiene and pruning

### Goal

Keep the project reviewable over time.

### Tasks

- define retention windows for every signal,
- add automatic pruning for all raw logs,
- review storage volume monthly,
- create a clear user action to delete all telemetry,
- keep a release-safe local cleanup script or command path.

### Acceptance criteria

- data volume remains bounded,
- pruning is automatic and clear,
- the user can always clear local data.

## Phase 7 — Optional future experiments

### Goal

Only after the core project is stable.

### Candidate experiments

- stronger app categorization,
- browser category taxonomy,
- more granular time-of-day analysis,
- location clustering quality tuning,
- local dashboard or notebook integration.

### Rule

Only do these after the current milestone plan is stable and the roadmap remains intact.

## Suggested delivery order

1. baseline telemetry hardening
2. app usage telemetry
3. browser/domain telemetry
4. coarse location telemetry
5. summary analytics and local review
6. pruning and hygiene
7. optional future experiments

This is the full planned development queue for the personal mobile telemetry project.
