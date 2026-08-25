# PMBRS Docs Merge Checklist

Use this checklist to reconcile the older question-sheet content with the newer documentation tree without losing any critical intent.

## Merge strategy

- Treat [docs](.) as the primary documentation source of truth.
- Treat [pmb_archive](../../../pmb_archive/) as a reference backup for older wording and intent.
- Keep the newer structure and organization, but preserve any concepts that were only present in the older material.

## Core concepts to preserve

Confirm that the following ideas are represented in the active docs:

- [ ] PMBRS is a personal behavioral measurement, experimentation, and representation learning platform.
- [ ] PMBRS is not a clinical diagnostic or deterministic mental-state inference system.
- [ ] PMBRS is batch-analysis-first rather than real-time-first.
- [ ] Canonical 60-second windows are the shared temporal backbone.
- [ ] Artifacts are first-class, lineage-traceable entities.
- [ ] Authority is layered: observational evidence, operational structure, and derived interpretation.
- [ ] Interpretability, uncertainty, and provenance must remain visible to users.
- [ ] Privacy and data minimization are architectural constraints.

## File-by-file review

### Foundation docs

- [ ] [conceptual-foundation/purpose_and_scope.md](conceptual-foundation/purpose_and_scope.md) — confirm scope, non-goals, success criteria, and operational philosophy.
- [ ] [conceptual-foundation/authority_model.md](conceptual-foundation/authority_model.md) — confirm the authority hierarchy and the distinction between authoritative and derived artifacts.
- [ ] [conceptual-foundation/artifact_philosophy.md](conceptual-foundation/artifact_philosophy.md) — confirm artifact-first thinking, immutability, and lineage semantics.
- [ ] [conceptual-foundation/temporal_model.md](conceptual-foundation/temporal_model.md) — confirm the canonical window model and temporal alignment rules.
- [ ] [conceptual-foundation/modality_philosophy.md](conceptual-foundation/modality_philosophy.md) — confirm modality categories and alignment semantics.
- [ ] [conceptual-foundation/interpretability_rules.md](conceptual-foundation/interpretability_rules.md) — confirm interpretability and uncertainty constraints.
- [ ] [conceptual-foundation/privacy_philosophy.md](conceptual-foundation/privacy_philosophy.md) — confirm privacy-by-design expectations.

### Top-level docs

- [ ] [constitution.md](constitution.md) — ensure it still reflects the full system vision and references the right principles.
- [ ] [index.md](index.md) — ensure navigation and the major sections remain intact.
- [ ] [glossary.md](glossary.md) — ensure definitions are consistent with the rest of the docs.

### Contracts and system rules

- [ ] [contracts/canonical_window_contract.md](contracts/canonical_window_contract.md)
- [ ] [contracts/missingness_semantics_contract.md](contracts/missingness_semantics_contract.md)
- [ ] [contracts/lineage_edge_contract.md](contracts/lineage_edge_contract.md)
- [ ] [contracts/experiment_declaration_contract.md](contracts/experiment_declaration_contract.md)
- [ ] [contracts/artifact_lifecycle_contract.md](contracts/artifact_lifecycle_contract.md)
- [ ] [invariants/system_invariants.md](invariants/system_invariants.md)

### Subsystem specs

- [ ] [ingestion/overview.md](ingestion/overview.md)
- [ ] [representation/training-pipeline.md](representation/training-pipeline.md)
- [ ] [experimentation/specification.md](experimentation/specification.md)
- [ ] [privacy-security/data-minimization.md](privacy-security/data-minimization.md)
- [ ] [visualization/desktop-app-specs/timeline-view.md](visualization/desktop-app-specs/timeline-view.md)
- [ ] [visualization/desktop-app-specs/experiment-comparison.md](visualization/desktop-app-specs/experiment-comparison.md)

## Merge rules

- Prefer the clearer wording when two versions say the same thing.
- Preserve the stricter or more operational constraint when one version is more specific.
- Keep the newer structure, but do not drop any concept that is central to the original question sheet.
- If a claim appears in one version and not the other, treat it as a candidate for inclusion unless it contradicts a stronger principle elsewhere.

## Completion criteria

The merge is ready when:

- [ ] all core concepts from the question sheet are represented somewhere in the active docs,
- [ ] there are no broken relative links,
- [ ] the markdown renders cleanly,
- [ ] the docs do not contain contradictory statements about scope, authority, or temporal model.
