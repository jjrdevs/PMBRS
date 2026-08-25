# Representation Quality Evaluation Metrics
## Purpose
Proxy evaluation metrics for behavioral embeddings per Constitution §14 — no ground truth labels exist, so we evaluate through structural indicators rather than supervised accuracy. **This evaluates whether the system produces stable, reproducible, behaviorally informative structure.**

## Metric Categories (from §14)
### Temporal Coherence
||---|---|
Transition smoothness        Consecutive windows produce nearby embeddings           Mean cosine similarity between t and t+1 > threshold T                                    │Embedding variance stability             Variance of embedding norms across consecutive windows  Extreme spikes suggest model instability/fit issues                           |

### Reconstruction Consistency
|| Metric    Description      Success Condition                     Note                                                         || 
---|----|
Reconstruction loss trend                Loss decreasing (or stable) on held-out temporal validation set        Standard VAE autoencoder check; contrastive models have an analog via positive-pair similarity                            ||
Forward-backward reconstruction symmetry                         Reconstruct window from embedding, then re-embed — distance ≈ 0    Checks round-trip fidelity. Large gaps → information loss in bottleneck                                       

### Clustering Stability
||---|---|
Cluster inertia / silhouette score (when applicable           Improved or stable across training iterations                    Measures how well-separated behavioral regimes are                                || 
Assignment stability under perturbation (bootstrap/resample the same windows → assign clusters → compare labels)   >85% agreement with previous clustering                    Robustness check: same behavior should cluster similarly                             |

### Modality Ablation Sensitivity
||---|---|
Cross-modal embedding agreement                               Embodings computed with/without modality M are correlated        Checks whether model over-relies on any one sensor                                        || 
Unimodal embedding quality                                  # Each modality alone produces meaningful structure       Ensures the system doesn't collapse when a data provider goes offline 

## Proxy Evaluation Philosophy (from §14)
> Explicit recognition of absent behavioral ground truth. Evaluations rely on proxy structural indicators: temporal continuity, contextual consistency, intervention sensitivity, perturbation robustness, ablation performance, reconstruction consistency, regime persistence, transition smoothness — **structural validation methodology rather than evidence of psychological truth.**

|| Proxy Indicator                What It Validates                    | Fail Signal                          || 
---|----|
Temporal continuity                     Embeddings change gradually over time; no sudden jumps without behavioral justification                       Anomaly: embedding drift that doesn't correlate with any modality signal           ||
Intervention sensitivity                     Representations shift detectably during declared experiments      False alarm: model claims regime change where none was observed                                   |Modality ablation                 Removing one sensor changes but doesn't break the representation               Catastrophic drop → over-reliance on single source                                 

---**Pending:** ADR-015 — Formalize this into an operational evaluation suite with concrete thresholds per metric. > 