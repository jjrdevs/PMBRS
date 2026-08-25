# Bromite → PMBRS Ingest Contract

Purpose
-------
This document defines a minimal, privacy-preserving ingest contract for Bromite (the browser) to emit browser telemetry artifacts that PMBRS can validate, store, and surface locally. The goal is hostname-level, summary-first metadata only — no full URLs, query strings, page text, or typed form values.

Design goals
------------
- Explicit boundary: Bromite is the producer; PMBRS is the consumer and validator.
- Minimal fields required for downstream analysis and provenance.
- Strong data minimization: block raw content and query strings by default.
- Versioned schema and forward-compatible validation.

Primary artifact: `browser_visit`
---------------------------------
Fields (required):

- `schema_version` (string) — version of this artifact schema, e.g. "1.0".
- `event_type` (string) — fixed value: `browser_visit`.
- `source_app` (string) — e.g. `bromite`.
- `app_id` (string) — Bromite package id or app identifier.
- `device_id` (string) — local device identifier (hashed or opaque) for provenance.
- `visit_id` (string) — unique id for this visit artifact (UUID recommended).
- `canonical_host` (string) — hostname or registrable domain (example: `example.com`). No path/query.
- `page_title` (string|null) — optional, only if non-sensitive and short.
- `visit_start_ms` (integer) — epoch ms.
- `visit_end_ms` (integer) — epoch ms.
- `dwell_ms` (integer) — derived or redundant, in ms.
- `category` (string) — suggested taxonomy: `work|news|shopping|social|dev|video|unknown`.
- `input_context` (object) — lightweight form interaction summary; schema below.
- `provenance` (object) — collection metadata (see below).
- `raw_content_blocked` (boolean) — must be `true` unless the user explicitly opted-in otherwise.

Input context schema (lightweight):

- `input_context.type` (string|null) — `text|email|search|password|unknown|null`.
- `input_context.focused` (boolean) — whether a field was focused during visit.
- `input_context.submitted` (boolean) — whether a submit action appears to have occurred.

Provenance (required object):

- `provenance.collected_by` (string) — `bromite`.
- `provenance.collection_version` (string) — bromite build or telemetry collector version.
- `provenance.collection_mode` (string) — `opt-in|default-off|debug`.
- `provenance.recorded_at_ms` (integer) — epoch ms when PMBRS receives the artifact.

JSON Schema (concise)
---------------------
Below is a compact formalization suitable for PMBRS validation (simplified):

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["schema_version","event_type","source_app","visit_id","canonical_host","visit_start_ms","visit_end_ms","dwell_ms","provenance","raw_content_blocked"],
  "properties": {
    "schema_version": {"type":"string"},
    "event_type": {"type":"string","const":"browser_visit"},
    "source_app": {"type":"string"},
    "app_id": {"type":"string"},
    "device_id": {"type":"string"},
    "visit_id": {"type":"string"},
    "canonical_host": {"type":"string"},
    "page_title": {"type":["string","null"]},
    "visit_start_ms": {"type":"integer"},
    "visit_end_ms": {"type":"integer"},
    "dwell_ms": {"type":"integer"},
    "category": {"type":"string"},
    "input_context": {
      "type":"object",
      "properties": {
        "type": {"type":["string","null"]},
        "focused": {"type":"boolean"},
        "submitted": {"type":"boolean"}
      }
    },
    "provenance": {"type":"object"},
    "raw_content_blocked": {"type":"boolean"}
  }
}
```

Example artifact
----------------

```json
{
  "schema_version": "1.0",
  "event_type": "browser_visit",
  "source_app": "bromite",
  "app_id": "org.bromite.browser",
  "device_id": "device-opaque-hash",
  "visit_id": "7f3d9a8c-...",
  "canonical_host": "example.com",
  "page_title": "Example — News",
  "visit_start_ms": 1692364800000,
  "visit_end_ms": 1692364865000,
  "dwell_ms": 65000,
  "category": "news",
  "input_context": {"type":"search","focused":true,"submitted":false},
  "provenance": {"collected_by":"bromite","collection_version":"0.1.0","collection_mode":"opt-in","recorded_at_ms":1692364870000},
  "raw_content_blocked": true
}
```

Transfer & handoff methods (pick one or support multiple)
-------------------------------------------------------

- Local file export: Bromite writes artifacts to an app-private JSONL file in a shared directory that PMBRS can import. Files must be signed or include provenance metadata.
- Local HTTP endpoint: PMBRS exposes a local loopback HTTP ingest endpoint (`http://127.0.0.1:PORT/ingest`) that Bromite can POST validated artifacts to. Authenticate by shared secret in app settings.
- Explicit user import: Bromite writes an export bundle and the user explicitly imports it into PMBRS via the UI (safe, user-driven).

Validation rules (on PMBRS ingest)
---------------------------------

1. Verify top-level `schema_version` is supported. If newer, reject or store as `rejected_schema` with reason.
2. Ensure `event_type == browser_visit`.
3. Ensure `raw_content_blocked === true` unless the user has explicit opt-in; any artifact with false should be flagged.
4. Validate required fields and types with the JSON Schema above.
5. Verify `visit_end_ms >= visit_start_ms` and `dwell_ms` roughly equals the difference (tolerance allowed).
6. Check `canonical_host` is a registrable domain; reject protocol-only values (e.g., `about:blank`).
7. Ensure `provenance.collected_by` is `bromite` and `collection_mode` matches local settings.

Retention and privacy
---------------------

- Default raw retention: 7–14 days (configurable in PMBRS settings).
- Summaries (daily/weekly per domain) stored longer (6–12 months).
- Provide per-artifact delete and bulk-clear UI in PMBRS.
- Enforce encryption-at-rest in PMBRS if available.

Versioning and backward compatibility
------------------------------------

- Include `schema_version` on every artifact.
- PMBRS should never assume unknown fields are sensitive; unknown fields may be ignored or logged for review.
- For schema upgrades, Bromite must provide a migration note in the provenance or separate release notes.

Acceptance tests (basic)
-----------------------

1. Bromite emits a valid `browser_visit` artifact and writes it to the agreed transfer method.
2. PMBRS ingests the artifact, validates schema, and stores it in the browser artifacts table.
3. A sample UI view shows visit timestamp, domain, dwell time, and category without exposing raw URL or page content.

Next steps
----------
- Decide preferred transfer method (file export, local HTTP, or explicit import).
- If you want, I can add a machine-readable JSON Schema file and a small PMBRS adapter skeleton to perform the validation and ingest.

Document history
----------------
- v1.0 — initial contract (authors: PMBRS / Bromite integration)
