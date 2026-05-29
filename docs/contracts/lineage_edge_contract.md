## Purpose

Defines valid lineage relationships between artifacts.

## Valid Edge Types

```yaml
- derived_from
- observed_from
- aggregated_from
- referenced_by
```

## Lineage Requirements

Every derived artifact must:

- reference upstream inputs,
- reference execution configuration,
- reference model/environment versions,
- preserve deterministic replay capability.

## DAG Constraints

Lineage graphs must:

- remain acyclic,
- preserve temporal ordering,
- prohibit recursive authority contamination.
