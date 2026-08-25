# Execution Environment & Reproducibility Setup

## Purpose

Define how PMBRS environments are configured for reproducible execution across pipeline stages, representation training runs, and future module swaps. Per Constitution §12: *"Derived artifacts preserve explicit transformation provenance, version references, execution metadata."*

## Base Requirements

| Component     | Recommendation            Rationale                                                                 ||  
---|---|    
Runtime Language                 Python 3.12+                            Primary implementation language for core modules (ingestion, alignment, feature extraction, orchestration)                    ||
Python environment manager       uv (recommended) or venv                       # Fast, reproducible dependency resolution; lock file support (`uv.lock`) ensures identical installs across machines             )          |   ML/Representation layer            Python + PyTorch or JAX on GPU if available     Embedding training benefits from hardware acceleration. Falls back gracefully to CPU-only mode.                             `Mobile client                  Kotlin Android (see ingestion/adapters/mobile-collection.md)        Native collection app running independently of hub environment                         || 
Desktop visualization           Electron/React stack                  Per visualization/architecture.md — runs separate runtime process                       ||
Storage engine                   SQLite 3.x                                       Built-in, zero-config, ACID-compliant local database                       

## Lock File Strategy for Reproducibility

Every major training run and pipeline execution records its dependency graph:
```yaml       
# .hermes/pipeline.lock pseudo-example snapshot structure  
snapshot_id:: hash-of-dependencies-at-time-T          
python_version: "3.12.x"      
dependencies::          pmbrs-core:        version     0.1.0             git_sha    abc123def                   timestamp   2026-08-xxT##:##:##+UTC
||                                      
torch                     2.x.y                                                   
pandas                              2.x.y                                        
|          ...                                  
```

This snapshot is referenced in artifact provenance metadata per Constitution §12 (*"Lineage references must identify upstream inputs, producing subsystem, execution timestamp, configuration snapshot, model version, dependency versions, code revision/environment."*). Goal: **any future re-run reproduces identical results given the same inputs**.)

## Optional Isolated Environments (Per-Subsystem)

While most of PMBRS shares one Python environment via `uv` + `pyproject.toml`, heavier dependencies can optionally run in isolated sub-environments if needed later for modularity:
```bash
./venvs/ingestion/       Lightweight deps only — requests, sqlite3 adapter wrappers etc.)  
./venvs/ml-training/     PyTorch/JAX + numpy/scipy — heavy GPU-enabled sandbox for representation learning.                      
```

This keeps the main runtime lean when ML training is not actively running per §5 ("Batch-first" — we don't need torch in memory 24/7, just during scheduled weekly retraining windows).

---

> Constitution Reference: §12 (Lineage-Centric Reproducibility), §17 (§§9) (Schema Versioning & System Evolution)