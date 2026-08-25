# PMBRS Documentation Index

## System Definition & Navigation

| Document | Description |
|----------|-------------|
| [README.md](../README.md) (repo root) | Project overview — what PMBRS is and isn't, core principles, quick links |
| [System Constitution](constitution.md) (🔒 Authority L1) | Full 17-principle system vision |
| [Glossary](glossary.md) | Shared terminology — artifact types, modalities, forbidden conflations |
| [ADR Template](adr/template.md) | Format for future Architecture Decision Records |

---

## Conceptual Foundation (🔒 Authority L0)

These documents express the system's core ideas and design motivations:

- [Purpose & Scope](conceptual-foundation/purpose_and_scope.md) — System boundary, user persona, non-goals
- [Authority Model](conceptual-foundation/authority_model.md) — Hierarchy from raw observation to interpretation
- [Artifact Philosophy](conceptual-foundation/artifact_philosophy.md) — Artifacts as first-class communication units
- [Temporal Model](conceptual-foundation/temporal_model.md) — Canonical 60-second window architecture
- [Modality Philosophy](conceptual-foundation/modality_philosophy.md) — Epistemological categorization (observational vs subjective vs inferred)  
- [Experimentation Philosophy](conceptual-foundation/experimentation_philosophy.md) — Self-experimentation principles, association over causation
- [Interpretability Rules](conceptual-foundation/interpretability_rules.md) — Traceability requirements for conclusions
- [Privacy Philosophy](conceptual-foundation/privacy_philosophy.md) — Local-first data architecture

---

## Phase-Specific Specifications (🔒 Authority L3)

- [Stage 1 Specification](phase-specs/stage_1.md) — Authorized context set, scope boundaries, acceptance criteria for initial release

---

## Module & Architecture Docs

### System-Level Contracts
- [Module Boundary Contracts](module-contracts.md) — Single-process modular architecture (Option C), module interface protocol, execution sequence  
- [System Invariants](invariants/system_invariants.md) — Artifact integrity, lineage validity, semantic separation guarantees

### Ingestion Subsystem
- [Overview](ingestion/overview.md) — Modality catalog, adapter contract definition, sync patterns
  - [Wearable Adapter](ingestion/adapters/wearable.md) — Garmin/Ouraring/Circular devices  
  - [Browser Telemetry Adapter](ingestion/adapters/browser.md) — Chrome/Firefox extension vs mobile approach
  - [Calendar Sync Adapter](ingestion/adapters/calendar.md) — Google Calendar, Apple calendar sync
  - [Mobile Collection Client](ingestion/adapters/mobile-collection.md) — Android architecture, local storage, sync pattern
  - **BoOX Note → Journal** [ADR-019](adr/ADR-019.md) — [Stage-0 recon](boox/recon-notes.md) (device + A/B OCR evidence) · [Stage-1 spec](boox/stage1-spec.md) (producer, OCR engine slot → local `qwen3.8:27b`, `journal` ingest) · [Stage-2 notes](boox/stage2-notes.md) (nightly entry, seeder, local ingest, scheduling wiring) · PC-side LLM-vision OCR over rendered page PNGs, ADB transport, idempotent manifest

### Temporal Alignment System (Constitution §6, §10)
- [Canonical Window Specification](temporal/specification.md) — Fixed 60s grid, boundary policy requirements, timezone/clock handling, missingness semantics

### Artifact Architecture & Governance (Constitution §11–§12, §17)
- [Specification](artifacts/specification.md): Artifact types, identity model, lineage DAG structure, immutability rules  
- [Governance Policy](artifacts/governance.md): Schema versioning layers, backward compatibility guarantees, regeneration-over-rewrite migration paths

### Feature Extraction Pipeline (Constitution §5, §9)
- [Specification](features/specification.md): Windowing strategy + feature definition per modality, rolling aggregation rules, missing-data handling policy

### Representation Learning Subsystem  
- [Model Selection Survey](representation/model-selection.md): Contrastive-time-series vs VAE/FactorVAE vs cross-modal CLIP-style embeddings. Awaiting decision in **ADR-011**.
- [Training Pipeline](representation/training-pipeline.md): Batch-first training loop: prepare → instantiate → train → evaluate quality checkpoint + rollback. ADR-**012** pending

