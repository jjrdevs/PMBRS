# Representation Learning — Training Pipeline (TBA)

## Purpose

Define the batch-first training loop for behavioral embedding models. This is not a real-time learning system. Per **ADR-017 D3**, the cadence is three-segment: **nightly passover** (ingest → align → feature → summary → publish), **weekly incremental training** (warm-start from prior checkpoint), and **monthly full retrain** with a pre-deploy quality gate (Constitution §14-6).

## Inputs to Training Pipeline

| Input | Source Artifact | Content  |
|---|---|---|
Feature vectors              `feature_vector`                    Per-modal, raw, temporal canonical windows                                      ||  
Behavioral regime labels     (optional) From manual + user-declared events or clustering results         Contextual context overlay for contrastive objectives (if available/used).                                      

## Output | Artifact Type        | Description                                   
|---|---|    
`behavioral_embedding`                      Per-window embedding vectors (the main output)              || 
`clustering_result`                            Cluster/regime assignments over windows (TBD: t-SNE, UMAP + HDBSCAN?)   
`embedding_evaluation_report`                Quality metrics computed on training run — loss curve, stability scores, drift indicators  

## Pipeline Stages

### Stage 1: Data Preparation
- Load feature vectors from artifact store. Filter by coverage threshold (windows with <X% modality coverage dropped or marked as low-confidence).
- Split into training/validation sets via temporal split (chronological order preserved — no random shuffle to avoid data leakage across time). Validation set uses the most recent N windows; all other prior history used for training.).

### Stage 2: Model Instantiation  
- Load model architecture from `model-selection.md` decision. ADR-011. Configuration + hyperparameters versioned per run.
- Optional warm-start: if prior checkpoint exists, resume from there rather than pre-training (incremental learning).

### Stage 3: Training Loop
Batch-first contrastive objective or VAE ELBO — configured by model choice.
- **Weekly cadence:** incremental training — warm-start from the most recent checkpoint when one exists (ADR-017 D3).
- **Full retrain (monthly floor, or earlier on feature drift):** cold re-fit at the monthly boundary OR when feature vectors have changed since the last full fit (ADR-017 D3).

### Stage 4: Evaluation & Quality Check  
Run proxy evaluation suite (§15) — temporal coherence, clustering stability, modality ablation sensitivity — before deploying new model checkpoint. If quality check fails metrics defined below, revert to previous checkpoint and flag for manual review.

## Configuration Versioning

Every training run records:
- Feature version (which features/vectors were used).  
- Model version + hyperparameter snapshot.
- Environment: Python version, GPU availability, dependency versions.
- Reproducibility: seed for deterministic initialization where applicable (acknowledging that contrastive/VAE objectives are inherently non-deterministic; Constitution §9 acknowledges this explicitly in interpretability constraint).

## Fail-Safe & Rollback

If evaluation metrics diverge from prior run beyond threshold (§14), the new checkpoint is rejected and replaced with previous stable snapshot. No silent model regression allowed — Constitution §15, "Evaluation as permanent operational layer."

---

**Pending**: ADR-012: Training Data Curation & Modality Ablation Strategy > 