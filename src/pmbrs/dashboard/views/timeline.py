"""Timeline view — human activity across sources (Phase B.2).

Value-first rework of Phase B (see ``docs/plans/dashboard-ux-b2.md``):

* shows *when things happened relative to now* ("3h ago"), with the local
  calendar date in the chart axis — not raw ``createdAtEpochMs``;
* honors the global filter (sources + time window);
* the artifact **IDs are demoted** to a collapsed "details" block instead of
  being the visual hero (they are debug, not insight).

Per source: artifact count, first→last activity (relative), and a time
histogram across the window.
"""

from __future__ import annotations

from typing import Any

from pmbrs.dashboard.views import (
    active_filter,
    filter_artifacts,
    latest_by_created,
    local_iso,
    rel_time,
    source_rows,
)


def collect(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Gather filtered per-source timeline stats for the canonical sources."""
    from pmbrs.core.storage import VALID_SOURCES

    grouped = source_rows(adapter)
    sources: dict[str, Any] = {}
    for source in ("mobile", "browser", "desktop", "journal", "other"):
        if source not in VALID_SOURCES:  # defensive: canonical set is fixed
            continue
        artifacts = filter_artifacts(grouped.get(source, []), filters)
        created = [a.created_at_epoch_ms for a in artifacts]
        newest = latest_by_created(artifacts, 5)
        sources[source] = {
            "count": len(artifacts),
            "min_created_at_epoch_ms": min(created) if created else None,
            "max_created_at_epoch_ms": max(created) if created else None,
            "first_rel": rel_time(min(created) if created else None),
            "last_rel": rel_time(max(created) if created else None),
            "latest_ids": [a.artifact_id for a in newest],
        }
    return {
        "sources": sources,
        "total_artifacts": sum(s["count"] for s in sources.values()),
        "filtered": active_filter(filters),
    }


def render(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Paint the Timeline view; returns the collected data (assertable in tests)."""
    import streamlit as st

    data = collect(adapter, filters)
    scope = "· filtered" if data["filtered"] else ""
    st.subheader(f"Timeline — activity across sources{scope}")
    st.caption(
        f"{data['total_artifacts']} artifact(s) across {len(data['sources'])} source(s) "
        "(times shown relative in your local timezone)."
    )
    if data["total_artifacts"] == 0:
        st.info("No artifacts match the current filter.")
        return data

    cards = st.columns(len(data["sources"]))
    for (source, stats), card in zip(data["sources"].items(), cards):
        with card:
            if stats["count"] == 0:
                st.metric(source, "0", "no activity")
                continue
            st.metric(
                source,
                f"{stats['count']}",
                f"last {stats['last_rel']}",
                help=f"first {stats['first_rel']}  ·  max {local_iso(stats['max_created_at_epoch_ms'])}",
            )

    # Time-based chart (human axis), one point per artifact.
    rows = [
        {
            "source": source,
            "created_at_local": local_iso(a.created_at_epoch_ms),
            "created_at_epoch_ms": int(a.created_at_epoch_ms),
        }
        for source, arts in source_rows(adapter).items()
        for a in filter_artifacts(arts, filters)
    ]
    if rows:
        import altair as alt
        import pandas as pd

        table = pd.DataFrame(rows)
        table["dt_ms"] = [int(r["created_at_epoch_ms"]) for r in rows]
        chart = (
            alt.Chart(table)
            .mark_circle()
            .encode(
                x=alt.X("dt_ms:T", title="time", axis=alt.Axis(format="%Y-%m-%d %H:%M")),
                y=alt.Y("source:N", sort=None, title="source"),
                color=alt.Color("source:N", legend=None),
            )
            .properties(height=240)
        )
        st.altair_chart(chart, width="stretch")

    # Raw IDs demoted into a collapsed details block (debug affordance).
    all_ids: list[str] = []
    for source, stats in data["sources"].items():
        all_ids.extend(stats["latest_ids"])
    if all_ids:
        with st.expander("Raw artifact IDs (last 5 per source)"):
            st.code("\n".join(all_ids), language="text")
    return data