### Experimentation System (Constitution §3)
- [Specification](experimentation/specification.md): Formal experiment definition schema, temporal scoping/overlap semantics, explicit vs inferred intervention handling

### Evaluation & Quality Monitoring Suite (§14–§15)
- [Integrity Checks](evaluation/integrity-checks.md): Nightly system checks — ingestion reliability, lineage DAG consistency, corruption detection/alerting  
- [Representation Quality Metrics](evaluation/representation-quality.md): Proxy evaluation — temporal coherence, clustering stability, modality ablation. **ADR-015** pending formalization

### Storage & Persistence Layer (ADR-010 closed; layout per ADR-017 D2)
- [Architecture Overview](storage/architecture.md): Raw JSON-per-file under `~/.pmbrs-private/store/raw/`; derived layers target JSONL + SQLite (`events.db`) once `StorageAdapter` ships. Encryption TBD (**ADR-016**)

### Privacy & Security (§16)  
- [Data Minimization Policy](privacy-security/data-minimization.md): Excluded modalities, included categories, sensitivity tier gating via `privacy_policy.yaml`
- [Lineage Invalidation Rules](privacy-security/lineage-invalidation.md): Authoritative observation deletion → derived artifact invalidation cascade

### Visualization & Desktop App (§15 replaceable subsystem)  
- [Architecture Overview](visualization/architecture.md): Electron + React, direct SQLite read-only access, dark-mode-first
  - [Timeline View Spec](visualization/desktop-app-specs/timeline-view.md): Primary temporal visualization — canonical window progression, behavioral embeddings, regime transitions
  - [Experiment Comparison View](visualization/desktop-app-specs/experiment-comparison.md): Side-by-side cohort diff: baseline vs intervention with temporally-matched comparison

### Pipeline & Compute Orchestration (§5 batch-first)  
- [Pipeline Orchestration Layout](orchestration/pipeline-orchestration.md): Sequential module execution, failure isolation + checkpointing. **ADR-004** pending
- [Task Scheduling Cycles](orchestration/task-scheduling.md): Near-realtime sync vs nightly full batch vs weekly retrain triggers
- [Execution Environment Setup](orchestration/environment.md): Python 3.12+, `uv` dependency manager, isolated venvs per subsystem

---

## Documentation Architecture: Directory Map

```
docs/
├── constitution.md                  # 🔒 L0 authority — system vision
├── glossary.md                      # Shared terminology
├── index.md                         # You are here
│
├── conceptual-foundation/           # 🔒 L0 — core ideas (8 files)
├── phase-specs/                     # 🔒 L3 — stage-bound specs
│
├── artifacts/                       # Type system + governance
├── contracts/                       # Formal schema contracts
│   └── provenance/                  # Provenance sub-hierarchy (5 specialized)
├── evaluation/                      # Quality metrics + checks  
├── experimentation/                 # Experiment definitions & schemas
├── features/                        # Feature extraction specs
├── ingestion/                       # Adapter specs (4 adapters)
├── boox/                            # BoOX Note→Journal: recon + Stage-1 spec (ADR-019)
├── invariants/                      # System integrity guarantees  
├── orchestration/                   # Pipeline scheduling, env config
├── privacy-security/                # Data minimization + lineage invalidation
├── representation/                  # Model selection + training pipeline
├── storage/                         # SQLite + filesystem architecture
├── temporal/                        # Canonical window spec
└── visualization/                   # Desktop UI specs (2 app-level)
    └── desktop-app-specs/           
```

## Status Legend (Constitution §17)

| Symbol | Meaning                                                                                                          | 
|--------|------------------------------------------------------------------------------------------------------------------|  
| 🔒     | Constitutional core — stable, principle-derived authority. Changes are rare and require cross-system review      |
| 📋     | Draft specification — open for iterative refinement within approved scope                                        |  
| ⏳     | Pending formal decision (ADR required before implementation)                                                     |
