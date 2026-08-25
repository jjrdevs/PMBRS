"""PMBRS — Personal Behavioral Modeling & Recommendation System.

Phase A packages the core artifact-storage surface (ADR-017 D2: raw layer is
one-JSON-per-file; the ``StorageAdapter`` is the single consumer-facing
abstraction over the store per ``docs/module-contracts.md``).

Local-first, single-user (Constitution §16). Stdlib only.
"""

__version__ = "0.1.0"

from pmbrs.core.artifact import (
    CANONICAL_KEYS,
    Artifact,
    LineageEdge,
    strict_validate,
)
from pmbrs.core.storage import StorageAdapter, default_config_path

__all__ = [
    "Artifact",
    "LineageEdge",
    "CANONICAL_KEYS",
    "strict_validate",
    "StorageAdapter",
    "default_config_path",
]
