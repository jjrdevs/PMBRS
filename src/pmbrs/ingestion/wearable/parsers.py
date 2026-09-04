"""Parsers for the Samsung Health file export (ADR-021 D4).

Input layout (one export dir, real files inspected 2026-08-31):

  <export>/
    com.samsung.shealth.tracker.heart_rate/<shard>/<uuid>.binning_data.json
        -> JSON array of
           {heart_rate, heart_rate_min, heart_rate_max, start_time, end_time}
           (start/end epoch ms, ~60-s bins)
    com.samsung.health.hrv/<shard>/<uuid>.binning_data.json
        -> JSON array of {start_time, end_time, sdnn, rmssd} (ms values,
           ~5-min windows at 30-s step)
    hr.csv   stress.csv   sleep.csv   sleep_stage.csv
        -> session-level rows; row 1 is a device-uuid banner, row 2 is the
           real header; timestamps are LOCAL wall time + a ``time_offset``
           column like ``UTC-0400``.

All parsers return typed records (model.py). Parsers are pure functions of
file bytes/paths: no network, no state, safe to run under the manifest gate.
"""
from __future__ import annotations

import csv
import io
import json
import re
from pathlib import Path
from typing import Iterable, Iterator

from .model import HRBin, HRVWindow, SleepSession, SleepStage, StressSession

#: Recognized wearable export subpaths (keeps parity with the host route's
#: WEARABLE_ALLOWED_PREFIXES in scripts/pmbrs_host_sync_ingest.py).
HR_DIR = "com.samsung.shealth.tracker.heart_rate/"
HRV_DIR = "com.samsung.health.hrv/"
HR_CSV = "hr.csv"
STRESS_CSV = "stress.csv"
SLEEP_CSV = "sleep.csv"
SLEEP_STAGE_CSV = "sleep_stage.csv"

#: Row 1 of these CSVs is a banner ("com.samsung.shealth.stress,7006003,9"),
#: row 2 is the real header.
_BANNER_CSVS = frozenset({STRESS_CSV, SLEEP_CSV, SLEEP_STAGE_CSV, HR_CSV})

_OFFSET_RE = re.compile(r"UTC(?P<sign>[+-])(?P<h>\d{2})(?P<m>\d{2})")
_TS_RE = re.compile(
    r"(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2}):(\d{2})\.(\d{1,6})"
)


def _parse_offset_ms(offset: str) -> int:
    """``UTC-0400`` -> -4h in ms (offset of local wall time vs UTC)."""
    m = _OFFSET_RE.search(offset or "")
    if not m:
        return 0
    sign = 1 if m.group("sign") == "+" else -1
    hours = int(m.group("h"))
    minutes = int(m.group("m"))
    return sign * (hours * 3600 + minutes * 60) * 1000


def parse_ts_ms(value: str, offset: str = "") -> int:
    """Convert a Samsung local timestamp (+ ``time_offset``) to epoch ms.

    Handles the ``2022-01-24 15:25:00.000`` shape used by the export.
    Raises ValueError on unparseable input (caller decides skip policy).
    """
    m = _TS_RE.match((value or "").strip())
    if not m:
        raise ValueError(f"unparseable timestamp: {value!r}")
    year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hour, minute, sec = int(m.group(4)), int(m.group(5)), int(m.group(6))
    frac_ms = int(round(float("0." + m.group(7))))
    import calendar

    utc_s = calendar.timegm((year, month, day, hour, minute, sec, 0, 0, 0))
    local_s = utc_s + _parse_offset_ms(offset)
    return local_s * 1000 + frac_ms


def _f(value: object, default: float = 0.0) -> float:
    text = str(value).strip() if value is not None else ""
    if not text:
        return default
    try:
        return float(text)
    except ValueError:
        return default


def _i(value: object) -> int | None:
    text = str(value).strip() if value is not None else ""
    if not text:
        return None
    try:
        return int(float(text))
    except ValueError:
        return None


def _csv_header_index(lines: list[str], banner: str) -> int | None:
    """Return the index (0-based) of the data line immediately following the
    row-1 banner starting with ``banner`` -- i.e. the real header line's index."""
    for i, line in enumerate(lines[:5]):
        if line.startswith(banner):
            return i + 1
    return None


def _banner_table(text: str) -> str:
    """First cell of the row-1 banner = the fully-qualified table name."""
    text = text.lstrip("\ufeff")
    first = next(iter(text.splitlines()), "") if text else ""
    return first.split(",", 1)[0].strip()


