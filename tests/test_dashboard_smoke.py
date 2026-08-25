"""Smoke tests for the Phase B dashboard views.

Verifies each view module imports cleanly and its ``collect`` function runs
against a tiny synthetic dataset (in a ``tmp_path`` store, never the real
``~/.pmbrs-private``). The ``render`` path is exercised with ``streamlit``
(stubbed or real) — tests never spin up a real Streamlit server.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

from pmbrs.core.artifact import Artifact
from pmbrs.core.storage import StorageAdapter


def _make_config(tmp_path: Path) -> Path:
    policy = {
        "artifact_root": str(tmp_path / "store"),
        "state_root": str(tmp_path / "state"),
        "checkpoint_root": str(tmp_path / "checkpoints"),
        "hermes_readonly_root": str(tmp_path / "hermes-readonly"),
        "queue_root": str(tmp_path / "store" / "pending"),
        "raw_root": str(tmp_path / "store" / "raw"),
        "summary_root": str(tmp_path / "store" / "summary"),
        "scheduler_state_file": str(tmp_path / "state" / "scheduler_state.json"),
        "export_snapshot_file": str(tmp_path / "state" / "hermes_snapshot.json"),
    }
    config_path = tmp_path / "policy.json"
    config_path.write_text(json.dumps(policy), encoding="utf-8")
    return config_path


SAMPLES: list[dict] = [
    {
        "artifactId": "art-mobile-1",
        "source": "mobile",
        "payload": {"kind": "demo-mobile-1"},
        "createdAtEpochMs": 1_750_000_000_000,
    },
    {
        "artifactId": "art-browser-1",
        "source": "browser",
        "payload": {"kind": "pageview"},
        "createdAtEpochMs": 1_750_001_000_000,
    },
    {
        "artifactId": "art-browser-2",
        "source": "browser",
        "payload": {"kind": "pageview"},
        "createdAtEpochMs": 1_750_002_000_000,
    },
]

VIEW_MODULES = ("overview", "timeline", "modality", "health", "experiments")


class _StubColumn:
    def __init__(self, outer: "StreamlitStub") -> None:
        self._outer = outer

    def __enter__(self) -> "_StubColumn":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._outer, name)


class _StubSidebar:
    def __init__(self, outer: "StreamlitStub") -> None:
        self._outer = outer

    def __getattr__(self, name: str) -> Any:
        return getattr(self._outer, name)


class _StubExpander:
    """Context manager stub for ``st.expander()``."""

    def __init__(self, outer: "StreamlitStub", label: str) -> None:
        self._outer = outer
        outer.calls.append(f"expander:{label}")

    def __enter__(self) -> "_StubExpander":
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        return getattr(self._outer, name)


class StreamlitStub:
    """Just enough of the ``streamlit`` API surface for the views' render paths."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.sidebar = _StubSidebar(self)

    # -- config / layout ----------------------------------------------------
    def set_page_config(self, **kwargs: Any) -> None:
        self.calls.append("set_page_config")

    def title(self, text: str) -> None:
        self.calls.append(f"title:{text}")

    def caption(self, text: str, **kwargs: Any) -> None:
        self.calls.append(f"caption:{text}")

    def subheader(self, text: str) -> None:
        self.calls.append(f"subheader:{text}")

    def divider(self, **kwargs: Any) -> None:
        self.calls.append("divider")

    # -- widgets ---------------------------------------------------------------
    def radio(self, label: str, options: list, **kwargs: Any) -> str:
        self.calls.append(f"radio:{label}")
        return options[0] if options else ""

    def selectbox(self, label: str, options: list, **kwargs: Any) -> str:
        self.calls.append(f"selectbox:{label}")
        return options[0] if options else ""

    def multiselect(self, label: str, options: list, **kwargs: Any) -> list:
        self.calls.append(f"multiselect:{label}")
        return list(options)

    def expander(self, label: str = "", **kwargs: Any) -> "_StubExpander":
        return _StubExpander(self, label)

    def toast(self, text: str, **kwargs: Any) -> None:
        self.calls.append(f"toast:{text}")

    @staticmethod
    def cache_resource(func: Any) -> Any:
        return func

    # -- output ----------------------------------------------------------------
    def metric(self, label: Any, value: Any = None, delta: Any = None, **kwargs: Any) -> None:
        self.calls.append(f"metric:{label}")

    def _emit(self, name: str, text: Any = "") -> None:
        self.calls.append(f"{name}:{str(text)[:40]}")

    def info(self, text: str) -> None:
        self._emit("info", text)

    def warning(self, text: str) -> None:
        self._emit("warning", text)

    def success(self, text: str) -> None:
        self._emit("success", text)

    def error(self, text: str) -> None:
        self._emit("error", text)

    def markdown(self, text: str, **kwargs: Any) -> None:
        self._emit("markdown", text)

    def code(self, text: str, language: str = "") -> None:
        self._emit("code", language)

    def json(self, value: Any) -> None:
        self.calls.append("json")

    def write(self, value: Any) -> None:
        self.calls.append("write")

    def columns(self, n: int) -> list[_StubColumn]:
        return [_StubColumn(self) for _ in range(n)]

    def dataframe(self, data: Any, **kwargs: Any) -> None:
        self.calls.append("dataframe")

    def altair_chart(self, chart: Any, **kwargs: Any) -> None:
        self.calls.append("altair_chart")

    def button(self, label: str = "", **kwargs: Any) -> bool:
        self.calls.append(f"button:{label}")
        return False


