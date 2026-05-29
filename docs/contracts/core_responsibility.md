# Core Responsibility Contract

## Purpose

Defines the core PMBRS responsibilities and the boundaries between system-owned behavior and replaceable subsystems.

This contract is intended to keep the system stable, prevent architectural drift, and preserve the separation between core artifact governance and implementation-specific modules.

## Core Responsibilities

PMBRS core owns the following:

- canonical temporal alignment and the fixed 60-second grid
- artifact governance and schema enforcement
- lineage tracking and reproducibility infrastructure
- provenance classification and type-specific provenance contracts
- modality abstraction contracts and missingness semantics
- ingestion contract definitions for authoritative artifacts
- feature extraction orchestration and representation-learning interfaces
- experimentation declaration infrastructure and experiment metadata contracts
- evaluation artifact infrastructure and quality evaluation contracts
- uncertainty propagation and confidence-aware metadata
- derived artifact management and supersession semantics
- artifact identity, content hashing, and canonicalization rules

## Replaceable Subsystems

The following may be replaced or extended as long as they preserve core contracts and invariants:

- visualization layers, dashboards, and reports
- mobile/desktop/interactive applications
- storage backends, databases, and physical persistence systems
- ingestion adapters and external integration bridges
- wearable integrations, browser telemetry systems, and calendar providers
- feature extraction algorithms and embedding architectures
- LLM providers, model backends, and optional analytics engines
- clustering, summarization, and interpretation subsystems

## Not Core

PMBRS does NOT own:

- UI/UX and end-user presentation systems
- hosted dashboards and business intelligence platforms
- underlying storage engines or persistence formats
- external data collectors and sensor hardware vendors
- proprietary LLM products or third-party model providers
- optional analytics tooling not required for contract conformance

## Philosophy

This contract enforces the principle: one contract = one implementation boundary.

- Each contract defines a single implementation boundary.
- No cross-module edits are allowed unless explicitly declared by the governing contract.
- Contracts are authoritative; examples are interpretive only.
- Core responsibility documents define what the system owns and what it explicitly does not own.

## Implementation Guidance

- Preserve artifact contract semantics regardless of the underlying implementation.
- Keep substitution points explicit and documented.
- Treat core contracts as invariant interfaces for replaceable subsystems.
- Require any subsystem replacement to preserve taxonomy, lineage, and provenance semantics.

## Related Contracts

- `artifact_base_contract.md`
- `schema_evolution_contract.md`
- `provenance/provenance_base_contract.md`
- `execution_rules.md`
