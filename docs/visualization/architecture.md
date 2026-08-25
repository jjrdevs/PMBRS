# Visualization Layer — Desktop App Architecture

## Purpose

Define the downstream consumer architecture for PMBRS as a **desktop application** per user preference. Per Constitution §15, visualization is an operational layer built on the governed artifact system — not part of the constitutional core itself and therefore replaceable or swappable if we need to change it later without touching ingestion, alignment, or representation pipelines underneath.

The visualization layer should support evidence-informed exploration and comparison without turning the system into a causal or prescriptive interface. It should present associations, uncertainty, and lineage clearly rather than imply deterministic truth.

## Platform & Technology Stack (Recommendation)

| Component               | Recommendation                                      Rationale                              ||
|------|---------|--------|    
Desktop Application Framework             Electron + React                         Cross-platform (Linux/Mac/Windows), rich ecosystem for data viz libs, good performance                       │                               UI library            TailwindCSS / shadcn/ui                        Modern component primitives; accessible by default                            |                Charting / Visualization Library    Three.js or Plotly/D3 via visx                  3D embedding space exploration + line/regime visualization needs                                      : 
Local Data Access                          Direct SQLite read-only queries (+ filesystem artifact reads)     No separate API server — app connects straight to user's data store locally                                  ||   
Styling                                    Dark-mode-first theme                       Aligns with deep-work aesthetic; reduces eye strain during long analysis sessions                 |

## Architecture Overview (Desktop + PMBRS Hub Integration)

```
┌───────────────────────┐         ┌──────────────────────  
│     Desktop App       │◀─reads▶  │    PMBRS Artifact      │           ||                       React/Electron                   │                     SQLite + filesystem   |              │                                                      React Router  │ Routing / page layout                                                                                      │    
│                        Route → `/timeline`, `/experiments/, etc                                      |  
└───────────────────────┘         └──────────────────────
```

**Key Design Choices:**

1. **App reads directly from the artifact store** — there is no separate API server layer because everything is local and single-user. Reads are fast (SQLite + JSON). Writes go back through the orchestrator or direct module calls that validate and persist artifacts to disk or DB.
2. **Visualization never modifies authoritative artifacts** — per Constitution §9, only observational evidence, experiment declarations, and manual journal entries may be written as user-originated records; the app writes only to derived or interpretive layers when presenting analysis. All app actions should be audit-logged if used for downstream evaluation.
3. **Lazy loading + virtual scrolling** — large temporal datasets may contain thousands of canonical windows. Visualization never loads the entire history at once; it fetches temporal ranges on demand via windowed queries against a SQLite range index.

## Desktop App Core Views/Components

| Route    Component                 Description                                                       
|------|---|--------  
Timeline                    | Temporal regime view  Regime transitions, modality coverage, behavioral embeddings projected onto canonical timeline         || 
Experiments                        | Experiment comparison                    Side-by-side cohort diffs: before/during/after intervention periods            |         
Modality Explorer               # Sparse overlay browser                          Inspect individual modalities' contributions to windows (what wearable says vs what calendar says)          :           
Settings / Configuration           System configuration panel                        Privacy policy, encryption toggle, adapter management, batch scheduling config.
| About / System Health       Health dashboard                      Nightly integrity check results, pipeline status summary  

## Security & Access Model

- Runs locally with OS-level file permissions on the artifact store (`~/.pmbrs-private/store/.*` — owner-only read/write access to directory tree contents). No network endpoint by default. This is the local-first, no-domain configuration mandated by §16; the domain-served route is an optional alternative (see ADR-017 D4).
- Desktop UI is local process — not networked service at all unless you explicitly config port forwarding over LAN later via `config.json`.

---

**Pending**: ADR §18 will formalize visualization layer tech stack choice if we want something other than Electron (e.g., Tauri, Rust-based + WebGPU rendering for GPU-heavy 3D embedding space visualizations). For now the above is a strawman — feel free to push back/refine before it gets locked down in an ADR.)

> Constitution Reference: §15 (§§4) – Downstream consumers not constitutional core, fully replaceable subsystems.