def _csv_rows(text: str) -> Iterator[dict[str, str]]:
    """Yield dicts from a Samsung CSV, skipping the row-1 banner.

    Robust to the banner being absent (some export versions): if the first
    line already parses as a usable header (contains ``start_time``), use it
    directly.
    """
    text = text.lstrip("\ufeff")
    lines = text.splitlines()
    start = 0
    if lines and "start_time" not in lines[0]:
        start = 1  # row 1 is the banner
    reader = csv.DictReader(io.StringIO("\n".join(lines[start:])))
    for row in reader:
        yield row


def _col(row: dict, *aliases: str) -> str | None:
    for name in aliases:
        value = row.get(name)
        if value not in (None, ""):
            return value
    return None


def iter_hr_bins(
    payload: list[dict] | list, *, source_file: str = ""
) -> Iterator[HRBin]:
    """JSON array of heart_rate binning records -> HRBin."""
    for rec in payload or []:
        if not isinstance(rec, dict):
            continue
        start = rec.get("start_time")
        end = rec.get("end_time")
        bpm = rec.get("heart_rate")
        if start is None or end is None or bpm is None:
            continue
        try:
            yield HRBin(
                start_ms=int(start),
                end_ms=int(end),
                bpm=float(bpm),
                bpm_min=float(rec.get("heart_rate_min", 0) or 0),
                bpm_max=float(rec.get("heart_rate_max", 0) or 0),
                source_file=source_file,
            )
        except (TypeError, ValueError):
            continue


def iter_hrv_windows(
    payload: list[dict] | list, *, source_file: str = ""
) -> Iterator[HRVWindow]:
    """JSON array of HRV windows -> HRVWindow (sdnn/rmssd already in ms)."""
    for rec in payload or []:
        if not isinstance(rec, dict):
            continue
        start = rec.get("start_time")
        end = rec.get("end_time")
        sdnn = rec.get("sdnn")
        rmssd = rec.get("rmssd")
        if start is None or end is None or sdnn is None or rmssd is None:
            continue
        try:
            start_ms_val = int(start)
            end_ms_val = int(end)
        except (TypeError, ValueError):
            continue
        # Sanity: drop corrupt/zero-timestamp records (e.g. start=0) that
        # would otherwise anchor a spurious window at epoch and blow out
        # the candidate set.
        if start_ms_val <= 0 or end_ms_val <= 0 or end_ms_val < start_ms_val:
            continue
        yield HRVWindow(
            start_ms=start_ms_val,
            end_ms=end_ms_val,
            sdnn_ms=float(sdnn),
            rmssd_ms=float(rmssd),
            source_file=source_file,
        )


def parse_stress_csv(text: str, *, rel_path: str = "") -> list[StressSession]:
    out: list[StressSession] = []
    for row in _iter_csv_records(text):
        start_s = _col(row, "start_time")
        end_s = _col(row, "end_time")
        if start_s is None:
            continue
        try:
            start = parse_ts_ms(start_s, _offset_of(row))
            end = parse_ts_ms(end_s, _offset_of(row)) if end_s else start
        except ValueError:
            continue
        raw = _col(row, "score")
        out.append(
            StressSession(
                start_ms=start,
                end_ms=end,
                score=_f(raw) if raw not in (None, "") else None,
                data_uuid=_col(row, "datauuid") or "",
            )
        )
    return out


def parse_sleep_csv(text: str, *, rel_path: str = "") -> list[SleepSession]:
    out: list[SleepSession] = []
    for row in _iter_csv_records(text):
        start_s = _col(row, "start_time", "com.samsung.health.sleep.start_time")
        end_s = _col(row, "end_time", "com.samsung.health.sleep.end_time")
        if start_s is None:
            continue
        try:
            start = parse_ts_ms(start_s, _offset_of(row))
            end = parse_ts_ms(end_s, _offset_of(row)) if end_s else start
        except ValueError:
            continue
        raw_score = _col(row, "sleep_score", "com.samsung.health.sleep.sleep_score")
        raw_eff = _col(row, "efficiency", "com.samsung.health.sleep.efficiency")
        raw_type = _col(row, "sleep_type", "com.samsung.health.sleep.sleep_type")
        out.append(
            SleepSession(
                start_ms=start,
                end_ms=end,
                sleep_score=_f(raw_score) if raw_score not in (None, "") else None,
                efficiency=_f(raw_eff) if raw_eff not in (None, "") else None,
                sleep_type=_i(raw_type),
                data_uuid=_col(row, "datauuid", "com.samsung.health.sleep.datauuid") or "",
            )
        )
    return out


