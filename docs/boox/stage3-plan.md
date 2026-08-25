# Stage-3 Plan: Boox Device-Push Sync (Headless App, LAN-First + Cloud Fallback)

| Field     | Value                                                                  |
|-----------|------------------------------------------------------------------------|
| Status    | Phases 0–2 delivered & verified 2026-08-22; Phase 3 (cutover) pending |
| Date      | 2026-08-21                                                             |
| ADR       | [`../adr/ADR-020.md`](../adr/ADR-020.md) (written alongside this plan) |
| Supersedes| Stage-2 ADB transport as the *production* path; ADB retained for dev/debug |
| Prior     | [`recon-notes.md`](recon-notes.md), [`stage1-spec.md`](stage1-spec.md), [`stage2-notes.md`](stage2-notes.md) |

## 1. What changed since Stage 2

Stage 2 shipped and works: `src/pmbrs/ingestion/boox/` + `scripts/pmbrs_boox_nightly.py`
pull the note cache over ADB, diff by sha256 manifest, OCR locally (qwen3.8:27b),
and drop journal artifacts into `~/.pmbrs-private/store/raw/journal/` (17 notes in flight).

Its standing weakness is the **transport window**: the sync only succeeds if the Boox
is awake, Wi‑Fi/LAN-reachable, and near the desk at the scheduled moment. The Stage-2
spec treats "device unreachable" as a handled no-op (`exit 3`), which is correct but
means notes sit un-synced until the next reachable window.

Stage 3 moves the *push* decision to the device so notes sync **as soon as the device
naturally has a network window**, from anywhere, without USB, ADB debug mode, or a
scheduled wake at a specific instant.

## 2. Confirmed user decisions (2026-08-21)

| # | Decision |
|---|----------|
| D1 | **LAN-first + cloud fallback** — mirrors the mobile `mobile-collection-local-cloud-fallback` pattern. |
| D2 | **Separate hostname + separate token** for the Boox (`boox-sync.jjrdev.com`), never sharing `mobile-sync.jjrdev.com`. |
| D3 | **No visible UI on the Boox.** A headless foreground-service app; the *persistent notification* is the entire "interface" and doubles as the debug/confirmation surface. Plus hub-side ack confirmation. |
| D4 | **Powered-off device → keep the PC-side sweep.** The existing nightly ADB job remains as the safety net for the one state nothing can wake. |
| D5 | **Wake strategy: opportunistic + one exact daily alarm.** No FCM-push dependency (treated as nudge, not wake, on a Wi‑Fi-only sleeping device). See §5. |

## 3. Verified device facts (NoteAir3, 2026-08-21)

Facts that constrain this design — all pulled live from the device:

- `sys.onyx.idledelay = 2500` → screen asleep after ~2.5 s idle; the device is almost always in screen-off sleep.
- `settings get global wifi_sleep_policy` = **2** (disconnect on screen sleep) → the device is **LAN-invisible while sleeping**; LAN-first can only mean "use LAN *when awake or woken*", never "keep the radio up".
- Wi‑Fi logs show self-initiated reconnects at **02:32, 07:32, 08:14** (~hourly, ONYX sync jobs) → the device already creates periodic Wi‑Fi windows on its own.
- `com.google.android.gms` present (NoteAir3 EEA, Android 12, `user/release-keys`) → FCM-capable *if* ever wanted; not required by this design.
- `battery_saver` off, `ignore_background_data` null, no ONYX app-freeze policy in sight → standard foreground-service + exact-alarm exemptions will hold.
- Wi‑Fi-only (no SIM/RIL), RSSI ≈ −58 dBm at home, `curl` present.
- ADB over USB currently working; `init.svc.adbd = running`.

## 4. Architecture

