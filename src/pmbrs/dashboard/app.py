"""PMBRS dashboard — Streamlit entry point (Phase B.2).

Read-only, local-first (Constitution §16). This module:

* caches a single :class:`pmbrs.core.storage.StorageAdapter` for the server
  session (constructed from ``config/external_data_policy.json``);
* builds the app shell: title, sidebar (view radio + **global filter**),
  top status strip, and view dispatch.

Phase B.2 (see ``docs/plans/dashboard-ux-b2.md``):

* **Overview** is the first view (at-a-glance home);
* **global filter** (sources multi-select + time window quick-pick) lives in
  the sidebar and is passed to every view's ``collect/render``;
* "Clear filters" button actually resets the widget state (via explicit
  widget keys and ``st.session_state``);
* dev commentary trimmed from the top bar.

The view modules (``pmbrs.dashboard.views.*``) stay decoupled from the app
shell: they accept ``(adapter, filters)`` and return a dict, so they remain
importable and testable without a running server.
"""

from __future__ import annotations

import importlib
import time
from typing import Any


def _views() -> dict[str, importlib.types.ModuleType]:
    views: dict[str, importlib.types.ModuleType] = {}
    for name in ("overview", "timeline", "modality", "health", "experiments"):
        views[name] = importlib.import_module(f"pmbrs.dashboard.views.{name}")
    return views


#: Display order (Overview first, per B.2 §1).
_VIEW_LABELS: tuple[tuple[str, str], ...] = (
    ("overview", "Overview"),
    ("timeline", "Timeline"),
    ("modality", "Modality"),
    ("health", "System Health"),
    ("experiments", "Experiments"),
)

#: Canonical raw sources (fixed set per ``pmbrs.core.storage.VALID_SOURCES``).
_ALL_SOURCES: tuple[str, ...] = ("mobile", "browser", "desktop", "journal", "other")

#: Time-window quick-picks. ``"all"`` → no bound.
_TIME_WINDOWS: tuple[tuple[str, str], ...] = (
    ("all", "All time"),
    ("24h", "Last 24 hours"),
    ("7d", "Last 7 days"),
    ("30d", "Last 30 days"),
)
_WINDOW_MS = {
    "all": None,
    "24h": 24 * 3600 * 1000,
    "7d": 7 * 86400 * 1000,
    "30d": 30 * 86400 * 1000,
}

#: Explicit widget keys (so "Clear filters" can rewrite them via session state).
_W_KEY_VIEW = "f_view"
_W_KEY_SOURCES = "f_sources"
_W_KEY_WINDOW = "f_window"

_VIEW_ORDER = [key for key, _ in _VIEW_LABELS]


def _make_filters(selected_sources: list[str] | None, window_ms: int | None) -> dict[str, Any]:
    """Build the filter dict passed to each view (``None`` → no bound)."""
    now_ms = int(time.time() * 1000)
    since = (now_ms - window_ms) if window_ms else None
    # An "all sources" value list is treated as *no source filter* (empty list
    # in the filter dict) so the view code can treat "None" and "empty list"
    # identically — both mean "don't narrow by source".
    sources = [s for s in (selected_sources or [])]
    if len(sources) == len(set(_ALL_SOURCES)):
        sources = []
    return {
        "sources": sources or None,
        "since_epoch_ms": since,
        "until_epoch_ms": None,
    }


def _get_adapter() -> Any:
    """Build (or return the cached) StorageAdapter for this Streamlit session.

    Cached in ``st.session_state`` so the policy file isn't re-read on every
    rerun. Import is deferred to the body: this module must stay importable
    under a stubbed ``streamlit`` (see the smoke tests).
    """
    import streamlit as st

    if "pmbrs_adapter" not in st.session_state:
        from pmbrs.core.storage import StorageAdapter, default_config_path

        st.session_state.pmbrs_adapter = StorageAdapter(config_path=default_config_path())
    return st.session_state.pmbrs_adapter


def _reset_filters() -> None:
    """Clear the sidebar filter widgets back to their defaults, then rerun."""
    import streamlit as st

    # Setting the session-state keys *before* the widgets re-render is how
    # Streamlit supports "programmatic widget reset".
    st.session_state[_W_KEY_SOURCES] = list(_ALL_SOURCES)
    st.session_state[_W_KEY_WINDOW] = "All time"
    st.rerun()


def main() -> None:
    import streamlit as st

    from pmbrs.dashboard.views import active_filter

    st.set_page_config(page_title="PMBRS", page_icon=":brain:", layout="wide")
    st.title("PMBRS — Personal Model of Behavioral Regulation")
    st.caption(
        "Behavioural analytics for deep work · locally stored, locally rendered "
        "(Constitution §16). Read-only surface."
    )

    # Sidebar: view picker + the global filter. Widgets are given explicit
    # keys so "Clear filters" can rewrite them via ``st.session_state``.
    with st.sidebar:
        st.markdown("### View")
        view_label = st.radio(
            "View",
            [label for _, label in _VIEW_LABELS],
            index=0,
            label_visibility="collapsed",
            key=_W_KEY_VIEW,
        )
        view_name = dict((label, key) for key, label in _VIEW_LABELS)[view_label]

        st.divider()
        st.markdown("### Filter")
        # ``default`` = all sources, "All time".
        selected_sources = st.multiselect(
            "Sources",
            options=list(_ALL_SOURCES),
            default=list(_ALL_SOURCES),
            placeholder="All sources",
            key=_W_KEY_SOURCES,
        )
        window_label = st.selectbox(
            "Time window",
            options=[label for _, label in _TIME_WINDOWS],
            index=0,
            key=_W_KEY_WINDOW,
        )
        window_key = dict((label, key) for key, label in _TIME_WINDOWS)[window_label]
        window_ms = _WINDOW_MS[window_key]

        st.divider()
        if st.button("Clear filters", use_container_width=True):
            _reset_filters()

    filters = _make_filters(selected_sources, window_ms)
    adapter = _get_adapter()

    if active_filter(filters):
        active_parts = []
        if filters.get("sources"):
            active_parts.append("sources: " + ", ".join(filters["sources"]))
        if filters.get("since_epoch_ms") is not None:
            active_parts.append(window_key)
        st.caption("Filter: " + " · ".join(active_parts))

    st.divider()

    # Dispatch to the selected view (render returns the collected dict for
    # downstream assertions in tests; we ignore the return here).
    views = _views()
    views[view_name].render(adapter, filters)


if __name__ == "__main__":
    main()
