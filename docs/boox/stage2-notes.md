# BOOX Stage 2 — Scheduled/Local Sync (2026-08-21)

## Scope

Nightly sync of the BOOX note store into the PMBRS journal raw store, driven by
a PC-side scheduled job. Phone notifications remain out of scope for Stage 2 —
the user's own task system (personal-task-system + task-notify-android APK) is
the single notification plane if the user later wants one. Per Constitution §16
(local-first) and the ADR-019 decision D5 (ADB / manifest-diffed transport),
the BoOX remains a **producer** and the PC is the **coordinator** — we are not
inventing a second scheduler.

Stage 2 is **not** the "BooxSync agent + authenticated HTTP protocol" idea from
the original notes; that remains Stage 3+ (or the "B" branch of ADR-019 D2
consequences, re-scoped if ADB proves insufficient). Stage 2 is the small,
practical thing that lets the 21-notes pipeline run on a schedule.

## What is new in Stage 2

| File | Purpose |
|---|---|
| `src/pmbrs/ingestion/boox/local_ingest.py` | In-process ingest backend. Writes artifacts straight into `~/.pmbrs-private/store/raw/journal/` using the **same** `persist_sync_batch` writer the HTTP server uses. No long-lived server, no HTTP hop — cleanest shape for a §16 local cron. |
| `src/pmbrs/ingestion/boox/seed.py` | Manifest seeder. Walks the existing `boox.*.json` artifacts in the store and rebuilds `PageRecord.last_artifact_id` / `png_sha256` / `png_dims` fields so `needs_ocr` skips them on the next run. Prevents re-OCR after a `/tmp` workdir wipe. |
| `scripts/pmbrs_boox_nightly.py` | Self-contained entry point. Sets up `sys.path` for repo layout, gates on ADB reachability (exits code 3 cleanly if the device is asleep), seeds the manifest on a cold start, runs one producer pass via the local sink, prints a machine-readable summary. |

## What did NOT change

- **Producer, engine slot, artifact builder, ADB client, page/manifest data types, CLI** —
  all identical to Stage 1. Only the *sink* and *entry point* are new.
- **The `journal` raw store layout and record shape** — unchanged; still the
  canonical 9-key ADR-017 D2 shape, still lands under
  `~/.pmbrs-private/store/raw/journal/`.

## Hard rules honored

- **No new scheduler invented.** The nightly BoOX sync is a *consumer* of
  whatever scheduling the user has (Hermes cron, cron, systemd, their task
  system, or a shell alias). We ship an entry point, not a cron system.
- **No second notification plane.** BoOX never notifies the phone. If a
  "X new journal pages synced" message is wanted, that is a task posted to the
  user's existing TaskService — a Stage 3 add-on, not a Stage 2 responsibility.
- **No new device-side code / APK.**
- **No new credential / auth token.** ADB over the trusted link is the
  boundary (same posture as `mobile-collection.md`).
- **Local-first, no network** for the sync itself. OCR does hit Ollama
  (`127.0.0.1:11434`) by design (ADR-019 D3); that is a loopback call to a
  local model.

## Failure modes and their exits

| Condition | Exit code | Behaviour |
|---|---|---|
| Ran OK (some pages may have failed) | 0 | Summary shows `failed=<n>` |
| No notes selected / all up-to-date | 2 | Nothing done |
| Device not reachable over ADB | 3 | No work performed; clean message |
| Unexpected producer error | 4 | Full traceback to stderr |

The **device-sleep** case (exit 3) is expected and correct: the BOOX goes to
sleep and drops off ADB when idle (verified in recon §"Device & access").
Every nightly pass that hits a sleeping device reports `device not reachable`
and does nothing — no partial state, no stack trace, no wasted OCR. A later
pass when the device is awake will pick up the delta per the manifest.

## Performance notes (Stage 2-relevant)

- Per-page OCR is **3–9 seconds** on a 499×666 render with `think:false` (the
  Qwen 3.8 default is "thinking on", which stalls at 300+ seconds — see
  `engine.py` default `"think": False`).
- 17 notes = ~2 min of OCR + pull time on the first live end-to-end run.
  Steady-state (manifest-diffed) nightly passes on the same corpus should be
  **~5 seconds** for the 17 committed pages, plus any actual new/changed pages.
- ADB shell on the e-ink device is slow; every call is bounded + retried
  (see `adb.py`). Batch pulls are not yet implemented — per-page `adb pull`
  calls happen in the producer loop. If the corpus grows past ~100 pages,
  consider a single bulk `adb pull .ksync` + local enumeration instead of
  per-page.

## Not in Stage 2 (deferred)

- **Phone notification on new notes.** Natural add-on (post a Task to
  TaskService, and the existing TaskNotify APK will pick it up per its
  WorkManager 30-min loop). Out of scope per the ADR-019 decision that the
  BoOX is a *data producer*, not a notification source.
- **Multi-page fan-out decode.** `resolve_pages` in `BooxCollector` returns a
  single cover page per note today (Stage 1 spec §C2). The decode of
  `virtual/page/pb` to produce a per-page list is the next Stage; the code
  structure (single method, stable hook) is ready for it.
- **Full-res render escape hatch.** The 500-px thumbs worked for all 17 live
  samples (see Stage-1 run). Only escalate if the user reports a specific
  note is garbled.
- **Boox engagement telemetry.** Out of the current ask (ADR-019
  consequences). A separate observational modality.
- **BooxSync agent + authenticated HTTP protocol.** Stage 3+ or the B branch
  of ADR-019 — only if ADB proves insufficient.
- **Books → Boox delivery.** Already out of scope per user decision 3.

## Scheduling wiring (for the operator)

The entry point is designed to be driven by any scheduler. For this host,
the pattern that already works (see `personal-task-system/tasks/reminder_scheduler.py`
— "Designed to run as a cronjob every 5-15 minutes via Hermes cron system")
applies equally to the BoOX sync. The recommended cadence:

```
01:00–05:00 local (any single window), nightly
```

- The BOOX should be **plugged in** at the sync time (or at least awake).
  A sleeping device will report exit 3 and do nothing — that is the
  designed behaviour, not a bug.
- The manifest + workdir are durable under `~/.pmbrs-private/state/` and
  `~/.cache/pmbrs-boox/` (not `/tmp`), so restarts do not lose idempotency.
- If the user wants to re-time, re-order, or gate on a "device awake"
  signal, the entry point's `sys.path` setup + `main(argv)` shape means a
  scheduler just calls it with whatever arguments they like — nothing in the
  producer or engine needs to change.
