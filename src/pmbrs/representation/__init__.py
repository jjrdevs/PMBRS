"""PMBRS Phase D — representation learning (training pipeline stub).

Implements the batch-first training loop required by ADR-017 D3:

* ``nightly passover`` / ``weekly incremental (warm-start)`` / ``monthly full
  retrain`` (see ``docs/representation/training-pipeline.md``),
* a small autoencoder stub over a deterministic feature set derived from raw
  artifact payloads (``model.py``),
* the training loop (``train.py``),
* the proxy-evaluation suite + rollback gate (``evaluate.py``),
* checkpoint save/load for warm starts (``checkpoint.py``),
* the offline-first CLI (``runner.py``).

``--local`` (the default) is airtight: no network, no ``mlflow`` import on
that code path (Constitution §16). MLflow logging is OPT-IN via ``--mlflow``
and is wrapped so an unreachable tracker never crashes a training run.

All store I/O goes through ``pmbrs.core.storage.StorageAdapter`` per
``docs/module-contracts.md`` — this module never opens store files directly.
"""

from pmbrs.representation.model import (
    FEATURE_VERSION,
    MODEL_ID,
    MODEL_SPEC,
    BehavioralEmbeddingModel,
    ModelSpec,
    extract_features,
)
# NOTE: we deliberately do NOT re-export the `train` and `evaluate` function
# names here — doing so would shadow the sibling submodules
# `pmbrs.representation.train` and `pmbrs.representation.evaluate`, breaking
# runner.py's `from pmbrs.representation import train as train_mod` /
# `evaluate as evals` (function object is not a module). The classes and
# constants are safe to re-export. Consumers who want the train/evaluate
# functions should import them directly from the submodules.
from pmbrs.representation.train import TrainConfig, TrainResult
from pmbrs.representation.evaluate import (
    EvalReport,
    GateThresholds,
    build_embedding_artifact,
    build_report_artifact,
)
from pmbrs.representation.checkpoint import (
    load_model_checkpoint,
    save_model_checkpoint,
)

__all__ = [
    "MODEL_ID",
    "FEATURE_VERSION",
    "MODEL_SPEC",
    "ModelSpec",
    "BehavioralEmbeddingModel",
    "extract_features",
    "TrainConfig",
    "TrainResult",
    # `train` and `evaluate` deliberately NOT re-exported — they would
    # shadow the submodule names; import them from the submodules directly.
    "EvalReport",
    "GateThresholds",
    "build_embedding_artifact",
    "build_report_artifact",
    "save_model_checkpoint",
    "load_model_checkpoint",
]
