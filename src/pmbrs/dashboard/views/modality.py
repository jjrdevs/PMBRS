"""Modality Explorer — a modality×kind matrix (Phase B.2).

Replaces the old "picker that dumps one payload" with the question the data
actually answers at a glance: **which artifact kinds appear under which
source?** The matrix is the hero; selecting a cell pins the newest matching
payload into a single ``st.json`` (the Phase B duplicate render of the same
payload into ``st.json`` *and* ``st.code`` is gone).

Honor the global filter (sources / time window).
"""

from __future__ import annotations

from typing import Any

from pmbrs.dashboard.views import (
    active_filter,
    filter_artifacts,
    payload_kind_of,
    rel_time,
    source_rows,
)


def collect(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Build the source→kind→count matrix plus the newest payload per cell."""
    from pmbrs.core.storage import VALID_SOURCES

    grouped = source_rows(adapter)
    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    for source in VALID_SOURCES:
        cells: dict[str, dict[str, Any]] = {}
        for artifact in filter_artifacts(grouped.get(str(source), []), filters):
            kind = payload_kind_of(artifact)
            cell = cells.setdefault(kind, {"count": 0, "latest": None})
            cell["count"] += 1
            if cell["latest"] is None or (
                artifact.created_at_epoch_ms > cell["latest"].created_at_epoch_ms
            ):
                cell["latest"] = artifact
        matrix[str(source)] = {
            "total": sum(c["count"] for c in cells.values()),
            "kinds": cells,
        }
    return {
        "matrix": matrix,
        "sources": sorted(matrix.keys()),
        "total_artifacts": sum(row["total"] for row in matrix.values()),
        "filtered": active_filter(filters),
    }


def cell_label(source: str, kind: str) -> str:
    """Human cell id ``source / kind`` used as the selector key."""
    return f"{source} / {kind}"


def render(adapter: Any, filters: dict[str, Any] | None = None) -> dict[str, Any]:
    """Paint the matrix + a single pinned payload; returns collected data."""
    import streamlit as st

    data = collect(adapter, filters)
    scope = "· filtered" if data["filtered"] else ""
    st.subheader(f"Modality — sources × artifact kinds{scope}")
    if data["total_artifacts"] == 0:
        st.info("No artifacts match the current filter.")
        return data

    # -- matrix (the hero) -----------------------------------------------
    kinds: dict[str, str] = {}
    for source in data["sources"]:
        for kind, cell in data["matrix"][source]["kinds"].items():
            kinds.setdefault(kind, cell["latest"].created_at_epoch_ms)
    kind_order = sorted(kinds, key=lambda k: -kinds[k])

    table = []
    for source in data["sources"]:
        row = {"source": source}
        for kind in kind_order:
            cell = data["matrix"][source]["kinds"].get(kind)
            row[kind] = cell["count"] if cell else 0
        row["total"] = data["matrix"][source]["total"]
        table.append(row)

    import pandas as pd

    df = pd.DataFrame(table, columns=["source"] + kind_order + ["total"])
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.caption("Count of artifacts per (source × kind). Blank = 0.")

    # -- single pinned payload (no duplicate render) ----------------------
    # Build the list of selectable cells (source, kind) that have data.
    cells = [
        (source, kind)
        for source in data["sources"]
        for kind in data["matrix"][source]["kinds"]
    ]
    options = [cell_label(s, k) for s, k in cells]
    label = st.selectbox("Inspect a cell's newest artifact", options, index=0)
    if label:
        picked = [c for c in cells if cell_label(*c) == label]
        if picked:
            source, kind = picked[0]
            latest = data["matrix"][source]["kinds"][kind]["latest"]
            st.caption(
                f"Newest in **{source} / {kind}** — `{latest.artifact_id}` "
                f"· {rel_time(latest.created_at_epoch_ms)} "
                f"· {json_pretty(latest.payload)} chars"
            )
            st.json(latest.payload)
    return data


def json_pretty(payload: Any) -> str:
    """Length of the pretty JSON of a payload (for the caption line)."""
    import json

    try:
        return len(json.dumps(payload, indent=2, default=str))
    except (TypeError, ValueError):
        return str(len(str(payload)))
