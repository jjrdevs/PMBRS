#!/usr/bin/env python3
"""Boox journal enqueue — drain the device-push inbox and enrich cleaned records.

Two modes:

  --mode drain     (default) — OCR any inbox note that isn't already cleaned +
                              re-enrich all already-cleaned boox records in
                              `raw/journal/` so they carry the current
                              temporal grid block (start / end / modified /
                              duration + canonical 60s window alignment).
  --mode backfill  — skip OCR entirely; only re-enrich whatever is in
                     `raw/journal/` (used after a device was unplugged and
                     the strokes have continued to evolve).

Idempotent. Both modes end with the same on-disk state: one
`raw/journal/boox.<uuid>.p<N>-<ts>.json` per (note, page) that is
temporally enriched. The temporal block is re-derived from device state each
pass so modified_start/end stay honest as the user continues to edit a note.

Exit codes:
  0  OK
  1  unexpected error
  2  nothing to do (inbox empty AND no records to enrich)
  3  device not reachable (only affects "enrich from device" — OCR-only
     records are left untouched, not errored)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
for p in (str(_REPO_ROOT), str(_REPO_ROOT / "src")):
    if p not in sys.path:
        sys.path.insert(0, p)

from pmbrs.core.artifact import Artifact  # noqa: E402
from pmbrs.ingestion.boox.adb import AdbClient  # noqa: E402
from pmbrs.ingestion.boox.inbox import InboxCollector  # noqa: E402
from pmbrs.ingestion.boox.journal_enrich import enrich_record_in_place  # noqa: E402
from pmbrs.ingestion.boox.local_ingest import LocalIngestClient  # noqa: E402
from pmbrs.ingestion.boox.manifest import BooxSyncManifest  # noqa: E402
from pmbrs.ingestion.boox.note_timestamps import extract_note_timing  # noqa: E402
from pmbrs.ingestion.boox.ocr.engine import OllamaEngine  # noqa: E402
from pmbrs.ingestion.boox.producer import BooxProducer  # noqa: E402
from pmbrs.ingestion.boox.seed import seed_manifest_from_store  # noqa: E402

DEFAULT_RAW = Path("/home/jjrdev/.pmbrs-private")
RAW_JOURNAL = DEFAULT_RAW / "store" / "raw" / "journal"
INBOX_BOOX = DEFAULT_RAW / "store" / "inbox" / "boox"
MANIFEST = DEFAULT_RAW / "state" / "boox_sync_manifest.json"
WORKDIR = DEFAULT_RAW / "workdir"


def _now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _boox_records() -> dict[str, Path]:
    """Map note-uuid → record-file for all `boox.*.json` files in raw/journal."""
    out: dict[str, Path] = {}
    for p in RAW_JOURNAL.glob("boox.*.json"):
        # filename: boox.<uuid>.p<N>-<ts>.json
        parts = p.name.split(".")
        if len(parts) >= 3:
            out.setdefault(parts[1], p)
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="pmbrs-boox-journal-enqueue", description=__doc__)
    p.add_argument("--mode", choices=["drain", "backfill"], default="drain")
    p.add_argument("--adb-serial", default=os.environ.get("BOOX_ADB_SERIAL") or "4EF2D7E9")
    p.add_argument("--dry-run", action="store_true",
                   help="OCR new but do NOT write back the enriched records")
    p.add_argument("--json", action="store_true", help="emit a JSON summary")
    args = p.parse_args(argv)

    now = _now_ms()
    records = _boox_records()
    inbox_has = INBOX_BOOX.is_dir() and len(list(INBOX_BOOX.iterdir())) > 0
    if not records and not inbox_has:
        print("no inbox notes and no existing boox records — nothing to do", file=sys.stderr)
        return 2

    # 1. Drain the inbox (OCR new → one clean record per new note/page).
    ocr_summary = {"notes": 0, "ocr": 0, "skipped": 0, "errors": 0}
    if args.mode == "drain":
        if not INBOX_BOOX.is_dir() or not list(INBOX_BOOX.iterdir()):
            print("inbox empty — OCR step skipped", file=sys.stderr)
        else:
            collector = InboxCollector(inbox_root=INBOX_BOOX)
            engine = OllamaEngine()
            manifest = BooxSyncManifest.load(MANIFEST, device_serial=args.adb_serial)
            if not manifest.notes:
                manifest = seed_manifest_from_store(MANIFEST, raw_root=str(RAW_JOURNAL),
                                                     device_serial=args.adb_serial)
                manifest.save()
            WORKDIR.mkdir(parents=True, exist_ok=True)
            producer = BooxProducer(
                collector=collector,
                engine=engine,
                ingest=LocalIngestClient(raw_root=str(RAW_JOURNAL)),
                manifest=manifest,
                workdir=WORKDIR,
                force=False,
                dry_run=False,
                device_alias="boox-noteair3",
                ocr_model="qwen3.8:27b",
                ingest_url="(local)",
            )
            run = producer.run()
            records = _boox_records()  # refresh: OCR may have added notes
            ocr_summary = {
                "notes": run.notes_total,
                "ocr": run.pages_new_ocr,
                "skipped": max(0, run.pages_total - run.pages_new_ocr),
                "errors": len(run.errors),
            }
            for e in run.errors:
                print(f"  OCR error: {e}", file=sys.stderr)

    # 2. Re-enrich every boox record with the current device temporal window.
    adb = AdbClient(serial=args.adb_serial)
    device_ok = adb.device_available()
    if not device_ok:
        print(f"device {args.adb_serial!r} not available — keeping any existing noteTemporal blocks; "
              f"new records will be enriched on the next pass when the tablet is back.", file=sys.stderr)

    enriched: dict[str, dict] = {}
    for uuid, path in records.items():
        record = json.loads(path.read_text())

        timing = None
        if device_ok:
            try:
                timing = extract_note_timing(adb, uuid)
            except Exception as exc:
                print(f"  {uuid}: timing extract failed ({type(exc).__name__}: {exc}) — leaving record as-is",
                      file=sys.stderr)
                ocr_summary["errors"] += 1
                continue
        else:
            # No device: can't re-derive. If the record already has a
            # temporal block from a previous pass, keep it untouched;
            # otherwise there's nothing honest to write — skip.
            continue

        if timing is not None:
            if not args.dry_run:
                enrich_record_in_place(path, record, timing, now_ms=now)
            enriched[uuid] = {
                "first": timing.first_written_ms,
                "last": timing.last_edited_ms,
                "durationSec": (timing.last_edited_ms - timing.first_written_ms) // 1000,
                "windowsCovered": (timing.last_edited_ms // 60_000) - (timing.first_written_ms // 60_000) + 1,
            }

    print(
        f"boox-enqueue: ocr={ocs_summary(ocr_summary)} enriched={len(enriched)} "
        f"records_total={len(records)} dry_run={args.dry_run}"
    )
    if args.json:
        print(json.dumps({
            "mode": args.mode,
            "now_ms": now,
            "ocr": ocr_summary,
            "enriched": enriched,
            "records_total": len(records),
        }, indent=2))

    return 0 if len(records) or ocr_summary["ocr"] else 2


def ocs_summary(s: dict) -> str:
    return f"notes={s['notes']} ocr={s['ocr']} skipped={s['skipped']} errors={s['errors']}"


if __name__ == "__main__":
    raise SystemExit(main())
