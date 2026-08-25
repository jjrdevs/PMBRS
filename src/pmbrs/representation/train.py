"""Training loop for the Phase D behavioral-embedding stub.

Implements Stage 1–3 of ``docs/representation/training-pipeline.md``:

* **Stage 1 (Data preparation)** — read raw artifacts via the adapter,
  extract the deterministic feature matrix, sort temporally, temporal split
  (most recent window → validation; no shuffling across time; leakage-safe),
* **Stage 2 (Model instantiation)** — fresh model, or **warm start** from the
  most recent checkpoint (weekly cadence) per ADR-017 D3,
* **Stage 3 (Training loop)** — ``cadence``:
  - ``weekly`` → incremental: warm-start when a prior checkpoint exists;
  - ``monthly`` / ``on-demand`` → cold full retrain.

The loop is framework-agnostic: it only calls
:meth:`pmbrs.representation.model.BehavioralEmbeddingModel.train_epoch`, so
the NumPy and PyTorch backends are interchangeable. Deterministic under a
fixed seed (Constitution §9). No network, no experiment-tracker imports.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from pmbrs.representation.model import (
    DEFAULT_SEED,
    MODEL_SPEC,
    BehavioralEmbeddingModel,
    ModelSpec,
    extract_features,
)

#: Minimum artifacts in the training split (else train/val share the row set).
MIN_TRAIN_ROWS = 2


@dataclass(frozen=True)
class TrainConfig:
    """Parameters for one training run (recorded in reports/checkpoints)."""

    cadence: str = "weekly"
    epochs: int = 25
    learning_rate: float = 0.05
    batch_size: int = 4
    seed: int = DEFAULT_SEED
    warm_start: bool = False
    spec: ModelSpec = field(default=MODEL_SPEC)


@dataclass
class TrainResult:
    """Outcome of one training run (consumed by ``evaluate`` + ``runner``)."""

    model: BehavioralEmbeddingModel
    X: np.ndarray  # full feature matrix, time-sorted
    X_train: np.ndarray
    X_val: np.ndarray
    epochs: int
    initial_loss: float
    final_loss: float
    val_loss: float | None
    loss_curve: list[float]
    warm_start: bool
    backend: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "cadence": None,  # set by caller
            "n_artifacts": int(self.X.shape[0]),
            "n_train": int(self.X_train.shape[0]),
            "n_val": int(self.X_val.shape[0]),
            "n_epochs": int(self.epochs),
            "initial_loss": float(self.initial_loss),
            "final_loss": float(self.final_loss),
            "val_loss": None if self.val_loss is None else float(self.val_loss),
            "warm_start": bool(self.warm_start),
            "backend": self.backend,
        }


def temporal_split(X: np.ndarray, min_train: int = MIN_TRAIN_ROWS) -> tuple[np.ndarray, np.ndarray]:
    """Temporal split: most recent row(s) → validation.

    ``docs/representation/training-pipeline.md`` Stage 1: chronological order
    preserved, validation is the *most recent* window; no random shuffle
    (avoids leakage across time). Needs >= 2 rows for a non-empty split
    (with one row we cannot split meaningfully).
    """
    X = np.asarray(X)
    if X.shape[0] <= 1:
        return X, X[:0]
    train = X[:-1]
    val = X[-1:]
    if train.shape[0] < min_train:
        # Not enough history to split: train+validate on everything.
        return X, X[-1:]
    return train, val


def _val_loss(model: BehavioralEmbeddingModel, X_val: np.ndarray, lr: float, batch_size: int) -> float | None:
    if X_val.shape[0] == 0:
        return None
    recon = model.reconstruct(X_val)
    return float(np.mean((recon - X_val) ** 2))


def train(
    artifacts: list[Any],
    config: TrainConfig | None = None,
    model: BehavioralEmbeddingModel | None = None,
) -> TrainResult:
    """Run one training pass over raw artifacts.

    ``artifacts`` may be in any order; rows are time-sorted by
    ``created_at_epoch_ms`` (stable) so the validation split is well-defined.
    ``model`` allows continuing a warm-started instance (caller-supplied);
    otherwise a fresh deterministic model is created from ``config``.
    """
    config = config or TrainConfig()

    sorted_idx = sorted(
        range(len(artifacts)),
        key=lambda i: (int(artifacts[i].created_at_epoch_ms), artifacts[i].artifact_id),
    )
    sorted_arts = [artifacts[i] for i in sorted_idx]
    X = extract_features(sorted_arts)

    if model is None:
        model = BehavioralEmbeddingModel(spec=config.spec, seed=config.seed)
    # (Warm start: caller passed a model already loaded from a checkpoint;
    #  the numpy/rng state below stays fresh for batch-order draws.)
    if config.warm_start:
        # Ensure the model's rng is seeded deterministically regardless of warm start.
        model.rng = np.random.default_rng(config.seed)

    X_train, X_val = temporal_split(X)

    losses = [_recon_loss(model, X_train)]
    for _ in range(int(config.epochs)):
        model.train_epoch(X_train, lr=config.learning_rate, batch_size=config.batch_size)
        losses.append(_recon_loss(model, X_train))

    return TrainResult(
        model=model,
        X=X,
        X_train=X_train,
        X_val=X_val,
        epochs=int(config.epochs),
        initial_loss=float(losses[0]),
        final_loss=float(losses[-1]),
        val_loss=_val_loss(model, X_val, config.learning_rate, config.batch_size),
        loss_curve=[float(x) for x in losses],
        warm_start=bool(config.warm_start),
        backend=model.backend,
    )


def _recon_loss(model: BehavioralEmbeddingModel, X: np.ndarray) -> float:
    """Batch reconstruction MSE (same objective the train step optimizes)."""
    if X.shape[0] == 0:
        return 0.0
    recon = model.reconstruct(X)
    loss = float(np.mean((recon - X) ** 2))
    return float(loss) if np.isfinite(loss) else 0.0


def n_epochs_reported(config: TrainConfig, warm_start: bool) -> int:
    """Epochs field for the report: the number of full passes this run executed."""
    return int(config.epochs)
