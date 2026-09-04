"""Produce canonical 60-s window artifacts from a Samsung Health export.

ADR-021 D4/D5. One 9-key artifact per emitted canonical window, batched in
``chunk_size`` (500) ``post_batch`` calls against the shared ingest
interface (``post_batch(artifacts) -> (accepted, stored)``), wired by
default to ``pmbrs.ingestion.boox.local_ingest.LocalIngestClient`` which
routes to the canonical raw-store writer ``persist_sync_batch``.

Emit set (ADR-021 D4 union):
  (a) windows with an HR-bin start            -> tier-1 ``heart_rate``
  (b) >=2 bins in the trailing 10-bin band    -> tier-2 ``hrv_proxy``
  (c) overlapped by a precomputed HRV window  -> tier-3 ``hrv``
  (d) containing a stress point               -> tier-4 ``stress``
  (e) overlapped by a sleep-stage segment     -> tier-5 ``sleep_stage``
A window is emitted iff at least one tier is present; tier-2 is only
evaluated at candidate windows from (a)/(c)/(d)/(e) so sparse multi-year
data does not explode the candidate set. Re-entrancy is file-safe: artifact
names are deterministic (``<artifactId>-<createdAtMs>.json``).
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from . import grid, hrv_proxy
from .artifact import build_window_artifact
from .manifest import (
    STATUS_EMPTY,
    STATUS_ERROR,
    STATUS_PROCESSED,
    WearableSyncManifest,
)
from .model import (
    TIER1,
    TIER2,
    TIER3,
    TIER4,
    TIER5,
    HRBin,
    HRVWindow,
    SleepStage,
    StressSession,
)
from .parsers import discover_export_files, parse_file


@dataclass
class EmitConfig:
    device_alias: str = "galaxy-watch7"
    export: str = ""
    transport: str = "inbox"
    producer_version: str = "0.1"
    chunk_size: int = 500
    max_windows: int = 0
    timezone: str = "UTC"


@dataclass
class RunStats:
    files_discovered: int = 0
    files_parsed: int = 0
    files_unchanged: int = 0
    files_error: int = 0
    bins_raw: int = 0
    duplicated_bins: int = 0
    bins: int = 0
    hrv_windows: int = 0
    stress_rows: int = 0
    sleep_stage_rows: int = 0
    windows_candidate: int = 0
    windows_emitted: int = 0
    hrv_proxy_windows: int = 0
    windows_by_modality: dict = field(default_factory=dict)
    artifacts_ingested: int = 0
    storage_paths: list = field(default_factory=list)


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _now_ms() -> int:
    return int(time.time() * 1000)



# ---------------- grouping helpers ----------------

def _hr_windows(bins: list[HRBin]) -> dict[int, list[HRBin]]:
    """Bins grouped by the canonical slot containing their ``start_ms``."""
    out: dict[int, list[HRBin]] = {}
    for b in bins:
        out.setdefault(grid.window_index_for_ms(b.start_ms), []).append(b)
    return out


def _overlapped_windows(start_ms: int, end_ms: int) -> set[int]:
    """Canonical slots overlapped by [start_ms, end_ms)."""
    lo = grid.window_index_for_ms(start_ms)
    hi = grid.window_index_for_ms(max(end_ms - 1, start_ms))
    return set(range(lo, hi + 1))


def _group_segments(items) -> dict[int, list]:
    out: dict[int, list] = {}
    for r in items:
        for idx in _overlapped_windows(r.start_ms, r.end_ms):
            out.setdefault(idx, []).append(r)
    return out


def _group_points(items) -> dict[int, list]:
    out: dict[int, list] = {}
    for r in items:
        out.setdefault(grid.window_index_for_ms(r.start_ms), []).append(r)
    return out


# ---------------- per-window payloads ----------------

def _hr_payload(bins: list[HRBin]) -> dict[str, Any]:
    n = len(bins)
    return {
        "bpm": round(sum(b.bpm for b in bins) / n, 3),
        "bpm_min": round(min(b.bpm_min for b in bins), 3),
        "bpm_max": round(max(b.bpm_max for b in bins), 3),
        "bins": n,
    }


def _hrv_proxy_payload(p: hrv_proxy.HrvProxy) -> dict[str, Any]:
    return {
        "bpm": round(p.value_bpm, 3),
        "windows": p.bins_used,
        "method": p.method,
    }


def _hrv_payload(w: HRVWindow) -> dict[str, Any]:
    return {
        "sdnn_ms": round(w.sdnn_ms, 2),
        "rmssd_ms": round(w.rmssd_ms, 2),
        "derived_by_watch": True,
    }


def _stress_payload(rows: list[StressSession]) -> dict[str, Any]:
    scores = [r.score for r in rows if r.score is not None]
    out: dict[str, Any] = {"readings": len(rows)}
    if scores:
        out["score"] = round(sum(scores) / len(scores), 2)
        out["score_min"] = round(min(scores), 2)
        out["score_max"] = round(max(scores), 2)
    return out


def _sleep_payload(segs: list[SleepStage]) -> dict[str, Any]:
    codes = [s.stage_code for s in segs]
    return {
        "segments": len(segs),
        "stage_codes": sorted(set(codes)),
        "dominant_stage": max(set(codes), key=codes.count),
    }



# ---------------- producer ----------------

class WearableProducer:
    """Parse an export directory and emit canonical window artifacts."""

    def __init__(
        self,
        ingest,
        manifest: WearableSyncManifest,
        cfg: EmitConfig | None = None,
    ) -> None:
        self.ingest = ingest
        self.manifest = manifest
        self.cfg = cfg or EmitConfig()

    # ---------------- public ----------------

    def run(self, export_root: str | Path) -> RunStats:
        root = Path(export_root)
        if not root.is_dir():
            raise FileNotFoundError(f"export root not found: {root}")
        export = self.cfg.export or root.name

        pairs = discover_export_files(root)
        stats = RunStats(files_discovered=len(pairs))

        bins: list[HRBin] = []
        hrv_ws: list[HRVWindow] = []
        stress: list[StressSession] = []
        sleep_segs: list[SleepStage] = []

        for rel, p in pairs:
            if not p.is_file():
                self.manifest.mark(
                    export=export, rel_path=rel, sha256="", by=0,
                    records=0, windows=0, status=STATUS_ERROR,
                    now_ms=_now_ms(), error="file missing",
                )
                stats.files_error += 1
                continue
            try:
                sha = _sha256(p)
            except OSError as e:
                self.manifest.mark(
                    export=export, rel_path=rel, sha256="", by=0,
                    records=0, windows=0, status=STATUS_ERROR,
                    now_ms=_now_ms(), error=f"hash: {e}",
                )
                stats.files_error += 1
                continue
            unchanged = not self.manifest.needs_processing(
                export=export, rel_path=rel, sha256=sha
            )
            try:
                text = p.read_text(encoding="utf-8")
                records = parse_file(rel, text)
            except (OSError, ValueError, KeyError) as e:
                self.manifest.mark(
                    export=export, rel_path=rel, sha256=sha, by=0,
                    records=0, windows=0, status=STATUS_ERROR,
                    now_ms=_now_ms(), error=f"{type(e).__name__}: {e}",
                )
                stats.files_error += 1
                continue

            recs = _split_records(records, bins, hrv_ws, stress, sleep_segs)
            status = STATUS_PROCESSED if recs else STATUS_EMPTY
            self.manifest.mark(
                export=export, rel_path=rel, sha256=sha, by=0,
                records=recs, windows=0, status=status, now_ms=_now_ms(),
            )
            if unchanged:
                stats.files_unchanged += 1
            else:
                stats.files_parsed += 1

        stats.bins_raw = len(bins)
        bins.sort(key=lambda b: (b.start_ms, b.end_ms))
        bins, n_duplicated = _dedup_bins(bins)
        stats.duplicated_bins = n_duplicated
        stats.bins = len(bins)
        stats.hrv_windows = len(hrv_ws)
        stats.stress_rows = len(stress)
        stats.sleep_stage_rows = len(sleep_segs)

        # --- align ---
        bin_wins = _hr_windows(bins)
        hrv_by_window = _group_segments(hrv_ws)
        stress_by_window = _group_points(stress)
        sleep_by_window = _group_segments(sleep_segs)

        candidates = set(bin_wins) | set(hrv_by_window) | set(stress_by_window) | set(sleep_by_window)
        proxy = hrv_proxy.proxy_bulk(bins, list(candidates))

        window_set = sorted(candidates | set(proxy))
        stats.windows_candidate = len(window_set)
        if self.cfg.max_windows > 0:
            window_set = window_set[: self.cfg.max_windows]

        # --- emit ---
        emitted = 0
        for i in range(0, len(window_set), max(1, self.cfg.chunk_size)):
            chunk = window_set[i : i + max(1, self.cfg.chunk_size)]
            batch = []
            for idx in chunk:
                lo = idx * grid.RESOLUTION_MS
                present: dict[str, bool] = {}
                payloads: dict[str, Any] = {}

                if idx in bin_wins:
                    present[TIER1] = True
                    payloads[TIER1] = _hr_payload(bin_wins[idx])
                if idx in proxy:
                    present[TIER2] = True
                    payloads[TIER2] = _hrv_proxy_payload(proxy[idx])
                if idx in hrv_by_window:
                    present[TIER3] = True
                    payloads[TIER3] = _hrv_payload(hrv_by_window[idx][0])
                if idx in stress_by_window:
                    present[TIER4] = True
                    payloads[TIER4] = _stress_payload(stress_by_window[idx])
                if idx in sleep_by_window:
                    present[TIER5] = True
                    payloads[TIER5] = _sleep_payload(sleep_by_window[idx])

                if not any(present.values()):
                    continue

                coverage = {
                    m: (1.0 if present and m in present else 0.0)
                    for m in ("heart_rate", "hrv_proxy", "hrv", "stress", "sleep_stage")
                }
                a = build_window_artifact(
                    canonical_index=idx,
                    window_start_ms=lo,
                    window_end_ms=lo + grid.RESOLUTION_MS,
                    modalities_present=present,
                    coverage=coverage,
                    modality_payloads=payloads,
                    device_alias=self.cfg.device_alias,
                    export=export,
                    transport=self.cfg.transport,
                    producer_version=self.cfg.producer_version,
                    hrv_proxy_method=(proxy[idx].method if idx in proxy else ""),
                    timezone=self.cfg.timezone,
                )
                batch.append(a)
                for m in present:
                    stats.windows_by_modality[m] = stats.windows_by_modality.get(m, 0) + 1
                if idx in proxy:
                    stats.hrv_proxy_windows += 1

            if batch:
                accepted, stored = self.ingest.post_batch(batch)
                stats.artifacts_ingested += int(accepted)
                stats.storage_paths.extend(stored)
            emitted += len(batch)

        stats.windows_emitted = emitted
        self.manifest.last_run_ms = _now_ms()
        self.manifest.save()
        return stats


def _split_records(records, bins, hrv_ws, stress, sleep_segs) -> int:
    count = 0
    for r in records:
        if isinstance(r, HRBin):
            bins.append(r); count += 1
        elif isinstance(r, HRVWindow):
            hrv_ws.append(r); count += 1
        elif isinstance(r, StressSession):
            stress.append(r); count += 1
        elif isinstance(r, SleepStage):
            sleep_segs.append(r); count += 1
    return count


def _dedup_bins(bins: list[HRBin]) -> tuple[list[HRBin], int]:
    """Drop duplicate bins (same canonical slot + identical bpm triple).
    Samsung's export can repeat a window when two session buckets overlap.
    Returns ``(deduped, removed_count)``.
    """
    seen: set[tuple] = set()
    out: list[HRBin] = []
    for b in bins:
        key = (
            grid.window_index_for_ms(b.start_ms),
            round(b.bpm, 3),
            round(b.bpm_min, 3),
            round(b.bpm_max, 3),
        )
        if key in seen:
            continue
        seen.add(key)
        out.append(b)
    return out, len(bins) - len(out)


def default_local_ingest(raw_root: str | Path):
    """Build the default local sink (boox client; interface-compatible)."""
    from pmbrs.ingestion.boox.local_ingest import LocalIngestClient

    return LocalIngestClient(raw_root=raw_root)


def new_manifest(state_path: str | Path, device_alias: str = "galaxy-watch7") -> WearableSyncManifest:
    return WearableSyncManifest.load(state_path, device_alias=device_alias)


__all__ = [
    "EmitConfig",
    "RunStats",
    "WearableProducer",
    "default_local_ingest",
    "new_manifest",
]
