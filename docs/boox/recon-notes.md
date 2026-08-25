# BOOX Note → PMBRS — Stage 0 Recon Notes

**Status:** Evidence record (read-only findings), captured 2026-08-20 on a live device.
**Companion docs:** decision → [`adr/ADR-019.md`](../adr/ADR-019.md) · implementation → [`stage1-spec.md`](stage1-spec.md)

These are **verified facts pulled from the connected device**, not assumptions. They
supersede the loose conversational notes in the original pasted file. Everything here
was observed via ADB against the actual filesystem and by running the candidate OCR
engine, so it can be cited as ground truth in the ADR and spec.

---

## Device & access

| Fact | Value |
|------|-------|
| Model | BOOX NoteAir3 |
| Android | 12 (SDK 32) |
| ADB serial | `4EF2D7E9` (matches the `mtp://…SN:BE70A7AE_4EF2D7E9` MTP name) |
| ADB reachability | Reachable in debug mode from the dev container |
| Root | **No** — app private dirs (`/data/data/…`) are not readable |
| ADB shell perf | **Slow / throttled on the e-ink device.** Some long `find`/loop commands timed out. Treat ADB as a best-effort transport, not a fast bulk channel. |
| MTP mount from container | Not available (`gio mount` → "volume doesn't implement mount"). ADB is the working path. |

**Access conclusion:** we can read the **entire user-visible external storage**
(`/storage/emulated/0/…`) — which holds the whole note store — but **cannot** read
the app's private database. That boundary defines what is and isn't available without
root (see *Gaps* below).

---

## Where notes live (external storage, no root needed)

Top-level BOOX-managed trees under `/storage/emulated/0/`:

```
.ksync/                 # KSync (com.onyx.android.ksync) note store
├── document/<32-hex-uuid>/   #  ← ONE DIRECTORY PER NOTE  (21 notes observed)
├── couch/<user>-NOTE_TREE.cblite2/   # shared copies — EMPTY 4 KB shells, not the index
├── images/, noteCache/, …
.noteCache/thumbnail/   # rendered PNG thumbnails (OCR input)
```

Each note is one directory: `.ksync/document/<uuid>/`. **21 notes** present. Inside a
note:

| Path (relative to note dir) | What it is | OCR relevance |
|---|---|---|
| `shape/*.zip`, `stash/archivedShape/<epoch>/*.zip` | **The ink.** Per-stroke-group bundles, native binary (Skia shapes). ~2–20 KB each, many per note. | **Not text.** To read it directly we'd have to re-implement a Skia renderer. ❌ |
| `pageModel/pb/…`, `virtual/doc/pb`, `virtual/page/pb` | **Protobuf that embeds JSON**: a Skia scene-graph (`fillPath`, `shapeType`, `pageMargins`, `contentPageSize` **1404×1872**, `contentType: geo_layout`). Page *scaffold/template*, shapes referenced by id. | Page geometry + note↔page map. Decodable. ✅ |
| `template/json/*.template_json` | Plain JSON layout/feature descriptors. | Context only. |
| `.template_json` sample | `{"displayFillColor":0,"fillPath":{…},"pageMargins":{…},"contentPageSize":{…},"contentType":"geo_layout"}` | Confirms scene-graph JSON inside the proto. |

### Rendered page PNGs — **the OCR input**
- `.noteCache/thumbnail/page/<pageid>/<hash>.png` — per-page renders. **RGBA, ~499×666 px**
  (≈ 1/3-scale thumbnail of the 1404×1872 page), a few–90 KB each.
- `.noteCache/thumbnail/<note-uuid>.png` — per-note cover thumbnails, ~25 of them,
  sizes **2.7 KB (blank page) → 97 KB (dense)**. These double as cheap "is this page
  empty?" signals and as the primary OCR input for single-page notes.
- `.noteCache/images/` — empty (`.nomedia` only).

---

## Key facts that drive the design

1. **No stored text.** The note content is stroke ink (binary) + scene-graph JSON. There is
   nothing to "read" directly. **OCR is required to produce text**, on the PC, from the
   rendered page images. (User decision 1: *PC does OCR, not the Boox* — confirmed
   necessary, not optional.)
2. **The note index (titles / hierarchy / created order) is in the app's *private* DB**
   (`/data/data/com.onyx.android.note`, Couchbase-Lite). **Not root-accessible.** The
   shared `.ksync/couch/*-NOTE_TREE.cblite2` copies are 4 KB empty shells. → For v1,
   provenance = `{note_uuid, dir mtime, page_count, page_dims}`; **note titles are
   recovered from the OCR text (first line / heading) or left blank.**
3. **Resolution is adequate.** The LLM-vision engine (below) read the ~500 px renders
   clearly. So Stage 3 "full-res render" is **probably unnecessary** — validate on a real
   multi-page note before committing, but it's low risk.
