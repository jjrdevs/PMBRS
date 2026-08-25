# Observational Provenance Contract

## Purpose

Provenance schema for sensor- and ingestion-derived artifacts. Extends `provenance_base_contract.md`.

## Extends

`provenance_base_contract.md`

## Applicability

These fields MUST be present when `provenance_type` is `observational`.

## Required Fields

```yaml
provenance_type: observational
provenance_version: string
provenance_timestamp: timestamp
provenance_agent: string
ingestion_source: string
ingestion_version: string
device_id: string
source_device: string
sensor_type: string
firmware_version: string
sampling_rate_hz: number
clock_source: string
ingestion_pipeline: string
observation_timestamp: timestamp
ingestion_timestamp: timestamp
timezone: string
```

## Optional Fields

- `collection_method`: string
- `source_url`: string
- `author_notes`: string

## Notes

- For artifacts that are not observational (e.g., declarative artifacts), validators MUST NOT require these fields.
- Implementations SHOULD preserve original observation timestamps and clock metadata.
- `collection_method` is an optional field for provenance objects where the ingestion path or capture technique is relevant.
