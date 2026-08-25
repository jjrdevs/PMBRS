# Module Boundary Contracts (Option C — Single-Process Modular Architecture)

## Overview

PMBRS is implemented as Option C: a **single Python process** composed of *structurally independent modules*. Each module's sole interface is the artifact store (SQLite + filesystem). Modules never pass data through in-memory handoff; they always read from and write to persisted artifacts. This allows future splitting into separate processes with zero logic changes.

## Core Rule

> Every downstream module treats upstream output as immutable artifacts. No module ever modifies another module's artifacts in-place. Derived outputs are new artifacts linked by lineage DAG edges.

## Module Execution Sequence (Batch)

```
1-ingest  → Raw observational & contextual data → SQLite + filesystem
2-align   → Canonical 60-second windows          → SQLite + filesystem
3-feature → Window-level feature vectors          → SQLite + filesystem
4-embed   → Representation embeddings             → SQLite + filesystem
5-experiment → Experiment evaluation reports      → SQLite + filesystem
6-evaluate → Quality & integrity checks           → SQLite + filesystem
```

Each step: reads its *required* upstream artifacts from storage, processes them, writes new artifact types to storage. Orchestration layer (`core/pipeline.py`) enforces sequencing only — it never mediates data flow between modules.

## Module Interface Specification

Every module must conform to this contract:

### `Module` Protocol (Python)

```python
class ModuleInterface(Protocol):
    """All PMBRS implementation modules implement"""

    name: str                              # e.g., "ingestion", "alignment"  
    dependencies: list[str]               # Upstream modules that must run before this  
    produces: list[ArtifactType]           # Artifact types written by this module

    async def run(self, artifact_store: StorageAdapter) -> ExecutionResult:
        """Execute one batch cycle."""
```

### Standard Module Lifecycle

1. **Check**: Determine if upstream artifacts exist/need processing (new raw data since last run?)
2. **Validate**: Schema version check on input artifacts — reject or upgrade via migration contract (Constitution §9)
3. **Process**: Compute derived output  
4. **Persist**: Write result artifacts with full lineage metadata (Constitution §11)

## Artifact Store Adapter Contract

All modules interact with the store through this adapter interface:

```python
class StorageAdapter(Protocol):
    """Thin wrapper over SQLite + filesystem."""

    # Artifact CRUD  
    async def save(self, artifact: BaseArtifact) -> None: ...
    async def get(self, id: str) -> Optional[BaseArtifact]: ...
    async def query(artifact_type: str, **filters) -> list[BaseArtifact]: ...  
    
    # Lineage tracking
    async def derive_from(child_id: str, parent_ids: list[str], edge_type: EdgeType): ...

    # State/checkpointing
    async def mark_module_complete(module_name: str, run_timestamp: str) -> None: ...
    async def get_last_run(module_name: str) -> Optional[ModuleRun]: ...
```

Modules **never** open raw database connections or filesystem paths directly. All I/O goes through `StorageAdapter`. This is what enables modular independence within a single process.

## Module Independence Guarantees

1. **No shared mutable state**. Modules communicate exclusively read/write through artifacts in the persistent store between runs, not via globals/imports/shared config objects as data pipes.
2. **Independent environments possible**: Each module can depend on different libraries — `ingestion` may need only requests, embedding needs GPU libraries (PyTorch), feature extraction needs scikit-learn. They run sequentially within the same main process via subprocess call or dynamic import.
3. **Failure isolation**: If `embedder` crashes, pipeline logs the failure. Next run retries from checkpoint without re-running ingest → align → features.

## Module File Layout Convention

```
src/pmbrs/
├── __init__.py                     # Re-exports all public artifact types
├── core/                           # Shared infrastructure (NOT module logic)  
│   ├── artifacts.py               # BaseArtifact class + lineage DAG operations
│   ├── storage.py                 # StorageAdapter implementation (SQLite + filesystem)
│   └── pipeline.py                # Orchestration engine, runs modules in order
├── ingestion/                      # Subsystem: reads external sources → writes observational artifacts
│   ├── __init__.py                # Module interface: name, dependencies, produces
│   └── adapters/
│       ├── wearable.py            
│       ├── browser.py             
│       ├── calendar.py            
│       └── mobile_sync.py         
├── temporal/                       # Subsystem: window creation, timezone handling, sparse alignment  
│   └── ...                        
├── features/                       # Subsystem: feature extraction vectors per window
│   └── ...                        
├── representation/                 # Representation learning — embeddings via training pipeline    
│   ├── model.py                   # Embedding model definition (PyTorch, contrastive learner)            
│   ├── train.py                   # Training loop over features + labels      
│   └── evaluate.py                # Metric computation (§14.5 — proxy eval suite)  
├── experimentation/                # Experiment definitions & cohort comparison   
│   └── ...
├── evaluation/                     # Quality/integrity/drift detection (not experiment eval)
│   └── ...
```

## Execution Model Details

### Batch Cycle Types

Each module can run in different batch cycle modes:

| Cycle | Triggered by | Modules run | Artifacts produced | Typical cadence (§14.7) |
|-------|--------------|-------------|-------------------|-------------------------|
| **Integrity** (nightly)   | `--cycle integrity` | ingest → align, experiment definitions written, evaluation artifacts | EvaluationReport    | Nightly |  

### Incremental vs Full Pipeline

Modules operate in *incremental mode* by default — they track their last checkpoint timestamp and only process new raw data since then. The pipeline orchestration layer (`core/pipeline.py`) tracks per-module checkpoints via `mark_module_complete()` / `get_last_run()` on `StorageAdapter`. 

Full reprocessing is available: `pmbrs run --full` — wipes all derived artifacts, reruns entire chain (observational artifacts preserved per §7).

---

> **Tying back to Constitution**
> - §5 Batch-analysis-first → Execution model is sequential batch cycles  
> - §11 Artifact Architecture → Module interface is artifact store only