def _install_stub(monkeypatch: pytest.MonkeyPatch) -> StreamlitStub:
    stub = StreamlitStub()
    monkeypatch.setitem(sys.modules, "streamlit", stub)
    return stub


def _fresh_views() -> dict[str, Any]:
    """Import the view modules (pop cached ones first so stubs are used)."""
    for name in (
        "pmbrs.dashboard.views",
        "pmbrs.dashboard.views.overview",
        "pmbrs.dashboard.views.timeline",
        "pmbrs.dashboard.views.modality",
        "pmbrs.dashboard.views.health",
        "pmbrs.dashboard.views.experiments",
    ):
        sys.modules.pop(name, None)
    from pmbrs.dashboard.views import (  # noqa: PLC0415
        experiments,
        health,
        modality,
        overview,
        timeline,
    )

    return {
        "overview": overview,
        "timeline": timeline,
        "modality": modality,
        "health": health,
        "experiments": experiments,
    }


@pytest.fixture()
def adapter(tmp_path: Path) -> StorageAdapter:
    """Synthetic in-``tmp_path`` store: 3 artifacts + snapshot + state files."""
    store = StorageAdapter(config_path=_make_config(tmp_path))
    for record in SAMPLES:
        store.save(Artifact.from_dict(record))
    (store.summary_root / "pmbrs_summary_1750000000000.json").write_text(
        json.dumps({
            "generated_at_epoch_ms": 1_750_000_500_000,
            "raw_file_count": 3,
            "mode": "hermes_read_only",
            "read_only": True,
        }),
        encoding="utf-8",
    )
    (store.state_root / "scheduler_state.json").write_text(
        json.dumps({
            "last_run_at_epoch_ms": 1_750_000_400_000,
            "last_status": "ran",
            "next_run_at_epoch_ms": 1_750_036_200_000,
            "last_checkpoint": "checkpoint-1",
        }),
        encoding="utf-8",
    )
    (store.checkpoint_root / "checkpoint-1.json").write_text("{}", encoding="utf-8")
    return store


# ---------------------------------------------------------------------------
# collect() — pure data gathering, no Streamlit involved
# ---------------------------------------------------------------------------

def test_timeline_collect(adapter: StorageAdapter) -> None:
    from pmbrs.dashboard.views import timeline

    data = timeline.collect(adapter)
    assert data["total_artifacts"] == 3
    assert data["sources"]["mobile"]["count"] == 1
    assert data["sources"]["browser"]["count"] == 2
    assert data["sources"]["browser"]["latest_ids"][0] == "art-browser-2"
    assert data["sources"]["journal"]["count"] == 0
    assert data["sources"]["other"]["min_created_at_epoch_ms"] is None


def test_modality_collect(adapter: StorageAdapter) -> None:
    """Phase B.2 shape: per-source matrix with kind→{count, latest} cells."""
    from pmbrs.dashboard.views import modality

    data = modality.collect(adapter)
    # matrix is keyed by source name, each row has total + kinds dict
    assert data["matrix"]["browser"]["total"] == 2
    assert data["matrix"]["browser"]["kinds"]["pageview"]["count"] == 2
    latest_art = data["matrix"]["mobile"]["kinds"]["demo-mobile-1"]["latest"]
    assert latest_art.payload == {"kind": "demo-mobile-1"}
    # Desktop has no artifacts (count 0, empty kinds)
    assert data["matrix"]["desktop"]["total"] == 0
    assert data["matrix"]["desktop"]["kinds"] == {}
    # sources list has all 5 canonical names
    assert set(data["sources"]) == {"mobile", "browser", "desktop", "journal", "other"}
    assert data["total_artifacts"] == 3


def test_health_collect(adapter: StorageAdapter) -> None:
    from pmbrs.dashboard.views import health

    data = health.collect(adapter)
    assert data["snapshot_count"] == 1
    assert data["last_publish"]["file"] == "pmbrs_summary_1750000000000.json"
    assert data["last_publish"]["generated_at_epoch_ms"] == 1_750_000_500_000
    assert data["scheduler"]["last_status"] == "ran"
    assert data["pending"]["count"] == 0
    assert data["checkpoints"] == ["checkpoint-1.json"]


