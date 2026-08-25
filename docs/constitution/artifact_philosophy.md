## Artifact-Oriented Architecture

Artifacts are the formal backbone of PMBRS.

All subsystems communicate through artifacts.

Artifacts enable:

- reproducibility,
- lineage,
- enforceable system boundaries,
- experimentation,
- modularity,
- reprocessing.

## Artifact Definition

An artifact is any structured object produced, consumed, transformed, stored, or referenced within PMBRS.

Artifacts include:

- raw events,
- canonical windows,
- features,
- embeddings,
- experiment declarations,
- evaluation outputs,
- semantic summaries.

## Artifact Axes

Artifacts are defined along orthogonal axes:

### Lineage Position

- raw,
- derived,
- interpretive.

### Epistemic Role

- authoritative,
- probabilistic,
- reproducible,
- transient.

### Operational Status

- immutable,
- mutable,
- append-only,
- cacheable.

## Immutability Philosophy

Immutable artifacts include:

- observational records,
- canonical windows,
- journal entries,
- experiment declarations,
- derived analytical outputs.

Mutable artifacts are limited to:

- caches,
- indexes,
- temporary operational layers.

## Lineage Philosophy

Artifacts form a directed acyclic graph (DAG).

Lineage relationships include:

- derived-from,
- aggregated-from,
- observed-from,
- referenced-by.

All derived artifacts must expose:

- upstream inputs,
- configuration references,
- model versions,
- execution provenance.

## Raw Preservation Philosophy

PMBRS adopts a raw-preserving architecture.

Behaviorally meaningful raw events and streams should be retained whenever feasible to:

- minimize irreversible information loss,
- support retraining,
- support future modeling,
- preserve reproducibility.

Exhaustive surveillance artifacts are excluded by default.

Examples excluded unless explicitly justified:

- screenshots,
- raw audio,
- full page contents,
- keystroke logging.
