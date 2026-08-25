# Mobile Collector — Privacy Review & Sign-off


Purpose: provide a concise reviewer checklist for privacy/legal to confirm the mobile collector's data practices and retention.

Reviewer: ____________________   Date: ___________

Checklist
- **Persisted fields**: confirm that only the following artifact fields are stored and retained as documented: `artifactId`, `source`, `payload` (JSON), `createdAtEpochMs`, `schemaVersion`, `deviceAlias`, `provenanceMetadataJson`, `synced` flag. Note any exceptions below.

- **Retention**: configured default is 7 days (`SyncSettings.retentionDays` defaults to 7). If product elects to expose retention via UI, confirm acceptable options (e.g., 1 / 7 / 30 days).

- **Access & export**: artifacts and telemetry may be exported via debug tooling or `adb run-as` for debug builds. Production builds should not expose direct export endpoints. Confirm whether additional access controls are required.

- **Minimization**: payloads may include structured event data. Confirm payload schema excludes PII by default; list any fields that may contain identifiers and recommend redaction/hashing if needed.

- **Encryption in transit**: client enforces HTTPS for non-local endpoints; HTTP is allowed only for loopback/test harnesses (e.g., `10.0.2.2`). For production, confirm staging certs and TLS tests are acceptable.

- **Auth & creds**: the optional auth token is persisted to `SyncSettings` (SharedPreferences). Recommend using Android EncryptedSharedPreferences or keystore protection for production tokens.

- **Telemetry**: counters persisted to `pmbrs_telemetry` are aggregate counts and `payload_bytes_sent` (aggregated). They do not store raw payloads.

- **Retention & deletion**: `collectorService.cleanupOldArtifacts()` deletes artifacts older than the configured retention window; changes applied via UI take effect immediately.

- **Reviewer decision**: Approve / Approve with mitigations / Deny

Mitigations (if any):

- Owner & timeline:

Sign-off

Signature: ____________________  Role: ____________  Date: __________
