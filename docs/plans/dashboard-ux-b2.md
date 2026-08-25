# PMBRS Dashboard — UI/UX Review & Change Plan (Phase B.2)

Date: 2026-08-19 · Scope: `src/pmbrs/dashboard/**` (Phase B dashboard) only.
Read-only, local-first constraints (Constitution §16) are preserved — this is a
presentation-layer refactor, not new store access.

## Why
Phase B shipped a correct **data** layer (read-only, adapter-first) but an
**inspector-first UI**: it surfaces store mechanics (artifact IDs, raw
epoch-ms, "reads go through StorageAdapter.query") before user value. For a
solo deep-work tool the hierarchy is inverted. Phase B.2 fixes hierarchy,
filters, semantics, and — importantly — wires the Experiments view to the
**real** Phase D training pipeline, which Phase B's placeholder does not do.

## Findings (evidence-based)
| # | Severity | Finding |
|---|----------|---------|
| 1 | 🔴 | No Overview/home: first screen is a `st.radio` into Timeline. "What happened + is it healthy?" needs 3 views to compose. |
| 2 | 🔴 | `experiments.py` detects `payload.kind=='experiment'`, but Phase D writes `payload.artifact_type=='derived.embedding_evaluation_report'` / `'derived.behavioral_embedding'` → real training runs show **nothing** here. |
| 3 | 🔴 | No semantic status (green/amber/red); pipeline liveness + pass/fail are plain-text deltas. |
| 4 | 🔴 | No filters (none of: time range, source, kind). |
| 5 | 🟠 | Raw epoch-ms axis on the chart; absolute UTC strings instead of relative/local time. |
| 6 | 🟠 | `modality.py` renders the same payload **twice** (`st.json` + `st.code` of `json.dumps`). |
| 7 | 🟠 | Timeline's "Latest 5 ids" code block is the visual focal point — debug noise as hero. |
| 8 | 🟠 | Modality Explorer is a picker dumping one payload, not a "what happened where" matrix. |
| 9 | 🟡 | `st.columns(5)` not responsive; no view icons; no last-updated hint; dev captions leak. |

Design intent (user): **hierarchy of information** (value first, mechanics
second), **filters** (time/source/kind), and **user intent** (a solo person
tracking their own behavior + knowing the pipeline is healthy).

## Plan (in execution order)
1. **`views/__init__.py`** — add shared helpers: `rel_time()` (relative time),
   `local_iso()` (local tz + human), `filter_artifacts()` (sources + time range +
   kind), `status_of()` → `("ok"|"warn"|"err"|"none", label)`, `VERDICT_COLORS`.
2. **`overview.py`** (new) — home: top-line metrics (total artifacts, sources
   active, last activity relative, latest training verdict), a 14-day activity
   histogram, and a "recent runs" list derived from Phase D reports.
3. **`app.py`** — Overview becomes the **first** view; global sidebar filters
   (sources multi-select + time-range quick-picks + "all") stored in
   `st.session_state` and passed to every view; trim dev captions.
4. **`timeline.py`** — relative + local time, human-readable (time-based) chart
   axis, demote raw IDs to a collapsed "details" block, honor global filters.
5. **`modality.py`** — modality×kind **matrix** (count table) as the hero,
   selectable (source, kind) row → single `st.json` of the newest matching
   payload (remove the redundant double render), honor filters.
6. **`health.py`** — color-coded metrics (`st.metric` deltas + color text),
   new **"Model / Training"** card from the latest Phase D report
   (verdict, final_loss, coherence/diversity, run cadence, backend), honor
   read-only roots.
7. **`experiments.py`** — **primary** source = real Phase D runs: pair
   `derived.embedding_evaluation_report` + `derived.behavioral_embedding`
   artifacts by `run_id`; show verdict (pass/fail color), metrics, cadence,
   backend, warm_start, embedding dim, n_windows; click a run → payload. Keep
   the old `kind=='experiment'` detection as a **fallback** section (still
   tested by existing smoke test).
8. **Tests** — extend `StreamlitStub` (`error`, `success`, `selectbox` with
   `index`, `data_editor`/`dataframe`) and smoke tests: overview collect,
   filter behavior (time/source), experiments reading real Phase D report shapes,
   model-run pairing, modality matrix.
9. **Verify** — full `pytest -q` green; headless `collect()` of every view
   against the real store; `streamlit run` health-check HTTP 200.

## Non-goals / preserved
- No store writes anywhere (read-only §16).
- No auth/domain (that's Phase C).
- No MLflow UI (self-hosted tracker is a separate surface).
- Existing `collect()`→dict + `render()`→dict contract is kept (assertable).

## Open decision (user)
Relative time defaults to the viewer's local timezone and "now" = server clock.
If you'd rather pin UTC or your specific tz offset, say so and I'll change the
helper. Everything else I'm proceeding with.
