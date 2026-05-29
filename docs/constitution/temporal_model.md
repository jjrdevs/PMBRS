## Canonical Temporal System

PMBRS uses a globally aligned fixed 60-second window grid as the canonical temporal reference system.

All modalities are projected onto this shared temporal structure using modality-specific alignment rules.

## Temporal Alignment Principles

The canonical temporal system exists to preserve:

- cross-modality coherence,
- reproducibility,
- lineage consistency,
- stable artifact interoperability.

All downstream systems must reference canonical temporal windows.

## Derived Temporal Views

Higher-resolution,
lower-resolution,
event-driven,
and multi-scale analyses are treated as derived views over the canonical timeline rather than independent temporal systems.

Examples:

- transition-focused short windows,
- daily aggregates,
- event-triggered sequences,
- intervention-centered temporal slices.

These remain lineage-linked to canonical windows.

## Missingness Semantics

All windows exist structurally regardless of modality completeness.

Windows must contain explicit metadata describing:

- modality coverage,
- signal quality,
- uncertainty,
- missingness.

Window validity is treated as a confidence-bearing analytical property rather than binary existence.
