# Stage 1 Phase Spec

## Purpose

Define the initial PMBRS stage for artifact modeling, canonical windows, provenance structure, and linear lineage validation without introducing higher-order analytical outputs.

## Scope

Stage 1 produces:

- canonical artifact superclass definitions
- provenance taxonomy and specialization
- missingness semantics
- canonical window artifacts
- example artifacts for observational, canonical, feature, embedding, and experiment declarations
- invariants for artifact integrity, lineage, and semantic separation

Stage 1 defines a single unified ArtifactBase schema from which all artifact types inherit; no parallel base schemas are permitted.

## Out of Scope

Stage 1 does NOT produce:

- interactive dashboards or UI layers
- query optimizer implementations
- clustering or advanced analytics
- semantic inference or causal modeling
- automated experiment recommendation systems
- full-scale storage engine architecture
- end-user visualization artifacts
- streaming ingestion workflows beyond canonical window alignment

## Allowed Outputs

Stage 1 is permitted to produce:

- contract definitions
- invariant definitions
- example artifacts
- validation rules

## Forbidden Outputs

Stage 1 must NOT produce:

- pipelines
- storage systems
- query systems
- analytics systems
- embeddings or inference logic
- UI or visualization logic

## Authorized Context Set

The following files constitute the only authorized context for Stage 1 work. This is a hard constraint: any file not listed is write-protected unless the phase spec explicitly authorizes it.

### Mandatory

- `docs/contracts/artifact_base_contract.md`
- `docs/contracts/missingness_semantics_contract.md`
- `docs/contracts/provenance/provenance_base_contract.md`
- `docs/contracts/artifact_lifecycle_contract.md`
- `docs/invariants/system_invariants.md`
- `docs/contracts/execution_rules.md`
- `docs/constitution/purpose_and_scope.md`
- `docs/constitution/authority_model.md`
- `docs/constitution/experimentation_philosophy.md`

### Conditional

Conditional contracts are strictly opt-in. They MUST NOT be included unless explicitly listed in the task specification by full file path. Semantic relevance does not permit inclusion.

- `docs/contracts/canonical_window_contract.md`
- `docs/contracts/modality_contract.md`
- `docs/contracts/provenance/observational_provenance_contract.md`
- `docs/contracts/provenance/declarative_provenance_contract.md`
- `docs/contracts/provenance/computational_provenance_contract.md`

### Optional

- `docs/examples/observational_artifact_example.yaml`
- `docs/examples/canonical_window_example.yaml`
- `docs/examples/feature_artifact_example.yaml`
- `docs/examples/embedding_artifact_example.yaml`
- `docs/examples/experiment_artifact_example.yaml`

Examples are consultative only. They MUST NOT introduce fields not present in the relevant contracts, even if those fields appear consistently across examples.

## Bidirectional Consistency Rule

- Every field appearing in any example MUST be explicitly defined in an authorized contract.
- Contracts are the source of truth for schema definition.
- No example may introduce implicit or undeclared fields.
- No contract may omit fields required by existing examples within Stage 1 scope.
- Examples are non-normative and may only validate structure; they MUST NOT be used to infer schema, semantics, or validation constraints.

## Contract Precedence

When documents conflict, apply the following authority hierarchy:

1. `constitution/` documents
2. `invariants/`
3. `contracts/`
4. `phase_specs/`
5. `examples/`

If a contract or phase spec appears to conflict with a higher-priority document, the higher-priority document wins.

## Task Binding Rule

Each Stage 1 task MUST declare the following before any implementation begins:

- required contracts
- required invariants
- target file set

Contracts may only be included if they are explicitly listed in the task specification by full file path. No implicit dependencies are allowed.

## Mutation Definition

A mutation is any change to:

- schema structure
- field definition
- validation rule
- required/optional status
- semantic meaning of a field
- lineage structure
- provenance fields
- lifecycle state transitions
- content hash recomputation

Non-mutative changes are limited to formatting or comments only if they do not affect semantics.

## Retrieval and Execution Workflow

To keep context efficient and avoid cross-contamination, Stage 1 should use a two-phase loop:

1. Retrieval phase:
   - Identify the exact authorized files required for the task.
   - Load only those files and the permitted reference set.
   - Extract the contract definitions, invariants, and phase-specific allowed module list.
   - If required files are not in the authorized context set, execution MUST stop immediately and emit a context expansion request. No partial execution is permitted.

2. Execution phase:
   - Apply the selected contract semantics to the target files.
   - Modify only the explicitly declared files.
   - Do not use unrelated repository files for reasoning or generation.

This loop prevents incidental attention to irrelevant content and keeps task scope tight.

## Enforcement

Enforcement for Stage 1 is governed by the Retrieval Phase rules and the Context Expansion constraint.

A context expansion request must include:

- the additional files being requested,
- the specific contract or domain justification,
- the task-level commitment to remain within Stage 1 scope.

If a task requires a file that is not authorized, the agent MUST stop and emit a context expansion request instead of proceeding.

## Undefined Field Rule

If a field, rule, or invariant is not explicitly defined in an authorized contract:

- it is considered undefined,
- no default value may be assumed,
- no inferred schema extension is permitted,
- execution MUST halt with a context expansion request.

## Acceptance Criteria

1. Artifact examples conform structurally to `artifact_base_contract.md`.
2. Provenance is classified into `observational`, `declarative`, or `computational` and matches its specialized contract field definitions exactly.
3. Canonical windows reference `missingness_semantics_contract.md` and preserve modality coverage semantics.
4. Content hashing is defined in `artifact_base_contract.md` with explicit algorithm, canonical serialization rules, and field inclusion/exclusion scope. All examples MUST compute hashes using this exact specification or explicitly mark them as `placeholder_hash` with validation exemption noted in metadata.
5. No contract and example pair contradicts on required field names or topology.
6. The phase spec explicitly states what Stage 1 does not produce.

## Notes

This phase spec is intentionally narrow to prevent drift into later-stage architecture. It should be used as the primary guidance document for any code generation or model-driven implementation in Stage 1.
