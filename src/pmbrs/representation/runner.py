"""Phase D training pipeline runner (CLI).

Usage (spec):
    python -m pmbrs.representation.runner --cadence {weekly,monthly,on-demand} \\
        [--local] [--mlflow] [--dry-run]

Behaviour:

* **Reads raw artifacts** through :class:`StorageAdapter` (adapter-first;
  read-only on the store; ``hermes_readonly`` is never touched).
* **Trains** the small auto-encoder stub on a deterministic feature matrix
  derived from the raw payloads (Stage 1–3 of ``training-pipeline.md``).
* **Evaluates** with the proxy suite and applies the **rollback gate**
  (Stage 4): gate **pass** → commit ``behavioral_embedding`` + report
  artifacts and ``mark_module_complete``; gate **fail** → commit **only**
  the ``embedding_evaluation_report`` (as a failed artifact) and do **not**
  replace the previous stable embedding artifact.
* **``--local``** (default) — airtight: no network is opened and ``mlflow``
  is **never imported**. All artifacts + the report are written locally.
* **``--mlflow``** — opt-in. If ``mlflow`` is installed and reachable the
  run is logged; if the server is unreachable the training run still
  succeeds (logging failures are contained to a warning). ``mlflow`` is
  imported **lazily, only inside this branch**, so ``--local`` works even
  when ``mlflow`` is not installed at all.
* **``--dry-run``** — run training + evaluation, print the report JSON, and
  **do not commit** anything to the store (store unchanged).

The model + training loop are framework-swappable (NumPy default, PyTorch
optional), deterministic under a fixed seed (Constitution §9), and free of
network access by default (Constitution §16 "local-first, offline-first").
"""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from pmbrs.core.storage import StorageAdapter
from pmbrs.representation import checkpoint as ckpt
from pmbrs.representation import evaluate as evals
from pmbrs.representation import train as train_mod
from pmbrs.representation.model import MODEL_SPEC, BehavioralEmbeddingModel

DEFAULT_CADENCES = ("weekly", "monthly", "on-demand")


@dataclass
class RunOptions:
    cadence: str
    local: bool = True
    mlflow: bool = False
    mlflow_tracking_uri: str | None = None
    mlflow_experiment_name: str | None = None
    dry_run: bool = False
    epochs: int = 25
    learning_rate: float = 0.05
    batch_size: int = 4
    seed: int = 1337
    policy_path: str | Path | None = None
    # Thresholds (gate). Defaults align with ``evaluate.GateThresholds``.
    loss_max: float = 2.0
    diversity_max: float = 0.9995


def parse_args(argv: Sequence[str] | None) -> RunOptions:
    parser = argparse.ArgumentParser(
        prog="pmbrs.representation.runner",
        description=(
            "Phase D: train the behavioral embedding stub, run the proxy-eval "
            "suite, and enforce the fail-safe rollback gate."
        ),
    )
    parser.add_argument("--cadence", required=True, choices=DEFAULT_CADENCES,
                        help="Training cadence lane (ADR-017 D3).")
    parser.add_argument("--local", action="store_true", default=True,
                        help="Local-first (default). No network, no mlflow import.")
    parser.add_argument("--no-local", action="store_true", default=False,
                        help="Clear --local (used by callers that must opt IN to remote).")
    parser.add_argument("--mlflow", action="store_true", default=False,
                        help="Opt-in: log the run to a self-hosted MLflow server.")
    parser.add_argument("--mlflow-tracking-uri", default=None,
                        help="MLflow tracking URI (default: http://127.0.0.1:5000).")
    parser.add_argument("--mlflow-experiment-name", default="pmbrs-representation-stub",
                        help="MLflow experiment name (default: pmbrs-representation-stub).")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Train + evaluate, print the report, do NOT commit.")
    parser.add_argument("--policy", default=None, type=Path,
                        help="Path to an external-data-policy JSON file (defaults to "
                             "the deployment policy at config/external_data_policy.json). "
                             "Intended for tests / temp stores.")
    parser.add_argument("--epochs", type=int, default=25)
    parser.add_argument("--learning-rate", type=float, default=0.05)
    parser.add_argument("--batch-size", type=int, default=4)
    parser.add_argument("--seed", type=int, default=1337)
    parser.add_argument("--loss-max", type=float, default=2.0,
                        help="Rollback-gate: max allowed final reconstruction loss.")
    parser.add_argument("--diversity-max", type=float, default=0.9995,
                        help="Rollback-gate: max allowed mean off-diag cosine (collapse detector).")

    a = parser.parse_args(argv)
    return RunOptions(
        cadence=a.cadence,
        local=True if not a.no_local else False,
        mlflow=a.mlflow,
        mlflow_tracking_uri=a.mlflow_tracking_uri,
        mlflow_experiment_name=a.mlflow_experiment_name,
        dry_run=a.dry_run,
        epochs=a.epochs,
        learning_rate=a.learning_rate,
        batch_size=a.batch_size,
        seed=a.seed,
        policy_path=a.policy,
        loss_max=a.loss_max,
        diversity_max=a.diversity_max,
    )


