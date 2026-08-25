"""Behavioral embedding model (Phase D stub) + deterministic feature extraction.

Design notes
------------
* The model is a small **autoencoder** (16 -> 12 -> 8 -> 12 -> 16; tanh
  hidden units, linear output) trained with SGD to reconstruct its own input
  feature vector. The 8-dim bottleneck (``latent``) is the per-window
  **behavioral embedding** — the shape matches
  ``docs/artifacts/examples/embedding_artifact_example.yaml``
  (``embedding_dimension: 8``).
* **Framework-swappable** (``docs/module-contracts.md`` module-independence):
  the same :class:`ModelSpec` and the same :class:`BehavioralEmbeddingModel`
  interface run on either a PyTorch backend (target backend, spec) or a
  hand-rolled NumPy backend (guaranteed-offline fallback). Weight state is
  exchanged only through :meth:`state_dict` / :meth:`load_state_dict` as
  plain ``{layer: [floats]}`` (JSON-serializable), so checkpoints are
  byte-identical across backends. ``torch`` is selected automatically when
  importable (``PMBRS_BACKEND`` env or ``backend="torch"`` forces a choice).
* Feature extraction is **deterministic and stdlib+numpy only**
  (Constitution §9 reproducibility): a one-hot source, a sha256-derived
  vector of the canonical payload JSON, and a few payload-shape statistics.
  The 5 demo artifacts are far too small for a predictive model — the goal
  is a well-formed ``behavioral_embedding`` artifact the rollback gate can
  judge, not accuracy.
* No network access and no experiment-tracker imports anywhere in this module.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
from dataclasses import dataclass
from typing import Any

import numpy as np

#: Version string stamped into artifacts and checkpoints whenever the feature
#: extraction below changes (training-pipeline.md §Configuration Versioning).
FEATURE_VERSION = "features-v0-payload-shape"

#: Stable model identity for the Phase D stub. ADR-011 model selection is
#: pending; per model-selection.md this stub is replaceable without an
#: interface change.
MODEL_ID = "pmbrs-embedding-stub-ae"

#: Embedding dimension (bottleneck) — matches the doc example (8).
EMBEDDING_DIM = 8

#: Default deterministic seed (Constitution §9 — reproducibility).
DEFAULT_SEED = 1337


@dataclass(frozen=True)
class ModelSpec:
    """Architecture + hyperparameter snapshot for one model build.

    Recorded verbatim in checkpoints and evaluation reports so a run is fully
    reproducible (training-pipeline.md §Configuration Versioning).
    """

    model_id: str = MODEL_ID
    feature_version: str = FEATURE_VERSION
    dims: tuple[int, ...] = (17, 12, 8, 12, 17)
    latent_index: int = 2  # layer whose input is the behavioral embedding
    learning_rate: float = 0.05
    batch_size: int = 4

    def __post_init__(self) -> None:
        if len(self.dims) < 3:
            raise ValueError("needs a bottleneck architecture (>= 3 dims)")
        if not (0 < self.latent_index < len(self.dims) - 1):
            raise ValueError("latent_index must point at an interior layer")

    @property
    def input_dim(self) -> int:
        return int(self.dims[0])

    @property
    def latent_dim(self) -> int:
        return int(self.dims[self.latent_index])


#: The default spec used by the Phase D stub.
MODEL_SPEC = ModelSpec()


# ---------------------------------------------------------------------------
# Feature extraction (deterministic, stdlib + numpy only)
# ---------------------------------------------------------------------------

_SOURCE_ORDER = ("mobile", "browser", "desktop", "journal", "other")


def canonical_payload_json(payload: dict[str, Any]) -> str:
    """Stable JSON serialization of a payload (sorted keys, compact)."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def hash_vector(text: str, n: int) -> list[float]:
    """Derive ``n`` values in [-1, 1] from the sha256 of ``text``.

    Pure function of the input — deterministic across runs and platforms.
    (A hash-based projection is the documented, intentional stand-in for a
    learned feature encoder in this stub.)
    """
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    values: list[float] = []
    i = 0
    while len(values) < n:
        lo = digest[i % len(digest)]
        hi = digest[(i + 1) % len(digest)]
        values.append((lo * 256 + hi) / 65535.0 * 2.0 - 1.0)
        i += 2
    return values


def _payload_depth(payload: Any) -> int:
    if isinstance(payload, dict):
        return 1 + max((_payload_depth(v) for v in payload.values()), default=0)
    if isinstance(payload, (list, tuple)):
        return 1 + max((_payload_depth(v) for v in payload), default=0)
    return 1


def _count_scalars(payload: Any) -> int:
    if isinstance(payload, dict):
        return sum(_count_scalars(v) for v in payload.values())
    if isinstance(payload, (list, tuple)):
        return sum(_count_scalars(v) for v in payload)
    return int(isinstance(payload, (int, float, str)) and not isinstance(payload, bool))


