# Experiment Declaration Contract

## Purpose

This contract defines the structure and semantics governing experiments within PMBRS.

The purpose of this contract is to support:

- structured self-experimentation,
- intervention comparison,
- longitudinal behavioral evaluation,
- reproducible analytical interpretation,
- evidence-informed personal interpretation.

Experiments are declarative observational structures rather than causal truth systems. They may support association analysis and comparison, but they do not guarantee causal inference.

---

## Scope

This contract applies to:

- intervention declarations,
- experiment metadata,
- scoped behavioral evaluations,
- experiment-linked evaluations,
- longitudinal comparison analyses.

---

## Core Principles

### Principle 1 — Experiments Are Declarative

Experiments declare:

- interventions,
- temporal boundaries,
- evaluation intent,
- observational scope.

Experiments do not guarantee causal inference.

---

### Principle 2 — Experiments Must Remain Lineage-Traceable

Experiment artifacts must preserve:

- linked interventions,
- evaluation references,
- temporal scope,
- associated analytical outputs.

---

### Principle 3 — Experiments Must Preserve Interpretive Humility

Experiment outputs:

- may propose associations,
- may identify correlations,
- may preserve uncertainty,
- may not assert deterministic causal truth,
- must remain traceable to observational evidence and lineage-linked artifacts.

---

## Required Fields

```yaml
experiment_id:
title:
hypothesis:
intervention:
scope:
evaluation_targets:
status:
start_timestamp:
end_timestamp:
```

---

## Intervention Semantics

Interventions are structured declarations describing intentional behavioral modification.

### Example

```yaml
intervention:
  type: caffeine_reduction
  parameters:
    max_daily_mg: 100
```

---

## Scope Semantics

Experiments may define:

- temporal scope,
- contextual scope,
- modality scope,
- behavioral scope.

### Example

```yaml
scope:
  temporal:
    weekdays_only: true
  contextual:
    work_hours_only: true
  modality:
    - sleep
    - heart_rate
    - productivity
```

---

## Evaluation Linkage

Experiments may reference:

- evaluation artifacts,
- comparison artifacts,
- embedding comparisons,
- longitudinal summaries.

Evaluation results must remain separate derived artifacts.

---

## Status Semantics

### Allowed Values

```yaml
status:
  - PROPOSED
  - ACTIVE
  - COMPLETED
  - ABANDONED
  - SUPERSEDED
```

---

## Validation Rules

- start_timestamp must exist.
- intervention definitions must be structured.
- experiment evaluations must remain lineage-traceable.
- experiment outputs may not overwrite authoritative evidence.

---

## Forbidden Behaviors

- Experiments may not imply deterministic causality.
- Experiment declarations may not rewrite historical artifacts.
- Derived interpretations may not masquerade as observational evidence.
- Experiments may not recursively redefine authoritative data.

---

## Reproducibility Requirements

Experiment declarations must preserve:

- intervention metadata,
- temporal scope,
- evaluation linkage,
- provenance metadata,
- schema versioning.

---

## Future Considerations

Potential future extensions:

- adaptive experiment protocols,
- confidence-aware evaluation,
- intervention overlap modeling,
- experiment recommendation systems.
