# Canonical Temporal Alignment — Specification

## Overview

PMBRS uses a globally aligned fixed **60-second window grid** as the canonical temporal reference system for all modalities. All sensor streams, sparse events, semantic artifacts, and derived representations are deterministically projected onto this shared timeline using modality-specific alignment rules.

This is **ADR-002 territory** — the specific boundary choice (epoch-aligned vs midnight-aligned) and timezone handling are decided there. This document defines the constraints that any ADR decision must satisfy.

## Core Properties

| Property | Constraint |
|---|---|
| Window duration | 60 seconds — fixed globally; not per-modality configurable |
| Alignment anchor | TBD via ADR-002: epoch-aligned (`UNIX_EPOCH + N*60s`) or midnight-local-day-aligned |
| Timezone policy | All canonical timestamps stored in UTC internally. Conversion to local timezone is a display-layer concern, not alignment-layer. |
| Clock drift handling | Wearables/mobile clocks may deviate from system clock by seconds/minutes. ADR-002 must resolve tolerance thresholds before flagging windows as misaligned. |

## Alignment Output Artifacts

| Artifact Type | Content | Relationship to Raw Data |
|---|---|---|
| `canonical_window` | Window ID, start/end UTC timestamps, modality coverage metadata | Structural backbone — does not contain behavioral data itself |
| `modality_alignment_mapping` | Maps each raw artifact ID to canonical window ID(s) it contributes to | Lineage trace: which windows reference which observations |
| `window_modality_coverage` | Per-window coverage descriptor — modalities present, signal quality per modality. | Used by downstream modules for missingness-aware processing |
| `missingness_mask` | Binary or multi-level mask per window × modality — explicitly marks gaps | Propagates to feature extraction (features marked as partially-observed) |

## Higher/Coarser Resolution Views

From Constitution §6: *"Higher-resolution, lower-resolution, event-driven, and multi-scale analyses are treated as derived views over the canonical timeline rather than independent temporal systems."*

A 5-minute aggregate is not a new primary alignment — it is a derived aggregation of exactly five consecutive canonical windows. The lineage DAG records this derivation explicitly.

## Window Coverage & Missingness (from Constitution §10)

- All canonical windows structurally exist regardless of modality completeness
- Windows carry explicit metadata describing:
  - Which modalities contributed (coverage bitmask)
  - Signal quality per contributing modality (confidence score)
  - Uncertainty flags — derived features from low-coverage windows are marked accordingly
- Dense observational modalities (wearable) primarily determine behavioral reliability
- Sparse semantic modalities act as contextual overlays — their absence does not invalidate the window

---

**Pending**: ADR-002 will specify boundary policy + timezone/clock handling.

> Constitution Reference: §6, §10, §11 (§§9), §14 (Window Coverage & Missingness)
