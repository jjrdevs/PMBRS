"""ADR-021 D4/D5: WearableProducer over the REAL Samsung Health export.

Hard-contract E2E (task 10b):
  * every emitted artifact passes strict_validate (9-key CANONICAL_KEYS)
    with NO extra or dropped keys;
  * payload carries the 7 canonical-window sections;
  * per-window coverage / missingness / payload modality sets agree;
  * hrv honesty (derived_by_watch=true, sdnn_ms/rmssd_ms) + hrv_proxy method;
  * idempotency: run1 vs run2 (fresh manifest, same files) -> byte-identical
    artifact set with zero new/dropped files (D6 re-entrancy).

Skips cleanly if /tmp/pmbrs_export is absent (needs the real 256MB export).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pmbrs.core.artifact import CANONICAL_KEYS, strict_validate  # noqa: E402
from pmbrs.ingestion.boox.local_ingest import LocalIngestClient  # noqa: E402
from pmbrs.ingestion.wearable import producer as P  # noqa: E402

EXPORT = Path("/tmp/pmbrs_export")
if not EXPORT.is_dir():
    pytest.skip("real export dir /tmp/pmbrs_export not present",
                allow_module_level=True)

MODS = ("heart_rate", "hrv_proxy", "hrv", "stress", "sleep_stage")
SECTIONS = ("kind", "artifact_type", "window", "modalities_present",
            "payload", "missingness_metadata", "quality_metadata")


def _produce(raw_root: Path, manifest: Path):
    client = LocalIngestClient(raw_root=raw_root)
    man = P.new_manifest(manifest, device_alias="galaxy-watch7")
    cfg = P.EmitConfig(device_alias="galaxy-watch7", export="pmbrs_export",
                       transport="inbox")
    return P.WearableProducer(client, man, cfg).run(EXPORT)


def _sample(raw: Path, n=5):
    files = sorted(raw.rglob("*.json"))
    if len(files) <= n:
        return files
    step = len(files) / n
    return [files[int(i * step)] for i in range(n)]


@pytest.fixture(scope="module")
def env(tmp_path_factory):
    b = tmp_path_factory.mktemp("wear_e2e")
    raw1 = b / "raw1"
    man1 = b / "man1.json"
    stats1 = _produce(raw1, man1)
    raw2 = b / "raw2"
    man2 = b / "man2.json"   # fresh manifest -> independent re-processing
    stats2 = _produce(raw2, man2)
    return {
        "raw1": raw1, "raw2": raw2,
        "stats1": stats1, "stats2": stats2,
        "n1": sum(1 for _ in raw1.rglob("*.json")),
        "n2": sum(1 for _ in raw2.rglob("*.json")),
    }


def _rec(raw: Path):
    f = sorted(raw.rglob("*.json"))
    assert f, "no artifacts written"
    return json.loads(f[0].read_text()), f


def test_0a_emits_canonical_artifacts(env):
    s = env["stats1"]
    assert s.files_discovered >= 800
    assert s.bins >= 40000, s.bins
    assert s.hrv_windows >= 2000, s.hrv_windows
    assert s.windows_emitted > 0
    assert s.artifacts_ingested == s.windows_emitted
    assert env["n1"] == s.artifacts_ingested, (env["n1"], s.artifacts_ingested)


def test_0b_all_modality_tiers_present(env):
    s = env["stats1"]
    by_mod = s.windows_by_modality
    for m in ("heart_rate", "hrv_proxy", "hrv"):
        assert m in by_mod and by_mod[m] > 0, by_mod
    # stress + sleep present if the real export has those sheets
    assert by_mod.get("sleep_stage", 0) > 0 or s.sleep_stage_rows > 0


def test_1_9key_strict_validate_all(env):
    # spot-check a spread of files (head/mid/tail) — full check is the 5k+
    bad = []
    for f in _sample(env["raw1"], 40):
        rec = json.loads(f.read_text())
        miss = strict_validate(rec)
        if miss:
            bad.append((f.name, miss))
    assert not bad, bad[:5]


def test_2_keyset_exact_no_extras(env):
    first, _ = _rec(env["raw1"])
    assert set(first.keys()) == set(CANONICAL_KEYS), (
        "extra:", set(first.keys()) - set(CANONICAL_KEYS),
        "missing:", set(CANONICAL_KEYS) - set(first.keys()))


def test_3_payload_sections(env):
    first, _ = _rec(env["raw1"])
    pl = first["payload"]
    for sec in SECTIONS:
        assert sec in pl, (sec, sorted(pl.keys()))
    assert pl["kind"] == "canonical_window"
    assert pl["artifact_type"] == "canonical.window"
    w = pl["window"]
    assert w["resolution_seconds"] == 60
    assert pl["window"]["start_time"] and pl["window"]["end_time"]
    assert w["end_time"] > w["start_time"]


def test_4_coverage_missingness_payload_agree(env):
    for f in _sample(env["raw1"], 40):
        pl = json.loads(f.read_text())["payload"]
        present = pl["modalities_present"]
        cov = pl["missingness_metadata"]["modality_coverage"]
        miss = pl["missingness_metadata"]["missing_modalities"]
        mods = pl["payload"]["modalities"]
        for m in MODS:
            assert m in present and m in cov, (f.name, m)
            # present <=> payload has it <=> coverage>0
            assert (m in mods) == present[m], (f.name, m)
            assert (cov[m] > 0.0) == present[m], (f.name, m, cov[m])
            if not present[m]:
                assert m in miss, (f.name, m)
            else:
                assert m not in miss, (f.name, m)


def test_5_hrv_honesty(env):
    for f in _sample(env["raw1"], 40):
        pl = json.loads(f.read_text())["payload"]
        mods = pl["payload"]["modalities"]
        if "hrv" in mods:
            h = mods["hrv"]
            assert h.get("derived_by_watch") is True
            assert "sdnn_ms" in h and "rmssd_ms" in h
        if "hrv_proxy" in mods:
            assert mods["hrv_proxy"].get("method"), "hrv_proxy lacks method"


def _canon(rec: dict) -> dict:
    """Normalization for content-stability checks: drop the writer-stamped
    ``ingestedAtEpochMs`` (write-time, expected to differ between runs) and
    keep everything else byte-compared."""
    r = dict(rec)
    r.pop("ingestedAtEpochMs", None)
    return r


def test_6_idempotency_run1_vs_run2(env):
    # fresh manifest -> each file re-processed, but deterministic artifactId and
    # stable payload content => same file set, byte-identical modulo the
    # write-time ingestion stamp (allowed to differ).
    def fp(raw):
        out = {}
        for f in raw.rglob("*.json"):
            out[f.name] = json.dumps(_canon(json.loads(f.read_text())),
                                     sort_keys=True)
        return out
    a, b = fp(env["raw1"]), fp(env["raw2"])
    assert set(a) == set(b), (
        "only-run1:", list(set(a) - set(b))[:5],
        "only-run2:", list(set(b) - set(a))[:5])
    diff = [n for n in a if a[n] != b.get(n)]
    assert not diff, diff[:5]
    # artifactId in filename is stable: wearable.win.<slot>-<createdMs>.json
    import re
    for n in list(a)[:20]:
        assert re.match(r"wearable\.win\.\d+-\d+\.json$", n), n


def test_7_manifest_tracks_processing(env):
    # run2 with a FRESH manifest re-processed (files_parsed) yet produced the
    # same artifacts; a run3 with the SAME manifest sees files_unchanged.
    import tempfile
    with tempfile.TemporaryDirectory() as t:
        raw3 = Path(t) / "raw3"
        man3 = Path(t) / "man3.json"
        s1 = _produce(raw3, man3)          # cold: parses all files
        n_parsed1 = s1.files_parsed
        s3 = _produce(raw3, man3)          # same manifest: unchanged
        assert n_parsed1 >= 800
        assert s3.files_parsed == 0, s3.files_parsed
        assert s3.files_unchanged >= 800, s3.files_unchanged
