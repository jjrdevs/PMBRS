# Mobile Collection Implementation Backlog

## Goal

Deliver a first viable Android phone-client implementation that turns the device into a privacy-preserving observational ingestion source for PMBRS.

## Delivery Strategy

The implementation should proceed in small, testable milestones. The goal of the first release is not breadth; it is reliability, privacy safety, and a clean handoff to the PMBRS ingestion pipeline.

## Milestone 0 — Alignment and Governance

### Tasks
- Confirm the initial modality set for the phone client.
- Decide which signals are enabled by default versus opt-in-only.
- Define the local privacy policy and retention behavior.
- Draft the initial payload contract for observational artifacts.
- Define the sync trigger policy: manual, trusted network, or both.

### Acceptance criteria
- A short scope document exists for the phone client.
- The initial signal list is explicit and bounded.
- Privacy defaults are documented and consistent with PMBRS policy.
- The artifact shape expected by PMBRS ingestion is documented.

## Milestone 1 — Foundation

### Tasks
- Create the Android app skeleton.
- Add a settings screen for privacy and sync preferences.
- Create the local SQLite schema for pending artifacts and sync state.
- Implement basic app lifecycle and startup behavior.
- Add a minimal status screen showing current collector state.

### Acceptance criteria
- The app builds and runs on Android.
- The app can create and persist a locally buffered artifact.
- The user can enable or disable collection from a settings screen.
- The app exposes a visible status and sync state.

## Milestone 2 — Core Collection

### Tasks
- Implement a screen-state collector.
- Implement a battery/device-state collector.
- Add artifact normalization from raw events to PMBRS-compatible payloads.
- Add timestamping, device metadata, and provenance fields.
- Add local deduplication for repeated events.

### Acceptance criteria
- At least two collectors emit structured observational artifacts.
- Each artifact includes stable provenance metadata.
- Duplicate events do not create duplicate queued artifacts.
- A stored artifact can be inspected locally without requiring sync.

## Milestone 3 — Sync and Reliability

### Tasks
- Implement queued sync with retry and exponential backoff.
- Add TLS-based transport and authentication handling.
- Add duplicate rejection handling for the PMBRS hub.
- Add a trusted-network or manual-trigger sync policy.
- Add error logging for transport and validation failures.

### Acceptance criteria
- A queued artifact can be successfully transmitted to the PMBRS hub.
- Sync failures are retried without data loss.
- The app can operate offline and resume once connectivity returns.
- Failure modes are visible and diagnosable.

## Milestone 4 — Hardening and Evaluation

### Tasks
- Reduce battery impact and background churn.
- Add observability for collector health and sync performance.
- Add retention and cleanup rules for old queued artifacts.
- Validate privacy defaults under real-world usage conditions.
- Review whether additional modalities should be added in a later phase.

### Acceptance criteria
- Collector behavior remains stable over extended use.
- Sync and storage failures are logged and understandable.
- Privacy and retention behavior is documented and reviewable.
- The implementation can be handed off for wider evaluation.

## Recommended First Slice

The best first slice is narrow and realistic:
- one screen-state collector,
- one battery/device-state collector,
- local buffering,
- one sync path,
- one simple settings screen.

This keeps the work focused on the PMBRS contract and avoids overbuilding before the ingestion interface is stabilized.

Current progress: the first-slice Android client now compiles, stores artifacts in SQLite, uses screen-state and device-state collectors, validates the sync endpoint URL, and schedules periodic sync through `PMBRSSyncWorker`. Next work includes WorkManager sync policy observability, background diagnostics, and documentation closure.
