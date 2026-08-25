# Experiment Comparison View — Desktop App Component Spec

## Purpose

Side-by-side cohort comparison interface for evaluating behavioral changes during declared experiments. Supports the context-aware comparison methodology per Constitution §13: no naive before-vs-after; instead baseline-normalized, regime-conditioned, weekday-matched analysis.

*This view requires active or completed `experiment_definition` artifacts and corresponding evaluation reports from the representation/evaluation pipeline.*

## UX Layout (Wireframe)

```text
┌───────────────────────────────────────────────────────┐
│ 📋 [Experiment Selector ▾]   │  [Comparison Mode ▾]  │
│                                                         │
│ ───── BEFORE ──── │ ───── DURING/EXPERIMENT ────       │
│ Embedding scatter ║ Embedding scatter                  │
│ (baseline period) ║ (experiment window)                │
│                                                         │
│ ███▓▒░░ Feature dist. ║ ███▓▒░░ Feature distribution    │
│ mean=2.3, std=0.7     ║ mean=1.8, std=0.9              │
│ Regime A: 45%         ║ Regime A: 22%                   │
│ Regime B: 35%         ║ Regime B: 61%                   │
├────────────────────╨───────────────────────────────────┤
│ ⏱ Timeline diff (regime transitions)                  │
│ ─A-A-B-B-B-  vs  ─B-B-B-A-B-                          │
│                                                         │
│ 💬 LLM-generated summary (non-authoritative, §9)       │
│ "During experiment period: HRV increased +12%,        │
│ regime B frequency doubled (p<0.05). No causal        │
│ inference intended — statistical association only."    │
└───────────────────────────────────────────────────────┘
```

## Comparison Modes

| Mode | Description | Constitution Anchor |
| --- | --- | --- |
| Temporally matched | Compare same-clock-time windows across baseline vs experiment periods | §13 — context-aware comparison |
| Weekday-matched | Compare the same weekday-of-week alignment (for example, Mon-to-Mon) | Reduces day-of-week confounding effect |
| Regime-conditioned | Compare only windows that shared the same pre-experiment regime label | Isolates intervention effect from natural state transitions |
| Distributional shift | Compare full embedding distribution shapes | §13 — comparative behavioral structure (distribution shifts) |

## Statistical Outputs (Display Layer)

All statistical displays should follow the Constitution §9 and §4 interpretability constraints:

- **Distribution metrics**: mean/median/std shifts between experiment and baseline periods.
- **Regime frequency table**: before-vs-during percentages for each cluster assignment.
- **Effect size indicators**: Cohen's d or similar magnitude measures, not p-values for causation claims.
- **Confidence intervals**: shown alongside all metrics per §14 uncertainty constraints.

### Critical Display Rule

Every comparison view should include this prominent disclaimer:
> ⚠️ Associational analysis only. No causal inference intended. Multiple interventions may overlap; confounding controls are probabilistic guidelines, not definitive isolation guarantees. Per Constitution §§9 and 13, deterministic "worked/failed" conclusions are not permitted.

## Data Requirements from Artifact Store

```sql
-- Conceptual query shape (per experiment scope)  
SELECT * FROM behavioral_embeddings be 
JOIN canonical_windows cw ON be.window_id = cw.window_id     
JOIN experiments e ON cw.start_time BETWEEN e.start_time AND e.end_time   
WHERE e.experiment_id = ?;      -- Scope resolved from experiment_definition artifact
```

Artifacts consumed by this view:
- `experiment_definition` (temporal boundary and scope)
- `behavioral_embedding` (trajectory/projection within those windows)
- `clustering_result` (regime assignment labels)
- `evaluation_report` (comparison methodology outcome, if precomputed by the analytic pipeline; the view can also compute summary statistics on the fly for interactive exploration)

---

> Constitution reference: §13 (experimentation formalization) and §9 (association, not causation). This supports the overlap rules in the experimentation spec and the baseline-normalization approach for comparative analysis. This remains a replaceable downstream UI component per §15.
