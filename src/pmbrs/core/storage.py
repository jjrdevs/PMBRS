"""PMBRS ``StorageAdapter`` — the single consumer-facing store interface.

Implements the adapter contract sketched in ``docs/module-contracts.md``
(save / get / query / derive_from / mark_module_complete / get_last_run)
for the **raw JSON layer** that is in use today (ADR-017 D2). The JSONL +
SQLite target layer is a future concern and is deliberately *not* built here.

Hard rules honored here:

* All root paths derive from ``config/external_data_policy.json``
  (raw, summary, pending, checkpoints, hermes_readonly, state).
* ``save`` writes ``raw/<source>/<artifactId>-<createdAtEpochMs>.json`` and
  returns the absolute path.
* ``hermes_readonly_root`` is **read-only** for this adapter: any write
  targeting it raises :class:`PermissionError`. The only writer of that tree
  is the existing publish path (``src/pmbrs_runtime.py``), per the read-only
  policy in ``config/external_data_policy.json``.
* Stdlib only (dataclasses, json, pathlib, typing) — no SQLite, no JSONL.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from pmbrs.core.artifact import Artifact, LineageEdge

DEFAULT_CONFIG_PATH = Path("/home/jjrdev/workspace/pmbrs/config/external_data_policy.json")

#: Canonical raw sources (docs/storage/architecture.md; same set the ingest
#: endpoint normalizes to in scripts/pmbrs_host_sync_ingest.py).
VALID_SOURCES: frozenset[str] = frozenset({"mobile", "browser", "desktop", "journal", "other"})

_POLICY_ROOT_KEYS = (
    "artifact_root",
    "state_root",
    "checkpoint_root",
    "hermes_readonly_root",
    "queue_root",
    "raw_root",
    "summary_root",
)


def default_config_path() -> Path:
    """Canonical location of the external-data policy for this deployment."""
    return DEFAULT_CONFIG_PATH


@dataclass(frozen=True)
class ModuleRun:
    """Checkpoint record describing one completed module run (module contract
    ``get_last_run`` returns this)."""

    module: str
    completed_at_epoch_ms: int
    artifact_ids: tuple[str, ...] = field(default_factory=tuple)
    run_id: str | None = None


class StorageAdapter:
    """Single-process artifact store adapter over the JSON raw layer.

    Consumers (dashboard, training stub, future pipeline modules) must route
    *all* store access through this class; they never open store files or
    paths directly (``docs/module-contracts.md`` core rule).

    Write-guarantee: the ``hermes_readonly`` root is refused for writes —
    the adapter treats :attr:`readonly_roots` as deny-listed destinations and
    raises :class:`PermissionError` if any save/checkpoint/write would land
    inside one of them.
    """

    def __init__(self, config_path: str | Path = DEFAULT_CONFIG_PATH) -> None:
        self.config_path = Path(config_path)
        self.policy: dict[str, Any] = self._load_policy(self.config_path)
        for key in _POLICY_ROOT_KEYS:
            if key not in self.policy:
                raise ValueError(f"policy file {self.config_path} is missing required root '{key}'")

        self.artifact_root = Path(self.policy["artifact_root"]).resolve()
        self.state_root = Path(self.policy["state_root"]).resolve()
        self.checkpoint_root = Path(self.policy["checkpoint_root"]).resolve()
        self.hermes_readonly_root = Path(self.policy["hermes_readonly_root"]).resolve()
        self.pending_root = Path(self.policy["queue_root"]).resolve()
        self.raw_root = Path(self.policy["raw_root"]).resolve()
        self.summary_root = Path(self.policy["summary_root"]).resolve()

        # READ-ONLY GUARD: roots this adapter must never write to.
        # Default = {hermes_readonly_root}; callers may deny-list more.
        self.readonly_roots: frozenset[Path] = frozenset({self.hermes_readonly_root})

        self._ensure_directories()

        # In-memory lineage DAG: child_id -> list of edges (in this phase
        # only). NOTE: persistence is intentionally NOT done here — the
        # JSONL/SQLite layer (ADR-001 target) will own durable lineage edges
        # once it ships. Re-deriving edges from artifacts is a later phase.
        self._lineage: dict[str, list[LineageEdge]] = {}

    # -- construction helpers -------------------------------------------------

    @staticmethod
    def _load_policy(config_path: Path) -> dict[str, Any]:
        with config_path.open("r", encoding="utf-8") as fh:
            return json.load(fh)

    def _ensure_directories(self) -> None:
        for path in (
            self.artifact_root,
            self.state_root,
            self.checkpoint_root,
            self.pending_root,
            self.raw_root,
            self.summary_root,
            self.hermes_readonly_root,
        ):
            path.mkdir(parents=True, exist_ok=True)

    # -- readonly guard ---------------------------------------------------------

    def _assert_writable(self, path: Path) -> None:
        """Refuse any write landing inside a readonly root (PermissionError)."""
        target = path.resolve()
        for root in self.readonly_roots:
            if target == root or root in target.parents:
                raise PermissionError(
                    f"refusing write to read-only root: {target} "
                    f"(inside {root}); only the publish path may write there"
                )

    # -- artifact CRUD ----------------------------------------------------------

    @staticmethod
    def _normalize_source(source: str) -> str:
        normalized = (source or "").strip().lower()
        # Legacy browser_* names normalize to canonical "browser" (ingest parity).
        if normalized.startswith("browser"):
            return "browser"
        return normalized if normalized in VALID_SOURCES else "other"

    def save(self, artifact: Artifact) -> str:
        """Persist one artifact to ``raw/<source>/<artifactId>-<createdAtEpochMs>.json``.

        Returns the absolute file path written. Raises :class:`PermissionError`
        if the destination falls inside a readonly root.
        """
        source = self._normalize_source(artifact.source)
        target = self.raw_root / source / f"{artifact.artifact_id}-{int(artifact.created_at_epoch_ms)}.json"
        self._assert_writable(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic-ish replace: write then replace so readers never see partial JSON.
        tmp = target.with_suffix(f".json.tmp-{int(time.time() * 1000)}")
        tmp.write_text(json.dumps(artifact.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(target)
        return str(target)

    def get(self, artifact_id: str) -> Artifact:
        """Load the artifact with the given id from ``raw/``.

        Searches ``raw/<source>/**`` for a matching ``artifactId`` field.
        Raises :class:`FileNotFoundError` if no stored artifact matches.
        """
        for path in self._iter_raw_files():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            artifact = Artifact.from_dict(data)
            if artifact.artifact_id == artifact_id:
                return artifact
        raise FileNotFoundError(f"artifact not found in raw store: {artifact_id!r}")

    def query(
        self,
        source: str | None = None,
        from_epoch: int | None = None,
        to_epoch: int | None = None,
        payload_kind: str | None = None,
        limit: int | None = None,
    ) -> list[Artifact]:
        """Query raw artifacts without consumers touching store files.

        Filters:
          * ``source``     — canonical source (``mobile|browser|desktop|journal|other``)
          * ``from_epoch`` — inclusive lower bound on ``createdAtEpochMs``
          * ``to_epoch``   — inclusive upper bound on ``createdAtEpochMs``
          * ``payload_kind`` — exact match on ``payload["kind"]``
          * ``limit``      — max results (after sorting by created time, asc)
        """
        matches: list[Artifact] = []
        for path in self._iter_raw_files():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                artifact = Artifact.from_dict(data)
            except (OSError, json.JSONDecodeError, TypeError, ValueError):
                continue  # skip unreadable / malformed files; schema gate is a later stage
            if source is not None and self._normalize_source(artifact.source) != self._normalize_source(source):
                continue
            if from_epoch is not None and artifact.created_at_epoch_ms < int(from_epoch):
                continue
            if to_epoch is not None and artifact.created_at_epoch_ms > int(to_epoch):
                continue
            if payload_kind is not None and artifact.payload.get("kind") != payload_kind:
                continue
            matches.append(artifact)

        matches.sort(key=lambda a: (a.created_at_epoch_ms, a.artifact_id))
        if limit is not None:
            matches = matches[: int(limit)]
        return matches

    def _iter_raw_files(self) -> Iterable[Path]:
        if not self.raw_root.exists():
            return []
        for path in sorted(self.raw_root.rglob("*.json")):
            if path.is_file():
                yield path

    # -- lineage ----------------------------------------------------------------

    def derive_from(
        self,
        upstream_ids: Iterable[str],
        module: str,
        output_id: str,
        edge_type: str = "derived",
    ) -> LineageEdge:
        """Record a lineage edge: ``output_id`` is derived from ``upstream_ids``
        by ``module``.

        IN-MEMORY ONLY for this phase (see NOTE above); durable edge storage
        lands with the JSONL+SQLite layer (ADR-001 target).
        """
        parents = tuple(str(x) for x in upstream_ids)
        edge = LineageEdge(
            child_id=str(output_id),
            parent_ids=parents,
            edge_type=edge_type,
            module=str(module),
            created_at_epoch_ms=int(time.time() * 1000),
        )
        self._lineage.setdefault(str(output_id), []).append(edge)
        return edge

    def lineage_edges(self, artifact_id: str) -> list[LineageEdge]:
        """Return the recorded lineage edges for one derived artifact (in-memory)."""
        return list(self._lineage.get(str(artifact_id), []))

    # -- checkpointing -----------------------------------------------------------

    def _checkpoint_path(self, module: str) -> Path:
        # Sanitize module names so they cannot escape the checkpoint root.
        safe = "".join(ch if (ch.isalnum() or ch in "-_.") else "-" for ch in str(module)) or "module"
        return self.checkpoint_root / f"{safe}.json"

    def mark_module_complete(self, module: str, artifact_ids: list[str] | None = None) -> Path:
        """Record that ``module`` completed a run; persists to
        ``<checkpoint_root>/<module>.json``. Returns the checkpoint path."""
        checkpoint = self._checkpoint_path(module)
        self._assert_writable(checkpoint)
        payload = {
            "module": str(module),
            "completedAtEpochMs": int(time.time() * 1000),
            "artifactIds": [str(x) for x in (artifact_ids or [])],
            "schemaVersion": "1.0",
        }
        checkpoint.parent.mkdir(parents=True, exist_ok=True)
        tmp = checkpoint.with_suffix(f".json.tmp-{int(time.time() * 1000)}")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(checkpoint)
        return checkpoint

    def get_last_run(self, module: str) -> ModuleRun | None:
        """Return the most recent checkpoint for ``module``, or None if it has
        never run (module contract ``get_last_run``)."""
        path = self._checkpoint_path(module)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        ids = data.get("artifactIds") or []
        return ModuleRun(
            module=str(data.get("module") or module),
            completed_at_epoch_ms=int(data.get("completedAtEpochMs") or 0),
            artifact_ids=tuple(str(x) for x in ids if isinstance(x, str)),
            run_id=data.get("runId"),
        )

    # -- generic write helper (gated by the readonly guard) ----------------------

    def write_json(self, path: str | Path, payload: Mapping[str, Any]) -> Path:
        """Write a JSON document under a managed root (gated by readonly guard).

        Intended for the summary/pending layers; ``raw`` artifact writes should
        go through :meth:`save`. Raises :class:`PermissionError` when targeting
        a readonly root.
        """
        target = Path(path)
        self._assert_writable(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(dict(payload), indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return target
