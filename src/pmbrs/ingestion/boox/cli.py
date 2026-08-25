#!/usr/bin/env python3
"""PMBRS BoOX note ingestion CLI (ADR-019).

One scheduled / manual sync pass over a connected BOOX NoteAir3:
pull note renders over ADB, OCR locally (Ollama qwen3.8:27b), and POST
``journal`` artifacts to the existing PMBRS ingest endpoint. Idempotent via the
sync manifest under ``~/.pmbrs-private/state/``.

Usage examples
--------------
  # Dry run: pull + hash only, no OCR, no ingest. See what WOULD happen.
  python3 -m pmbrs.ingestion.boox.cli --dry-run

  # OCR + ingest a single note (safe first real run):
  python3 -m pmbrs.ingestion.boox.cli --note-uuid 59fcdd081cae4e7cb852a34c122dd521

  # All notes (default), force re-OCR:
  python3 -m pmbrs.ingestion.boox.cli --force

Environment
-----------
  PM_BRS_OCR_OLLAMA_URL      default http://127.0.0.1:11434
  PM_BRS_OCR_MODEL           default qwen3.8:27b
  PM_BRS_BOOX_RAW_ROOT       default ~/.pmbrs-private (ADR-017 D1)
  PM_BRS_BOOX_WORKDIR        default ~/.cache/pmbrs-boox
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def _default_raw_root() -> Path:
    return Path(os.environ.get("PM_BRS_BOOX_RAW_ROOT") or "/home/jjrdev/.pmbrs-private")


def _default_workdir() -> Path:
    return Path(os.environ.get("PM_BRS_BOOX_WORKDIR") or str(Path.home() / ".cache" / "pmbrs-boox"))


def _default_manifest_path(raw_root: Path) -> Path:
    return Path(os.environ.get("PM_BRS_BOOX_MANIFEST") or str(raw_root / "state" / "boox_sync_manifest.json"))


def _default_ingest_url() -> str:
    return os.environ.get("PM_BRS_BOOX_INGEST_URL") or "http://127.0.0.1:8765/api/v1/artifacts/sync"


def _default_serial() -> str:
    return os.environ.get("BOOX_ADB_SERIAL") or "4EF2D7E9"


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pmbrs-boox", description=__doc__, formatter_class=argparse.ArgumentDefaultsHelpFormatter)

    # Device / notes
    p.add_argument("--adb-serial", default=_default_serial(), help="ADB serial of the BoOX device")
    p.add_argument("--note-uuid", action="append", dest="note_uuids", help="Limit to this note UUID (repeatable). Omit for all notes.")
    p.add_argument("--max-notes", type=int, default=None, help="Cap on number of notes to process in this run")

    # Run shape
    p.add_argument("--dry-run", action="store_true", help="Pull + hash + report, but skip OCR and ingest")
    p.add_argument("--force", action="store_true", help="Ignore manifest and re-OCR all selected notes")

    # OCR
    p.add_argument("--ocr-url", default=os.environ.get("PM_BRS_OCR_OLLAMA_URL") or "http://127.0.0.1:11434")
    p.add_argument("--ocr-model", default=os.environ.get("PM_BRS_OCR_MODEL") or "qwen3.8:27b")
    p.add_argument("--ocr-temperature", type=float, default=0.1)
    p.add_argument("--ocr-timeout", type=float, default=float(os.environ.get("PM_BRS_OCR_TIMEOUT") or 300.0),
                   help="Per-page OCR HTTP timeout, seconds (default: 300)")

    # Ingest / storage
    p.add_argument("--ingest-url", default=_default_ingest_url())
    p.add_argument("--raw-root", default=None, help=argparse.SUPPRESS)  # reserved for a custom manifest path
    p.add_argument("--manifest", default=None, help="Override the manifest path for this run")
    p.add_argument("--workdir", default=None, help="Local scratch dir for pulled PNGs")

    p.add_argument("--json", action="store_true", help="Emit the run summary as JSON (machine-readable)")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    # Late imports keep --help and arg validation fast even if deps are missing.
    from pmbrs.ingestion.boox.adb import AdbClient, BooxCollector
    from pmbrs.ingestion.boox.manifest import BooxSyncManifest
    from pmbrs.ingestion.boox.ocr.engine import OllamaEngine
    from pmbrs.ingestion.boox.producer import BooxProducer, IngestClient

    adb = BooxCollector(AdbClient(serial=args.adb_serial, adb_bin=os.environ.get("ADB_BIN") or "adb"))
    engine = OllamaEngine(base_url=args.ocr_url, model=args.ocr_model,
                          temperature=args.ocr_temperature, timeout_s=args.ocr_timeout)
    ingest = IngestClient(url=args.ingest_url)

    manifest_path = Path(args.manifest) if args.manifest else _default_manifest_path(_default_raw_root())
    manifest = BooxSyncManifest.load(manifest_path, device_serial=args.adb_serial)

    workdir = Path(args.workdir) if args.workdir else _default_workdir()

    producer = BooxProducer(
        collector=adb,
        engine=engine,
        ingest=ingest,
        manifest=manifest,
        workdir=workdir,
        force=args.force,
        dry_run=args.dry_run,
        max_notes=args.max_notes,
        ocr_temperature=args.ocr_temperature,
        ocr_model=args.ocr_model,
        ingest_url=args.ingest_url,
    )

    selected = args.note_uuids if args.note_uuids else None
    if args.dry_run and not adb.adb.device_available():
        print(f"[warn] ADB serial {args.adb_serial!r} not currently connected; dry-run may not reach the device.", file=sys.stderr)
        if selected is None and not args.max_notes:
            # Without a connected device and no explicit selection, there is
            # nothing to do — refuse to guess.
            print("[error] No connected device and no explicit --note-uuid / --max-notes for a dry run.", file=sys.stderr)
            return 2

    summary = producer.run(note_uuids=selected)

    if args.json:
        print(summary.to_json())
    else:
        d = summary.to_dict()
        print(f"notes={d['notesTotal']} pages={d['pagesTotal']} "
              f"freshOcr={d['pagesNewOcr']} blanks={d['blankPages']} "
              f"ingested={d['artifactsIngested']} failed={d['failedPages']} "
              f"elapsed={d['elapsedMs']}ms")
        for e in d.get("errors", []):
            print(f"  ! {e}", file=sys.stderr)

    # Exit codes: 0 = ran (even if some pages failed), 2 = nothing to do.
    return 0 if (summary.artifacts_ingested > 0 or summary.blank_pages > 0 or summary.failed_pages > 0 or summary.dry_run) else 2


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["main", "build_arg_parser"]
