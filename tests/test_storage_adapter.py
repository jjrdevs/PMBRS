"""StorageAdapter tests.

TEST HYGIENE: every test that WRITES uses a fresh per-test temporary store
(tempfile.TemporaryDirectory) pointed at by a synthetic policy JSON. None of
these tests touch the real ``/home/jjrdev/.pmbrs-private`` store.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from pmbrs.core.artifact import Artifact
from pmbrs.core.storage import StorageAdapter


def make_policy(root: Path) -> dict:
    """Minimal synthetic policy pointing at a throwaway temp store."""
    store = root / "store"
    return {
        "artifact_root": str(store),
        "state_root": str(root / "state"),
        "checkpoint_root": str(root / "checkpoints"),
        "hermes_readonly_root": str(root / "hermes-readonly"),
        "queue_root": str(store / "pending"),
        "raw_root": str(store / "raw"),
        "summary_root": str(store / "summary"),
        "default_schedule_minutes": 60,
        "retention_days": 7,
        "read_only_policy": {
            "hermes_mode": "read_only",
            "raw_data_is_authoritative": True,
            "allow_hermes_write": False,
            "allow_hermes_touch": False,
        },
    }


@pytest.fixture()
def env():
    """Fresh temporary store + config + adapter. Yields (adapter, root)."""
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        config_path = root / "external_data_policy.json"
        config_path.write_text(json.dumps(make_policy(root), indent=2), encoding="utf-8")
        adapter = StorageAdapter(config_path=config_path)
        yield adapter, root


def make_artifact(
    artifact_id: str = "art-1",
    source: str = "mobile",
    created_at: int = 1_720_000_000_000,
    kind: str | None = None,
    ingested_at: int = 1_720_000_000_100,
) -> Artifact:
    return Artifact(
        artifact_id=artifact_id,
        source=source,
        payload={"kind": kind or source},
        created_at_epoch_ms=created_at,
        schema_version="1.0",
        device_alias="test-device",
        provenance_metadata_json={"collector": "pytest"},
        ingested_at_epoch_ms=ingested_at,
        ingest_status="accepted",
    )


# -- construction -------------------------------------------------------------


def test_all_six_roots_created(env):
    adapter, root = env
    for name in ("raw_root", "summary_root", "pending_root", "checkpoint_root",
                 "state_root", "hermes_readonly_root"):
        target = getattr(adapter, name)
        assert target.is_dir(), f"{name} missing on disk: {target}"


def test_readonly_roots_default_contains_hermes(env):
    adapter, root = env
    assert adapter.hermes_readonly_root in adapter.readonly_roots


def test_policy_without_root_key_rejected(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"artifact_root": str(tmp_path / "s")}), encoding="utf-8")
    with pytest.raises(ValueError, match="missing required root"):
        StorageAdapter(config_path=bad)


# -- save / get round-trip ----------------------------------------------------


def test_save_writes_canonical_path_and_returns_absolute(env):
    adapter, _ = env
    artifact = make_artifact(artifact_id="art-x", source="browser", created_at=1_720_000_042_000)
    path = adapter.save(artifact)
    p = Path(path)
    assert p.is_absolute()
    assert p == adapter.raw_root / "browser" / "art-x-1720000042000.json"
    assert p.parent.is_dir()
    on_disk = json.loads(p.read_text(encoding="utf-8"))
    assert on_disk["artifactId"] == "art-x"
    assert on_disk["createdAtEpochMs"] == 1_720_000_042_000


def test_save_get_round_trip(env):
    adapter, _ = env
    artifact = make_artifact(artifact_id="roundtrip-1", source="journal", created_at=1_720_000_005_000)
    adapter.save(artifact)
    loaded = adapter.get("roundtrip-1")
    assert loaded.artifact_id == artifact.artifact_id
    assert loaded.source == artifact.source
    assert loaded.payload == artifact.payload
    assert loaded.created_at_epoch_ms == artifact.created_at_epoch_ms
    assert loaded.ingest_status == artifact.ingest_status
    assert loaded.to_dict() == artifact.to_dict()


def test_get_missing_raises_file_not_found(env):
    adapter, _ = env
    with pytest.raises(FileNotFoundError):
        adapter.get("does-not-exist")


# -- query --------------------------------------------------------------------


def test_query_filters(env):
    adapter, _ = env
    adapter.save(make_artifact("q-a", "mobile", created_at=1_000, kind="app"))
    adapter.save(make_artifact("q-b", "mobile", created_at=2_000, kind="call"))
    adapter.save(make_artifact("q-c", "browser", created_at=1_500, kind="visit"))
    adapter.save(make_artifact("q-d", "mobile", created_at=3_000, kind="app"))

    assert [a.artifact_id for a in adapter.query(source="mobile")] == ["q-a", "q-b", "q-d"]
    assert [a.artifact_id for a in adapter.query(payload_kind="app")] == ["q-a", "q-d"]
    assert [a.artifact_id for a in adapter.query(from_epoch=1_500, to_epoch=2_000)] == ["q-c", "q-b"]
    limited = adapter.query(limit=2)
    # Ordered by createdAtEpochMs ascending, then id; limit keeps the earliest.
    assert [a.artifact_id for a in limited] == ["q-a", "q-c"]
    assert adapter.query(source="journal") == []
    assert len(adapter.query()) == 4


def test_query_normalizes_legacy_browser_source(env):
    adapter, _ = env
    adapter.save(make_artifact("q-browser", "browser_visit", created_at=1_000, kind="visit"))
    assert [a.artifact_id for a in adapter.query(source="browser")] == ["q-browser"]


# -- lineage ------------------------------------------------------------------


def test_derive_from_returns_edge_and_records_it(env):
    adapter, _ = env
    edge = adapter.derive_from(["a1", "a2"], module="align", output_id="win-60-1")
    assert edge.child_id == "win-60-1"
    assert edge.parent_ids == ("a1", "a2")
    assert edge.module == "align"
    assert adapter.lineage_edges("win-60-1") == [edge]
    assert adapter.lineage_edges("unknown") == []


# -- checkpoints ---------------------------------------------------------------


def test_module_checkpoint_round_trip(env):
    adapter, root = env
    assert adapter.get_last_run("align") is None

    adapter.mark_module_complete("align", ["art-1", "art-2"])
    cp_file = root / "checkpoints" / "align.json"
    assert cp_file.is_file()
    data = json.loads(cp_file.read_text(encoding="utf-8"))
    assert data["module"] == "align"
    assert data["artifactIds"] == ["art-1", "art-2"]
    assert data["completedAtEpochMs"] > 0

    run = adapter.get_last_run("align")
    assert run is not None
    assert run.module == "align"
    assert run.artifact_ids == ("art-1", "art-2")
    assert run.completed_at_epoch_ms == data["completedAtEpochMs"]


def test_mark_module_complete_rewrites_on_rerun(env):
    adapter, _ = env
    adapter.mark_module_complete("features", ["a1"])
    first = adapter.get_last_run("features")
    adapter.mark_module_complete("features", ["a1", "a2"])
    second = adapter.get_last_run("features")
    assert second is not None
    assert second.artifact_ids == ("a1", "a2")
    assert second.completed_at_epoch_ms >= first.completed_at_epoch_ms


# -- readonly guard ------------------------------------------------------------


def test_save_cannot_target_readonly_root(env):
    adapter, root = env
    # A crafted artifact whose raw_root was pointed at the readonly root is the
    # realistic attack: an adapter whose raw root overlaps hermes_readonly.
    rogue = StorageAdapter(config_path=adapter.config_path)
    rogue.raw_root = adapter.hermes_readonly_root / "raw"
    rogue.raw_root.mkdir(parents=True, exist_ok=True)
    with pytest.raises(PermissionError):
        rogue.save(make_artifact("evil-1"))


def test_readonly_guard_rejects_direct_write_into_hermes_root(env):
    adapter, _ = env
    with pytest.raises(PermissionError):
        adapter.write_json(
            adapter.hermes_readonly_root / "sneaky.json",
            {"note": "should never be written"},
        )


def test_readonly_guard_rejects_nested_write_into_hermes_root(env):
    adapter, _ = env
    with pytest.raises(PermissionError):
        adapter.write_json(
            adapter.hermes_readonly_root / "nested" / "deeper.json",
            {"note": "nested write must also be refused"},
        )


def test_writable_summary_write_succeeds_through_write_json(env):
    adapter, root = env
    target = adapter.write_json(
        adapter.summary_root / "pmbrs_summary_1.json",
        {"raw_file_count": 1},
    )
    assert (root / "store" / "summary" / "pmbrs_summary_1.json").is_file()
    assert target == Path(str(target))
