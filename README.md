# PMBRS — Personal Behavioral Measurement, Representation & Experimentation Platform

A local-first platform for structured self-experimentation and evidence-informed personal interpretation of multimodal longitudinal behavioral data.

## Quick Links

| Document | Description |
|----------|-------------|
| [docs/constitution.md](docs/constitution.md) | Full system constitution (17 principles) |
| [docs/index.md](docs/index.md) | Documentation index and roadmap |
| [docs/adr/](docs/adr/) | Architecture Decision Records |

## What This Is

A personal behavioral measurement, experimentation, and representation learning platform designed to discover reproducible statistical associations between behaviors, interventions, contexts, and outcomes. Focused on self-experimentation rather than diagnosis or automated prescription.

## What This Is Not

- Clinical diagnostic tool
- Deterministic mental-state inference system
- Productivity scorecard
- Autonomous behavioral optimizer
- Closed-loop control system

## Core Principles

1. **Artifact-oriented** — immutability, lineage, schema versioning
2. **Canonical 60-second temporal alignment** across all modalities
3. **Multi-layer authority model** — observational > canonical > derived > interpretive
4. **Batch-analysis-first**, not real-time-first
5. **Local-first privacy** architecture
6. **Scientific humility** — association, not causation

## Project Structure

```
pmbrs/
├── README.md                 # This file
├── docs/
│   ├── constitution.md       # 17-principle system constitution
│   ├── index.md              # Documentation index
│   └── adr/                  # Architecture Decision Records
│       └── templates         # ADR template, future decisions
├── config/                   # Configuration files
└── scripts/                  # Utility and orchestration scripts
```
