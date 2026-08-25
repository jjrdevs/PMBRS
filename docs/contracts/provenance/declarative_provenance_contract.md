# Declarative Provenance Contract

## Purpose

Describes provenance semantics for user-authored or manually-declared artifacts such as experiments, journal entries, annotations, and manual corrections.

## Extends

`provenance_base_contract.md`

## Required Fields

```yaml
provenance_type: declarative
provenance_version: string
provenance_timestamp: timestamp  # when declaration was recorded
provenance_agent: string  # user id or local_profile_id
declaration_method: enum(manual_user_declaration, import, copy)
author_display_name: string
```

## Optional Fields

- `source_url` — when imported from external content.
- `author_contact` — optional contact or identifier.

## Notes

This contract intentionally omits sensor-specific fields. Validators must apply declarative provenance when `provenance_type` is `declarative`.
