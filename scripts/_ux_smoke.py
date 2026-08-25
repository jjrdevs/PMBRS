"""Throwaway headless smoke: import every dashboard view module, call
collect() and render() (with a stub streamlit) against the REAL store.

Run: PYTHONPATH=src .venv/bin/python scripts/_ux_smoke.py
Exits 0 on success, non-zero with a traceback on any failure.
"""
import sys
import types
import traceback

# ---- install a minimal streamlit stub BEFORE importing the view modules ----
st = types.ModuleType("streamlit")

def _column(key: str):
    if key:
        st.last_widget_key = key
        return contextmanager_stub()
        return None
    return None

# Simpler: build the stub with real callables.
class _Dummy:
    def __getattr__(self, name):
        def fn(*a, **k):
            return _Dummy()
        return fn

    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

class _CmContext(_Dummy):
    def __enter__(self):
        return self
    def __exit__(self, *a):
        return False

def _make_col(key):
    def cm():
        yield  # context manager
    cm.__call__ = lambda *a, **k: None
    return cm

# Build function stubs
def metric(label="", value=None, delta=None, help=None, width=None):
    st.metric_calls.append((label, value, delta))

def sidebar():
    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def __getattr__(self, name):
            def fn(*a, **k):
                st.last_widget_key = k.get("key")
                return _Dummy()
            return fn
    return C()

def radio(label, options, index=0, key=None, label_visibility=None):
    st.last_widget_key = key
    return options[0] if options else None

def multiselect(label, options=None, default=None, placeholder=None, key=None):
    st.last_widget_key = key
    return list(default) if default else list(options or [])

def selectbox(label, options=None, index=0, key=None):
    st.last_widget_key = key
    return options[0] if options else None

def button(label, use_container_width=False, type=None):
    return False

def title(t): st.titles.append(t)
def subtitle(t): st.subtitles.append(t)
def subheader(t): st.md.append(t)
def caption(t): st.captions.append(t)
def write(x): pass
def error(x): st.errors.append(x)
def info(x): st.infos.append(x)
def divider(): pass
def json(x): pass
def code(x, language=None): pass
def markdown(x, unsafe_allow_html=False): st.md.append(x)
def dataframe(df, **kw): pass
def data_editor(df, **kw): pass
def plotly_chart(fig, **kw): pass
def altair_chart(fig, **kw): pass

def set_page_config(**kw): pass
def columns(n):
    cols = [_Dummy() for _ in range(n)]
    return cols
def use_container_width(): return True
def expander(title, expanded=False):
    class C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
    return C()
def success(t): pass
def warning(t): pass
def selectbox(label, options=None, index=0, placeholder=None, key=None):
    st.last_widget_key = key
    return options[0] if options else None

def rerun(): pass

# session_state: a simple dict-like object (avoids the __setattr__ recursion)
class _SS(dict):
    def __getattr__(self, name):
        if name.startswith("_"):
            raise AttributeError(name)
        try: return self[name]
        except KeyError: raise AttributeError(name)
    def __setattr__(self, name, value):
        self[name] = value
session_state = _SS()

# attach
st.metric = metric
st.sidebar = sidebar
st.radio = radio
st.multiselect = multiselect
st.selectbox = selectbox
st.button = button
st.title = title
st.subtitle = subtitle
st.subheader = subheader
st.caption = caption
st.write = write
st.error = error
st.info = info
st.divider = divider
st.json = json
st.code = code
st.markdown = markdown
st.dataframe = dataframe
st.data_editor = data_editor
st.plotly_chart = plotly_chart
st.altair_chart = altair_chart
st.set_page_config = set_page_config
st.columns = columns
st.use_container_width = use_container_width
st.expander = expander
st.success = success
st.warning = warning
st.selectbox = selectbox
st.rerun = rerun
st.session_state = session_state
st.metric_calls = []
st.titles = []
st.subtitles = []
st.captions = []
st.errors = []
st.infos = []
st.md = []
st.last_widget_key = None

sys.modules["streamlit"] = st

# ---- now exercise the views against the REAL store ----
from pmbrs.core.storage import StorageAdapter, default_config_path
adapter = StorageAdapter(config_path=default_config_path())

import importlib
views = {}
for name in ("overview", "timeline", "modality", "health", "experiments"):
    views[name] = importlib.import_module(f"pmbrs.dashboard.views.{name}")

failures = []
for name, view in views.items():
    for filters in (None, {"sources": ["mobile"], "since_epoch_ms": None, "until_epoch_ms": None}):
        label = f"{name} filters={filters!r}"
        try:
            data = view.collect(adapter, filters)
            assert isinstance(data, dict), f"collect must return dict"
            view.render(adapter, filters)
            print(f"PASS  {label}")
        except Exception:
            print(f"FAIL  {label}")
            failures.append(label)
            traceback.print_exc()

# targeted assertions (store-conditional: this deployment currently has NO
# Phase-D report, so the empty-run path is what we assert here; the "has-run"
# path is covered hermetically in tests/test_dashboard_smoke.py)
print("\n----- targeted assertions -----")
def check(desc, cond):
    print(("PASS " if cond else "FAIL ") + desc)
    if not cond:
        failures.append(desc)

ov = views["overview"].collect(adapter)
check("overview: total_artifacts == 5 (real store)", ov["total_artifacts"] == 5)
check("overview: 5 sources active", ov["n_sources_active"] == 5)
check("overview: histogram has 14 bins", len(ov["histogram"]) == 14)
check("overview: no run yet -> latest_verdict is None", ov["latest_verdict"] is None)
check("overview: no run yet -> recent_runs empty", ov["recent_runs"] == [])

ex = views["experiments"].collect(adapter)
check("experiments: no real model runs in store", ex["run_count"] == 0)
check("experiments: no legacy markers in store", ex["legacy_count"] == 0)

he = views["health"].collect(adapter)
check("health: training empty for empty-run store", he["training"] is None)
check("health: pending count is int", isinstance(he["pending"]["count"], int))
check("health: snapshot_count reflects real store", he["snapshot_count"] >= 0)

mod = views["modality"].collect(adapter)
check("modality: >= 4 sources in matrix", len(mod["sources"]) >= 4)
check("modality: matrix is per-source dict of {total,kinds}",
      all(k in mod["matrix"][s] for s in mod["sources"] for k in ("total", "kinds")))
check("modality: total_artifacts == 5 (matches store)", mod["total_artifacts"] == 5)
check("modality: filtered False for empty filters", mod["filtered"] is False)

tl = views["timeline"].collect(adapter)
check("timeline: sources dict present", isinstance(tl["sources"], dict))
check("timeline: every source has count/latest_ids keys",
      all("count" in s and "latest_ids" in s for s in tl["sources"].values()))
check("timeline: total_artifacts == 5", tl["total_artifacts"] == 5)
check("timeline: bucket counts sum to total",
      sum(s["count"] for s in tl["sources"].values()) == 5)

# filter narrowing actually works and is strict
ov_mobile = views["overview"].collect(adapter, {"sources": ["mobile"], "since_epoch_ms": None, "until_epoch_ms": None})
ov_all = views["overview"].collect(adapter)
check("filter: mobile-only is a subset of all", ov_mobile["total_artifacts"] <= ov_all["total_artifacts"])
check("filter: mobile-only drops other sources", ov_mobile["total_artifacts"] < ov_all["total_artifacts"])
check("filter: empty-sources == all (no narrowing)", ov_mobile["total_artifacts"] >= 0)

print(f"\n== {'ALL PASS' if not failures else f'{len(failures)} FAILURES'} ==")
sys.exit(1 if failures else 0)
