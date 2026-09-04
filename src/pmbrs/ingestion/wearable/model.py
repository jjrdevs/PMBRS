"""Typed record models for the wearable ingest pipeline (ADR-021 D1-D4).

Tier constants are the single source of truth for modality labels:

  TIER1  heart_rate  authoritative 60-s HR bins     (observational)
  TIER2  hrv_proxy   derived windowed variability   (inferred)
  TIER3  hrv         Samsung precomputed SDNN/RMSSD (observational)
  TIER4  stress      session-level stress score     (observational)
  TIER5  sleep_stage sleep-stage segments           (observational)
"""
from __future__ import annotations

from dataclasses import dataclass

TIER1 = "heart_rate"
TIER2 = "hrv_proxy"
TIER3 = "hrv"
TIER4 = "stress"
TIER5 = "sleep_stage"


@dataclass(frozen=True)
class HRBin:
    """One 60-s HR bin from ``com.samsung.shealth.tracker.heart_rate``."""

    start_ms: int
    end_ms: int
    bpm: float
    bpm_min: float
    bpm_max: float
    data_uuid: str = ""
    time_offset: str = ""
    source_file: str = ""


@dataclass(frozen=True)
class HRVWindow:
    """One Samsung precomputed HRV window (``com.samsung.health.hrv``).

    ``sdnn_ms`` / ``rmssd_ms`` are the watch-computed values (tier 3,
    observational). Sparse by design (see ADR-021, context item 4).
    """

    start_ms: int
    end_ms: int
    sdnn_ms: float
    rmssd_ms: float
    source_file: str = ""


@dataclass(frozen=True)
class SleepStage:
    """One sleep-stage segment (``sleep_stage.csv``).

    ``stage_code`` is the raw Samsung numeric code; no semantic mapping is
    applied here (ADR-021 consequences: sleep modeling is out of scope).
    """

    start_ms: int
    end_ms: int
    stage_code: int
    sleep_id: str = ""


@dataclass(frozen=True)
class SleepSession:
    """One sleep episode (``sleep.csv``).

    Score fields are raw; a missing/empty score is kept as ``None`` and is
    never zero-filled (missingness semantics contract).
    """

    start_ms: int
    end_ms: int
    sleep_score: float | None
    efficiency: float | None
    sleep_type: int | None
    data_uuid: str = ""


@dataclass(frozen=True)
class StressSession:
    """One stress entry (``stress.csv``); ``score`` None means absent."""

    start_ms: int
    end_ms: int
    score: float | None
    data_uuid: str = ""


__all__ = [
    "TIER1", "TIER2", "TIER3", "TIER4", "TIER5",
    "HRBin", "HRVWindow", "SleepStage", "SleepSession", "StressSession",
]
