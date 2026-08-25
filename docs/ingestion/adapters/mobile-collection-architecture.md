# Mobile Collection Technical Architecture

## Purpose

This document outlines the technical structure for the Android phone client so that it can function as a replacement ingestion adapter for PMBRS.

## Architecture Overview

The client should be organized as a small, modular Android app with a clear separation between collection, storage, normalization, and sync.

### Core layers

1. UI layer
   - Settings and consent management
   - Collector status and sync status
   - Basic diagnostics for troubleshooting

2. Collector layer
   - Screen-state collector
   - Battery/device-state collector
   - Optional future collectors for motion or connectivity context

3. Normalization layer
   - Converts raw device events into PMBRS-compatible observational artifact payloads
   - Adds time, device identity, provenance, and schema metadata

4. Storage layer
   - Local SQLite database for buffered artifacts and sync state
   - Write-ahead persistence so events are not lost when the app is restarted

5. Sync layer
   - Queues artifacts for delivery
   - Retries on failure using backoff
   - Handles duplicate rejection and partial success safely

6. Privacy layer
   - Consent gating
   - Permission minimization
   - Trusted-network or manual sync policy
   - Retention and cleanup rules

## Suggested Component Layout

```text
app/
  ui/
  collectors/
  normalization/
  storage/
  sync/
  privacy/
  model/
```

## Data Flow

1. A collector observes an event on the phone.
2. The event is normalized into an observational artifact payload.
3. The payload is written to the local SQLite database.
4. The sync worker picks up pending artifacts.
5. The artifact is transmitted to the PMBRS hub over an encrypted channel.
6. The hub acknowledges or rejects the artifact, and the local state is updated accordingly.

## Recommended Technology Choices

| Concern | Recommendation | Reason |
|---|---|---|
| UI | Jetpack Compose | Native Android UI and low-friction iteration |
| Persistence | SQLite via SQLiteOpenHelper | Local-first storage and reliable offline buffering for the initial build |
| Networking | Retrofit or Ktor | Simple HTTP client support for encrypted sync |
| Background work | WorkManager | Battery-aware background execution |
| Serialization | Kotlinx Serialization or Moshi | Clean JSON payload handling |

## Artifact Model Expectations

Each emitted artifact should preserve the following ideas:
- timestamp
- device identity or alias
- provenance information
- event payload content
- schema version information
- explicit opt-in or consent context when applicable

## API and Sync Contract Expectations

The app should interact with the PMBRS hub through a narrow, explicit contract:
- POST a batch of artifacts to `/api/v1/artifacts/sync`
- receive an explicit `syncedIds` response list
- support idempotent retries using stable artifact IDs
- preserve provenance and avoid silently dropping events
- treat `syncedIds` as the single source of truth for marking artifacts synced

### Current mobile sync payload shape

The mobile client sends artifacts using this structure:

```json
{
  "artifacts": [
    {
      "artifactId": "<string>",
      "source": "screen_state",
      "payload": "{...}",
      "createdAtEpochMs": 1234567890,
      "schemaVersion": "1.0",
      "deviceAlias": "device-123",
      "provenanceMetadata": "{...}"
    }
  ]
}
```

Where `payload` and `provenanceMetadata` are both JSON-serialized strings.

### Expected response contract

The server should return a `SyncResponse` object with at least:

```json
{
  "syncedIds": ["artifact-1", "artifact-2"],
  "message": "Optional status or diagnostic text"
}
```

The mobile app marks an artifact as synced only when its `artifactId` appears in `syncedIds`.

## First Release Scope

The first release should focus on:
- one or two low-risk collectors,
- local buffering,
- one sync path with manual and scheduled delivery,
- simple error handling,
- explicit privacy defaults.

This keeps the implementation aligned with PMBRS expectations while avoiding unnecessary complexity.