def extract_feature(artifact: Any) -> list[float]:
    """Deterministic 16-d feature vector for one raw artifact.

    Layout: ``[one-hot source (5)] + [sha256 payload vector (8)] +
    [n_keys/16, depth/8, n_scalars/16, has_kind (4)]``.
    """
    payload = dict(artifact.payload or {})
    source = (artifact.source or "other").lower()
    if source.startswith("browser"):
        source = "browser"
    if source not in _SOURCE_ORDER:
        source = "other"

    vec: list[float] = [1.0 if s == source else 0.0 for s in _SOURCE_ORDER]
    vec += hash_vector(canonical_payload_json(payload), 8)
    n_keys = float(len(payload))
    vec.append(min(n_keys / 16.0, 1.0))
    vec.append(min(_payload_depth(payload) / 8.0, 1.0))
    vec.append(min(_count_scalars(payload) / 16.0, 1.0))
    vec.append(1.0 if "kind" in payload else 0.0)
    return vec


def extract_features(artifacts: list[Any]) -> np.ndarray:
    """Feature matrix ``(n_artifacts x input_dim)``; rows keep input order."""
    if not artifacts:
        raise ValueError("no artifacts to extract features from")
    return np.array([extract_feature(a) for a in artifacts], dtype=np.float32)


# ---------------------------------------------------------------------------
# Backends (NumPy fallback always; PyTorch when available)
# ---------------------------------------------------------------------------

def _tanh_act(z: np.ndarray) -> np.ndarray:
    return np.tanh(z)