def test_experiments_collect_placeholder_and_marker(adapter: StorageAdapter) -> None:
    """Phase B.2 shape: run_count / legacy_count (replaces old `count` / `experiments`)."""
    from pmbrs.dashboard.views import experiments

    # None of the samples are Phase-D reports or hand-marked experiments → both zero.
    data = experiments.collect(adapter)
    assert data["run_count"] == 0
    assert data["legacy_count"] == 0

    # An artifact *hand-marked* with payload.kind == "experiment" is detected as legacy.
    record = dict(SAMPLES[1], artifactId="art-experiment-1", payload={"kind": "experiment"})
    adapter.save(Artifact.from_dict(record))
    data = experiments.collect(adapter)
    assert data["legacy_count"] == 1
    assert data["legacy"][0]["artifact_id"] == "art-experiment-1"
    # run_count still zero (no real Phase-D report)
    assert data["run_count"] == 0


# ---------------------------------------------------------------------------
# render() — stubbed streamlit, no server
# ---------------------------------------------------------------------------

def test_render_views_smoke(adapter: StorageAdapter, monkeypatch: pytest.MonkeyPatch) -> None:
    _install_stub(monkeypatch)
    views = _fresh_views()
    for name in VIEW_MODULES:
        result = views[name].render(adapter)
        assert isinstance(result, dict)
    assert views["experiments"].EXPERIMENT_MARKER == "experiment"


