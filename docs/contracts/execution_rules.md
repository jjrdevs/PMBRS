# Execution Rules

## Purpose

Defines the rules governing how contracts, specs, examples, and implementation boundaries are managed.

This document is intended to prevent repository drift, clarify authority, and keep change scope disciplined.

## Scope Isolation Rules

- One contract = one implementation boundary.
- Contracts define the authoritative scope for a module or feature.
- No cross-module edits are permitted unless explicitly declared by the relevant contracts or phase spec.
- Examples are interpretation aids only and are never authoritative.
- Contracts may only be included if they are explicitly listed in the task specification. Keyword-based or semantic inference for contract inclusion is forbidden.

## Spec Priority Order

When resolving conflicts or making decisions, apply the following priority order:

1. `constitution/` documents
2. `invariants/`
3. `contracts/`
4. `phase_specs/`
5. `examples/`

Examples are useful for interpretation but must never override contract or invariant requirements. Examples MUST NOT introduce fields or schema elements that are not present in the applicable contracts. Examples are non-normative and MUST NOT be used to infer schema, semantics, or validation constraints.

## Enforcement Rules

- Any file not explicitly listed in the authorized context set or the task’s approved scope is write-protected.
- If a task requires touching additional files, the work must begin with a proposal that explicitly names those files and the responsible contracts.
- Changes must be limited to files declared in the phase spec, contract, or authorized execution mapping.
- A mutation is any change to schema structure, field definition, validation rule, required/optional status, or semantic meaning of a field.
- Write-protection is the enforcement mechanism: unlisted files may be read only if they are explicitly authorized as reference, and they may not be modified.
- If a field, rule, or invariant is undefined in an authorized contract, no default may be assumed and no inferred schema extension is permitted.

## Change Discipline

- AI agents and contributors must propose cross-module changes before executing them.
- Implementation changes should be scoped and reviewed against contract boundaries.
- Explicitly document the requested modification set before editing files.
- Avoid “slow repo corruption” by keeping changes confined to the declared contract surface.

## Allowed Modification Rules

- Only files explicitly listed in a contract or phase spec may be modified in a single task.
- If a task requires touching multiple modules, the task must declare every affected contract and related implementation boundary.
- Cross-cutting changes require an explicit execution mapping or authorized phase spec.

## Contract Completeness Checklist

A good contract MUST include:

- inputs / outputs
- state model
- error cases
- side effects
- dependencies
- forbidden behaviors

If any item is missing, the model may fill gaps creatively and introduce drift.

## Execution Mapping

Whenever a contract or phase spec defines a feature, it MUST include a spec-to-file mapping table or an explicit implementation boundary description.

### Example Mapping Table

```text
contracts/provenance -> /src/provenance/*
contracts/artifact_base_contract.md -> /src/artifacts/*
phase_specs/stage_1.md -> allowed modules list
```

### Recommended Mapping Rules

- Contracts map to implementation modules.
- Phase specs map to allowed module lists for a stage.
- Invariants map to runtime or validation subsystems.
- Examples map to reference data only.

## Related Documents

- `core_responsibility.md`
- `schema_evolution_contract.md`
- `artifact_base_contract.md`
- `phase_specs/stage_1.md`
