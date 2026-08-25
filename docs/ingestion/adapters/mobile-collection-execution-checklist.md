# Mobile Collection Execution Checklist

## Purpose

Use this checklist as the implementation guide for the first phone-device delivery slice.

## Pre-Implementation Checklist

- [ ] Confirm the initial modality list.
- [ ] Decide which signals are enabled by default.
- [ ] Document the privacy and retention policy.
- [ ] Confirm the sync trigger model.
- [ ] Define the expected artifact schema for the first release.

## Milestone 1 Checklist

- [x] Android project skeleton exists.
- [x] Settings screen is present.
- [x] SQLite database schema is defined.
- [x] The app can persist at least one artifact locally.
- [x] The app shows collector and sync status.

## Milestone 2 Checklist

- [x] Screen-state collector emits events.
- [x] Battery/device-state collector emits events.
- [x] Events are normalized into structured payloads.
- [x] Provenance metadata is attached.
- [x] Periodic background collection is scheduled at startup.
- [x] Duplicate events are filtered locally.

## Milestone 3 Checklist

- [x] Pending artifacts are transmitted to the PMBRS hub.
- [x] Sync retries after transient failures.
- [x] Duplicate artifact responses are handled safely.
- [x] Offline behavior does not corrupt the queue.
- [x] Sync failures are logged and visible.

## Milestone 4 Checklist

- [ ] Collector behavior is stable under normal use.
- [ ] Battery impact remains acceptable.
- [x] Retention cleanup rules are implemented.
- [ ] Privacy defaults are reviewed and documented.
 - [x] A short handoff note exists for the next iteration.

## Definition of Done for the First Slice

The first slice is complete when:
- the app can collect at least one low-risk signal,
- the artifact is stored locally,
- the artifact can be synced to the PMBRS hub,
- privacy defaults are explicit,
- and the implementation is documented for the next phase.