```
        ┌──────────────────────────────────────────────────────────────┐
        │  BOOX NoteAir3 (headless app, no UI)                         │
        │                                                              │
        │  WatchFolder (new/changed page PNGs in the note cache)       │
        │        │                                                     │
        │        ▼                                                     │
        │  Queue DB (pending → uploading → acked / failed)             │
        │        │     ▲                                               │
        │        │     │ ack (syncedIds, per artifactId)               │
        │        ▼     │                                               │
        │  WorkManager / ConnectivityCallback (Wi-Fi-available)        │
        │  + 1× daily setExact alarm (fallback window)                │
        │        │                                                     │
        │        ▼                                                     │
        │  uploader: POST /api/v1/artifacts/sync                       │
        │       bearer token (boox-dedicated), retry/backoff          │
        └────────┼─────────────────────────────────────────────────────┘
                 │  LAN endpoint preferred → tunnel fallback
                 ▼
   boox-sync.jjrdev.com  →  cloudflared  →  127.0.0.1:8788
                 │
                 ▼
   ┌───────────────────────────────────────────────────┐
   │  Hub: pmbrs_host_sync_ingest.py                   │
   │  + bearer-token auth (new) + route guard (new)    │
   │  + inbox/ dir = raw uploaded page PNGs (new)      │
   └───────────────────────────────────────────────────┘
                 │
                 ▼
   ┌───────────────────────────────────────────────────┐
   │  Stage-1/2 pipeline (unchanged contract)          │
   │  producer: enumerate inbox → dedupe vs manifest   │
   │  → OCR (qwen3.8:27b, engine slot) → artifact      │
   │  → raw/journal/                                   │
   └───────────────────────────────────────────────────┘
                 ▲
   nightly ADB sweep  │  (retained: covers powered-off / app-outage / anything the
   (Stage-2, existing)└── device app never pushed)
```

**The device ships *input* (PNGs + note UUID + page order + sha256), not finished artifacts.**
OCR stays on the PC (ADR-019 D1, user decision unchanged). The only thing Stage 3
replaces is *how the PNGs arrive*: `adb pull` → inbox drop. The Stage-1/2 producer
code path stays; its read-side changes from "ADB tree" to "union of inbox + ADB".

## 5. Wake strategy (D5)

| Path | Trigger | Behavior | Cost |
|------|---------|----------|------|
| **Opportunistic** | `ConnectivityManager` "Wi-Fi available + connected" callback; note-watcher fires on new PNG | If queue non-empty → upload. If empty → no-op. | ~0 — event-driven, no timers. Reuses the device's own periodic Wi‑Fi windows (02:32/07:32 evidence) plus every time the user touches the device. |
| **Daily exact alarm** | `AlarmManager.setExact` at 02:00 (configurable) | Wake → Wi‑Fi connect → upload if queued → release wake lock → sleep. Handler exits immediately when queue empty. | One ~30–60 s Wi‑Fi burst/day, only when queued — well under 1%/day on a NoteAir-class battery. |
| **PC sweep** | existing `scripts/pmbrs_boox_nightly.py` (ADB) | Unchanged. Retained *specifically* because nothing can wake a powered-off device. | Existing cost; steady-state cost ≈ 0 (empty tree). |

Explicitly **not** in the design:
- FCM push as a *wake* mechanism (GMS on this device only lands pushes within its own reconnect windows; treated as a future nudge-at-best, never the critical path).
- Forcing `wifi_sleep_policy = 0` (keep radio up through sleep) — that is the more expensive option and the user preference is to avoid it.
- Any persistent polling loop (Termux etc.) — that is precisely the failure mode the queue + WorkManager design exists to prevent.

## 6. Device app (Phase 1)

**Host model:** a minimal Android app whose *only purpose* is to exist so the
foreground service can run (Android 12 background restrictions). No screens, no
Compose, no settings UI. The foreground service carries the required persistent
notification (D3) — which at the same time *is* the debug surface:
`"BooxSync · 3 queued · last 02:14 ✓ (3/3 acked)"`.

