"""Phase D representation-stub tests.

Covers (per docs/plans/dashboard-milestone-1.md Phase D acceptance):

* ``--cadence weekly --local --dry-run`` → store unchanged, no mlflow import.
* ``--cadence monthly`` (committed, gate pass) → both artifacts committed +
  ``mark_module_complete`` called.
* Forced gate failure (``--loss-max 0``) → report artifact committed,
  behavioral_embedding NOT committed.
* Weekly warm-start (second run loads the checkpoint from the first).
* ``--mlflow`` against an unreachable server → the run still succeeds.

All write tests use a throwaway temp-store + synthetic policy (same pattern
as ``tests/test_storage_adapter.py``). Nothing here touches the real
``~/.pmbrs-private`` store.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from pmbrs.core.artifact import Artifact
from pmbrs.core.storage import StorageAdapter
from pmbrs.representation import runner as runner_mod


# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


def make_policy(root: Path) -> dict:
    store = root / "store"
    return {
        "artifact_root": str(store),
        "state_root": str(root / "state"),
        "checkpoint_root": str(root / "checkpoints"),
        "hermes_readonly_root": str(root / "hermes-readonly"),
        "queue_root": str(store / "pending"),
        "raw_root": str(store / "raw"),
        "summary_root": str(store / "summary"),
        "read_only_policy": {
            "hermes_readonly_is_enforced": True,
            "raw_data_is_authoritative": True,
        },
    }


@pytest.fixture
def tmp_store(tmp_path: Path):
    config_path = tmp_path / "policy.json"
    config_path.write_text(json.dumps(make_policy(tmp_path), indent=2), encoding="utf-8")
    return tmp_path, config_path


def make_artifact(
    artifact_id: str,
    source: str,
    created_at: int,
) -> Artifact:
    return Artifact(
        artifact_id=artifact_id,
        source=source,
        payload={"kind": source, "demo": True},
        created_at_epoch_ms=created_at,
        schema_version="1.0",
        device_alias="pytest-device",
        provenance_metadata_json={"collector": "pytest"},
        ingested_at_epoch_ms=created_at + 1_000,
        ingest_status="accepted",
    )


def seed_raw(adapter: StorageAdapter, n: int = 4) -> list[str]:
    """Seed ``n`` synthetic raw artifacts (one per distinct source)."""
    sources = ["mobile", "browser", "desktop", "journal"]
    ids = []
    for i in range(n):
        src = sources[i % len(sources)]
        art = make_artifact(f"seed-{i}", src, 1_720_000_000_000 + i * 60_000)
        adapter.save(art)
        ids.append(art.artifact_id)
    return ids


def files_under(root: Path) -> dict[str, str]:
    import hashlib
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            out[str(p)] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


def options(config_path: Path, **kw):
    argv = ["--cadence", kw.get("cadence", "weekly"), "--local", "--policy", str(config_path)]
    if kw.get("dry_run"):
        argv.append("--dry-run")
    if kw.get("monthly"):
        argv[1] = "monthly"
    if kw.get("loss_max") is not None:
        argv += ["--loss-max", str(kw["loss_max"])]
    if kw.get("mlflow"):
        argv += ["--no-local", "--mlflow", "--mlflow-tracking-uri", kw.get("mlflow_uri", "http://127.0.0.1:1")]
    return runner_mod.parse_args(argv)


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------


def test_dry_run_weekly_stores_unchanged_and_no_mlflow(tmp_store):
    root, config_path = tmp_store
    adapter = StorageAdapter(config_path=config_path)
    seed_raw(adapter)
    before = files_under(root)

    # Ensure a clean start w.r.t. mlflow (tests must not leak an import).
    sys.modules.pop("mlflow", None)

    opts = options(config_path, dry_run=True)
    result = runner_mod.run(opts)

    assert result["verdict"] == "pass"
    assert result["dry_run"] is True
    assert result["report"]["verdict"] == "pass"
    # mlflow must NOT be importable as a side effect of a --local --dry-run run.
    assert "mlflow" not in sys.modules
    # Store unchanged.
    assert files_under(root) == before


def test_monthly_pass_commits_both_artifacts(tmp_store):
    root, config_path = tmp_store
    adapter = StorageAdapter(config_path=config_path)
    seed_raw(adapter)

    opts = options(config_path, monthly=True)
    result = runner_mod.run(opts)

    assert result["verdict"] == "pass"
    committed_types = [t for t, _ in result["committed"]]
    assert "behavioral_embedding" in committed_types
    assert "embedding_evaluation_report" in committed_types
    # mark_module_complete wrote a checkpoint record.
    assert adapter.get_last_run(f"pmbrs_embedding_monthly") is not None
    # Report artifact is on disk under raw/other (per Phase D layout choice).
    report_artifact_id = result["artifacts"][0][1]
    loaded = adapter.get(report_artifact_id)
    assert loaded is not None
    assert loaded.payload.get("artifact_type") == "derived.embedding_evaluation_report"


def test_forced_failure_commits_report_only(tmp_store):
    root, config_path = tmp_store
    adapter = StorageAdapter(config_path=config_path)
    seed_raw(adapter)

    # loss_max=0 forces the gate to fail (final_loss > 0 always).
    opts = options(config_path, monthly=True, loss_max=0.0)
    result = runner_mod.run(opts)

    assert result["verdict"] == "fail"
    committed_types = [t for t, _ in result["committed"]]
    assert "embedding_evaluation_report" in committed_types
    assert "behavioral_embedding" not in committed_types
    # The behavioral_embedding slot must be None in the artifacts dict.
    embedding_slot = result["artifacts"][1]
    assert embedding_slot == ("embedding", None)
    # Report still on disk.
    report_artifact_id = result["artifacts"][0][1]
    loaded = adapter.get(report_artifact_id)
    assert loaded.payload["verdict"] == "fail"


def test_weekly_warm_start_loads_prior_checkpoint(tmp_store):
    root, config_path = tmp_store
    adapter = StorageAdapter(config_path=config_path)
    seed_raw(adapter)

    first = runner_mod.run(options(config_path, cadence="weekly"))
    assert first["verdict"] == "pass"
    assert first["report"]["warm_start"] is False

    # Second weekly run in the same store: the checkpoint saved by the first
    # run should be picked up as a warm start.
    second = runner_mod.run(options(config_path, cadence="weekly"))
    assert second["verdict"] == "pass"
    assert second["report"]["warm_start"] is True


def test_mlflow_unreachable_does_not_kill_run(tmp_store):
    root, config_path = tmp_store
    adapter = StorageAdapter(config_path=config_path)
    seed_raw(adapter)

    # --mlflow against a port that's almost certainly closed.
    opts = options(
        config_path,
        monthly=True,
        mlflow=True,
        mlflow_uri="http://127.0.0.1:1",
    )
    result = runner_mod.run(opts)

    # Logging failures must be contained to a warning: the training verdict
    # and artifact commits proceed as if --mlflow were not passed.
    assert result["verdict"] == "pass"
    committed_types = [t for t, _ in result["committed"]]
    assert "behavioral_embedding" in committed_types
    assert "embedding_evaluation_report" in committed_types
