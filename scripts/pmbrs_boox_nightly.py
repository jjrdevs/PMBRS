#!/usr/bin/env python3
"""PMBRS BoOX nightly sync entry point (Stage 2).

Self-contained so it can be driven by a scheduler (Hermes cron, systemd timer,
the user's task system, or a shell alias) with no environment setup beyond a
Python that can see the PMBRS repo.

Behaviour:
  1. Ensure ``src/`` is importable (repo layout) — so a plain ``python3 <this>``
     works from any cwd.
  2. Check the BoOX is reachable over ADB. If it is asleep/disconnected, exit
     cleanly with code 3 (scheduler can report "device unavailable") *before*
     doing any work. No partial state, no stack trace.
  3. Load/seed the sync manifest from the journal store (idempotency).
  4. Run one producer pass using the **local in-process ingest** backend
     (writes straight into ``~/.pmbrs-private/store/raw/journal/`` — no HTTP
     server needed; §16 local-first).
  5. Print a one-line machine-summary.

Exit codes:
  0  ran (even if some pages failed; summary shows it)
  2  nothing to do (no selected notes / all up-to-date)
  3  device not reachable over ADB
  4  unexpected producer error

Usage examples:
  python3 scripts/pmbrs_boox_nightly.py                 # full pass, all notes
  python3 scripts/pmbrs_boox_nightly.py --max-notes 5   # bounded first run
  python3 scripts/pmbrs_boox_nightly.py --force         # re-OCR everything
  python3 scripts/pmbrs_boox_nightly.py --dry-run       # pull + report only
  python3 scripts/pmbrs_boox_nightly.py --note-uuid <u> # single note
"""
from __future__ import annotations

import os
import sys

# --- ensure repo ``src/`` is importable regardless of cwd -----------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir))
_SRC = os.path.join(_REPO_ROOT, "src")
for p in (_SRC, _REPO_ROOT):
    if p not in sys.path:
        sys.path.insert(0, p)

import argparse
import json
from datetime import datetime, timezone


def _default_manifest() -> str:
    env = os.environ.get("PM_BRS_BOOX_MANIFEST")
    if env:
        return env
    return os.path.expanduser("~/.pmbrs-private/state/boox_sync_manifest.json")


def _default_workdir() -> str:
    env = os.environ.get("PM_BRS_BOOX_WORKDIR")
    if env:
        return env
    return os.path.expanduser("~/.cache/pmbrs-boox")


