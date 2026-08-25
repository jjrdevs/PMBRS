Subject: Request for privacy review — PMBRS mobile collector

Hi Privacy Team,

Please review the attached privacy sign-off package for the PMBRS mobile collector. The package includes:

- `mobile/HANDOFF.md` — implementation details and relevant files
- `mobile/OBSERVABILITY.md` — observability and telemetry details
- `docs/privacy/mobile-privacy-signoff.md` — checklist and proposed mitigations
- sample telemetry export: `pmbrs_telemetry.xml` (if present)

Summary of changes for review:

- Background sync now requires HTTPS for production endpoints; HTTP allowed only for localhost/test harnesses.
- Optional auth token support added for staged sync validation (Authorization: Bearer <token>).
- Telemetry counters added (run counts, success/failure categories, `payload_bytes_sent`).
- Retention configurable via settings (default 7 days). Data deletion is performed by the collector.

Requested review items:

1. Confirm the persisted artifact fields and retention duration are acceptable.
2. Confirm the telemetry counters collected are within our privacy constraints.
3. Approve the proposed sign-off or provide required mitigations and owners.

Please reply with Approve / Approve with mitigations / Deny and any mitigation actions.

Thanks,
Mobile Engineering
# Draft Email to Privacy Reviewers

Subject: Request: Privacy review for PMBRS mobile collector (retention, telemetry, transport)

Hi Privacy Team,

We're requesting a short privacy review for the PMBRS mobile collector feature. Summary and artifacts are attached below. The goal is to confirm the data minimization, retention, and transport guarantees before wider QA or release.

Key facts
- Retention default: 7 days (`SyncSettings.retentionDays`)
- Persisted artifact fields: `artifactId`, `source`, `payload`, `createdAtEpochMs`, `schemaVersion`, `deviceAlias`, `provenanceMetadataJson`, `synced`
- Telemetry: aggregate counters only (`pmbrs_telemetry`), includes `payload_bytes_sent` aggregated; no raw payloads stored in telemetry
- Transport: TLS enforced for non-local endpoints; optional auth token stored in SharedPreferences for debug builds (recommend EncryptedSharedPreferences in production)

Attachments
- `mobile/HANDOFF.md`
- `docs/ingestion/adapters/mobile-collection-implementation-plan-next-steps.md`
- `mobile/OBSERVABILITY.md`
- `docs/privacy/mobile-privacy-signoff.md` (checklist)
- sample telemetry export: `pmbrs_telemetry.xml`

Requested action
- Please review `docs/privacy/mobile-privacy-signoff.md` and record one of: Approve / Approve with mitigations / Deny.
- If mitigations required, please list required changes, owner, and timeline.

Suggested reviewers: @product-privacy, @legal-privacy

Thanks,
Mobile engineering