def _build_adapter(options: RunOptions) -> StorageAdapter:
    """Adapter over the deployment store.

    The adapter is constructed from the external-data-policy JSON file
    (defaults to the deployment policy at
    ``config/external_data_policy.json``; ``--policy`` overrides, e.g. a
    temp-store policy in tests). All store access then goes through the
    adapter per ``docs/module-contracts.md``.
    """
    if options.policy_path is not None:
        return StorageAdapter(options.policy_path)
    return StorageAdapter()


def _log(msg: str) -> None:
    print(msg, flush=True)


def _maybe_log_mlflow(options: RunOptions, report_dict: dict[str, Any]) -> None:
    """OPT-IN mlflow logging. Only called when --mlflow was passed.

    Lazy-imported; any exception (missing package, unreachable server) is
    contained to a warning and never crashes the run (spec: mlflow must be
    optional and non-fatal).
    """
    uri = options.mlflow_tracking_uri or "http://127.0.0.1:5000"
    exp = options.mlflow_experiment_name or "pmbrs-representation-stub"
    try:
        import mlflow  # lazy import — never imported on the --local path
        mlflow.set_tracking_uri(uri)
        mlflow.set_experiment(exp)
        with mlflow.start_run(run_name=f"pmbrs-{report_dict.get('run_id', 'run')}") as run:
            mlflow.log_param("cadence", report_dict.get("cadence"))
            mlflow.log_param("model_id", report_dict.get("model_id"))
            mlflow.log_param("feature_version", report_dict.get("feature_version"))
            mlflow.log_param("n_artifacts", report_dict.get("n_artifacts"))
            mlflow.log_param("n_epochs", report_dict.get("n_epochs"))
            mlflow.log_metric("final_loss", float(report_dict.get("final_loss") or 0.0))
            if report_dict.get("val_loss") is not None:
                mlflow.log_metric("val_loss", float(report_dict["val_loss"]))
            mlflow.log_metric("coherence", float(report_dict["quality_metrics"]["coherence"]))
            mlflow.log_metric("diversity", float(report_dict["quality_metrics"]["diversity"]))
            mlflow.set_tag("verdict", report_dict.get("verdict"))
            _log(f"[mlflow] logged run_id={run.info.run_id} to {uri}")
    except Exception as exc:  # noqa: BLE001 — must never crash the train run
        _log(f"[mlflow] WARNING: opt-in logging failed (non-fatal): {exc!r}")


