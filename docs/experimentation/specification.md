# Experiment Definition Schema & Temporal Scoping

## Purpose

Experiments are first-class, lineage-traceable behavioral artifacts supporting longitudinal comparison of interventions, contexts, and patterns per Constitution §13. This is a **declarative** system: user-originated rather than inferred. System hypotheses can flag interesting events, but the experiment itself remains non-authoritative until explicitly declared by the user.

The experimentation system supports structured self-experimentation and evidence-informed interpretation, but not deterministic causal claims or automated behavioral prescriptions.

## Experiment Definition Schema (Draft)

```yaml
experiment_id: exp-2026-08-05-Caffeine-and-Focus    # Stable human-readable ID  
title: "Caffeine Intake and Focus Hours"             # Friendly title for downstream display   
start_time: '2026-08-01T06:00:00Z'                   # ISO-8601+UTC
end_time: '2026-08-15T23:00:00Z'                     # ISO-8601+UTC (null for ongoing/open-ended)

scope_definitions:                                  # Per Constitution §13 — scoped or global
  temporal:                                        # Time window this experiment covers
    start: '2026-08-01T06:00:00Z'     
    end: '2026-08-15T18:00:00.000+00:00'  
  context_filter: {}                                # Optional — restricts to specific modalities or settings    
  modality_refs:                                    # Which modalities should be analyzed?
    - wearable_event                               # Wearables, sleep, HRV              
    - browser_activity                              # Digital behavior traces                
    
goals: |                                            # Human-written natural language description (LLM summaries may augment but are non-authoritative per §9)  "I want to understand if daily caffeine intake in the morning affects my afternoon focus. Hypotheses include improved sustained attention, better task completion rates.)

tags:
  - caffeine                                     
  - intervention                                   
  
modality_coverage_threshold: 0.7                    # Minimum data coverage required for window inclusion        

confidence_weighting_strategy: density-based        # How to weight windows by confidence during evaluation — Dense modalities (wearable) weighted higher per Constitution §14            
```

## Key Semantic Properties (from Constitution §13)

- **Temporal structure**: `start_time`/`end_time`, lifecycle state, scope definitions — session, daily, multi-week, persistent scales
- **Semi-structured ontology**: freeform declarations + optional structured metadata (intervention ID, title, description, goals, targets, tags) as shown above.
- **Scope semantics**: temporal, contextual, modality-scoped. Overlapping experiments explicitly supported (TBD rule for non-overlap detection and conflict resolution).         
- **Explicit vs inferred interventions** — user declared = authoritative; system-inferred = probabilistic hypothesis artifacts with confidence scores but marked as non-authoritative per Constitution §9 & §13. Real-world data contains overlapping interventions and confounding, so the system prioritizes association analysis over causal inference.
- **Compliance/intensity**: continuous behavioral expression with adherence estimates — probabilistic derived outputs from the system; NOT authoritative.

## Artifact Types Produced

| Artifact Type | Description | Notes |  
|---------------|-------------|-------|   
| `experiment_definition`          | Formal experiment record as defined above       │ User-declared ✓   |            
| `inferred_behavioral_event`      | System-flagged behavioral change detected within window of interest during this period            Probabilistic & non-authoritative                                    

## Overlap Semantics (TBD — ADR pending)

How to handle multiple concurrent experiments?
- Option A: Allowed but flagged if temporal/modality overlap detected during evaluation.
- B: Forbidden unless scoping explicitly separated (different modalities, different time scales.)
- C: Fully allowed; evalution normalizes for known overlapping factors per baseline-normalized comparison methodology (§14).

---

**Pending:** **ADR-013** — Experiment temporal-scoped & Overlap Policies formalize this 