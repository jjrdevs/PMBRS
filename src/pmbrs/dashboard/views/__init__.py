"""PMBRS dashboard views (Phase B / B.2).

Each view module exposes:

* ``collect(adapter, filters=None) -> dict`` — pure data gathering over the
  :class:`pmbrs.core.storage.StorageAdapter` (no Streamlit, testable in
  isolation). ``filters`` is optional and **backwards-compatible**: ``None``
  means "no filtering", so the Phase B ``collect(adapter)`` contract still holds.
* ``render(adapter, filters=None) -> dict`` — calls ``collect`` and paints the
  view with Streamlit (Streamlit is imported lazily inside ``render`` so the
  data logic stays importable without a running server).

READ-ONLY: none of these modules call ``save`` / ``derive_from`` /
``mark_module_complete`` (see ``pmbrs.dashboard.app``).

Phase B.2 additions (see ``docs/plans/dashboard-ux-b2.md``):
* time helpers (``rel_time``, ``local_iso``) — relative + local display;
* ``filter_artifacts`` — the global user filter (sources / time window);
* Phase-D glue helpers — ``artifact_type``, ``is_report``, ``is_embedding``,
  ``run_id`` — so the Experiments & Health views read the *real* training
  pipeline output (``derived.*`` artifacts), not just legacy ``kind`` markers.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Iterable

# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------


def format_epoch_ms(epoch_ms: int | None) -> str:
    """Render an epoch-ms timestamp as an ISO-8601 UTC string for display."""
    if not epoch_ms:
        return "—"
    try:
        moment = datetime.fromtimestamp(int(epoch_ms) / 1000.0, tz=timezone.utc)
    except (OverflowError, OSError, ValueError):
        return str(epoch_ms)
    return moment.strftime("%Y-%m-%d %H:%M:%S UTC")


def local_iso(epoch_ms: int | None) -> str:
    """Render an epoch-ms timestamp in the viewer's *local* timezone."""
    if not epoch_ms:
        return "—"
    try:
        return datetime.fromtimestamp(int(epoch_ms) / 1000.0).strftime(
            "%Y-%m-%d %H:%M:%S"
        )
    except (OverflowError, OSError, ValueError):
        return str(epoch_ms)


def rel_time(epoch_ms: int | None, now_ms: int | None = None) -> str:
    """Human relative time: ``"just now"``, ``"5m ago"``, ``"2d ago"``, ``"in 3h"``."""
    if not epoch_ms:
        return "—"
    if now_ms is None:
        now_ms = int(time.time() * 1000)
    delta_s = (int(now_ms) - int(epoch_ms)) // 1000
    future = delta_s < 0
    delta_s = abs(delta_s)

    if delta_s < 60:
        text = "just now" if not future else "in <1m"
    elif delta_s < 3600:
        text = f"{delta_s // 60}m"
    elif delta_s < 86400:
        text = f"{delta_s // 3600}h {delta_s % 3600 // 60:02d}m" if future else f"{delta_s // 3600}h"
    elif delta_s < 86400 * 30:
        text = f"{delta_s // 86400}d"
    else:
        text = f"{delta_s // (86400 * 30)}mo"

    if text in ("just now", "in <1m"):
        return text
    return f"in {text}" if future else f"{text} ago"


def payload_kind_of(artifact: Any) -> str:
    """Best-effort ``payload["kind"]`` (``(untyped)`` when absent/not a mapping)."""
    payload = getattr(artifact, "payload", None) or {}
    kind = payload.get("kind") if isinstance(payload, dict) else None
    return str(kind) if kind else "(untyped)"


def source_rows(adapter: Any) -> dict[str, list[Any]]:
    """Group all raw artifacts by canonical source (adapter order)."""
    from pmbrs.core.storage import VALID_SOURCES

    rows: dict[str, list[Any]] = {source: [] for source in sorted(VALID_SOURCES)}
    for artifact in adapter.query():
        key = str(artifact.source).strip().lower()
        rows.setdefault(key, []).append(artifact)
    return rows


def latest_by_created(artifacts: list[Any], n: int) -> list[Any]:
    """Return the ``n`` most recently created artifacts (newest first)."""
    return sorted(artifacts, key=lambda a: a.created_at_epoch_ms, reverse=True)[: max(n, 0)]


# ---------------------------------------------------------------------------
# Global user filter (Phase B.2)
# ---------------------------------------------------------------------------

#: Recognised filter keys. Unknown keys are ignored.
FILTER_KEYS = ("sources", "since_epoch_ms", "until_epoch_ms")


def filter_artifacts(
    artifacts: Iterable[Any],
    filters: dict[str, Any] | None = None,
) -> list[Any]:
    """Apply the global user filter (subset of sources + a time window).

    * ``filters["sources"]`` — iterable of source names; empty/None = all.
    * ``filters["since_epoch_ms"]`` — inclusive lower bound; None = no bound.
    * ``filters["until_epoch_ms"]`` — inclusive upper bound; None = no bound.

    Pure and total: never raises on ``None`` filters.
    """
    filters = filters or {}
    sources = filters.get("sources")
    since = filters.get("since_epoch_ms")
    until = filters.get("until_epoch_ms")

    source_set = set(sources) if sources else None
    out: list[Any] = []
    for a in artifacts:
        src = str(getattr(a, "source", "")).strip().lower()
        if source_set is not None and src not in source_set:
            continue
        ms = int(getattr(a, "created_at_epoch_ms", 0) or 0)
        if since is not None and ms < int(since):
            continue
        if until is not None and ms > int(until):
            continue
        out.append(a)
    return out


def active_filter(filters: dict[str, Any] | None) -> bool:
    """True when the filter actually narrows anything (for a UI hint)."""
    filters = filters or {}
    if filters.get("sources"):
        return True
    if filters.get("since_epoch_ms") is not None:
        return True
    if filters.get("until_epoch_ms") is not None:
        return True
    return False


# ---------------------------------------------------------------------------
# Phase-D glue — read the *real* training pipeline output (Phase B.2)
# ---------------------------------------------------------------------------

REPORT_TYPE = "derived.embedding_evaluation_report"
EMBEDDING_TYPE = "derived.behavioral_embedding"


def artifact_type(artifact: Any) -> str | None:
    """``payload["artifact_type"]`` when the artifact is a derived record."""
    payload = getattr(artifact, "payload", None) or {}
    if not isinstance(payload, dict):
        return None
    value = payload.get("artifact_type")
    return str(value) if value else None


def is_report(artifact: Any) -> bool:
    """True when ``artifact`` is a Phase-D ``embedding_evaluation_report``."""
    return artifact_type(artifact) == REPORT_TYPE


def is_embedding(artifact: Any) -> bool:
    """True when ``artifact`` is a Phase-D ``behavioral_embedding``."""
    return artifact_type(artifact) == EMBEDDING_TYPE


def run_id(artifact: Any) -> str | None:
    """The Phase-D ``run_id`` that links a report + its embedding (lineage)."""
    payload = getattr(artifact, "payload", None) or {}
    if not isinstance(payload, dict):
        return None
    value = payload.get("run_id")
    return str(value) if value else None


def verdict_of(artifact: Any) -> str | None:
    """``payload["verdict"]`` (``pass``/``fail``) for a Phase-D report."""
    payload = getattr(artifact, "payload", None) or {}
    if not isinstance(payload, dict):
        return None
    value = payload.get("verdict")
    return str(value).lower() if value else None