def _default_raw_root() -> str:
    env = os.environ.get("PM_BRS_BOOX_RAW_ROOT")
    if env:
        return env
    return os.path.expanduser("~/.pmbrs-private/store")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pmbrs-boox-nightly",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument("--adb-serial", default=os.environ.get("BOOX_ADB_SERIAL") or "4EF2D7E9")
    p.add_argument("--note-uuid", action="append", dest="note_uuids", help="Limit to this note UUID (repeatable).")
    p.add_argument("--max-notes", type=int, default=None)
    p.add_argument(
        "--transport",
        choices=["auto", "inbox", "adb"],
        default=os.environ.get("PM_BRS_BOOX_TRANSPORT") or "auto",
        help=(
            "auto (default): use the local inbox if non-empty, else fall back to ADB; "
            "inbox: force the local inbox (ADR-020 D5); "
            "adb: force ADB pull (legacy, ADR-019 D2)."
        ),
    )
    p.add_argument(
        "--inbox-root",
        default=os.environ.get("PM_BRS_BOOX_INBOX") or "/home/jjrdev/.pmbrs-private/store/inbox/boox",
        help="Local inbox directory (device push → hub) that the 'inbox' transport reads from.",
    )

    run = p.add_argument_group("run shape")
    run.add_argument("--dry-run", action="store_true")
    run.add_argument("--force", action="store_true")

    ocr = p.add_argument_group("ocr")
    ocr.add_argument("--ocr-url", default=os.environ.get("PM_BRS_OCR_OLLAMA_URL") or "http://127.0.0.1:11434")
    ocr.add_argument("--ocr-model", default=os.environ.get("PM_BRS_OCR_MODEL") or "qwen3.8:27b")
    ocr.add_argument("--ocr-temperature", type=float, default=0.1)
    ocr.add_argument("--ocr-timeout", type=float, default=float(os.environ.get("PM_BRS_OCR_TIMEOUT") or 300.0))

    sink = p.add_argument_group("ingest sink")
    sink.add_argument(
        "--sink",
        choices=["local", "http"],
        default="local",
        help="local: write straight into the raw store (default, §16). http: POST to --ingest-url.",
    )
    sink.add_argument("--raw-root", default=_default_raw_root(), help="raw store root (local sink)")
    sink.add_argument("--ingest-url", default=os.environ.get("PM_BRS_BOOX_INGEST_URL") or "http://127.0.0.1:8765/api/v1/artifacts/sync")

    p.add_argument("--manifest", default=_default_manifest())
    p.add_argument("--workdir", default=_default_workdir())
    p.add_argument("--json", action="store_true", help="Emit the summary as JSON (machine-readable).")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    from pmbrs.ingestion.boox.adb import AdbClient, BooxCollector
    from pmbrs.ingestion.boox.inbox import InboxCollector
    from pmbrs.ingestion.boox.manifest import BooxSyncManifest
    from pmbrs.ingestion.boox.ocr.engine import OllamaEngine
    from pmbrs.ingestion.boox.producer import BooxProducer
    from pmbrs.ingestion.boox.seed import seed_manifest_from_store

    # 1. Choose the transport (ADR-020 D5: same page, same on-disk name,
    #    same manifest idempotency contract across transports).
    #
    #   inbox     — local directory of PNGs the device pushed through the
    #               Phase-0 authed hub (the new production path).
    #   adb       — pull pages over ADB (legacy; ADR-019 D2).
    #   auto      — prefer inbox if non-empty, else fall back to ADB.
    #
    # The manifest's `needs_ocr(uuid, page_id, sha256)` check is the
    # *single source of truth* for "already handled" — both transports
    # feed it, and both are re-entrancy-safe.
    inbox_collector = InboxCollector(inbox_root=args.inbox_root)
    inbox_has_pages = len(inbox_collector.list_notes()) > 0

    use_inbox = args.transport == "inbox" or (args.transport == "auto" and inbox_has_pages)
    if use_inbox:
        collector = inbox_collector
        print("boox-nightly: transport=inbox  "
              f"({len(inbox_collector.list_notes())} note(s) pending at {args.inbox_root!r})")
    else:
        if args.transport == "inbox":
            print(f"boox-nightly: ERROR transport=inbox was requested but {args.inbox_root!r} has no notes.",
                  file=sys.stderr)
            return 4
        adb_client = AdbClient(serial=args.adb_serial)
        if not adb_client.device_available():
            msg = f"device not reachable over ADB: {args.adb_serial!r}"
            print(f"boox-nightly: WARN {msg}", file=sys.stderr)
            if args.json:
                print(json.dumps({"status": "skipped", "reason": msg}))
            return 3
        collector = BooxCollector(adb_client)
        print(f"boox-nightly: transport=adb  (serial {args.adb_serial!r}, inbox was empty)")

    # 2. Select notes (default: all on-device).
    selected = args.note_uuids
    if selected is None:
        try:
            selected = collector.list_notes()
        except Exception as exc:  # noqa: BLE001
            print(f"boox-nightly: ERROR listing notes: {type(exc).__name__}: {exc}", file=sys.stderr)
            return 4
        if args.max_notes is not None and args.max_notes >= 0:
            selected = selected[: args.max_notes]

    if not selected:
        print("boox-nightly: nothing to do (no notes selected).")
        return 2

    # 3. Manifest (seed from store on a cold start so we don't re-OCR committed pages).
    raw_root = args.raw_root
    manifest = BooxSyncManifest.load(args.manifest, device_serial=args.adb_serial)
    if not manifest.notes:
        manifest = seed_manifest_from_store(
            args.manifest,
            raw_root=raw_root.rstrip("/") + "/raw",
            device_serial=args.adb_serial,
        )
        if manifest.notes:
            manifest.save()

    # 4. Wire the sink + engine.
    engine = OllamaEngine(
        base_url=args.ocr_url,
        model=args.ocr_model,
        temperature=args.ocr_temperature,
        timeout_s=args.ocr_timeout,
    )
    if args.sink == "local":
        from pmbrs.ingestion.boox.local_ingest import LocalIngestClient

        ingest = LocalIngestClient(raw_root=raw_root.rstrip("/") + "/raw")
    else:
        from pmbrs.ingestion.boox.producer import IngestClient

        ingest = IngestClient(url=args.ingest_url)

    # 5. Run.
    producer = BooxProducer(
        collector=collector,
        engine=engine,
        ingest=ingest,
        manifest=manifest,
        workdir=args.workdir,
        force=args.force,
        dry_run=args.dry_run,
        ocr_temperature=args.ocr_temperature,
        ocr_model=args.ocr_model,
        ingest_url=args.ingest_url if args.sink == "http" else "(local)",
    )

    started = datetime.now(timezone.utc)
    try:
        summary = producer.run(note_uuids=selected)
    except Exception as exc:  # noqa: BLE001 — top-level guard for the scheduler
        print(f"boox-nightly: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 4

    # 6. Report.
    ended = datetime.now(timezone.utc)
    d = summary.to_dict()
    d["startedUtc"] = started.isoformat()
    d["endedUtc"] = ended.isoformat()
    d["notesSelected"] = len(selected)
    if args.json:
        print(json.dumps(d, indent=2))
    else:
        print(
            f"boox-nightly: notes={d['notesTotal']} pages={d['pagesTotal']} "
            f"ocr={d['pagesNewOcr']} blanks={d['blankPages']} "
            f"ingested={d['artifactsIngested']} failed={d['failedPages']} "
            f"{d['elapsedMs']}ms"
        )
        for e in d.get("errors", []):
            print(f"  ! {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "build_parser"]
