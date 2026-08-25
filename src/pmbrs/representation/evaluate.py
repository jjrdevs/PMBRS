"""Proxy evaluation suite + rollback gate (Phase D, Stage 4).

Per ``docs/representation/training-pipeline.md`` Stage 4 and
``docs/evaluation/representation-quality.md``: no ground-truth labels exist
(Constitution §14), so quality is judged through **structural proxy
metrics** over the produced embeddings:

* **coherence** — mean cosine similarity between temporally consecutive
  embeddings (transition smoothness; reported, not gated),
* **reconstruction** — proxy of forward/backward round-trip fidelity
  (reported),
* **diversity (anti-collapse)** — mean off-diagonal pairwise cosine
  similarity of the embedding set; too close to 1.0 means every window
  embeds to the same point (degenerate / collapsed model). **Gated**:
  ``gate_diversity_max``.
* **loss** — final reconstruction MSE from training. **Gated**:
  ``gate_loss_max``.

Verdict: ``pass`` iff the gated metrics are within thresholds. The runner
enforces the rollback semantics: on ``fail`` a ``behavioral_embedding``
artifact is **not** committed (the previous stable snapshot stays live),
while the ``embedding_evaluation_report`` is still written as a failed
artifact and the failure is logged (``training-pipeline.md`` §Fail-Safe &
Rollback).

No network access and no experiment-tracker imports in this module.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pmbrs.core.artifact import Artifact
from pmbrs.representation.model import EMBEDDING_DIM, FEATURE_VERSION, MODEL_ID, ModelSpec
from pmbrs.representation.train import TrainResult

#: Artifact ``source`` / type naming (derived artifacts live under raw/<source>/
#: per the adapter's ``save`` layout; the type is recorded in the payload for
#: the consumer — the JSONL+SQLite layer will index by artifact_type natively).
EMBEDDING_ARTIFACT_ID_PREFIX = "behavioral_embedding"
REPORT_ARTIFACT_ID_PREFIX = "embedding_evaluation_report"
EMBEDDING_SOURCE = "other"  # derived, locally produced (not an ingested source)

SCHEMA_VERSION = "1.0"


@dataclass(frozen=True)
class GateThresholds:
    """Rollback-gate thresholds (``training-pipeline.md`` §Fail-Safe & Rollback)."""

    loss_max: float = 2.0
    diversity_max: float = 0.9995  # mean off-diag cosine; ~1.0 => collapse

    def to_dict(self) -> dict[str, float]:
        return {"loss_max": self.loss_max, "diversity_max": self.diversity_max}


@dataclass
class EvalReport:
    """One proxy evaluation run + gate verdict.

    The JSON payload written to the ``embedding_evaluation_report`` artifact
    is :meth:`to_dict` — required fields (spec): model_id, feature_version,
    n_artifacts, n_epochs, final_loss, a proxy-eval quality metric
    (``diversity``) and the ``verdict``.
    """

    model_id: str
    feature_version: str
    n_artifacts: int
    n_epochs: int
    final_loss: float
    val_loss: float | None
    coherence: float
    diversity: float
    embedding_dim: int
    backend: str
    warm_start: bool
    cadence: str
    thresholds: GateThresholds
    run_id: str
    created_at_epoch_ms: int
    checks: dict[str, Any] = field(default_factory=dict)

    @property
    def verdict(self) -> str:
        return "pass" if all(v["passed"] for v in self.checks.values()) else "fail"

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_type": "derived.embedding_evaluation_report",
            "model_id": self.model_id,
            "feature_version": self.feature_version,
            "n_artifacts": int(self.n_artifacts),
            "n_epochs": int(self.n_epochs),
            "final_loss": float(self.final_loss),
            "val_loss": None if self.val_loss is None else float(self.val_loss),
            "quality_metrics": {
                "coherence": float(self.coherence),
                "diversity": float(self.diversity),
                "embedding_dim": int(self.embedding_dim),
            },
            "checks": {name: dict(value, passed=bool(value["passed"])) for name, value in self.checks.items()},
            "verdict": self.verdict,
            "thresholds": self.thresholds.to_dict(),
            "run_id": self.run_id,
            "backend": self.backend,
            "warm_start": bool(self.warm_start),
            "cadence": self.cadence,
            "created_at_epoch_ms": int(self.created_at_epoch_ms),
        }


# ---------------------------------------------------------------------------
# Proxy metric primitives
# ---------------------------------------------------------------------------


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na = float(np.linalg.norm(a))
    nb = float(np.linalg.norm(b))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))


def temporal_coherence(embeddings: np.ndarray) -> float:
    """Mean cosine similarity between consecutive (time-ordered) embeddings.

    Higher = smoother trajectory (representation-quality.md §transition
    smoothness). With a single embedding there is no transition to measure.
    """
    if embeddings.shape[0] < 2:
        return 0.0
    sim = [_cosine(embeddings[i], embeddings[i + 1]) for i in range(embeddings.shape[0] - 1)]
    return float(np.mean(sim))


def anti_collapse_diversity(embeddings: np.ndarray) -> float:
    """1 - mean off-diagonal pairwise cosine similarity of the embedding set.

    0.0 means every window collapsed onto one direction (degenerate);
    closer to 1 means the embeddings spread out. Gated on `>= floor` is
    equivalent to gating the raw mean similarity on `<= 1 - floor`; we
    report the **raw mean off-diagonal cosine** as `diversity_proxy` in the
    checks dict and gate on that (see :func:`gate`).
    """
    n = embeddings.shape[0]
    if n < 2:
        return 0.0
    normed = embeddings / (np.linalg.norm(embeddings, axis=1, keepdims=True) + 1e-12)
    sim = normed @ normed.T
    mask = ~np.eye(n, dtype=bool)
    return float(np.mean(sim[mask]))


def evaluate(
    result: TrainResult,
    cadence: str,
    run_id: str,
    created_at_epoch_ms: int,
    thresholds: GateThresholds | None = None,
    spec: ModelSpec | None = None,
) -> EvalReport:
    """Run the proxy suite over a training result and apply the rollback gate.

    Returns an :class:`EvalReport` whose ``verdict`` is ``"pass"`` or
    ``"fail"``. The runner is responsible for the commit/rollback side
    effects; this module is pure (no store access).
    """
    thresholds = thresholds or GateThresholds()
    spec = spec or result.model.spec
    embeddings = result.model.embedding(result.X)

    coherence = temporal_coherence(embeddings)
    raw_diversity = anti_collapse_diversity(embeddings)  # mean off-diag cosine in [~0, 1]

    loss_ok = float(result.final_loss) <= float(thresholds.loss_max)
    diversity_ok = raw_diversity <= float(thresholds.diversity_max)

    report = EvalReport(
        model_id=spec.model_id,
        feature_version=spec.feature_version,
        n_artifacts=int(result.X.shape[0]),
        n_epochs=int(result.epochs),
        final_loss=float(result.final_loss),
        val_loss=result.val_loss,
        coherence=coherence,
        diversity=raw_diversity,
        embedding_dim=int(spec.latent_dim),
        backend=result.backend,
        warm_start=result.warm_start,
        cadence=cadence,
        thresholds=thresholds,
        run_id=run_id,
        created_at_epoch_ms=created_at_epoch_ms,
        checks={
            "final_loss": {"value": float(result.final_loss), "threshold": float(thresholds.loss_max), "rule": "<=", "passed": loss_ok},
            "diversity": {"value": raw_diversity, "threshold": float(thresholds.diversity_max), "rule": "<=", "passed": diversity_ok},
        },
    )
    return report


# ---------------------------------------------------------------------------
# Artifact builders (payload shapes for the adapter to persist)
# ---------------------------------------------------------------------------


def make_run_id(cadence: str, created_at_epoch_ms: int) -> str:
    """Stable run identifier grouped by (cadence, model_id) per Phase D spec."""
    return f"run-{MODEL_ID}-{cadence}-{created_at_epoch_ms}"


def build_embedding_artifact(result: TrainResult, report: EvalReport, upstream_ids: list[str]) -> Artifact:
    """The ``behavioral_embedding`` artifact (only written on gate **pass**)."""
    embeddings = result.model.embedding(result.X)
    rows = result.X.shape[0]
    payloads = {
        f"window-{i:03d}": [float(v) for v in embeddings[i]] for i in range(rows)
    }
    artifact_id = f"{EMBEDDING_ARTIFACT_ID_PREFIX}-{created(report)}_{report.run_id.split('-')[-1]}"
    payload = {
        "artifact_type": "derived.behavioral_embedding",
        "model_id": report.model_id,
        "feature_version": report.feature_version,
        "embedding_model": report.model_id,
        "embedding_dimension": int(report.embedding_dim),
        "n_windows": int(rows),
        "embeddings": payloads,
        "run_id": report.run_id,
        "upstream_artifacts": [str(x) for x in upstream_ids],
        "final_loss": float(report.final_loss),
        "schema_version": SCHEMA_VERSION,
    }
    return Artifact(
        artifact_id=artifact_id,
        source=EMBEDDING_SOURCE,
        payload=payload,
        created_at_epoch_ms=report.created_at_epoch_ms,
        schema_version=SCHEMA_VERSION,
        device_alias="local:pmbrs-representation",
        provenance_metadata_json={"module": "representation", "pipeline": f"phase-d-{report.cadence}"},
        ingested_at_epoch_ms=report.created_at_epoch_ms,
        ingest_status="accepted",
    )


def build_report_artifact(report: EvalReport, upstream_ids: list[str]) -> tuple[Artifact, str]:
    """The ``embedding_evaluation_report`` artifact (written **always**).

    Returns ``(artifact, run_id)`` — the report artifact id carries the run
    id so the two artifacts of a run stay linked (lineage/rollback).
    """
    artifact_id = f"{REPORT_ARTIFACT_ID_PREFIX}-{created(report)}_{report.run_id.split('-')[-1]}"
    payload = report.to_dict()
    payload["upstream_artifacts"] = [str(x) for x in upstream_ids]
    return (
        Artifact(
            artifact_id=artifact_id,
            source=EMBEDDING_SOURCE,
            payload=payload,
            created_at_epoch_ms=report.created_at_epoch_ms,
            schema_version=SCHEMA_VERSION,
            device_alias="local:pmbrs-representation",
            provenance_metadata_json={
                "module": "representation",
                "pipeline": f"phase-d-{report.cadence}",
                "verdict": report.verdict,
            },
            ingested_at_epoch_ms=report.created_at_epoch_ms,
            ingest_status="accepted",
        ),
        artifact_id,
    )


def created(report: EvalReport) -> str:
    """Compact timestamp component for stable artifact ids in one run."""
    return str(report.created_at_epoch_ms)


def run_module_name(cadence: str) -> str:
    """Adapter module name for checkpoint bookkeeping (one per cadence lane)."""
    return f"pmbrs_embedding_{cadence}"
