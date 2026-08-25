# PMBRS Build Plan — Dashboard, Storage Adapter, and Training Loop

**Date:** 2026-08-19
**Scope owner:** user + Hermes assistant
**Governing:** Constitution, ADR-017 (2026-08-19), `docs/module-contracts.md`
**Explicitly out of scope:** ADR-012 (experiment tracking), ADR-018 (visualization stack port — Electron/React), ADR-003 close (already de-facto settled by the running ingest), multi-user / multi-device, GPU inference, screen capture (§7 prohibition).

---

## 1. What "all of this" means

Per the 2026-08-19 decisions (ADR-017), this plan covers:

1. A `StorageAdapter` protocol that matches `docs/module-contracts.md` **and** the on-disk reality of `~/.pmbrs-private/store/raw/*/*.json`. (D2)
2. A working dashboard that reads the current 5 sample artifacts + the 3 published snapshots, running either locally or on the `mobile-sync.jjrdev.com` domain under a separate protected route. (C1 + C7)
3. A training pipeline stub that can run nightly passover, weekly incremental, and monthly full retrain, with a quality gate. (C6)
4. Doc closeout: `training-pipeline.md` wording fix, `ADR-010` status decision, and `requirements.txt` additions. (C1 follow-through)

It does **not** include: Android app UI work, multi-device sync, screen capture, new modality collectors, GPU, the Electron/React port (that's ADR-018 scope).

---

## 2. Assumptions (all verified 2026-08-19)

| # | Assumption | Verified by |
|---|-----------|------------|
| A1 | User-data root is `~/.pmbrs-private` (`chmod 700`, single root) | `config/external_data_policy.json`; 3 scripts; `pmbrs_runtime.py` |
| A2 | Raw format is one-JSON-per-file, written by `pmbrs_host_sync_ingest.py` | 5 sample files; script shape |
| A3 | The 8-field raw record shape is already fixed in code | `pmbrs_host_sync_ingest.py:31–63` |
| A4 | Hermes read-only snapshot is `~/.pmbrs-private/hermes-readonly/pmbrs_summary.json` (chmod 444) | `pmbrs_publish_summary_to_hermes.sh` |
| A5 | Domain is `mobile-sync.jjrdev.com`; existing route `POST /api/v1/artifacts/sync`; no dashboard route yet | `SyncSettings.kt`, `SyncApi.kt` |
| A6 | Dashboard substrate is Streamlit + DuckDB (reversible per §15) | ADR-017 substrate section |
| A7 | `StorageAdapter` is the consumer-facing interface for both the dashboard and the ML stub | `docs/module-contracts.md` §StorageAdapter protocol |
| A8 | Local-first is the default (§16); domain-served is optional, not mandatory | Constitution §16 |
| A9 | Cadence split: nightly passover / weekly incremental training / monthly full retrain | ADR-017 D3 + user decision |
| A10 | `mobile-event-dashboard/` is a *pattern template*, not a substrate | user decision + relative-import breakage |

---

## 3. Phases

Each phase has a **T-shirt effort** (S = < 1 session, M = 1–3 sessions, L = 3+ sessions), **inputs**, **outputs**, **acceptance criteria**, and a small **verification** step. Phases that do not depend on each other can run in parallel; the rest are sequential.

### Dependency graph

```mermaid
flowchart LR
    A[Phase A: StorageAdapter] --> B[Phase B: Dashboard prototype (local)]
    B --> C[Phase C: Dashboard on domain route]
    A --> D[Phase D: Training pipeline stub]
    A --> E[Phase E: Documentation closeout]
    C --> F[Phase F: End-to-end acceptance]
    D --> F
    E --> F
```

---

### Phase A — `StorageAdapter` implementation (M)

**Why first:** ADR-017 D2 makes this the single consumer-facing interface for both the dashboard and the training stub. Everything after it depends on a working adapter.

**Inputs:**
- `docs/module-contracts.md` §StorageAdapter protocol
- `config/external_data_policy.json` (all 6 root paths)
- `~/.pmbrs-private/store/raw/*/*.json` (5 sample files)
- Constitution §10 (modularity), §11 (artifact architecture), §16 (local-first)

**Deliverables:**

| File | Purpose |
|------|---------|
| `src/pmbrs/core/storage.py` | `StorageAdapter` (dataclass-based, JSON-backed) |
| `src/pmbrs/core/__init__.py` | package init |
| `src/pmbrs/core/artifact.py` | `Artifact` / `ArtifactRef` dataclasses matching the on-disk shape |
| `src/pmbrs/__init__.py` | top-level package |
| `tests/test_storage_adapter.py` | 5–8 test cases covering the protocol |
| `tests/test_artifact_shape.py` | schema/shape test against the 5 sample files |

**Acceptance criteria:**

- [ ] `StorageAdapter(config_path=…)` loads `external_data_policy.json`, derives all 6 roots (raw, summary, pending, checkpoints, hermes-readonly, state), and creates them if missing.
- [ ] `adapter.get(artifact_id)` returns either a typed `Artifact` or raises `FileNotFoundError`.
- [ ] `adapter.query(source=None, from_epoch=None, to_epoch=None, payload_kind=None, limit=None)` returns `list[Artifact]` from `raw/` without opening files directly from outside the adapter.
- [ ] `adapter.save(artifact)` writes to `raw/<source>/<artifact_id>-<created_at>.json` and returns the absolute path.
- [ ] `adapter.derive_from(upstream_ids, module, output_id)` records the lineage edge in an in-memory DAG (persisted later, Phase D) and returns the edge.
- [ ] `adapter.mark_module_complete(module, artifact_ids)` and `adapter.get_last_run(module)` behave per the contract, with a `state/`-backed checkpoint under `~/.pmbrs-private/checkpoints/`.
- [ ] **Read-only for Hermes is honoured**: reading from `hermes-readonly/` via the adapter is allowed *only* when `allowed_roots` is set to that path; writing to `hermes-readonly/` is refused (concern about §16: only `pmbrs_runtime.publish_summary_snapshot` writes to that dir, via a separate code path, not through the adapter).
- [ ] Tests pass with `pytest tests/test_storage_adapter.py tests/test_artifact_shape.py -v`.
- [ ] The adapter reads **only** JSON; no SQLite, no JSONL (per ADR-017 D2).

**Verification:** after running the adapter against the 5 sample files, `adapter.query(limit=20)` returns all 5 artifacts, each with a well-formed `Artifact` dataclass.

**Files to touch / create:**
- `src/pmbrs/__init__.py` (new)
- `src/pmbrs/core/__init__.py` (new)
- `src/pmbrs/core/artifact.py` (new)
- `src/pmbrs/core/storage.py` (new)
- `tests/test_storage_adapter.py` (new)
- `tests/test_artifact_shape.py` (new)
- `requirements.txt` (add: `pytest` already present; no new dependency for this phase)

**T-shirt:** M

---

### Phase B — Dashboard prototype: local Streamlit + DuckDB (M)

Rides on top of Phase A. Reads the same 5 sample artifacts + the 3 published snapshots, renders 4 views, no domain, no auth.

**Inputs:**
- Phase A deliverables (adapter + tests passing)
- `docs/visualization/architecture.md` (core views section)
- `docs/orchestration/task-scheduling.md` (for the "System Health" view content)

**Deliverables:**

| File | Purpose |
|------|---------|
| `src/pmbrs/dashboard/app.py` | Streamlit entry point |
| `src/pmbrs/dashboard/views/timeline.py` | Timeline view (artifact count over time, by source) |
| `src/pmbrs/dashboard/views/modality.py` | Modality Explorer (per-source breakdown of payload kinds) |
| `src/pmbrs/dashboard/views/health.py` | System Health (last publish, last ingest, schedule state, pending-queue size, checkpoint age) |
| `src/pmbrs/dashboard/views/experiments.py` | Experiments stub (reads `state/` if experiments artifacts exist; placeholder otherwise) |
| `scripts/pmbrs_dashboard.py` | thin wrapper: `python scripts/pmbrs_dashboard.py` → launches Streamlit on `:8501` |
| `requirements.txt` (add) | `streamlit>=1.35`, `duckdb>=0.11`, `pandas>=2.1`, `altair>=5.3` |

**Acceptance criteria:**

- [ ] `python scripts/pmbrs_dashboard.py` launches Streamlit at `http://127.0.0.1:8501` with no other services needed.
- [ ] **Timeline view** shows one card per source (`mobile`, `browser`, `desktop`, `journal`, `other`) with artifact count + min/max timestamp + latest 5 artifact IDs.
- [ ] **Modality explorer** shows a dropdown per source; selecting one renders the JSON payload of the most recent artifact as pretty-printed code.
- [ ] **System Health** shows: last `pmbrs_summary_*.json` publish time, `last_run_at_epoch_ms` from `scheduler_state.json`, pending-queue count (0 is fine), and the 3 most recent checkpoint filenames.
- [ ] **Experiments view** renders "no experiment artifacts yet" unless `checkpoints/` or `raw/` contains an artifact with `module == "experiment"` (none of the 5 samples do → the placeholder text renders).
- [ ] No write path exists in the Streamlit app: the adapter is opened in read-only mode (enforced by wrapping `StorageAdapter` with a `ReadonlyAdapter` that raises on `save/derive_from/mark_module_complete`).
- [ ] All views render from `~/.pmbrs-private/` via the adapter (no direct file paths in the Streamlit code).
- [ ] The `requirements.txt` additions resolve with `pip install -r requirements.txt` and `pytest` still passes.

**Verification:** after starting the dashboard, open `http://127.0.0.1:8501` in a browser, click through the 4 views, and confirm the 5 sample artifacts appear in the Timeline + Modality views.

**Files to touch / create:**
- `src/pmbrs/dashboard/__init__.py` (new)
- `src/pmbrs/dashboard/app.py` (new)
- `src/pmbrs/dashboard/views/__init__.py` (new)
- `src/pmbrs/dashboard/views/timeline.py` (new)
- `src/pmbrs/dashboard/views/modality.py` (new)
- `src/pmbrs/dashboard/views/health.py` (new)
- `src/pmbrs/dashboard/views/experiments.py` (new)
- `scripts/pmbrs_dashboard.py` (new)
- `requirements.txt` (add 4 new deps)

**T-shirt:** M

---

### Phase C — Dashboard on the domain route (L)

Same Streamlit app, but:

- Served behind the existing `mobile-sync.jjrdev.com` reverse proxy.
- On a dedicated route prefix (`/dashboard/`) and an API prefix (`/api/v1/dashboard/*`).
- Authenticated at the domain edge (session auth).
- AuthZ is **read-only** for the dashboard role (enforced in the adapter read-only wrapper, not by convention).

**Inputs:**
- Phase B deliverables
- Domain admin access (`jjrdev@jjrdev.com`, `mobile-sync.jjrdev.com`)
- Decision on auth mechanism (see Open Questions Q5)

**Deliverables:**

| File | Purpose |
|------|---------|
| `src/pmbrs/dashboard/auth.py` | Session middleware, role check, CSRF token |
| `src/pmbrs/dashboard/api.py` | FastAPI app (read-only endpoints) serving the same data as the Streamlit views |
| `src/pmbrs/dashboard/proxy.toml` (or `nginx` config snippet) | Route-level config for the reverse proxy |
| `scripts/pmbrs_dashboard_serve.py` | Production entry: FastAPI + Streamlit behind one process (or two, per domain-edge preference) |
| `tests/test_dashboard_auth.py` | Role + route isolation tests |
| `docs/runbooks/dashboard-on-domain.md` | Runbook: how to deploy, rotate the session secret, roll back |

**Acceptance criteria:**

- [ ] `https://mobile-sync.jjrdev.com/dashboard/` loads the same 4 views as Phase B — from the browser, with a login screen first.
- [ ] `https://mobile-sync.jjrdev.com/api/v1/dashboard/timeline?source=mobile` returns the same JSON the Streamlit view renders, with the session cookie.
- [ ] The Android sync endpoint POST (`/api/v1/artifacts/sync`) is **not affected**: it still accepts the existing 8-field payload, and the `dashboard` role **cannot** reach it (route isolation + authZ).
- [ ] A `curl` without the session cookie on `/dashboard/` gets a 401 (redirect to login) or 403.
- [ ] A `curl` on `/api/v1/dashboard/timeline` with the Android device token (if any) gets 403 — the dashboard role and the device role are distinct.
- [ ] HTTPS enforced (no plaintext HTTP on any dashboard route).
- [ ] The Streamlit local instance (Phase B) still works — the dashboard code is the **same** regardless of how it is hosted (§16 escape hatch).

**Verification:** from the browser, log in, click through the 4 views. From the terminal, `curl -I https://mobile-sync.jjrdev.com/dashboard/` → 302 → 200 after login. `curl https://mobile-sync.jjrdev.com/api/v1/artifacts/sync` with the Android device token still works (write path isolated).

**Files to touch / create:**
- `src/pmbrs/dashboard/auth.py` (new)
- `src/pmbrs/dashboard/api.py` (new)
- `scripts/pmbrs_dashboard_serve.py` (new)
- `tests/test_dashboard_auth.py` (new)
- `docs/runbooks/dashboard-on-domain.md` (new)
- Domain edge config (nginx reverse proxy on `mobile-sync.jjrdev.com`)
- `requirements.txt` (add: `fastapi`, `uvicorn`, `jose` or `authlib`, `passlib[bcrypt]`)

**T-shirt:** L

---

### Phase D — Training pipeline stub (M)

Implements the "training stub" that ADR-017 D3 requires: nightly (passover) is already exercised by the existing `pmbrs_runtime.run_cycle` + `pmbrs_publish_summary_to_hermes.sh` — this phase adds the *weekly* and *monthly* training entries.

**Inputs:**
- Phase A deliverables (adapter)
- `docs/representation/training-pipeline.md` (batch-first training loop spec)
- `docs/representation/model-selection.md` (proxy evaluation suite — ADR-011/015)
- `docs/representation/feature-configuration.md` (feature set, ADR-013)
- The cadence split from ADR-017 D3
- Decision on the experiment tracker (W&B vs MLflow) — see Open Questions Q3

**Deliverables:**

| File | Purpose |
|------|---------|
| `src/pmbrs/representation/__init__.py` | package init |
| `src/pmbrs/representation/model.py` | behavioral embedding model definition (e.g. a small Transformer or MLP over the feature vectors) |
| `src/pmbrs/representation/train.py` | training loop (weekly incremental, monthly full) |
| `src/pmbrs/representation/evaluate.py` | proxy-eval suite + rollback gate (`embedding_evaluation_report`) |
| `src/pmbrs/representation/checkpoint.py` | checkpoint save/load (warm-start from prior run) |
| `src/pmbrs/representation/runner.py` | CLI: `pmbrs-train --cadence {weekly, monthly, on-demand}` |
| `tests/test_representation_stub.py` | training stub tests (runs the model once on the 5 sample artifacts, verifies checkpoint shape) |
| `requirements.txt` (add) | `torch` or `lightning` (pick one), `scikit-learn`, the chosen experiment tracker |

**Acceptance criteria:**

- [ ] `python -m pmbrs.representation.runner --cadence weekly --dry-run` runs the training loop once, produces a checkpoint under `~/.pmbrs-private/checkpoints/`, and writes an `embedding_evaluation_report` artifact.
- [ ] The report artefact contains (at minimum): model_id, feature_version, n_artifacts, n_epochs, loss, a small proxy-eval metric (e.g. silhouette on the embeddings vs source labels), and a `pass` / `fail` gate verdict.
- [ ] `--cadence monthly` performs a cold-start full retrain (no warm start) and produces the same report shape.
- [ ] `--cadence weekly` performs a warm-start incremental (resumes from the most recent checkpoint) when a prior checkpoint exists.
- [ ] If the evaluation gate **fails** (the model's embedding on the current window diverges beyond threshold), the runner refuses to write a new `behavioral_embedding` artifact and logs the failure (rollback semantics).
- [ ] All training runs are grouped by `(run_date, cadence, model_id)` in the chosen experiment tracker.
- [ ] `pytest tests/test_representation_stub.py -v` passes.
- [ ] No network call to any experiment tracker happens when `--local` is passed (privacy: run fully offline).

**Verification:** after `--cadence weekly --dry-run`, confirm the checkpoint file exists under `~/.pmbrs-private/checkpoints/pmbrs_embedding_weekly_<timestamp>/`, and the `embedding_evaluation_report` artifact is recorded against the training run (via the tracker or the local checkpoint directory).

**Files to touch / create:**
- `src/pmbrs/representation/__init__.py` (new)
- `src/pmbrs/representation/model.py` (new)
- `src/pmbrs/representation/train.py` (new)
- `src/pmbrs/representation/evaluate.py` (new)
- `src/pmbrs/representation/checkpoint.py` (new)
- `src/pmbrs/representation/runner.py` (new)
- `tests/test_representation_stub.py` (new)
- `requirements.txt` (add ML deps)

**T-shirt:** M

---

### Phase E — Documentation closeout (S)

The four doc items that ADR-017 surfaced should be resolved in the same PR as Phase A-D land.

| Item | Status | Change |
|------|--------|--------|
| `docs/representation/training-pipeline.md` | says "nightly or weekly" | update to "nightly passover / weekly incremental / monthly full retrain" (per ADR-017 D3) |
| `docs/adr/ADR-010` (Storage Layout) | referenced as "pending" in `PROJECT_SUMMARY.md` and `index.md` | either (a) write ADR-010 closing it and citing ADR-017 D2 as the constraint, or (b) update `PROJECT_SUMMARY.md` + `index.md` to say "pending, constrained by ADR-017 D2" — user chooses |
| `mobile-event-dashboard/.hermes.md` | still says "FastAPI-based event management with 15+ API endpoints" | leave as-is; the pattern is the point, and the user explicitly said it's a prior artifact |
| `requirements.txt` | currently only `pytest>=7.0` | gets extended across Phases B/C/D — final shape listed below |

**Acceptance criteria:**
- [ ] `grep -riE "nightly|weekly|monthly" docs/` returns the D3 split only (no "nightly or weekly" left over).
- [ ] `docs/index.md` and `docs/PROJECT_SUMMARY.md` ADR-010 status is consistent (either "closed, see ADR-017 D2" or "pending, constrained by ADR-017 D2").
- [ ] `requirements.txt` contains the union of dependencies added in Phases B, C, D.

**Final `requirements.txt` shape (expected):**
```
# Core
pytest>=7.0

# Phase A — StorageAdapter
# (no new deps; stdlib + dataclasses only)

# Phase B — Dashboard prototype
streamlit>=1.35
duckdb>=0.11
pandas>=2.1
altair>=5.3

# Phase C — Domain hosting
fastapi>=0.110
uvicorn[standard]>=0.29
authlib>=1.3
passlib[bcrypt]>=1.7
cryptography>=42.0

# Phase D — Training loop
# (pick one: "lightning" or "torch>=2.2" — recommend lightning)
lightning>=2.2
scikit-learn>=1.4
# (experiment tracker — DECIDED Q2: MLflow, self-hosted single-binary
#  `mlflow server`, reachable via the user's Cloudflare tunnel → jjrdev.com;
#  free + local, satisfies §16. `--local` still allows fully-offline runs.)
mlflow>=2.11
```

The tracker is decided (Q2: MLflow self-hosted). Phase D can start as soon as
Phase A's `StorageAdapter` is green.

---

### Phase F — End-to-end acceptance (S)

The final proof that the whole system works together.

**Checklist:**

- [ ] Start the local dashboard (`python scripts/pmbrs_dashboard.py`), log in (if local auth is on), and walk through all 4 views. All 5 sample artifacts + 3 published snapshots are visible.
- [ ] From a separate machine, reach `https://mobile-sync.jjrdev.com/dashboard/` and log in. Same 4 views, same data.
- [ ] Confirm the Android `POST /api/v1/artifacts/sync` still works (send one test artifact, confirm it lands in `~/.pmbrs-private/store/raw/mobile/` and the dashboard Timeline view picks it up on refresh).
- [ ] Confirm the dashboard role **cannot** reach the sync endpoint (403 / 405).
- [ ] Run `python -m pmbrs.representation.runner --cadence weekly --dry-run --local`. Confirm the checkpoint + evaluation report are recorded.
- [ ] Run `pytest tests/ -v` — all green.
- [ ] Confirm `~/.pmbrs-private/hermes-readonly/pmbrs_summary.json` is `chmod 444` and the dashboard does not modify it.

**T-shirt:** S (it's the verification step, not new work)

---

## 4. Sequencing & parallelism

```
Phase A (StorageAdapter)                [M]   — blocking; must land first
   |
   +— Phase B (Dashboard local)         [M]   — depends on A
   |     |
   |     +— Phase C (Dashboard domain)  [L]   — depends on B; can overlap with D
   |
   +— Phase D (Training stub)           [M]   — depends on A; parallel with B/C
   |
   +— Phase E (Doc closeout)            [S]   — runs alongside A-D; closes at the end
   |
   +— Phase F (End-to-end acceptance)   [S]   — last step, gates the milestone
```

A single engineer can finish A → B → E in the first pass (1–2 days), then A → D in parallel with B → C (2–3 days), then F (half a day). Total: **~4–6 days of work** for a single developer, assuming no blockers.

For the user + Hermes working together, the natural split is:

| Phase | Owner | Notes |
|-------|-------|-------|
| A | **Hermes** (me) | The adapter is straightforward; I can write it and the tests in one pass. |
| B | **Hermes** | Streamlit views + DuckDB; I can write and run locally. |
| C | **User + Hermes** | Domain edge + auth + route config; needs your access to the reverse proxy. |
| D | **Hermes** | `lightning` training loop; I can scaffold and test. |
| E | **Hermes** | Doc patches; mechanical after A-D land. |
| F | **User** (verification) + **Hermes** (support) | You click through, I fix what's broken. |

---

## 5. Open questions — ANSWERED (2026-08-19)

| # | Question | Decision |
|---|----------|----------|
| Q1 | **ADR-010 status** | ✅ **Closed** — written as `adr/ADR-010.md` (Superseded by ADR-017 D2); `PROJECT_SUMMARY.md` + `index.md` updated. |
| Q2 | **Experiment tracker** | ✅ **MLflow, self-hosted** — run as a local single-binary (`mlflow server`), reachable through the user's **Cloudflare tunnel → `jjrdev.com` domain**. Chosen because it is free + local (satisfies §16) yet still "cloud-and-easy" from the browser via the tunnel. `requirements.txt` pins `mlflow>=2.11`. `--local` flag still allows fully-offline runs with no tracker contact. |
| Q3 | **Dashboard auth** | ✅ **Keep the existing passcode + cookie/IP remembrance for now** — the user has a working-but-weak passcode in place. Hardening is a **deferred sub-step of Phase C** (documented), not a blocker to the local dashboard (Phase B) or to wiring Phase C's route. A later pass adds: constant-time compare, secret rotation, IP allow-list, expiry. |
| Q4 | **Reverse proxy access** | ✅ **User has access** — setup is a **local proxy + Cloudflare tunnel** on their domain. When Phase C starts, the user will hand Hermes **write access to the relevant config file**. Phase C is therefore unblocked, pending that handoff. |
| Q5 | **Local dashboard port** | ✅ Streamlit default `8501` (no conflict reported). |

---

## 6. Risks & mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| `StorageAdapter` grows to a general ORM (scope creep) | M | Acceptance criteria in Phase A are explicit and narrow; the protocol from `docs/module-contracts.md` is the source of truth, not my design |
| Streamlit is single-session by default | M | §16 is single-user; if multi-user becomes a need, the Phase C FastAPI read-side API is already there |
| DuckDB + 5 JSON files is slow | L | 5 files is trivial; at 100K+ files the adapter's batch reader becomes the optimization (DuckDB `read_json_auto` over a directory) |
| Android app sync client currently has no auth token (just a URL) | M | Phase C is read-side only; the Android write path is unaffected by the dashboard auth |
| `lightning` install fails on the local env | L | Fallback is raw `torch`; the abstraction is small enough to swap |
| `mobile-sync.jjrdev.com` reverse proxy is not reachable from my sandbox | L | Phase C is blocked if Q4's answer is "no"; Phases A, B, D, E still proceed |

---

## 7. What I will NOT do without a green light

- No code for Phase A (StorageAdapter) — **waiting for your "write A" or equivalent**.
- No changes to `mobile-event-dashboard/` (it's a pattern-borrow, not a substrate).
- No `pip install` of any new package (Streamlit, DuckDB, FastAPI, lightning) — that only happens when the corresponding phase starts.
- No changes to the Android app.
- No writes outside `/home/jjrdev/workspace/pmbrs/` (and, for Phase C, not even outside the repo until the reverse-proxy config is explicitly approved).

---

## 8. What I can do RIGHT AFTER you answer the open questions

If you say "yes, go":

1. **Phase A** — I write the adapter + tests in one message, run `pytest`, report green/red.
2. **Phase B** — I write the Streamlit app + 4 views, `pip install` the deps, launch the dashboard, and report a `MEDIA:\u003cscreenshot\u003e` of each view.
3. **Phase E** — I patch the 2 doc lines (training-pipeline wording, ADR-010 status), report the diff.
4. **Phase D** — I scaffold the training stub + tests, run one dry-run, report the checkpoint + eval report.
5. **Phase C** — depends on your reverse-proxy access (Q4).

That's the whole plan, in this order, with acceptance criteria at every phase.
