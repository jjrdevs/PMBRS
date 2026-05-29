# System Invariants

## Purpose

This document defines the non-negotiable system invariants governing PMBRS.

These invariants represent constitutional architectural constraints.

Violations of these invariants constitute architectural failure.

---

# Authority Invariants

## Invariant: Authoritative Artifact Immutability

### Statement

Finalized authoritative artifacts are immutable.

### Rationale

Immutability preserves:

- historical integrity,
- observational traceability,
- reproducibility.

### Violation Consequences

- lineage corruption,
- epistemological contamination,
- irreproducible analysis.

### Validation Method

- mutation validator,
- lifecycle transition validator.

### Related Contracts

- artifact_lifecycle_contract.md
- deletion_supersession_contract.md

---

## Invariant: Derived Artifacts May Not Overwrite Authoritative Artifacts

### Statement

Derived artifacts may never overwrite authoritative observational evidence.

### Rationale

Interpretation must remain separate from observation.

### Violation Consequences

- recursive semantic contamination,
- interpretability collapse,
- authority ambiguity.

### Validation Method

- lineage validator,
- authority-state validator.

### Related Contracts

- computational_provenance_contract.md
- artifact_lifecycle_contract.md

---

# Temporal Invariants

## Invariant: Canonical Temporal Alignment

### Statement

Canonical windows must align to the global fixed 60-second temporal grid.

### Rationale

Shared alignment preserves:

- multimodal coherence,
- reproducibility,
- temporal interoperability.

### Violation Consequences

- temporal fragmentation,
- inconsistent modality comparison,
- evaluation instability.

### Validation Method

- temporal alignment validator.

### Related Contracts

- canonical_window_contract.md

---

# Lineage Invariants

## Invariant: Derived Artifacts Require Upstream Lineage

### Statement

All derived artifacts must preserve explicit upstream lineage references.

### Rationale

Lineage enables:

- reproducibility,
- auditability,
- regeneration.

### Violation Consequences

- irreproducible outputs,
- orphaned analytical artifacts,
- provenance failure.

### Validation Method

- lineage DAG validator.

### Related Contracts

- computational_provenance_contract.md

---

# Interpretability Invariants

## Invariant: User-Facing Conclusions Must Remain Traceable

### Statement

User-facing conclusions must remain traceable to observational artifacts and transformation lineage.

### Rationale

Traceability preserves interpretability and epistemological integrity.

### Violation Consequences

- opaque reasoning,
- unverifiable claims,
- trust degradation.

### Validation Method

- interpretability validator,
- lineage traversal checks.

### Related Contracts

- computational_provenance_contract.md
- experiment_declaration_contract.md

---

# Epistemological Invariants

## Invariant: Inference May Not Masquerade as Observation

### Statement

Probabilistic inferred artifacts may not be represented as directly observed evidence.

### Rationale

Observation and inference represent fundamentally different epistemological categories.

### Violation Consequences

- semantic contamination,
- false certainty,
- interpretability collapse.

### Validation Method

- authority-role validator,
- artifact classification validator.

### Related Contracts

- computational_provenance_contract.md
- observational_provenance_contract.md

---

## Invariant: Correlation May Not Be Represented as Causation

### Statement

PMBRS may identify statistical associations but may not assert deterministic causal truth.

### Rationale

Behavioral systems are observational and probabilistic.

### Violation Consequences

- invalid interpretations,
- behavioral overreach,
- false explanatory confidence.

### Validation Method

- evaluation output validator,
- semantic interpretation validator.

### Related Contracts

- experiment_declaration_contract.md

---

# Reproducibility Invariants

## Invariant: Derived Artifacts Must Preserve Computational Provenance

### Statement

All derived artifacts must preserve sufficient provenance for equivalent regeneration.

### Rationale

Reproducibility is a foundational PMBRS requirement.

### Violation Consequences

- irreproducible analytics,
- unverifiable evaluations,
- lineage fragmentation.

### Validation Method

- provenance completeness validator.

### Related Contracts

- computational_provenance_contract.md

---

# Missingness Invariants

## Invariant: Missingness Must Remain Explicit

### Statement

Missingness may not be represented implicitly.

### Rationale

Explicit missingness prevents silent analytical contamination.

### Violation Consequences

- model contamination,
- false behavioral assumptions,
- uncertainty collapse.

### Validation Method

- canonical window validator,
- modality completeness validator.

### Related Contracts

- missingness_semantics_contract.md

---

# Operational Invariants

## Invariant: Local-First Privacy

### Statement

PMBRS authoritative behavioral data is local-first by default.

### Rationale

Behavioral telemetry is highly sensitive and privacy-critical.

### Violation Consequences

- privacy risk,
- security degradation,
- trust collapse.

### Validation Method

- storage policy validator,
- synchronization validator.

### Related Contracts

- privacy_philosophy.md
