# Representation Learning — Model Selection Survey

## Purpose

Survey viable embedding models for behavioral data representations in PMBRS. All candidates must satisfy Constitution §4: partial interpretability (conclusions traceable to observable artifacts).

## Candidate Architectures

### Option A: Contrastive Time-Series Embedding (SimCLR-style)
- **Approach**: Augmentation-based contrastive learning on sliding feature windows; positive pairs are temporally adjacent or regime-matched segments. Negative pairs are distant-in-time windows.
- Fits PMBRS well because behavioral data is inherently temporal and we care about trajectory structure, not classification labels (no ground truth available per Constitution §14).
- **Pros**: Proven for unsupervised representation learning; naturally handles multi-modal input via modality-specific augmentations; no labeled data needed.
- **Cons**: Requires careful hyperparameter tuning for temperature parameter and augmentation design; interpretability is indirect (projections in embedding space, not human-readable features).

### Option B: Variational Autoencoder (VAE) / Factor VAE
- Learn latent distribution of behavioral patterns; can separate shared factors from modality-specific nuisance dimensions. Disentangled variant could isolate intervention effects from baseline behavior explicitly (§13 experimentation goal).
- **Pros**: Probabilistic outputs naturally encode uncertainty (Constitution §4). Reconstruction loss provides a proxy validation metric the system understands and evaluates against.
- **Cons**: Latent space interpretation requires additional work; training stability can be an issue with high-dimensional sparse input like behavioral windows.

### Option C: Cross-Modal CLIP-style Architecture
- Pairwise alignments between modalities (e.g., wearable + browser activity → unified embedding via contrastive alignment). Inspired by contrastive language-image pretraining but applied to behavioral time series across heterogeneous sensors/modalities.
- **Pros**: Naturally preserves modality distinction (§8 epistemological roles); allows querying "what does the representation look like when we only have X?" (modality ablation for robustness, Constitution §14).
- **Cons**: Most complex architecture; requires paired data aligned at same temporal resolution (which is exactly what canonical windows provide — big advantage of our 60s alignment from Section 6).

## Decision Criteria (for ADR pending)

| Criterion | Weight?   Must satisfy Constitution requirements.                        || 
Trainable on personal-scale data (~thousands to tens of thousands of canonical windows        # Non-negotiable for a single-user platform
Produce stable temporal embeddings (coherence across consecutive windows)                     Section 14 — Evaluation explicitly measures this                                    | Support modality ablation analysis                                                    §8. Replace models without changing interface definition                            ||  
Embedding dimension configurable (small enough to visualize; large enough to capture structure   # Desktop app visualization layer will need 2-3D projections            

## Recommendation (Preliminary — ADR Pending)

**Contrastive approach (A or C)** appears most aligned with PMBRS goals because:
1. No label supervision required (Constitution explicitly excludes deterministic inference, §4).
2. Naturally suited to batch-first processing (§5).
3. Produces embeddings that capture trajectory structure — exactly what experimentation comparison needs (§13).

A cross-modal variant (C) is particularly interesting long-term but adds complexity. Starting with a single-modal contrastive encoder on wearable features + iterating toward full multi-modal fusion may be the pragmatic path forward (§15 replaceable subsystem philosophy: start simple, swap later within contract constraints).

---

**Pending**: ADR-011 — Embedding Model Selection formalized > 