def test_render_views_empty_store(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Render paths must survive an empty raw store (no KeyError/zero-division)."""
    store = StorageAdapter(config_path=_make_config(tmp_path))
    _install_stub(monkeypatch)
    views = _fresh_views()
    for name in VIEW_MODULES:
        result = views[name].render(store)
        assert isinstance(result, dict)


def test_timeline_chart_serializes_under_real_altair(adapter: StorageAdapter) -> None:
    """Regression: altair >=6 (Vega-Lite v6) rejects a list of records for `data`.

    The Timeline scatter must therefore be fed a Mapping (pandas DataFrame)
    and produce a valid spec — verified here with the *real* altair, not a
    stub, because ``st.altair_chart`` crashed on ``chart.to_dict()`` with
    ``AltairChart(..., data=[{...}])`` under altair 6.x.
    """
    import altair as alt
    import pandas as pd

    # Same construction as src/pmbrs/dashboard/views/timeline.py.
    rows = [
        {"source": a.source, "created_at_epoch_ms": int(a.created_at_epoch_ms)}
        for a in adapter.query()
    ]
    chart = (
        alt.Chart(pd.DataFrame(rows))
        .mark_circle()
        .encode(
            x=alt.X("created_at_epoch_ms:Q", title="createdAtEpochMs"),
            y=alt.Y("source:N", sort=None, title="source"),
        )
        .properties(height=220)
    )
    spec = chart.to_dict()
    # Altair 6 (Vega-Lite v6) references a Mapping by name in the spec; the
    # actual records live on ``chart.data`` (a pandas DataFrame here).
    assert str(type(chart.data).__name__) == "DataFrame"
    assert len(chart.data) == len(rows) and len(rows) > 0
    assert spec.get("data", {}).get("name"), "spec must reference the DataFrame"
    # And prove the list-of-records form is what altair 6 rejects:
    with pytest.raises(Exception):
        alt.Chart(rows).mark_circle().to_dict()


# ---------------------------------------------------------------------------
# Phase B.2 additions: overview, real Phase-D run path, filter narrowing
# ---------------------------------------------------------------------------

def test_overview_collect(adapter: StorageAdapter) -> None:
    """Overview 'at-a-glance' home view — data gathering against the fixture store."""
    from pmbrs.dashboard.views import overview

    data = overview.collect(adapter)
    assert data["total_artifacts"] == 3
    assert data["n_sources_active"] == 2          # mobile + browser
    assert data["sources_active"] == ["browser", "mobile"]  # sorted list
    assert len(data["histogram"]) == 14         # 14-day bins
    # No Phase-D report exists yet → latest verdict + runs both empty
    assert data["latest_verdict"] is None
    assert data["recent_runs"] == []


def _phase_d_report_payload(
    *, verdict: str = "pass", run_id: str = "2026-08-10-weekly"
) -> dict[str, Any]:
    """Faithful ``derived.embedding_evaluation_report`` payload (subset of to_dict)."""
    return {
        "artifact_type": "derived.embedding_evaluation_report",
        "model_id": "pmbrs-emb-v1",
        "feature_version": "v1",
        "n_artifacts": 3,
        "n_epochs": 25,
        "final_loss": 0.2441,
        "val_loss": None,
        "quality_metrics": {"coherence": 0.296, "diversity": 0.334, "embedding_dim": 8},
        "checks": {
            "final_loss": {"value": 0.2441, "threshold": 0.5, "rule": "<=", "passed": True},
            "diversity": {"value": 0.334, "threshold": 0.9995, "rule": "<=", "passed": True},
        },
        "verdict": verdict,
        "run_id": run_id,
        "backend": "torch-cpu",
        "warm_start": False,
        "cadence": "weekly",
        "created_at_epoch_ms": 1_750_010_000_000,
    }


def _phase_d_embedding_payload(*, run_id: str = "2026-08-10-weekly") -> dict[str, Any]:
    """Faithful ``derived.behavioral_embedding`` payload (subset)."""
    return {
        "artifact_type": "derived.behavioral_embedding",
        "model_id": "pmbrs-emb-v1",
        "feature_version": "v1",
        "run_id": run_id,
        "embedding_dim": 8,
        "n_artifacts": 3,
        "final_loss": 0.2441,
        "created_at_epoch_ms": 1_750_010_000_000,
    }


def test_experiments_reads_real_phase_d_runs(adapter: StorageAdapter) -> None:
    """Experiments view must surface a Phase-D report + its paired embedding by run_id."""
    from pmbrs.dashboard.views import experiments

    # Save a report and a matching embedding (same run_id).
    report_art = Artifact.from_dict({
        "artifactId": "rep-1_5",
        "source": "other",
        "payload": _phase_d_report_payload(verdict="pass"),
        "createdAtEpochMs": 1_750_010_000_000,
    })
    embedding_art = Artifact.from_dict({
        "artifactId": "emb-1_5",
        "source": "other",
        "payload": _phase_d_embedding_payload(),
        "createdAtEpochMs": 1_750_010_000_000,
    })
    adapter.save(report_art)
    adapter.save(embedding_art)

    data = experiments.collect(adapter)
    assert data["run_count"] == 1
    # The run row carries the key metrics for a quick pass/fail read.
    run = data["runs"][0]
    assert run["verdict"] == "pass"
    assert run["final_loss"] == 0.2441
    assert run["n_epochs"] == 25
    # Embeddings are paired to the run (lineage via run_id).
    assert run["embedding_committed"] is True
    assert run["embedding_id"] == "emb-1_5"


def test_overview_surface_latest_pass_run(adapter: StorageAdapter) -> None:
    """Overview must surface the latest Phase-D verdict on the home view."""
    from pmbrs.dashboard.views import overview

    adapter.save(Artifact.from_dict({
        "artifactId": "rep-2_5",
        "source": "other",
        "payload": _phase_d_report_payload(verdict="pass"),
        "createdAtEpochMs": 1_750_010_000_000,
    }))

    data = overview.collect(adapter)
    assert data["latest_verdict"] == "pass"
    assert len(data["recent_runs"]) == 1
    assert data["recent_runs"][0]["verdict"] == "pass"
    assert data["recent_runs"][0]["final_loss"] == 0.2441


def test_filter_narrows_across_views(adapter: StorageAdapter) -> None:
    """The global filter (sources) must narrow every view consistently."""
    from pmbrs.dashboard.views import experiments, health, modality, overview, timeline

    sources_filter = {"sources": ["mobile"], "since_epoch_ms": None, "until_epoch_ms": None}

    tl_all = timeline.collect(adapter)
    tl_mobile = timeline.collect(adapter, sources_filter)
    assert tl_all["total_artifacts"] == 3
    assert tl_mobile["total_artifacts"] == 1
    assert "browser" not in [s for s, v in tl_mobile["sources"].items() if v["count"]]

    mod_all = modality.collect(adapter)
    mod_mobile = modality.collect(adapter, sources_filter)
    assert mod_all["total_artifacts"] == 3
    assert mod_mobile["total_artifacts"] == 1
    assert mod_mobile["matrix"]["mobile"]["total"] == 1
    assert mod_mobile["matrix"]["browser"]["total"] == 0

    ov_all = overview.collect(adapter)
    ov_mobile = overview.collect(adapter, sources_filter)
    assert ov_all["total_artifacts"] == 3
    assert ov_mobile["total_artifacts"] == 1


def test_time_range_filter_excludes(adapter: StorageAdapter) -> None:
    """A time-window filter must exclude artifacts outside the window."""
    from pmbrs.dashboard.views import overview

    # Window [1.750005e12, 1.750003e12] includes browser-1 & browser-2 but excludes mobile-1.
    lo = 1_750_000_500_000
    hi = 1_750_003_000_000
    win = {"sources": None, "since_epoch_ms": lo, "until_epoch_ms": hi}
    data = overview.collect(adapter, win)
    assert data["total_artifacts"] == 2
    assert "browser" in data["sources_active"]
    assert "mobile" not in data["sources_active"]
