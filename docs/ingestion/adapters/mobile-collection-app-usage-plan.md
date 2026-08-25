# App Usage Telemetry Implementation Plan

## Source of truth status

This is the active milestone plan for the next implementation step.

- The broader product strategy lives in `mobile-collection-personal-roadmap.md`.
- This file is the working plan for the current task: app usage telemetry.
- When in doubt, defer to the roadmap for design decisions and to this file for implementation steps.

## Goal

Add the first rich signal for the personal telemetry project: app usage telemetry.

This is the next milestone in the personal roadmap and should answer:

- how much time is spent in each app,
- which apps are used most often,
- when app usage occurs across the day,
- whether there are daily or weekly behavioral patterns,
- whether app usage correlates with battery, network, or screen-state patterns.

## Why this is the next step

App usage is the most immediately valuable signal for a personal project because it is:

- highly informative for daily self-analysis,
- less invasive than browser history or location,
- available through Android usage access APIs,
- easy to aggregate into daily and weekly summaries,
- a natural first expansion beyond the baseline device-state telemetry.

## Design principles

This plan follows the personal roadmap:

- local-only by default,
- opt-in by signal,
- summary-first storage,
- fail-closed behavior,
- short raw-retention windows,
- no fabricated data.

## Scope

### Included in v1

- app package name,
- app label,
- foreground session start,
- foreground session end,
- session duration,
- daily totals by app,
- time-of-day bucket,
- optional app category label.

### Excluded from v1

- browsing history,
- raw URL logs,
- page content,
- precise location traces,
- cloud storage,
- cross-user analytics.

## Data model

### Raw app usage record

Each app session should be stored as a structured local artifact with:

- artifactType: "observational.app_usage.session"
- appPackage: string
- appLabel: string | null
- sessionStartMs: long
- sessionEndMs: long
- durationMs: long
- sourceDeviceId: string
- timestamp: long
- schemaVersion: string

### Daily app summary record

Derived summary rows should include:

- date: YYYY-MM-DD
- appPackage: string
- appLabel: string | null
- totalForegroundMs: long
- sessionCount: int
- firstSeenMs: long
- lastSeenMs: long

This summary layer becomes the main analytical artifact. Raw session rows are temporary.

## Android-specific requirements

### Permission gate

Use the Android usage access model via `PACKAGE_USAGE_STATS`.

Important constraints:

- this is not a normal runtime permission,
- it is typically granted through system settings,
- it can be revoked by the user or by the OS,
- it is not guaranteed to exist on every device or OEM configuration.

If usage access is unavailable:

- do not fabricate records,
- do not silently skip without logging,
- surface a clear local status like: “App usage unavailable: usage access not granted.”

### Background assumptions

This collector should be treated as opportunistic rather than guaranteed continuous observation.

- OS battery optimization can reduce background collection granularity,
- system restrictions can limit reporting windows,
- session boundaries may be approximate depending on OS behavior.

## Collector design

Create a new collector next to the existing low-risk collectors:

- `AppUsageCollector.kt`
- logically grouped under the collectors package with `CollectorService` integration

### Responsibilities

1. Check if usage access is available.
2. Query usage stats for a bounded time window.
3. Normalize usage entries into session records.
4. Persist raw session data in the local artifact store.
5. Generate daily summaries.
6. Prune old raw logs based on retention policy.

### Minimal pattern

Follow the current style used by:

- `ScreenStateCollector`
- `DeviceStateCollector`
- `CollectorService`
- `PermissionHelper`

They should all return `Result<T>` and fail closed on permission issues.

## Integration plan

### 1. Add feature toggle

Add a setting in the existing settings model:

- `appUsageTelemetryEnabled: Boolean`

This toggle should be independent from the baseline device-state telemetry and from future browser/location signals.

### 2. Add collector to `CollectorService`

Update `CollectorService.collectAll()` to include the new collector only when the feature is enabled.

Required behavior:

- if disabled, skip it silently,
- if permission is not granted, fail cleanly without fake data,
- if querying fails, log the exception and continue.

### 3. Add local storage path

Use the existing local artifact database and structure to persist app usage session artifacts.

Each record should include:

- artifact ID,
- source,
- payload,
- created time,
- schema version,
- provenance metadata,
- synced flag.

### 4. Add summary generation

After raw app usage records are collected, create daily summary rows keyed by:

- date,
- package name,
- app label,
- total foreground duration,
- session count.

This becomes the primary artifact for analysis and the basis for charts, tables, and local dashboards.

## Retention and cleanup

### Raw data retention

- raw app session records: 14–30 days

### Summary retention

- daily app summaries: 6–12 months

### Automatic cleanup

Add a cleanup pass that:

- removes raw session records older than the raw-retention window,
- keeps the daily summary table for longer,
- logs how much was removed,
- does not delete summary data unless the user explicitly requests a full reset.

## User-facing controls

The app should expose:

- App usage telemetry: on/off
- App usage permission status
- Clear app usage logs
- Clear all local telemetry
- Current retention window

This is important so the user is always aware of what is being collected and can remove it locally without friction.

## Acceptance criteria

The feature is complete when all of the following are true:

- app usage collection is opt-in,
- the app checks `PACKAGE_USAGE_STATS` before trying to read usage data,
- missing permission is handled gracefully,
- raw app usage session records are stored locally,
- daily summaries are generated from the raw records,
- raw logs are pruned after the configured retention window,
- the user can clear local telemetry,
- the app never fabricates usage data,
- the system remains local-only by default.

## Review checklist

Before moving to the next signal, confirm:

- app usage is giving useful daily insight,
- storage growth is controlled,
- the raw logs are not drifting into long-lived storage,
- permission failures are visible and understandable,
- summary generation is easier to analyze than raw logs,
- the feature remains useful without adding broader, riskier collectors.

## Recommended order after this milestone

1. baseline device telemetry remains stable,
2. app usage is validated and useful,
3. browser/domain telemetry,
4. coarse location telemetry,
5. derived summaries and local dashboards,
6. optional raw traces only if the user explicitly decides they are needed.

This is the correct next step under the personal roadmap.
