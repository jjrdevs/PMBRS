"""Overview — the "at-a-glance" home view (Phase B.2).

The first thing a solo deep-work user asks is *"what happened, and is the
pipeline healthy?"* — not *"how is the store laid out?"* This view answers
that in one screen:

* top-line metrics: total artifacts, sources active, last activity (relative),
  latest training verdict (pass/fail, colour);
* a 14-day activity histogram (when you were active, at a glance);
* a "recent runs" list from the Phase-D reports.

Read-only; honors the global filter (sources / time window).
"""

from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Any

from pmbrs.dashboard.views import (
    active_filter,
    filter_artifacts,
    is_report,
    rel_time,
    verdict_of,
)


def _day_key(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%d")


def collect(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Top-line dashboard facts + a 14-day activity histogram (UTC days)."""
    artifacts = filter_artifacts(adapter.query(), filters)
    now_ms = int(time.time() * 1000)
    now = datetime.fromtimestamp(now_ms / 1000.0, tz=timezone.utc)

    total = len(artifacts)
    sources_active = {
        str(getattr(a, "source", "")).strip().lower()
        for a in artifacts
        if str(getattr(a, "source", "")).strip().lower()
    }

    last_activity_ms = max(
        (int(getattr(a, "created_at_epoch_ms", 0) or 0) for a in artifacts),
        default=None,
    )

    # 14-day histogram (UTC days).
    bin_ms = 86400 * 1000
    start_day = (now_ms // bin_ms - 13) * bin_ms
    bins = {day: 0 for day in range(14)}
    for a in artifacts:
        ms = int(getattr(a, "created_at_epoch_ms", 0) or 0)
        idx = (ms // bin_ms) - (start_day // bin_ms)
        if 0 <= idx < 14:
            bins[idx] += 1

    # recent Phase-D runs (reports), newest first, top 5.
    reports = [a for a in artifacts if is_report(a)]
    reports.sort(key=lambda a: int(getattr(a, "created_at_epoch_ms", 0) or 0), reverse=True)
    recent_runs = []
    for r in reports[:5]:
        payload = r.payload or {}
        recent_runs.append(
            {
                "verdict": (verdict_of(r) or "unknown").lower(),
                "cadence": payload.get("cadence"),
                "final_loss": payload.get("final_loss"),
                "created_at_epoch_ms": int(getattr(r, "created_at_epoch_ms", 0) or 0),
                "rel": rel_time(int(getattr(r, "created_at_epoch_ms", 0) or 0)),
            }
        )

    latest_verdict = recent_runs[0]["verdict"] if recent_runs else None

    # 14-day series for the chart (human labels).
    histogram = []
    for idx in range(14):
        day_ms = start_day + idx * bin_ms
        dt = datetime.fromtimestamp(day_ms / 1000.0, tz=timezone.utc)
        histogram.append({
            "day": _day_key(dt),
            "label": dt.strftime("%m-%d"),
            "count": bins[idx],
            "dt_ms": day_ms,
        })

    return {
        "total_artifacts": total,
        "sources_active": sorted(sources_active),
        "n_sources_active": len(sources_active),
        "last_activity_ms": last_activity_ms,
        "last_activity_rel": rel_time(last_activity_ms) if last_activity_ms else "—",
        "latest_verdict": latest_verdict,
        "recent_runs": recent_runs,
        "histogram": histogram,
        "filtered": active_filter(filters),
    }


def render(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Paint the Overview home; returns collected data (assertable)."""
    import streamlit as st

    data = collect(adapter, filters)
    scope = "· filtered" if data["filtered"] else ""
    st.title(f"PMBRS Overview{scope}")
    st.caption("What happened, and whether the pipeline is healthy — at a glance.")

    cols = st.columns(4)
    with cols[0]:
        st.metric("Total artifacts", data["total_artifacts"])
    with cols[1]:
        st.metric(
            "Sources active",
            data["n_sources_active"],
            help=", ".join(data["sources_active"]) or "none",
        )
    with cols[2]:
        st.metric("Last activity", data["last_activity_rel"])
    with cols[3]:
        verdict = data["latest_verdict"]
        if verdict == "pass":
            st.metric("Latest training", "🟢 pass")
        elif verdict == "fail":
            st.metric("Latest training", "🔴 fail")
        else:
            st.metric("Latest training", "—", delta="no runs yet")

    # 14-day activity histogram.
    st.markdown("##### Activity — last 14 days")
    if any(b["count"] for b in data["histogram"]):
        import altair as alt
        import pandas as pd

        df = pd.DataFrame(
            [{
                "dt_ms": b["dt_ms"],
                "label": b["label"],
                "count": b["count"],
            } for b in data["histogram"]]
        )
        chart = (
            alt.Chart(df)
            .mark_bar()
            .encode(
                x=alt.X(
                    "label:N",
                    sort=[b["dt_ms"] for b in data["histogram"]],
                    title="day",
                ),
                y=alt.Y("count:Q", title="artifacts"),
                tooltip=["label", "count"],
            )
            .properties(height=200)
        )
        st.altair_chart(chart, width="stretch")
    else:
        st.info("No activity in the last 14 days that matches the current filter.")

    st.divider()

    # recent runs.
    st.markdown("##### Recent training runs")
    if data["recent_runs"]:
        for run in data["recent_runs"]:
            badge = {"pass": "🟢", "fail": "🔴"}.get(run["verdict"], "⚪")
            st.markdown(
                f"{badge} **{run['verdict'] or 'unknown'}**  ·  "
                f"{run['cadence'] or '—'} cadence  ·  "
                f"loss {run['final_loss'] if run['final_loss'] is not None else '—'}  ·  {run['rel']}"
            )
    else:
        st.caption("No Phase-D training runs recorded yet.")

    # sources active (compact).
    if data["sources_active"]:
        st.caption(
            "Active sources: " + " · ".join(f"`{s}`" for s in data["sources_active"])
        )
    return data
