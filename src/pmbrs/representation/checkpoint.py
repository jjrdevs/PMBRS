"""Model checkpoint save/load for warm starts (Phase D, Stage 2).

The checkpoint is a single JSON document living under the adapter-managed
``checkpoint_root`` (``~/.pmbrs-private/checkpoints/pmbrs_embedding_<cadence>.json``
via :meth:`StorageAdapter._checkpoint_path`, which :func:`save_model_checkpoint`
reuses by delegating to the adapter's managed path). It records enough to
rebuild the exact model deterministically (Constitution §9 reproducibility):

* ``spec``            — architecture + hyperparameter snapshot,
* ``weights``         — :meth:`BehavioralEmbeddingModel.state_dict` (portable,
                        JSON-safe; NumPy and PyTorch backends load the same weights),
* ``metadata``        — model_id, feature_version, seed, backend, cadence,
                        the training run it came from (run_id, final_loss).

``save_model_checkpoint`` writes via the adapter (readonly-guard respected,
single-file-per-artifact discipline kept). ``load_model_checkpoint`` rebuilds
a :class:`BehavioralEmbeddingModel` and restores weights — this is the
warm-start path used by ``--cadence weekly``.

No network access and no experiment-tracker imports in this module.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from pmbrs.core.storage import StorageAdapter
from pmbrs.representation.model import BehavioralEmbeddingModel, ModelSpec

SCHEMA_VERSION = "1.0"


def _model_record(adapter: StorageAdapter, cadence: str) -> Path:
    module = f"pmbrs_embedding_{cadence}"
    safe = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in module) or "module"
    # NOTE: this is a distinct file from the adapter's own module-completion
    # checkpoint (``mark_module_complete``), per the plan's requirement that a
    # *model* checkpoint (weights) live under checkpoints/<module>.json for
    # the cadence lane. Both live under the same managed checkpoint_root.
    return adapter.checkpoint_root / f"model-{safe}.json"


def save_model_checkpoint(
    adapter: StorageAdapter,
    model: BehavioralEmbeddingModel,
    cadence: str,
    *,
    run_id: str | None = None,
    final_loss: float | None = None,
    n_epochs: int | None = None,
    seed: int | None = None,
) -> Path:
    """Persist the model weights + spec for later warm starts.

    Writes ``<checkpoint_root>/model-pmbrs_embedding_<cadence>.json`` and
    honors the adapter's readonly-root guard (raises ``PermissionError`` if
    the checkpoint root is deny-listed — it is not by default).
    """
    target = _model_record(adapter, cadence)
    adapter._assert_writable(target)  # readonly-root guard (adapter contract)
    record: dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "module": f"pmbrs_embedding_{cadence}",
        "model_id": model.spec.model_id,
        "feature_version": model.spec.feature_version,
        "backend": model.backend,
        "seed": int(seed if seed is not None else model.seed),
        "spec": {
            "model_id": model.spec.model_id,
            "feature_version": model.spec.feature_version,
            "dims": [int(d) for d in model.spec.dims],
            "latent_index": int(model.spec.latent_index),
            "learning_rate": float(model.spec.learning_rate),
            "batch_size": int(model.spec.batch_size),
        },
        "weights": model.state_dict(),
        "metadata": {
            "cadence": cadence,
            "run_id": run_id,
            "final_loss": None if final_loss is None else float(final_loss),
            "n_epochs": None if n_epochs is None else int(n_epochs),
            "saved_at_epoch_ms": int(time.time() * 1000),
        },
    }
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(f".json.tmp-{int(time.time() * 1000)}")
    tmp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(target)
    return target


def load_model_checkpoint(adapter: StorageAdapter, cadence: str) -> BehavioralEmbeddingModel | None:
    """Load the most recent model checkpoint for a cadence lane, or ``None``.

    Rebuilds the exact spec, then restores the portable weight state — the
    warm-start path (``--cadence weekly``). A corrupt or missing checkpoint
    yields ``None`` (the caller then falls back to a cold start).
    """
    target = _model_record(adapter, cadence)
    if not target.exists():
        return None
    try:
        record = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    spec_data = record.get("spec") or {}
    try:
        spec = ModelSpec(
            model_id=str(spec_data.get("model_id") or record.get("model_id") or "pmbrs-embedding-stub-ae"),
            feature_version=str(spec_data.get("feature_version") or record.get("feature_version") or "features-v0"),
            dims=tuple(int(d) for d in (spec_data.get("dims") or (16, 12, 8, 12, 16))),
            latent_index=int(spec_data.get("latent_index", 2)),
            learning_rate=float(spec_data.get("learning_rate", 0.05)),
            batch_size=int(spec_data.get("batch_size", 4)),
        )
    except (TypeError, ValueError):
        return None

    try:
        model = BehavioralEmbeddingModel(spec=spec, seed=int(record.get("seed", 1337)))
        model.load_state_dict({k: [float(v) for v in vals] for k, vals in (record.get("weights") or {}).items()})
    except (KeyError, ValueError, TypeError, ImportError):
        return None
    return model


def checkpoint_record(adapter: StorageAdapter, cadence: str) -> dict[str, Any] | None:
    """Raw checkpoint JSON (for reporting/inspection), or ``None`` if absent."""
    target = _model_record(adapter, cadence)
    if not target.exists():
        return None
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