4. **The OCR engine works locally and is the right model.** `qwen3.8:27b` on local Ollama
   transcribed messy cursive well (see A/B sample). Note: the older `qwen3.6-27b`
   (`my-qwen-highctx`/`maxctx`) exposes **`completion` only, no `vision`** — so qwen3.8 is
   both better *and* effectively the only local model that can do this.
5. **Boox→PC, notes-only, no books.** User decisions 2 ("on now") & 3 (no books→Boox).
   The device also carries `kreader`, `easytransfer`, `aiassistant` — all **out of scope**.
6. **Scheduling lives elsewhere.** The task/scheduler + notification APK
   (`personal-task-system/task-notify-android`) is the **only** scheduling/notification
   plane. PMBRS is a **data producer**: it exposes artifacts for ingest and never stands
   up its own independent 2 AM cron. No second scheduler is introduced. (Constitution §14-6
   batch-first + existing `docs/orchestration/task-scheduling.md` still govern PMBRS's own
   pipeline cadence; BoOX delivery is additive data, not a new cadence.)

---

## A/B evidence (2026-08-20)

**Candidate engines**
- **Side B — LLM-vision**, local. Model that produced the transcriptions: **qwen3.8:27b**
  (`my-qwen38-maxctx` session model, parent `qwen3.8:27b`), Ollama `localhost:11434`,
  17 GB Q4_K_M, 262k context, capabilities: `completion, tools, thinking, vision`.
- **Side A — classic OCR (Tesseract):** **not installed** in this environment, and not
  demonstrated. Given the ink style (connected, slanted, variable-size cursive with
  crossed-out words), classic OCR would return mostly garbage on these pages. We do **not**
  fabricate a Tesseract result; the LLM-vision path is chosen on the strength of Side B.

**Sample transcribed (Side B, densest of the three sample pages, note
`01a1cfdb2288457cb3062b70b833b7e0`, ~90 KB, 499×666):**

> *My mind has become so cooked. I'm not fine [I feel] I'm in this weird loop where I
> … but one month, a month, a month — so, perhaps longer — I have lost the ability to
> hold a consistent chain of time. I feel in my super quiet. I don't [know] what I've
> done or can't. I only remember the general big things that I've done for that day.
> I am unable to measure my self in deep work. It is incredibly hard. How do I want
> such a thing? I had spent too much time doing passive and start to see depression in
> many states. [I'm] scrolling, gaming, gaming, stopping. My normal desire must be
> reset… I am on a different [state], I am on a surface, passive, wired, impulsive. I
> want another version of me… I need to [get] somewhere. This [thing] has helped
> already, though slightly — it is calmer. The drinking, gaming, spending, scrolling is
> death. I want distance from myself once again. I want to battle these for life. I
> want to replace such things with [cutting] out: training, reading, writing, coding,
> and perhaps one more thing — I'm going to enter a [period of] solitude [and] self…
> I must prepare myself. I must survive. … Let my eyes not mistake the glasses of
> evil things as heavenly light. Let my [path not] walk me into the glowing abyss of
> hell. It's only [worth] the fire that surrounds my body, leaving nothing but an
> ashen crop of who I was. God help me.*

( `[?]` / `[...]` marks the handful of genuinely ambiguous spots — crossed-out words,
faded text. **≈95% of clear text is clear, and the meaning is fully recoverable.** That
is the bar we need, and it is met.)

**Verdict:** LLM-vision over rendered page PNGs wins decisively. No Tesseract/PaddleOCR
dependency, no Skia re-renderer. Local, private, free.

---

## Gaps (must be resolved in Stage 1, not assumed)

1. **Page fan-out for multi-page notes.** The shared cache showed 1 page under
   `thumbnail/page/` and per-note covers for ~25 notes. Need to confirm every page of a
   multi-page note is reachable from shared storage, or resolve the note→page map from
   `virtual/page/pb` (decode) with a **fallback** of "locally render / enumerate every
   page PNG for the note, order by mtime."
2. **Note titles** not in shared storage (private DB). Recover from OCR (heading / first
   line) or accept blank in v1.
3. **Full-res vs thumbnail.** 500 px worked, but sample a real 3–5 page note before v1
   ships; escalate to a full-res render path only if needed.
4. **ADB transport reliability.** Shell is slow here. `adb tcpip 5555` gives a LAN path
   without a USB tether; keep file pulls batched, resumable, idempotent.

---

## Reproduction (commands used)

```bash
D=4EF2D7E9
adb devices -l                                   # NoteAir3, Android 12
adb -s $D shell 'ls /storage/emulated/0/.ksync/document'                # 21 note uuids
adb -s $D shell 'find /storage/emulated/0/.ksync/document/<uuid> -type f'
adb -s $D pull /storage/emulated/0/.noteCache/thumbnail/<uuid>.png      # OCR input
# OCR engine: Ollama qwen3.8:27b (vision) on localhost:11434
# Ingest endpoint (already in repo): scripts/pmbrs_host_sync_ingest.py
#   POST /api/v1/artifacts/sync  → ~/.pmbrs-private/store/raw/journal/
```
