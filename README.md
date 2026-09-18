# PMBRS — Local-First Behavioral Data & ML Platform

An end-to-end, **local-first** platform that turns multimodal behavioral data
(e-ink journal exports, wearable signals, on-device notes) into clean, canonical
records; learns compact **behavioral embeddings** with a PyTorch autoencoder; and
serves the results through an **authenticated analytics API**, an **MLflow**
experiment store, and a **Streamlit/Altair** dashboard — plus a **Kotlin/Compose**
Android collector and instrumented battery experiments.

> **Positioning (read this first).** This is a *real, working ML + data
> pipeline*, not a mockup. No cloud, no telemetry, no network at inference —
> every stage is deterministic, versioned, and test-isolated. It is built for
> reproducible, self-directed experimentation, but the software pattern is the
> same one used in production ML: *ingest → canonicalize → feature-extract →
> representation-learn → analytical-store → authenticated-serve → track*.

---

## Pipeline (device → insight)

```
[Boox e-ink]        [Galaxy Watch]            [Kotlin/Compose app]
   ADB pull             wearable sync                on-device events
        |                    |                             |
        v                    v                             v
   OCR (engine)         HRV / grid parse              native ingest
        |                    |                             |
        +--------------------+-----------------------------+
                                 v
              canonical JSONL artifacts
        immutability · lineage · schema versioning · 60 s temporal alignment
                                 v
        deterministic feature extraction (stdlib + numpy; sha256-derived)
                           (reproducibility by construction — no wall clock, no IO)
                                 v
        representation learning — PyTorch autoencoder  (16 → 12 → 8 → 12 → 16)
                                8-d latent = per-window behavioral embedding
              (framework-swappable: PyTorch target, hand-rolled NumPy offline fallback)
                                 v
        Parquet compaction (pyarrow, snappy) + roll-ups   ->   DuckDB (analytical queries)
                                 v
        FastAPI read-only JSON API (passcode + TLS)  +  MLflow tracking  +  Streamlit / Altair
                                 v
                 LLM insight synthesis (opt-in) over canonical artifacts
```

---

## At a glance

| Concern | What it is |
|---|---|
| **ML** | PyTorch autoencoder (16→12→8→12→16) → **8-d behavioral embedding**; train/val split; **MLflow** experiment tracking (opt-in / self-hosted); framework-swappable with a guaranteed-offline **NumPy** fallback |
| **Data / ETL** | ADB device pull + **OCR** (Boox), **wearable (HRV)** parsing, canonical JSONL artifacts → **Parquet (pyarrow, snappy)** + roll-ups → **DuckDB** analytical queries |
| **Feature eng.** | Deterministic, stdlib+numpy feature extraction (one-hot source, sha256-derived payload vector, shape stats); versioned when logic changes |
| **Serving** | Read-only **FastAPI** JSON API behind **passcode auth + TLS**; self-hosted **MLflow** server; **Streamlit + Altair** dashboard |
| **Collection device** | **Kotlin/Compose** Android app (minSdk 24 / target 36, coroutines) + scripted **battery experiments** (run / collect / report) |
| **LLM layer** | Opt-in insight synthesis + note classification over canonical artifacts (prompts, windowing, artifact capture) |
| **Quality** | **26+ pytest files** (ingestion, compaction, representation, dashboard/auth, artifact shape) · **GitHub Actions CI** · **6 ADRs** · 17-principle constitution |
| **Core stack** | Python 3.11 · PyTorch · scikit-learn · DuckDB · pyarrow/Parquet · FastAPI · uvicorn · Streamlit · Altair · MLflow · httpx · Kotlin/Compose |

---

## Architecture by module

```
src/pmbrs/
├── core/            # canonical Artifact model + storage (immutability, lineage, schema versioning)
├── ingestion/
│   ├── boox/        # ADB pull -> OCR engine -> page / inbox / manifest / producer / artifact
│   └── wearable/    # parsers, HRV proxy, grid, model, producer, artifact  (Galaxy Watch)
├── representation/  # model (autoencoder, framework-swappable), train, evaluate, runner, checkpoint
├── compaction/      # parquet_writer (pyarrow/snappy), rollup, reader, compact()
├── dashboard/       # FastAPI app + api, passcode auth, session, filters, theme
├── insights/        # opt-in LLM synthesis, prompts, windowing, task reader, artifact capture
├── notes/           # note pipeline: classify, LLM, read-journal, writers, watermark, playbook
└── auth/            # token store (passcode / token handling for the read-only API)
```

**Authority model:** observational > canonical > derived > interpretive.
**Temporal contract:** canonical 60-second windows across all modalities.
**Reproducibility:** pure cores + injected seams (RNG/time/IO), no wall clock or network
in the deterministic path.

---

## Quickstart

```bash
# Data / ML env (see requirements.txt)
python -m pip install -r requirements.txt

# Ingest a Boox e-ink export (ADB pull -> OCR -> canonical JSONL)
python -m pmbrs.ingestion.boox.cli --help

# Train / evaluate the representation model (deterministic, offline NumPy by default)
python -m pmbrs.representation.train --local        # offline, no MLflow
python -m pmbrs.representation.train --mlflow       # opt-in MLflow tracking (self-hosted server)

# Compaction -> Parquet + rollups
python -m pmbrs.compaction.compact

# Serve the read-only analytics API (passcode + TLS)
uvicorn pmbrs.dashboard.app:app --host 127.0.0.1 --port 9100

# Dashboard
streamlit run src/pmbrs/dashboard/app.py
```

## Verifying (all green)

```bash
python -m pytest tests/ -v --tb=short
```

Test files cover: artifact shape (Boox), Boox producer / manifest, mobile raw ingest,
Parquet compaction + rollup, dashboard auth + smoke, and the representation pipeline.
CI runs the same suite on `ubuntu-latest` (see `workflows/ci-integration.yml`) and
uploads a failure artifact on red.

---

## Design principles (the ones that matter to a reviewer)

1. **Artifact-oriented** — immutable records, explicit lineage, schema versioning.
2. **Canonical 60-s alignment** — one time grid for every modality.
3. **Multi-layer authority** — no modality silently overwrites another.
4. **Batch-analysis first** — designed for reproducible analysis, not real-time control.
5. **Local-first privacy** — no telemetry, no network at inference.
6. **Scientific humility** — surfaces association, not causation; rollback gate judges the embedding artifact, not a "score."

---

## Honest scope (stated plainly, on purpose)

- The training dataset is small; the autoencoder's goal is a **well-formed, versioned,
  judge-able behavioral-embedding artifact**, not predictive accuracy.
- The **NumPy backend is a guaranteed-offline** path so the pipeline never depends on a
  CUDA/torch import; **PyTorch is the target backend** when available.
- The dashboard is **read-only** and **passcode + TLS** gated — there is no write path from
  the web layer into the canonical store.
- The LLM layer is **opt-in** and runs only over canonical artifacts.

---

## Links

- [docs/constitution.md](docs/constitution.md) — 17-principle system constitution
- [docs/index.md](docs/index.md) — documentation index & roadmap
- [docs/adr/](docs/adr/) — Architecture Decision Records
- [workflows/ci-integration.yml](workflows/ci-integration.yml) — CI
