"""Experiments — real Phase-D training runs (Phase B.2).

Primary source is the **actual** representation pipeline output
(``src/pmbrs/representation``), which writes two artifact types per run,
kept together by their ``run_id`` (lineage / rollback):

* ``derived.embedding_evaluation_report`` — ``verdict`` (pass/fail),
  ``final_loss``, ``coherence``/``diversity``, ``cadence``, ``backend``,
  ``warm_start``, ``embedding_dim``.
* ``derived.behavioral_embedding`` — written **only on pass** (rollback gate);
  ``n_windows``, ``embedding_dimension``.

Phase B.2 pairs a report with its embedding by ``run_id`` and renders each run
with a colour-coded verdict; the payload is inspectable behind an expander.
The legacy "detect `payload.kind == 'experiment'`" behaviour (Phase B) is kept
as a small fallback section, so artifacts hand-marked as experiments still show.
"""

from __future__ import annotations

from typing import Any

from pmbrs.dashboard.views import (
    is_embedding,
    is_report,
    payload_kind_of,
    run_id,
    verdict_of,
)

REPORT_TYPE = "derived.embedding_evaluation_report"
EMBEDDING_TYPE = "derived.behavioral_embedding"
LEGACY_MARKER = "experiment"  # Phase B fallback (kept for backward-compat).
EXPERIMENT_MARKER = LEGACY_MARKER  # public alias (existing tests reference this).


# ---------------------------------------------------------------------------
# Collection
# ---------------------------------------------------------------------------


def _pair_run(report: Any, embeddings: list[Any]) -> dict[str, Any]:
    """Assemble a single Phase-D run record from its report + (<=1) embedding."""
    payload = report.payload or {}
    embedding = embeddings[0] if embeddings else None
    epayload = (embedding.payload or {}) if embedding is not None else {}
    verdict = (verdict_of(report) or "").lower()
    return {
        "run_id": run_id(report) or report.artifact_id,
        "report_id": report.artifact_id,
        "embedding_id": embedding.artifact_id if embedding is not None else None,
        "created_at_epoch_ms": int(getattr(report, "created_at_epoch_ms", 0) or 0),
        "verdict": verdict or "unknown",
        "cadence": payload.get("cadence"),
        "backend": payload.get("backend"),
        "model_id": payload.get("model_id"),
        "feature_version": payload.get("feature_version"),
        "n_artifacts": payload.get("n_artifacts"),
        "n_epochs": payload.get("n_epochs"),
        "final_loss": payload.get("final_loss"),
        "quality_metrics": payload.get("quality_metrics"),
        "checks": payload.get("checks"),
        "warm_start": payload.get("warm_start"),
        "embedding_committed": embedding is not None,
        "n_windows": epayload.get("n_windows"),
        "embedding_dim": epayload.get("embedding_dimension") or payload.get("quality_metrics", {}).get("embedding_dim"),
        "report_payload": payload,
        "embedding_payload": epayload,
    }


