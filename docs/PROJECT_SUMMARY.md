# PMBRS Project Summary

## Overview
PMBRS (Personal Model of Behavioral Regulation System) is a personal behavioral analytics framework that captures, analyzes, and visualizes multi-modal behavioral data to support deep work optimization. It follows 17 constitutional principles with a focus on:

- **Modular Architecture**: Single-process modular design where ingestion → alignment → feature extraction → representation learning → evaluation pipelines
- **Batch-First Approach**: Not real-time streaming - designed for offline analysis of historical behavior patterns  
- **Artifact-Centric Governance**: All data is treated as immutable artifacts with lineage tracking, provenance metadata, and explicit versioning
- **Replaceable Subsystems**: Visualization layer (desktop app) is intentionally separate from core architectural components per Constitution §15

## Key Components

### Core Architecture Layers

1. **Ingestion Layer**:
   - Multiple modality adapters (wearables, browser telemetry, calendar sync, mobile collection client)
   - Error handling strategies with deduplication and retry logic
   - Privacy-aware data minimization policies

2. **Temporal Alignment System**:  
   - Canonical windows defined by fixed 60s grid boundary policy 
   - Timezone alignment and clock synchronization rules
   - Missingness indicator semantics

3. **Feature Extraction Pipeline**:
   - Per-modality feature definitions with rolling aggregations
   - Handling for partial data coverage and missing-windows scenarios  

4. **Representation Learning Subsystem**:
   - Unsupervised learning approaches (contrastive, VAE, CLIP-style)
   - Batch-first training cycles with quality evaluation checkpoints
   - Robustness testing including modality ablation sensitivity

5. **Experimentation Framework**:
   - Formal experiment definition schema  
   - Context-aware comparison methodology (baseline-normalized, regime-conditioned)
   - Statistical output includes effect sizes with confidence intervals only

6. **Evaluation & Quality Monitoring Suite**:
   - Nightly integrity checks
   - Representation quality proxy metrics 
   - Longitudinal drift detection capabilities

### Operational Components  

1. **Pipeline Orchestration**:
   - Single-process modular execution sequences orchestrated by YAML/config 
   - Failure isolation with checkpointing and rollback safeguards  
   - Scheduling cycles (real-time mobile sync vs nightly batch runs)

2. **Execution Environment**:
   - Python 3.12+ runtime + uv dependency management
   - SQLite + JSON artifact storage backend
   - Optional isolated environments for heavy subsystems

3. **Visualization Layer**: 
   - Electron/React desktop application
   - Timeline view showing behavioral embeddings across canonical windows  
   - Experiment comparison views with context-aware cohort analysis

## Constitutional Principles (17-point vision)
1. Core vision of system scope and constraints
2. Artifact architecture design specifications  
3. Temporal model alignment principles
4. Privacy-first data minimization policies
5. Batch execution philosophy ("not real-time streaming")
6. Evaluation operationalization (proxy metrics due to lack of supervised ground truth)
7. Reproducibility requirements (lineage provenance, lock files) 
8. Replaceable downstream consumers (visualization layer)  
9. Interpretability constraints (associational not causal conclusions only)
10. Data quality governance
11. Schema evolution and backward compatibility policies
12. System security model (encryption at rest options pending formal decision)
13. Modality adapter contract definitions
14. Storage architecture design choices

## Project Status  

### Completed Documentation 
- All required architectural component specifications written
- Master docs index built with full ADR roadmap and navigation  
- Module-level contracts defined for cross-cutting subsystem interfaces

### Pending Formal Records (ADR Requirements)
1. **ADR-001**: Storage Backend Choice - SQLite vs alternatives
2. **ADR-002**: Canonical Window Boundary Policy 
3. **ADR-003**: Artifact Identity Scheme Content Hash + UUID split point  
4. **ADR-004**: Pipeline Orchestration Mechanism / Single Process Modular Design  
5. **ADR-005**: Modality Adapter Contract Definitions
6. **ADR-006**: Batch Ingestion Pipeline Design 
7. **ADR-007**: Android Client Architecture & Local Sync Pattern
8. **ADR-008**: Sparse-to-Dense Alignment Rules per Modality  
9. **ADR-009**: Feature Extraction Windowing Strategy + Incremental Reprocessing
10. **ADR-010**: Storage Layout — ✅ **Closed 2026-08-19** (superseded into ADR-017 D2; canonical layout in `storage/architecture.md`, see `adr/ADR-010.md`) 
11. **ADR-011**: Embedding Model Selection (contrastive vs VAE vs CLIP-style)
12. **ADR-012**: Training Data Curation & Modality Ablation Strategy
13. **ADR-013**: Experiment Definition Schema + Temporal Scoping/Overlap Rules
14. **ADR-014**: Context-Aware Comparison Methodology 
15. **ADR-015**: Proxy Evaluation Metric Suite for Representation Quality  
16. **ADR-016**: Encryption at Rest Mechanism Selection (TBD)
17. **ADR-018**: Visualization Layer Architecture Choice (Electron confirmed)

## File Structure

Documents organize into subsystem directories with clear hierarchy:
- `/docs/`
  - `index.md` - Master navigation index 
  - `constitution.md` - Core system principles (252 lines, original intact)
  - `module-contracts.md` - Cross-cutting artifact I/O contracts
  - Subsystem folders: ingestion/, temporal/, artifacts/, features/, representation/, experimentation/, evaluation/, orchestration/, privacy-security/, storage/, visualization/
- `/README.md` - Project overview and principles

## Next Steps  

1. Begin drafting formal ADRs (starting with most critical ones)
2. Implement module contract interfaces as defined
3. Set up development environment with prescribed tooling  
4. Create sample artifact structures for testing
5. Begin adapter implementation work in ingestion layer

This repository provides complete documentation of the PMBRS system design, architecture decisions, and operational procedures to support its future development and maintenance.