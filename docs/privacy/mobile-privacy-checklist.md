# Mobile Collector Privacy Checklist

This checklist summarizes privacy considerations for the PMBRS mobile collector and provides a compact list of artifacts, retention, gating, and reviewer action items.

## Summary
- Purpose: Collect low-risk observational artifacts from mobile devices to support research and product telemetry. The first slice includes `ScreenStateCollector` and `DeviceStateCollector` artifacts.
- Data store: Local SQLite on device; periodic sync to PMBRS hub when network and policy gates allow.

## Persisted fields
- `artifactId` (opaque identifier)
- `source` (artifact type, e.g., `screen_state`)
- `payload` (JSON blob containing observation fields)
- `createdAtEpochMs` (timestamp)
- `schemaVersion` (artifact schema)
- `deviceAlias` (user-provided or device-provided alias)
- `provenanceMetadataJson` (opaque JSON for provenance; contains non-PII metadata)

## Retention and deletion
- Default retention: 7 days (configurable by product decision).
- Retention policy applied via scheduled cleanup task that deletes older records.

## Network and sync policy
- Default sync interval: 6 hours.
- `trustedNetworkOnly` gating: when enabled, sync runs only on unmetered networks (Wi‑Fi/Ethernet).
- `syncBaseUrl` requires HTTPS for public hosts. HTTP allowed only for `localhost` loopback for testing.
- Optional `authToken` may be stored and used for bearer authentication during sync. Token storage: `SharedPreferences` (app-private).

## Privacy risks & mitigations
- Risk: `payload` may embed PII depending on collector implementation.
  - Mitigation: audit `payload` schema; remove or anonymize any PII before persisting.
- Risk: `deviceAlias` may be user-identifying.
  - Mitigation: document usage and provide mechanism to opt out or reset alias.
- Risk: `provenanceMetadataJson` may unintentionally include identifiers.
  - Mitigation: define a strict schema for provenance metadata and validate before storage.

## Reviewer checklist
- [ ] Confirm `payload` schemas do not contain PII.
- [ ] Confirm `provenanceMetadataJson` schema and fields.
- [ ] Approve retention setting (7 days or alternative) or request UI exposure.
- [ ] Confirm TLS enforcement and token handling meet security policy.
- [ ] Confirm telemetry counters do not leak user identifiers and are stored locally.

## Reviewer approvals
- Privacy reviewer: ____________________  Date: _______
- Product owner: ______________________  Date: _______

***
Generated: 2026-08-08