def collect(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Pair Phase-D reports with their embeddings into run records."""
    from pmbrs.dashboard.views import filter_artifacts

    artifacts = filter_artifacts(adapter.query(), filters)

    reports = [a for a in artifacts if is_report(a)]
    embeddings = [a for a in artifacts if is_embedding(a)]
    emb_by_run: dict[str, list[Any]] = {}
    for e in embeddings:
        rid = run_id(e)
        emb_by_run.setdefault(rid or e.artifact_id, []).append(e)

    runs = [_pair_run(r, emb_by_run.get(run_id(r) or r.artifact_id, [])) for r in reports]
    runs.sort(key=lambda r: r["created_at_epoch_ms"], reverse=True)

    # Legacy Phase-B fallback: artifacts hand-marked with payload.kind=='experiment'.
    legacy = [
        {
            "artifact_id": a.artifact_id,
            "source": a.source,
            "created_at_epoch_ms": int(getattr(a, "created_at_epoch_ms", 0) or 0),
            "kind": payload_kind_of(a),
            "payload": a.payload,
        }
        for a in artifacts
        if str(payload_kind_of(a)).lower() == LEGACY_MARKER
        and not (is_report(a) or is_embedding(a))
    ]
    legacy.sort(key=lambda r: r["created_at_epoch_ms"], reverse=True)

    return {
        "run_count": len(runs),
        "runs": runs,
        "pass_count": sum(1 for r in runs if r["verdict"] == "pass"),
        "fail_count": sum(1 for r in runs if r["verdict"] == "fail"),
        "latest_verdict": runs[0]["verdict"] if runs else None,
        "legacy": legacy,
        "legacy_count": len(legacy),
    }


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------


def render(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Paint the real training runs + the legacy fallback; returns data."""
    import streamlit as st

    data = collect(adapter, filters)
    st.subheader("Experiments — representation training runs")
    st.caption(
        "Read from the Phase-D `derived.*` artifacts (rollback-gated). "
        "`behavioral_embedding` is committed only when the evaluation gate passes."
    )

    if data["run_count"] == 0:
        st.info("No Phase-D training runs in the store yet (run `pmbrs.representation.runner`).")
    else:
        cols = st.columns(3)
        cols[0].metric("Runs", data["run_count"])
        cols[1].metric("Pass", data["pass_count"], delta=None)
        cols[2].metric("Fail", data["fail_count"], delta=None)
        st.divider()

        for i, run in enumerate(data["runs"]):
            verdict = run["verdict"]
            if verdict == "pass":
                badge = "🟢 PASS"
            elif verdict == "fail":
                badge = "🔴 FAIL"
            else:
                badge = "⚪ UNKNOWN"
            with st.expander(
                f"{badge}  ·  {run.get('cadence') or '—'} cadence  ·  "
                f"loss {run.get('final_loss') if run.get('final_loss') is not None else '—'}  ·  "
                f"{'warm-start' if run.get('warm_start') else 'cold-start'}  ·  run #{len(data['runs'])-i}",
                expanded=(i == 0),
            ):
                left, right = st.columns(2)
                with left:
                    st.markdown("**Evaluation report**")
                    st.write(
                        f"- model: `{run.get('model_id')}`  \n"
                        f"- feature_version: `{run.get('feature_version')}`  \n"
                        f"- backend: `{run.get('backend')}`  \n"
                        f"- artifacts: {run.get('n_artifacts')}  ·  epochs: {run.get('n_epochs')}  \n"
                        f"- **final_loss**: {run.get('final_loss')}  \n"
                        f"- quality: {run.get('quality_metrics')}"
                    )
                    checks = run.get("checks") or {}
                    for name, chk in checks.items():
                        ok = bool(chk.get("passed", True))
                        mark = "✅" if ok else "❌"
                        st.caption(
                            f"{mark} {name}: {chk.get('value')} "
                            f"(threshold {chk.get('threshold')})"
                        )
                with right:
                    st.markdown("**Rollback gate**")
                    if run.get("embedding_committed"):
                        st.success(
                            f"🟢 `behavioral_embedding` committed "
                            f"({run.get('n_windows')} windows × {run.get('embedding_dim')}d)"
                        )
                    else:
                        st.warning("🔴 embedding withheld (gate failed) — report only.")
                    st.caption(f"report: `{run.get('report_id')}`")
                    if run.get("embedding_id"):
                        st.caption(f"embedding: `{run.get('embedding_id')}`")
                    if data["legacy_count"] == 0 and i < data["run_count"]:
                        with st.expander("Raw report JSON"):
                            st.json(run.get("report_payload"))
                st.divider()

    # -- legacy Phase-B fallback (hand-marked experiments) ----------------
    if data["legacy_count"] > 0:
        st.markdown("### Legacy experiment-marked artifacts")
        for row in data["legacy"]:
            st.markdown(f"- `{row['artifact_id']}` (source `{row['source']}`, kind `{row['kind']}`)")
            with st.expander("payload"):
                st.json(row["payload"])
    return data
