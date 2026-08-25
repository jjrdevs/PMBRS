"""System Health — pipeline liveness + latest Phase-D training status.

Shown (Phase B.2):

* **top-line metrics** with green / amber / red semantic colour:
  last summary publish, scheduler last run, pending queue, published snapshots.
* a **"Training (Phase D)"** card read from the latest Phase-D evaluation
  report: verdict (pass/fail, colour), final loss, coherence / diversity,
  backend, cadence, embedding committed?
* the 3 most recent checkpoint filenames.

Reads via the adapter's resolved roots (config owns the paths). Read-only.
"""

from __future__ import annotations

import json
import time
from typing import Any

from pmbrs.dashboard.views import format_epoch_ms, is_report, rel_time, run_id


def _read_json(path: Any) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def collect(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Gather health facts from the adapter-managed read-only state trees."""
    from pathlib import Path

    # -- last published summary snapshot ---------------------------------
    summary_root = Path(adapter.summary_root)
    last_publish: dict[str, Any] | None = None
    snapshot_count = 0
    if summary_root.exists():
        for path in sorted(summary_root.glob("pmbrs_summary_*.json")):
            snapshot_count += 1
            data = _read_json(path)
            if not isinstance(data, dict):
                continue
            generated = int(data.get("generated_at_epoch_ms") or 0)
            if last_publish is None or generated >= last_publish["generated_at_epoch_ms"]:
                last_publish = {
                    "file": path.name,
                    "generated_at_epoch_ms": generated,
                    "raw_file_count": data.get("raw_file_count"),
                    "mode": data.get("mode"),
                    "read_only": data.get("read_only"),
                }

    # -- scheduler state --------------------------------------------------
    scheduler_path = Path(adapter.state_root) / "scheduler_state.json"
    scheduler = _read_json(scheduler_path)
    now_ms = int(time.time() * 1000)
    last_run = int(scheduler.get("last_run_at_epoch_ms") or 0) if scheduler else None
    next_run = int(scheduler.get("next_run_at_epoch_ms") or 0) if scheduler else None
    # scheduler "ok" if we have a state file and either a next run is due or last run was recent (<= 7 days).
    scheduler_ok = (
        scheduler is not None
        and (
            (next_run is not None and next_run > now_ms)
            or (last_run is not None and (now_ms - last_run) <= 7 * 86400 * 1000)
        )
    )
    scheduler_state: dict[str, Any] = {
        "last_run_at_epoch_ms": last_run,
        "last_status": scheduler.get("last_status") if scheduler else None,
        "next_run_at_epoch_ms": next_run if scheduler else None,
        "last_checkpoint": scheduler.get("last_checkpoint") if scheduler else None,
        "present": scheduler is not None,
        "ok": scheduler_ok,
    }

    # -- pending queue ----------------------------------------------------
    pending_root = Path(adapter.pending_root)
    pending_files = sorted(pending_root.glob("*.json")) if pending_root.exists() else []
    pending = {"count": len(pending_files), "files": [p.name for p in pending_files[:5]]}

    # -- checkpoints (3 most recent by mtime) -----------------------------
    checkpoint_root = Path(adapter.checkpoint_root)
    checkpoints: list[str] = []
    if checkpoint_root.exists():
        checkpoint_files = [p for p in checkpoint_root.glob("*.json") if p.is_file()]
        checkpoint_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
        checkpoints = [p.name for p in checkpoint_files[:3]]

    # -- latest Phase-D training run --------------------------------------
    latest_report: dict[str, Any] | None = None
    for artifact in adapter.query():
        if not is_report(artifact):
            continue
        generated = int(getattr(artifact, "created_at_epoch_ms", 0) or 0)
        if latest_report is None or generated >= latest_report["generated_at_epoch_ms"]:
            payload = artifact.payload or {}
            qm = payload.get("quality_metrics") or {}
            latest_report = {
                "report_id": artifact.artifact_id,
                "run_id": run_id(artifact),
                "generated_at_epoch_ms": generated,
                "verdict": str(payload.get("verdict", "")).lower(),
                "final_loss": payload.get("final_loss"),
                "cadence": payload.get("cadence"),
                "backend": payload.get("backend"),
                "model_id": payload.get("model_id"),
                "n_artifacts": payload.get("n_artifacts"),
                "n_epochs": payload.get("n_epochs"),
                "warm_start": payload.get("warm_start"),
                "coherence": qm.get("coherence"),
                "diversity": qm.get("diversity"),
                "embedding_dim": qm.get("embedding_dim"),
            }

    return {
        "last_publish": last_publish,
        "snapshot_count": snapshot_count,
        "scheduler": scheduler_state,
        "pending": pending,
        "checkpoints": checkpoints,
        "training": latest_report,
    }


def render(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Paint the System Health view; returns the collected data (assertable)."""
    import streamlit as st

    data = collect(adapter, filters)
    st.subheader("System Health")

    # -- top-line status --------------------------------------------------
    publish = data["last_publish"]
    scheduler = data["scheduler"]

    def _col(value: bool | None, ok_color: str = "green", warn_color: str = "orange") -> str:
        if value is True:
            return ok_color
        if value is False:
            return warn_color
        return "gray"

    cols = st.columns(4)
    with cols[0]:
        if publish:
            st.metric(
                "Last summary publish",
                rel_time(publish["generated_at_epoch_ms"]),
                help=f"`{publish['file']}` · {format_epoch_ms(publish['generated_at_epoch_ms'])}",
            )
        else:
            st.metric("Last summary publish", "never")
    with cols[1]:
        last_run_rel = rel_time(scheduler["last_run_at_epoch_ms"]) if scheduler["present"] else "unknown"
        delta = (
            f"{scheduler['last_status']}" if scheduler["present"] else "no scheduler_state.json"
        )
        color = _col(scheduler["ok"], ok_color="green", warn_color="orange")
        st.markdown(
            f"##### Scheduler last run"
        )
        st.markdown(
            f"<span style='color:{color};font-weight:600'>{last_run_rel}</span>",
            unsafe_allow_html=True,
        )
        st.caption(delta or "—")
    with cols[2]:
        count = data["pending"]["count"]
        st.metric(
            "Pending queue",
            count,
            delta=None,
            help=f"{len(data['pending']['files'])} file(s) listed" if count else "clean",
        )
        if count > 0:
            st.markdown(
                f"<span style='color:orange;font-size:0.85em'>{count} pending — drain soon</span>",
                unsafe_allow_html=True,
            )
    with cols[3]:
        st.metric("Published snapshots", data["snapshot_count"])

    st.divider()

    # -- Phase-D training card -------------------------------------------
    training = data["training"]
    st.markdown("##### Phase-D Training")
    if not training:
        st.caption("No Phase-D evaluation report in the store yet.")
    else:
        verdict = training["verdict"]
        if verdict == "pass":
            badge, color = "🟢 PASS", "green"
        elif verdict == "fail":
            badge, color = "🔴 FAIL", "red"
        else:
            badge, color = "⚪ " + str(verdict).upper(), "gray"
        cells = st.columns(4)
        with cells[0]:
            st.markdown(f"**Verdict:** <span style='color:{color};font-weight:600'>{badge}</span>", unsafe_allow_html=True)
            st.caption(f"{training.get('cadence') or '—'} cadence  ·  {training.get('backend') or '—'}")
        with cells[1]:
            st.markdown(f"**Final loss:** `{training.get('final_loss')}`")
            st.caption(f"{training.get('n_artifacts')} artifacts  ·  {training.get('n_epochs')} epochs")
        with cells[2]:
            st.markdown(f"**Coherence / Diversity:** `{training.get('coherence')} / {training.get('diversity')}`")
            st.caption(f"embedding dim {training.get('embedding_dim')}")
        with cells[3]:
            st.markdown(f"**Warm start:** {training.get('warm_start')}")
            st.caption(f"run `{training.get('run_id') or training.get('report_id')}`")

    # -- checkpoints ------------------------------------------------------
    st.markdown("##### 3 most recent checkpoints")
    if data["checkpoints"]:
        st.code("\n".join(data["checkpoints"]), language="text")
    else:
        st.write(f"*No checkpoint files yet (scheduler references `{scheduler['last_checkpoint'] or '—'}`).*")

    if publish:
        st.caption(
            f"Last snapshot `{publish['file']}`: mode={publish['mode']}, read_only={publish['read_only']}, "
            f"raw_file_count={publish['raw_file_count']}"
        )
    return data
