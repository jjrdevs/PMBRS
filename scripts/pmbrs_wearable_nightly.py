#!/usr/bin/env python3
"""PMBRS wearable (Galaxy Watch 7 / Samsung Health) nightly sync (ADR-021).

Self-contained entry point for a scheduler (Hermes cron, systemd timer, or a
manual run). Two supported sources:

1. ``--source phone`` (default): pull the newest Samsung Health export from
   the phone over ADB and normalize it to the canonical export layout, then
   run the producer.
2. ``--source-dir DIR``: run the producer directly against an existing
   canonical or alias layout (e.g. a previously pulled ``/tmp/pmbrs_export``).

Phone export layout (Samsung Health ``share`` export, verified 2026-08-31):

  /sdcard/Download/Samsung Health/<user>_<YYYYMMDDHHMMSS>/
    com.samsung.shealth.tracker.heart_rate.<ts>.csv          -> hr.csv
    com.samsung.shealth.stress.<ts>.csv                      -> stress.csv
    com.samsung.shealth.sleep.<ts>.csv                       -> sleep.csv
    com.samsung.health.sleep_stage.<ts>.csv                  -> sleep_stage.csv
    jsons/com.samsung.shealth.tracker.heart_rate/<shard>/*.json -> com.samsung.shealth.tracker.heart_rate/<shard>/*.json
    jsons/com.samsung.health.hrv/<shard>/*.json              -> com.samsung.health.hrv/<shard>/*.json

The producer (``pmbrs.ingestion.wearable``) is layout-agnostic across those
three spellings (see ``parsers.discover_export_files``).

Idempotency: the manifest (``~/.pmbrs-private/state/wearable_sync_manifest.json``
by default) records per-file sha256 + status; unchanged files are skipped
(re-parsed cheaply, no artifacts re-emitted).

Exit codes:
  0  ran (some rows may be empty; summary shows detail)
  2  nothing to do (empty export / all rows empty)
  3  phone unreachable over ADB (phone source only)
  4  unexpected producer / ADB error
  5  producer OK, but artifact compaction (step 3) failed

Usage examples:
  python3 scripts/pmbrs_wearable_nightly.py                  # ADB pull + run
  python3 scripts/pmbrs_wearable_nightly.py --source-dir /tmp/pmbrs_export
  python3 scripts/pmbrs_wearable_nightly.py --json           # machine summary
  python3 scripts/pmbrs_wearable_nightly.py --dry-run        # pull + parse only, no emit
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# --- ensure repo ``src/`` + ``scripts/`` are importable regardless of cwd -----
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
for p in (_REPO_ROOT, os.path.join(_REPO_ROOT, "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

PHONE_EXPORT_BASE = "/sdcard/Download/Samsung Health"

DEFAULT_MANIFEST = os.environ.get("PM_BRS_WEARABLE_MANIFEST") or os.path.expanduser(
    "~/.pmbrs-private/state/wearable_sync_manifest.json"
)
DEFAULT_WORKDIR = os.environ.get("PM_BRS_WEARABLE_WORKDIR") or os.path.expanduser(
    "~/.cache/pmbrs-wearable"
)
DEFAULT_RAW_ROOT = os.environ.get("PM_BRS_WEARABLE_RAW_ROOT") or os.path.expanduser(
    "~/.pmbrs-private/store"
)
DEFAULT_ADB_SERIAL = os.environ.get("WEARABLE_ADB_SERIAL") or "R5CW61SY12N"
DEVICE_ALIAS_DEFAULT = "galaxy-watch7"
# Default local inbox the device pusher (the phone-side app) drops wearable
# export files into via ``POST /api/v1/wearable/files`` (ADR-021 D4):
#   ~/.pmbrs-private/store/inbox/wearable/com.samsung.shealth.tracker.heart_rate/<uuid>/...
#   ~/.pmbrs-private/store/inbox/wearable/com.samsung.health.hrv/<uuid>/...
#   ~/.pmbrs-private/store/inbox/wearable/{hr,stress,sleep,sleep_stage}.csv
# Layout is identical to a phone-export after ADB pull, so the producer's
# discovery + manifest idempotency contract is transport-agnostic (mirrors
# the ADR-020 D5 boox ``--transport auto`` model).
DEFAULT_INBOX_ROOT = os.environ.get("PM_BRS_WEARABLE_INBOX") or os.path.expanduser(
    "~/.pmbrs-private/store/inbox/wearable"
)

#: Canonical export-relative -> phone-export-relative. Order matters for
#: discovery (CSVs are read before JSON dirs), not for copying.
LAYOUT_PHONE_TO_CANONICAL: list[tuple[str, str]] = [
    ("hr.csv", "com.samsung.shealth.tracker.heart_rate.<ts>.csv"),
    ("stress.csv", "com.samsung.shealth.stress.<ts>.csv"),
    ("sleep.csv", "com.samsung.shealth.sleep.<ts>.csv"),
    ("sleep_stage.csv", "com.samsung.health.sleep_stage.<ts>.csv"),
    # JSON dirs copied wholesale (file names already canonical).
    ("com.samsung.shealth.tracker.heart_rate/", "jsons/com.samsung.shealth.tracker.heart_rate/"),
    ("com.samsung.health.hrv/", "jsons/com.samsung.health.hrv/"),
]


def _adb(serial: str, args: list[str], timeout: int = 120) -> int:
    cmd = ["adb", "-s", serial, *args]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"adb {' '.join(args)} failed: {proc.stderr.strip() or proc.stdout.strip()}")
    return proc.returncode


def _adb_list_l(serial: str, path: str) -> list[str]:
    """Return device-side mtimed+names under ``path`` (ls -l output)."""
    out = subprocess.run(
        ["adb", "-s", serial, "shell", "ls -l", path],
        capture_output=True, text=True, timeout=60,
    )
    if out.returncode != 0:
        return []
    lines = out.stdout.splitlines()
    names: list[str] = []
    for line in lines[1:]:  # skip total line if present
        parts = line.split()
        # ls -l: perms links owner group size month day time-or-year name...
        if len(parts) >= 9:
            # name is parts[8:] joined (handles spaces in names)
            name = " ".join(parts[8:]).strip()
            if name and name not in (".", ".."):
                names.append(name)
    return names


def find_phone_export(serial: str) -> str | None:
    """Return the newest sibling of ``PHONE_EXPORT_BASE/<user>_<ts>``.

    Prefers numeric-mtime ordering from ``ls -l`` when parseable; falls back
    to parsing ``<user>_<14-digit ts>`` out of the name.
    """
    try:
        listing = subprocess.run(
            ["adb", "-s", serial, "shell", "ls", "-1", PHONE_EXPORT_BASE],
            capture_output=True, text=True, timeout=60,
        )
    except subprocess.TimeoutExpired:
        return None
    if listing.returncode != 0:
        return None
    names = [n.strip() for n in listing.stdout.splitlines() if n.strip() and n.strip() not in (".", "..")]
    if not names:
        return None
    # Prefer directories whose name ends with a 14-digit timestamp (newest).
    stamped = [n for n in names if re.fullmatch(r".*_\d{14}", n)]
    if stamped:
        stamped.sort()
        return f"{PHONE_EXPORT_BASE}/{stamped[-1]}"
    # Otherwise pick the newest by mtime (ls -lt).
    listing_t = subprocess.run(
        ["adb", "-s", serial, "shell", "ls", "-1t", PHONE_EXPORT_BASE],
        capture_output=True, text=True, timeout=60,
    )
    if listing_t.returncode == 0:
        first = listing_t.stdout.splitlines()
        for line in first:
            n = line.strip()
            if n and n not in (".", ".."):
                return f"{PHONE_EXPORT_BASE}/{n}"
    return None


def _resolve_phone_path(export_dir: str, canonical: str) -> str:
    """Map a canonical layout path to the phone-export path.

    ``canonical`` ends with ``.csv`` or ``/`` for dir. Uses the known mapping;
    for directory entries we use the full path directly.
    """
    if canonical.endswith(".csv"):
        for can, ph in LAYOUT_PHONE_TO_CANONICAL:
            if can == canonical:
                # ph contains a <ts> placeholder; match by prefix.
                prefix = ph.split("<ts>")[0]
                return f"{export_dir}/{prefix}"
        raise ValueError(f"no phone mapping for CSV {canonical!r}")
    for can, ph in LAYOUT_PHONE_TO_CANONICAL:
        if can == canonical:
            return f"{export_dir}/{ph.rstrip('/')}"
    raise ValueError(f"no phone mapping for dir {canonical!r}")


def pull_and_normalize(serial: str, export_dir: str, workdir: Path, dry_run: bool = False) -> dict[str, str]:
    """ADB pull a phone export into the canonical layout under ``workdir/export``.

    Returns the per-canonical-destination local path (csvs: the resolved
    phone-absolute-src for reference; dirs: the pull dir on the host).
    """
    local_root = Path(workdir) / "export"
    local_root.mkdir(parents=True, exist_ok=True)
    result: dict[str, str] = {}

    listing = subprocess.run(
        ["adb", "-s", serial, "shell", "ls", "-1", export_dir],
        capture_output=True, text=True, timeout=60,
    )
    top_names = {n.strip(): True for n in listing.stdout.splitlines() if n.strip() and n.strip() not in (".", "..")}

    for can, ph in LAYOUT_PHONE_TO_CANONICAL:
        phone_src = _resolve_phone_path(export_dir, can)
        local_dst = local_root / can.rstrip("/")
        if can.endswith(".csv"):
            # Locate the actual phone file by prefix (timestamp suffix varies).
            prefix = ph.split("<ts>")[0]
            match = None
            for n in top_names:
                if n.startswith(prefix):
                    match = n
                    break
            if match is None:
                raise FileNotFoundError(f"{prefix}* not found under {export_dir}")
            phone_abs = f"{export_dir}/{match}"
            local_csv = local_root / can
            if dry_run:
                result[can] = f"{phone_abs} -> {local_csv} (dry-run)"
                continue
            print(f"wearable-nightly: pulling {match!r} -> {local_csv}")
            _adb(serial, ["pull", phone_abs, str(local_csv)], timeout=120)
        else:
            # Directory pull (json binning data).
            if dry_run:
                result[can] = f"{phone_src} -> {local_dst} (dry-run)"
                continue
            print(f"wearable-nightly: pulling dir {ph!r} -> {local_dst}")
            _adb(serial, ["pull", phone_src, str(local_dst)], timeout=300)
        result[can] = str(local_dst)
    return result


def _resolve_raw_dir(store_root: str) -> str:
    """Resolve a store root (or an already-``/raw`` dir) to the raw-sink dir.

    The boox nightly (ADR-020) treats ``--raw-root`` as the STORE root
    (~/.pmbrs-private/store) and appends ``/raw`` for the sink, so wearable
    canonical windows land at ``<store>/raw/<source>/``. This mirrors that and
    is idempotent: if the caller already passed a path ending in ``/raw`` it is
    returned unchanged, so ``compact`` (which defaults to ``<store>/raw``) reads
    the same tree the producer wrote.
    """
    r = store_root.rstrip("/")
    if r.endswith("/raw"):
        return r
    return r + "/raw"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pmbrs-wearable-nightly",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = p.add_argument_group("source / transport")
    src.add_argument(
        "--transport",
        choices=["auto", "inbox", "adb"],
        default=os.environ.get("PM_BRS_WEARABLE_TRANSPORT") or "auto",
        help=(
            "auto (default): use the local inbox if it has any recognized "
            "wearable files, else fall back to ADB pull. "
            "inbox: only the local inbox (no ADB); benign no-op if it is empty. "
            "adb: only ADB pull (legacy; requires an unlocked, tethered phone). "
            "Mirrors the ADR-020 D5 boox transport model."
        ),
    )
    src.add_argument(
        "--inbox-root",
        default=DEFAULT_INBOX_ROOT,
        help="Local device-push inbox directory for the 'inbox' transport.",
    )
    # Legacy (kept for backward compat): --source=phone maps to
    # --transport=adb, --source=local-dir still requires --source-dir.
    src.add_argument(
        "--source",
        choices=["phone", "local-dir"],
        default=None,
        help="(DEPRECATED use --transport) phone → --transport=adb; local-dir + --source-dir.",
    )
    src.add_argument(
        "--source-dir",
        default=None,
        help="Explicit canonical/alias export dir. Wins over --transport when set.",
    )
    src.add_argument("--adb-serial", default=DEFAULT_ADB_SERIAL)
    src.add_argument("--phone-export", default=None,
                     help="Override the phone export dir (auto-detected by default).")

    run = p.add_argument_group("run shape")
    run.add_argument("--dry-run", action="store_true",
                     help="Pull + parse + plan; do not emit artifacts.")
    run.add_argument("--max-windows", type=int, default=None,
                     help="Cap windows emitted (for testing / first-run budgeting). 0 = no cap.")

    sink = p.add_argument_group("ingest sink")
    sink.add_argument("--raw-root", default=DEFAULT_RAW_ROOT,
                      help="store root for the local sink (artifacts land under <raw-root>/raw/<source>/, "
                           "matching the boox convention).")
    sink.add_argument("--manifest", default=DEFAULT_MANIFEST)
    sink.add_argument("--workdir", default=DEFAULT_WORKDIR,
                      help="Local cache dir (the phone export is normalized under <workdir>/export).")
    sink.add_argument("--device-alias", default=DEVICE_ALIAS_DEFAULT)
    sink.add_argument("--timezone", default="UTC")

    compact_g = p.add_argument_group("compaction (step 3 - rollups + parquet)")
    compact_g.add_argument("--no-compact", action="store_true",
                           help="Skip artifact compaction (rollup artifacts + parquet) after the producer.")
    compact_g.add_argument("--compact-spans", default=None,
                           help="Comma list of rollup spans (default: 5m,1h,1d). Use <secs>s for custom.")
    compact_g.add_argument("--compact-min-coverage", type=float, default=None,
                           help="Per-modality coverage floor for 'partial' rollups (default 0.5).")
    compact_g.add_argument("--rollup-root", default=None,
                           help="Override the rollup sink dir (default <store>/rollup).")
    compact_g.add_argument("--compact-out-dir", default=None,
                           help="Override the parquet out dir (default <store>/data).")

    p.add_argument("--json", action="store_true",
                   help="Emit the summary as JSON (machine-readable).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    # Back-compat: --source overrides --transport for legacy callers.
    #   --source=phone      → transport=adb (explicit)
    #   --source=local-dir  → requires --source-dir
    #   --source (unset)    → honor --transport (default "auto")
    transport = args.transport  # type: str
    if args.source == "phone":
        transport = "adb"
    elif args.source == "local-dir" and not args.source_dir:
        print("wearable-nightly: ERROR --source=local-dir requires --source-dir", file=sys.stderr)
        return 4

    started = datetime.now(timezone.utc)
    from pmbrs.ingestion.wearable import producer as P
    from pmbrs.ingestion.wearable import parsers as parsers_mod

    # 1. Resolve the source export layout on the host (ADR-021 D4).
    #    Priority: --source-dir (explicit) > inbox (transport auto|inbox, non-empty) > ADB.
    #    The inbox is where the phone-side pusher drops export files via
    #    POST /api/v1/wearable/files. Layout is byte-identical to an ADB-pulled
    #    phone export, so ``discover_export_files`` and downstream manifest
    #    idempotency are transport-agnostic (mirrors the ADR-020 D5 boox model).
    local_export: str | None = None
    if args.source_dir:
        if not Path(args.source_dir).is_dir():
            print(f"wearable-nightly: ERROR source dir missing: {args.source_dir}", file=sys.stderr)
            return 4
        local_export = args.source_dir
    elif transport in ("inbox", "auto"):
        inbox_root = Path(args.inbox_root)
        files = parsers_mod.discover_export_files(inbox_root)
        if files:
            local_export = str(inbox_root)
            print(f"wearable-nightly: transport=inbox  ({len(files)} file(s) pending at {inbox_root!r})")
        else:
            if transport == "inbox":
                print("wearable-nightly: WARN transport=inbox requested but inbox is empty (benign no-op)",
                      file=sys.stderr)
                if args.json:
                    print(json.dumps({"status": "skipped", "reason": "inbox_empty", "inbox": str(inbox_root)}))
                return 2
            # auto falls through to ADB below — announce BEFORE the ADB block runs
            # so the operator sees the decision in the natural "why are we doing
            # this?" order.
            print(f"wearable-nightly: transport=auto → inbox empty, falling back to adb (serial {args.adb_serial!r})")
            transport = "adb"

    if local_export is None and transport == "adb":
        if not shutil.which("adb"):
            print("wearable-nightly: ERROR adb not on PATH", file=sys.stderr)
            return 4
        # Reachability (light probe).
        probe = subprocess.run(["adb", "-s", args.adb_serial, "shell", "echo", "ok"],
                               capture_output=True, text=True, timeout=15)
        if probe.returncode != 0 or "ok" not in probe.stdout:
            msg = f"device not reachable over ADB: {args.adb_serial!r}"
            print(f"wearable-nightly: WARN {msg}", file=sys.stderr)
            if args.json:
                print(json.dumps({"status": "skipped", "reason": msg}))
            return 3
        export_dir = args.phone_export or find_phone_export(args.adb_serial)
        if not export_dir:
            msg = f"no phone export found under {args.adb_serial!r} {PHONE_EXPORT_BASE}/"
            print(f"wearable-nightly: WARN {msg}", file=sys.stderr)
            if args.json:
                print(json.dumps({"status": "skipped", "reason": msg}))
            return 3
        print(f"wearable-nightly: phone-export={export_dir}")
        workdir = Path(args.workdir)
        pull_and_normalize(args.adb_serial, export_dir, workdir, dry_run=args.dry_run)
        local_export = str(workdir / "export")

    if local_export is None:
        # Defensive: all expected branches return early. Reaching here means
        # transport was "inbox" with an empty inbox (already returned 2 above)
        # or "adb" with a failed probe (already returned 3 above). Safety net.
        print("wearable-nightly: ERROR internal source-resolution invariant violated", file=sys.stderr)
        return 4

    # 2. Manifest + sink + producer.
    manifest = P.new_manifest(args.manifest, device_alias=args.device_alias)
    if args.dry_run:
        # Dry-run: parse + count, no emit.
        from pmbrs.ingestion.wearable.parsers import discover_export_files, parse_file
        root = Path(local_export)
        pairs = discover_export_files(root)
        counts = {"discovered": len(pairs), "parsed": 0, "errors": 0}
        for rel, p in pairs:
            try:
                text = p.read_text(encoding="utf-8")
                recs = parse_file(rel, text)
                counts["parsed"] += len(recs)
            except Exception as exc:  # noqa: BLE001
                counts["errors"] += 1
        d = {**counts, "startedUtc": started.isoformat(), "endedUtc": datetime.now(timezone.utc).isoformat()}
        if args.json:
            print(json.dumps(d, indent=2))
        else:
            print(f"wearable-nightly: dry-run {d['discovered']} files, {d['parsed']} records, {d['errors']} errors")
        return 0
    raw_dir = _resolve_raw_dir(args.raw_root)
    ingest = P.default_local_ingest(raw_dir)
    cfg = P.EmitConfig(
        device_alias=args.device_alias,
        export=os.path.basename(local_export.rstrip("/")) or "pmbrs_export",
        transport="local",
        timezone=args.timezone,
        max_windows=args.max_windows or 0,
    )
    producer = P.WearableProducer(ingest, manifest, cfg)

    # 3. Run.
    try:
        stats = producer.run(local_export)
    except Exception as exc:  # noqa: BLE001 — top-level guard for the scheduler
        print(f"wearable-nightly: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4
    try:
        manifest.save()
    except Exception as exc:  # noqa: BLE001
        print(f"wearable-nightly: WARN manifest save failed: {type(exc).__name__}: {exc}", file=sys.stderr)

    # 3b. Compaction (step 3) - derive rollup artifacts + parquet over the
    #     accepted windows. Deterministic + idempotent (a re-run over the same
    #     windows overwrites identical files), so nightly re-runs are safe.
    compaction_info: dict | None = None
    if not args.no_compact:
        try:
            from pmbrs.compaction import DEFAULT_MIN_COVERAGE, DEFAULT_SPANS, compact
            spans = (
                [x.strip() for x in args.compact_spans.split(",") if x.strip()]
                if args.compact_spans
                else list(DEFAULT_SPANS)
            )
            min_cov = (
                args.compact_min_coverage
                if args.compact_min_coverage is not None
                else DEFAULT_MIN_COVERAGE
            )
            cstats = compact(
                raw_root=raw_dir,
                out_dir=args.compact_out_dir,
                spans=spans,
                min_coverage=min_cov,
                source="mobile",
                rollup_root=args.rollup_root,
                device_alias=args.device_alias,
                parquet=True,
            )
            compaction_info = cstats.to_dict()
            if not args.json:
                c = compaction_info
                print(
                    "wearable-nightly: compact "
                    f"windows={c['windows_loaded']} rollups={c['rollups_built']} "
                    f"spans={','.join(c['spans']) or '-'} partial={c['partial_rollups']} "
                    f"parquet={c['parquet']['ok']}"
                )
        except Exception as exc:  # noqa: BLE001 - fail loudly; producer already succeeded
            print(f"wearable-nightly: ERROR compaction failed: {type(exc).__name__}: {exc}", file=sys.stderr)
            if args.json:
                print(json.dumps({"status": "error", "stage": "compaction", "error": str(exc)}))
            return 5

    ended = datetime.now(timezone.utc)
    d = dataclasses.asdict(stats)
    d.pop("storage_paths", None)
    d["source"] = "local-dir" if args.source_dir else transport
    d["localExport"] = local_export
    d["manifest"] = args.manifest
    d["startedUtc"] = started.isoformat()
    d["endedUtc"] = ended.isoformat()
    if compaction_info is not None:
        d["compaction"] = compaction_info
    if args.json:
        print(json.dumps(d, indent=2, default=str))
    else:
        print(
            "wearable-nightly: "
            f"files={d['files_discovered']} unchanged={d['files_unchanged']} errors={d['files_error']} "
            f"bins={d['bins']}(raw={d['bins_raw']}, dup={d['duplicated_bins']}) "
            f"hrv={d['hrv_windows']} stress={d['stress_rows']} sleep={d['sleep_stage_rows']} "
            f"windows={d['windows_emitted']} artifacts={d['artifacts_ingested']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "build_parser"]