def parse_sleep_stage_csv(text: str, *, rel_path: str = "") -> list[SleepStage]:
    out: list[SleepStage] = []
    for row in _iter_csv_records(text):
        code = _i(_col(row, "stage"))
        if code is None:
            continue
        start_s = _col(row, "start_time")
        end_s = _col(row, "end_time")
        if start_s is None:
            continue
        try:
            start = parse_ts_ms(start_s, _offset_of(row))
            end = parse_ts_ms(end_s, _offset_of(row)) if end_s else start
        except ValueError:
            continue
        out.append(
            SleepStage(
                start_ms=start,
                end_ms=end,
                stage_code=code,
                sleep_id=_col(row, "sleep_id") or "",
            )
        )
    return out


def _iter_csv_records(text: str):
    for row in _csv_rows(text):
        if row and _col(row, "start_time", "com.samsung.health.sleep.start_time"):
            yield row


def _offset_of(row: dict) -> str:
    return _col(row, "time_offset", "com.samsung.health.sleep.time_offset") or ""


def parse_hr_json(text: str, *, rel_path: str) -> list[HRBin]:
    return list(iter_hr_bins(json.loads(text), source_file=rel_path))


def parse_hrv_json(text: str, *, rel_path: str) -> list[HRVWindow]:
    return list(iter_hrv_windows(json.loads(text), source_file=rel_path))


#: Alternate local export layout alias (adb-pulled copy on this machine keeps
#: the binning JSONs under ``hr_bins/`` with
#: ``<uuid>.com.samsung.health.heart_rate.binning_data.json`` names). Mapped
#: onto the canonical ``HR_DIR`` rel path so downstream code is layout-agnostic.
HR_BINS_ALIAS = "hr_bins/"
HR_BIN_FILE_SUFFIX = ".com.samsung.health.heart_rate.binning_data.json"


def discover_export_files(root: str | Path) -> list[tuple[str, Path]]:
    """Walk an export dir; return ``(rel_path, abs_path)`` for known files.

    ``rel_path`` uses the canonical wearable layout
    (``com.samsung.shealth.tracker.heart_rate/<shard>/<file>.json``) so the
    host inbox and an adb-pulled copy are indistinguishable downstream.
    """
    root = Path(root)
    found: list[tuple[str, Path]] = []
    if not root.is_dir():
        return found
    for rel in (HR_CSV, STRESS_CSV, SLEEP_CSV, SLEEP_STAGE_CSV):
        p = root / rel
        if p.is_file():
            found.append((rel, p))
    for d in (HR_DIR, HRV_DIR):
        base = root / d.rstrip("/")
        if not base.is_dir():
            continue
        for p in sorted(base.rglob("*.json")):
            rel = d + p.relative_to(base).as_posix()
            found.append((rel, p))
    base = root / HR_BINS_ALIAS.rstrip("/")
    if base.is_dir():
        for p in sorted(base.rglob("*.json")):
            rel = HR_DIR + p.relative_to(base).as_posix()
            found.append((rel, p))
    # de-dup (an export could carry both canonical and alias layouts)
    seen: set[Path] = set()
    deduped: list[tuple[str, Path]] = []
    for rel, p in found:
        rp = p.resolve()
        if rp in seen:
            continue
        seen.add(rp)
        deduped.append((rel, p))
    return deduped


def parse_file(rel_path: str, text: str) -> list:
    """Dispatch one export file to the right parser.

    Returns a list of typed records (HRBin | HRVWindow | StressSession |
    SleepSession | SleepStage). Raises ValueError for unrecognized shapes.
    """
    if rel_path.startswith(HR_DIR) and (
        rel_path.endswith(".json") or rel_path.endswith(HR_BIN_FILE_SUFFIX)
    ):
        return parse_hr_json(text, rel_path=rel_path)
    if rel_path.startswith(HRV_DIR) and (
        rel_path.endswith(".json") or rel_path.endswith(HR_BIN_FILE_SUFFIX)
    ):
        return parse_hrv_json(text, rel_path=rel_path)
    if rel_path == STRESS_CSV:
        return parse_stress_csv(text, rel_path=rel_path)
    if rel_path == SLEEP_CSV:
        return parse_sleep_csv(text, rel_path=rel_path)
    if rel_path == SLEEP_STAGE_CSV:
        return parse_sleep_stage_csv(text, rel_path=rel_path)
    if rel_path == HR_CSV:
        # hr.csv is a CSV mirror of the binning JSON; the structured records
        # are already carried by the JSON shards -- skip to avoid double emit.
        return []
    raise ValueError(f"unrecognized wearable export file: {rel_path!r}")