**Reuse from `pmbrs/mobile/`** (already written, patterns proven):
- `sync/` — queue DB, WorkManager + foreground handling, retry/backoff.
- `network/` — endpoint selection (LAN primary → tunnel fallback), bearer-token client.
  Swapped-out: all `collector/` and UI packages are *not* ported.

**New (the actual Boox-specific code):**
1. **Note-watcher** — watches `/storage/emulated/0/.ksync/document/<uuid>/` and the
   `.noteCache/thumbnail/` page PNG tree; flags new/changed pages by sha256 vs the
   device-side "uploaded?" manifest (second manifest, see §7).
2. **Uploader** — per-page PNG → `POST /api/v1/artifacts/sync` (payload: note UUID,
   page order, sha256, PNG bytes; the PC's inbox writer saves it).
3. **Alarm** — one `setExact` daily, installed at first run; re-armed after each fire.
4. **Connectivity listener** — "Wi-Fi connected" event → upload-if-queued.
5. **Permissions needed**: `MANAGE_EXTERNAL_STORAGE` (one-time grant; required to read
   other apps' shared-storage dirs on Android 12), `FOREGROUND_SERVICE`,
   `SCHEDULE_EXACT_ALARM`, `INTERNET`, `POST_NOTIFICATIONS`.

**Out of scope for v1** (explicitly deferred, per ADR-019 consequences): engagement
telemetry collectors (note open/close, stroke activity) — a *later* ADR, using the same
app shell if the layering keeps it cheap.

## 7. Hub + PC (Phases 0, 2)

**Phase 0 — auth prerequisites (blocks device work)**
- Add bearer-token auth to `pmbrs_host_sync_ingest.py` (currently *zero* — verified by
  grep, 2026-08-21; fine LAN-only, non-negotiable once the tunnel is in the critical path).
- Store tokens in `~/.pmbrs-private/config/` (outside the repo); issue **one token for
  the Boox**, independent of any future phone token.
- New tunnel hostname `boox-sync.jjrdev.com` → same `127.0.0.1:8788` service, separate
  token, separate log line. Rationale: different data class (raw handwritten journal
  pages — the recon sample transcript is deeply personal, more sensitive than phone
  telemetry), independent failure/revoke boundary, matches the mobile fallback plan's
  own rule (tunnel exposes only the ingestion API, never the raw store).
- **Route guard**: the new authed route is the Boox-specific `POST /api/v1/artifacts/sync`
  (same path, token disambiguates) — no new store exposure, no new API for OCR.

**Phase 2 — inbox + producer rewire**
- New inbox dir: `~/.pmbrs-private/store/inbox/boox/<uuid>/<page>.png` (staging, not the
  raw store — the raw store continues to hold only *finished* artifacts).
- Producer change: `enumerate()` reads `union(inbox, adb_tree)`; the rest of
  `producer/ocr/artifact` is unchanged. ADB stays as a second source so the sweep keeps
  working during and after cutover (zero cutover risk).
- Two-layer manifest idempotency (same sha256, two stores):
  - **Device-side** `uploaded?` manifest (queue DB acked set) — stops re-pushes.
  - **PC-side** `boox_sync_manifest.json` (existing, Stage-2) — stops re-OCRs.
  Both exist already in the respective codebases; no new logic, just both get consulted.

## 8. Cutover (Phase 3)

1. Run both paths in parallel for a full week (device push on, sweep on).
   Success = every new note reaches `raw/journal/` within one of the device's natural
   Wi‑Fi windows, and the sweep reports 0 new finds after day 2.
2. Confirm the sweep's `exit 3` (device unreachable) no longer *blocks* any note —
   i.e., every note also arrived via push.
3. Decision: keep the sweep as-is (recommended — nearly free) as the power-off/app-outage
   net. ADB debug mode may then be turned off on the device (removes the ADB-over-LAN
   dependency entirely from the production path; ADB remains available for the rare deep
   debug).

## 9. Failure modes & debug

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Wi‑Fi never reconnects (rare, home router off) | Hub: no acks, device notification stuck on "queued" | Next natural window / user touches device / next daily alarm. |
| Device powered off at write time | Hub last-ack timestamp vs. note mtime | ADB sweep (if device was off, it's *on* again by the time the sweep runs, or it wasn't a real "written" note yet — sweep is a best-effort net, not a guarantee). |
| App killed / crashloop | Hub: no acks, device app absent from `pm list packages` | Reinstall from APK (kept in repo `mobile/boox-app/`); queue DB survives reinstall if on shared storage, else re-sync from ADB. |
| Token leaked | Rotate via hub (Phase 0 includes a `rotate` subcommand) | New token issued, old invalidated; device gets new token via ADB once. |
| Note tree layout changes (ONYX OS update) | Watcher: 0 pages detected + ADB sweep finds pages | Stage-2 `adb.py` still parses the real layout — sweep keeps working while watcher is re-pinned. |

## 10. Open (intentionally unresolved)

- **Telemetry collectors** (Boox engagement): deferred to a later ADR; this app's
  *shell* is structured so it's cheap to add, but v1 ships uploader-only.
- **Books→Boox delivery**: still out of scope (ADR-019 user decision 3, unchanged).
- **FCM as a nudge**: not built in v1; if the opportunistic + alarm paths ever prove
  insufficient (e.g., the user wants sync within minutes of writing, from off-LAN,
  without waiting for a daily alarm), FCM is the next lever to pull — the app's
  network layer is already FCM-shaped (separate endpoint, token, queue), so adding it
  is a module, not a rewrite.

---

## 11. Progress ledger (live)

| Phase | Scope | State | Verified by |
|-------|-------|-------|-------------|
| **0** | Hub auth (bearer + role), `boox-sync` hostname, token store | Done | `test_phase0_auth` (15), tunnel → 200/401/403 |
| **1** | Headless device app (foreground svc, wake, LAN→cloud client, dedup) | Done | Real NoteAir: `ok=22 failed=0`, inbox=22, 2nd pass no-dupe |
| **2** | `InboxCollector` + nightly `--transport auto/inbox/adb` + producer provenance | Done | `InboxCollector` live pull; nightly dry-run; `test_boox_*` (11) |
| **3** | Cutover: retire/freeze ADB-sweep as *primary*, keep as powered-off net; parallel-run + exit criterion | Pending | — |

**Phase-1 on-device fixes that shipped** (discovered while getting it running):
`setExactAndAllowWhileIdle` (was `set()`), `SCHEDULE_EXACT_ALARM` + `USE_EXACT_ALARM`
manifest entries, `PushTracking` device-side dedup (atomic json in `filesDir`),
exported `CommandReceiver` for `am broadcast` control surface, one-shot
`LaunchActivity` bootstrap (Android 12 stopped/notLaunched state — ONYX honors it
strictly, so a launcher is required; without it *every* background-start path is
silently dropped).

**Phase-2 files**: `src/pmbrs/ingestion/boox/inbox.py` (drop-in `InboxCollector`),
`scripts/pmbrs_boox_nightly.py --transport {auto,inbox,adb}` (default `auto` = inbox
if non-empty, else ADB), `producer.py` provenance now reports the collector's
`transport_name` (artifact stays transport-agnostic, ADR-020 D5).

**Phase-3 exit criterion** (to unblock cutover): one week where inbox receives ≥95%
of pages in the last 7 days with the ADB sweep finding nothing new; then the sweep
can drop to "powered-off net" frequency (e.g. weekly) without losing throughput.

---
*Cross-references: ADR-019 (BoOX journal ingestion, ADB transport decision),
ADR-017 (tunnel + domain), `../ingestion/adapters/mobile-collection-architecture.md`,
`../ingestion/adapters/mobile-collection-local-cloud-fallback-plan.md`.*