def run(options: RunOptions, adapter: StorageAdapter | None = None) -> dict[str, Any]:
    """Execute the Phase D pipeline once.

    Returns a summary dict (used by the CLI + tests).
    """
    adapter = adapter or _build_adapter(options)

    # 1. Read raw artifacts (read-only; adapter-first — never open store files).
    raw = adapter.query()
    if not raw:
        _log("[phase-d] no raw artifacts found in the store; nothing to train on.")
        report_dict = {
            "run_id": f"run-{MODEL_SPEC.model_id}-{options.cadence}-{int(time.time() * 1000)}",
            "cadence": options.cadence,
            "n_artifacts": 0,
            "verdict": "skip",
            "reason": "no raw artifacts",
        }
        _print_report(report_dict)
        return {"verdict": "skip", "report": report_dict, "artifacts": []}

    # 2. (Weekly cadence) warm-start from the prior checkpoint if present.
    warm_model: BehavioralEmbeddingModel | None = None
    warm_start = False
    if options.cadence == "weekly":
        warm_model = ckpt.load_model_checkpoint(adapter, options.cadence)
        warm_start = warm_model is not None
        if warm_start:
            _log(f"[phase-d] warm-start loaded from {ckpt._model_record(adapter, options.cadence)}")
        else:
            _log("[phase-d] no prior checkpoint; cold start for weekly lane")

    # 3. Train.
    train_cfg = train_mod.TrainConfig(
        cadence=options.cadence,
        epochs=options.epochs,
        learning_rate=options.learning_rate,
        batch_size=options.batch_size,
        seed=options.seed,
        warm_start=warm_start,
        spec=MODEL_SPEC,
    )
    result = train_mod.train(raw, config=train_cfg, model=warm_model)
    _log(f"[phase-d] trained {len(raw)} artifacts over {result.epochs} epochs "
         f"(backend={result.backend}, warm_start={result.warm_start}, "
         f"final_loss={result.final_loss:.6g})")

    # 4. Proxy eval + rollback gate (Stage 4).
    now_ms = int(time.time() * 1000)
    thresholds = evals.GateThresholds(loss_max=options.loss_max, diversity_max=options.diversity_max)
    report = evals.evaluate(
        result, cadence=options.cadence, run_id=evals.make_run_id(options.cadence, now_ms),
        created_at_epoch_ms=now_ms, thresholds=thresholds, spec=MODEL_SPEC,
    )
    report_dict = report.to_dict()

    # 5. Commit / rollback. Dry-run: print only, don't touch the store.
    upstream_ids = [a.artifact_id for a in raw]
    report_artifact, report_id = evals.build_report_artifact(report, upstream_ids)
    embedding_artifact = (
        evals.build_embedding_artifact(result, report, upstream_ids)
        if report.verdict == "pass"
        else None
    )

    if options.dry_run:
        _log("[dry-run] skipping commit; store unchanged.")
        _print_report(report_dict)
        return {
            "verdict": report.verdict,
            "report": report_dict,
            "dry_run": True,
            "artifacts": [("report", report_id),
                          ("embedding", embedding_artifact.artifact_id if embedding_artifact else None)],
            "committed": [],
        }
    committed: list[tuple[str, str]] = []
    if options.local and not options.mlflow:
        pass  # --local is the default, nothing extra.
    if options.mlflow:
        _maybe_log_mlflow(options, report_dict)

    # Report artifact: ALWAYS written (pass or fail).
    rp = adapter.save(report_artifact)
    adapter.derive_from(upstream_ids, module=f"pmbrs_embedding_{options.cadence}",
                        output_id=report_id, edge_type="derived")
    committed.append(("embedding_evaluation_report", report_id))
    _log(f"[phase-d] committed embedding_evaluation_report {report_id} -> {rp}")

    if report.verdict == "pass":
        ep = adapter.save(embedding_artifact)
        adapter.derive_from([report_id] + list(upstream_ids),
                            module=f"pmbrs_embedding_{options.cadence}",
                            output_id=embedding_artifact.artifact_id, edge_type="derived")
        committed.append(("behavioral_embedding", embedding_artifact.artifact_id))
        _log(f"[phase-d] committed behavioral_embedding {embedding_artifact.artifact_id} -> {ep}")
        module_name = evals.run_module_name(options.cadence)
        adapter.mark_module_complete(module_name, artifact_ids=[embedding_artifact.artifact_id, report_id])
        # Model checkpoint for the next weekly warm start (best-effort).
        try:
            cp = ckpt.save_model_checkpoint(
                adapter, result.model, options.cadence,
                run_id=report.run_id, final_loss=result.final_loss,
                n_epochs=result.epochs, seed=options.seed,
            )
            _log(f"[phase-d] saved model checkpoint -> {cp}")
        except PermissionError as perr:
            _log(f"[phase-d] WARNING: model checkpoint save refused: {perr}")
    else:
        # Fail-safe roll-back: previous stable embedding artifact stays; we
        # only record the failed report (and a log line).
        _log(f"[phase-d] ROLLBACK: gate failed; did NOT commit behavioral_embedding. "
             f"Previous stable snapshot remains live. Failed report committed: {report_id}")
        adapter.mark_module_complete(evals.run_module_name(options.cadence),
                                     artifact_ids=[report_id])

    _print_report(report_dict)
    return {
        "verdict": report.verdict,
        "report": report_dict,
        "dry_run": False,
        "artifacts": [
            ("report", report_id),
            ("embedding", embedding_artifact.artifact_id if embedding_artifact else None),
        ],
        "committed": committed,
    }


def _print_report(report_dict: dict[str, Any]) -> None:
    _log("[phase-d] embedding_evaluation_report:")
    _log(json.dumps(report_dict, indent=2, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    options = parse_args(argv)
    try:
        result = run(options)
    except PermissionError as perr:
        _log(f"[phase-d] ERROR: {perr}")
        return 2
    verdict = result.get("verdict")
    return 0 if verdict in ("pass", "skip") else 3


if __name__ == "__main__":
    raise SystemExit(main())