class NumpyAutoencoderBackend:
    """Mini-batch SGD autoencoder, plain NumPy (guaranteed-offline path)."""

    name = "numpy"

    def __init__(self, spec: ModelSpec, seed: int) -> None:
        rng = np.random.default_rng(seed)
        n_layers = len(spec.dims) - 1
        self.W = [
            (rng.standard_normal((spec.dims[i], spec.dims[i + 1])) * (4.0 / math.sqrt(spec.dims[i]))).astype(np.float32)
            for i in range(n_layers)
        ]
        self.b = [np.zeros(spec.dims[i + 1], dtype=np.float32) for i in range(n_layers)]

    # -- forward -------------------------------------------------------------
    def activations(self, x: np.ndarray) -> list[np.ndarray]:
        """Layer activations: ``acts[k]`` is the *input* to layer k."""
        acts = [x]
        a = x
        n_layers = len(self.W)
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            a = np.tanh(a @ W + b) if i < n_layers - 1 else (a @ W + b)
            acts.append(a)
        return acts

    def forward(self, x: np.ndarray) -> np.ndarray:
        return self.activations(x)[-1]

    # The latent (behavioral embedding) is the input to the decoder half.
    def latent(self, x: np.ndarray, latent_index: int) -> np.ndarray:
        return self.activations(x)[latent_index]

    def train_step(self, X: np.ndarray, lr: float, batch_size: int, rng: np.random.Generator) -> float:
        n = X.shape[0]
        batch_size = max(1, min(batch_size, n))
        order = rng.permutation(n)
        total = 0.0
        batches = 0
        n_layers = len(self.W)
        for start in range(0, n, batch_size):
            x = X[order[start : start + batch_size]]
            m = x.shape[0]
            acts = self.activations(x)
            recon = acts[-1]
            err = recon - x
            total += float(np.sum(err * err))
            batches += 1
            # dL/doutput = 2*err/m (linear output layer).
            delta = (2.0 * err) / m
            for i in range(n_layers - 1, -1, -1):
                self.W[i] = self.W[i] - lr * (acts[i].T @ delta)
                self.b[i] = self.b[i] - lr * delta.sum(axis=0)
                if i > 0:
                    delta = delta @ self.W[i].T * (1.0 - np.tanh(acts[i + 1]) ** 2)
        return total / max(batches, 1)

    # -- portable weight state ------------------------------------------------
    def state_dict(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        for i, (W, b) in enumerate(zip(self.W, self.b)):
            out[f"W{i}"] = [float(v) for v in np.asarray(W).ravel()]
            out[f"b{i}"] = [float(v) for v in np.asarray(b).ravel()]
        return out

    def load_state_dict(self, state: dict[str, list[float]]) -> None:
        for i in range(len(self.W)):
            self.W[i] = np.array(state[f"W{i}"], dtype=np.float32).reshape(self.W[i].shape)
            self.b[i] = np.array(state[f"b{i}"], dtype=np.float32).reshape(self.b[i].shape)


class TorchAutoencoderBackend:
    """PyTorch autoencoder (target backend). Same state-dict layout as NumPy."""

    name = "torch"

    def __init__(self, spec: ModelSpec, seed: int) -> None:
        try:
            import torch
        except ImportError as exc:  # pragma: no cover - env dependent
            raise ImportError("torch is required for the torch backend") from exc
        self._torch = torch
        torch.manual_seed(seed)
        if not torch.has_cuda:
            torch.set_num_threads(1)
        dims = list(spec.dims)
        layers: list[Any] = []
        for i in range(len(dims) - 1):
            layers.append(torch.nn.Linear(dims[i], dims[i + 1]))
            layers.append(torch.nn.Identity() if i == len(dims) - 2 else torch.nn.Tanh())
        self._net = torch.nn.Sequential(*layers)

    def _to(self, x: np.ndarray) -> Any:
        return self._torch.from_numpy(np.ascontiguousarray(x.astype(np.float32)))

    def activations(self, x: np.ndarray) -> list[np.ndarray]:
        torch = self._torch
        a = self._to(x)
        acts = [a]
        with torch.no_grad():
            for mod in self._net:
                a = mod(a)
                acts.append(a.detach().cpu().numpy())
        return acts

    def forward(self, x: np.ndarray) -> np.ndarray:
        return self.activations(x)[-1]

    def latent(self, x: np.ndarray, latent_index: int) -> np.ndarray:
        return self.activations(x)[latent_index]

    def train_step(self, X: np.ndarray, lr: float, batch_size: int, rng: np.random.Generator) -> float:
        torch = self._torch
        self._net.train()
        opt = torch.optim.SGD(self._net.parameters(), lr=lr)
        tensor = self._to(X)
        n = X.shape[0]
        batch_size = max(1, min(batch_size, n))
        order = rng.permutation(n)
        total = 0.0
        batches = 0
        for start in range(0, n, batch_size):
            xb = tensor[order[start : start + batch_size]]
            opt.zero_grad()
            loss = torch.nn.functional.mse_loss(self._net(xb), xb)
            loss.backward()
            opt.step()
            total += float(loss.item())
            batches += 1
        return total / max(batches, 1)

    # -- portable weight state ------------------------------------------------
    def state_dict(self) -> dict[str, list[float]]:
        out: dict[str, list[float]] = {}
        i = 0
        for mod in self._net:
            if isinstance(mod, self._torch.nn.Linear):
                out[f"W{i}"] = [float(v) for v in mod.weight.detach().cpu().numpy().ravel()]
                out[f"b{i}"] = [float(v) for v in mod.bias.detach().cpu().numpy().ravel()]
                i += 1
        return out

    def load_state_dict(self, state: dict[str, list[float]]) -> None:
        torch = self._torch
        i = 0
        with torch.no_grad():
            for mod in self._net:
                if isinstance(mod, torch.nn.Linear):
                    w = torch.tensor(state[f"W{i}"], dtype=torch.float32).reshape(mod.weight.shape)
                    b = torch.tensor(state[f"b{i}"], dtype=torch.float32).reshape(mod.bias.shape)
                    mod.weight.copy_(w)
                    mod.bias.copy_(b)
                    i += 1


def _make_backend(spec: ModelSpec, backend: str, seed: int) -> NumpyAutoencoderBackend | TorchAutoencoderBackend:
    if backend == "numpy":
        return NumpyAutoencoderBackend(spec, seed)
    try:
        return TorchAutoencoderBackend(spec, seed)
    except ImportError:
        if backend == "torch":
            raise
        return NumpyAutoencoderBackend(spec, seed)


# ---------------------------------------------------------------------------
# Unified model interface
# ---------------------------------------------------------------------------


class BehavioralEmbeddingModel:
    """Backend-agnostic behavioral-embedding model (autoencoder stub).

    * :meth:`embedding` — latent (behavioral embedding) for input features.
    * :meth:`reconstruct` — full autoencoder output.
    * :meth:`train_epoch` — one mini-batch SGD epoch → mean MSE loss.
    * :meth:`state_dict` / :meth:`load_state_dict` — portable, JSON-safe weights.
    """

    def __init__(self, spec: ModelSpec = MODEL_SPEC, backend: str = "auto", seed: int = DEFAULT_SEED) -> None:
        self.spec = spec
        self.seed = int(seed)
        self.rng = np.random.default_rng(seed)
        name = os.environ.get("PMBRS_BACKEND", backend)
        if name not in ("auto", "numpy", "torch"):
            raise ValueError(f"unknown backend: {name!r}")
        self._backend = _make_backend(spec, name, seed)

    @property
    def backend(self) -> str:
        return self._backend.name

    @property
    def n_params(self) -> int:
        return sum(len(v) for v in self.state_dict().values())

    def embedding(self, X: np.ndarray) -> np.ndarray:
        """Latent behavioral embedding ``(n x latent_dim)`` for ``X``."""
        return np.asarray(self._backend.latent(X, self.spec.latent_index), dtype=np.float32)

    def reconstruct(self, X: np.ndarray) -> np.ndarray:
        return np.asarray(self._backend.forward(X), dtype=np.float32)

    def train_epoch(self, X: np.ndarray, lr: float | None = None, batch_size: int | None = None) -> float:
        return float(
            self._backend.train_step(
                X,
                lr=float(lr if lr is not None else self.spec.learning_rate),
                batch_size=int(batch_size if batch_size is not None else self.spec.batch_size),
                rng=self.rng,
            )
        )

    def state_dict(self) -> dict[str, list[float]]:
        return {k: [float(v) for v in vals] for k, vals in sorted(self._backend.state_dict().items())}

    def load_state_dict(self, state: dict[str, list[float]]) -> None:
        self._backend.load_state_dict(state)
