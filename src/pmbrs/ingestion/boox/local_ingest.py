"""Local ingest backend — writes artifacts to the PMBRS raw store in-process.

Same function the HTTP ingest server uses (`persist_sync_batch` from
`scripts/pmbrs_host_sync_ingest.py`), but without an HTTP hop and without a
long-lived server — ideal for the nightly local cron job (ADR-019 D4/D5, §16).

The two backends (HTTP `IngestClient`, local `LocalIngestClient`) satisfy the
same `post_batch(artifacts) -> (accepted, stored)` interface, so the producer
is agnostic to which one it's wired to.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from pmbrs.core.artifact import Artifact

DEFAULT_RAW_ROOT = Path("/home/jjrdev/.pmbrs-private/store/raw")


class LocalIngestClient:
    """Direct-store ingest backend (no server, no network)."""

    def __init__(self, raw_root: str | Path = DEFAULT_RAW_ROOT) -> None:
        self.raw_root = Path(raw_root)

    def post_batch(self, artifacts: Iterable[Artifact]) -> tuple[int, list[str]]:
        from scripts.pmbrs_host_sync_ingest import persist_sync_batch  # canonical writer

        batch: list[dict[str, Any]] = [a.to_dict() for a in artifacts]
        written = persist_sync_batch(self.raw_root, batch)
        return (len(written), [str(p) for p in written])


__all__ = ["LocalIngestClient", "DEFAULT_RAW_ROOT"]
