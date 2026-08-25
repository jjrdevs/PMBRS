# Privacy Sign-off Package — Mobile Collector

This package is intended for privacy reviewers and includes a short summary, links to docs, and suggested artifacts to attach.

Summary
- Feature: PMBRS mobile collector — local artifact persistence, scheduled/manual sync to a hub, retention pruning, debug telemetry.
- Key privacy controls: retention default 7 days, TLS required for non-local endpoints, optional auth token stored in prefs (recommend encrypted storage), telemetry aggregates only.

Attachments to include
- `mobile/HANDOFF.md`
- `docs/ingestion/adapters/mobile-collection-implementation-plan-next-steps.md`
- `mobile/OBSERVABILITY.md`
- `docs/privacy/mobile-privacy-signoff.md` (reviewer checklist)
- Example telemetry export: `pmbrs_telemetry.xml` (generated from a debug device)

Suggested message to privacy reviewers

Subject: Request: Privacy review for PMBRS mobile collector

Hi Privacy Team,

We're requesting a short review of the PMBRS mobile collector. Summary and artifacts are attached. Key points:
- Retention default: 7 days (configurable in debug builds/UI if product approves).
- Collected artifact fields: `artifactId`, `source`, `payload`, `createdAtEpochMs`, `schemaVersion`, `deviceAlias`, `provenanceMetadataJson`, `synced`.
- Telemetry: aggregate counters only; no raw payloads persisted in telemetry.
- Transport: TLS required for non-local endpoints.

Please use `docs/privacy/mobile-privacy-signoff.md` to record approval or required mitigations.

Thanks,
Mobile Eng
