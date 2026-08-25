# BoOX Note Ingestion — Stage 1 Implementation Spec

**Status:** Spec for implementation (Stage 1 = producer + OCR + ingest glue).
**Authority:** Implements [ADR-019](../adr/ADR-019.md). Facts from [recon-notes.md](recon-notes.md).
**Scope:** BoOX NoteAir3 → PMBRS `journal` artifacts. **Notes only.** No books, no telemetry,
no custom Boox app, no cloud OCR, no new scheduler.

---

## Goals

- Pull a selected subset of BoOX notes (by `note-uuid` list or "all unsynced") from the
  device over ADB.
- For each note, resolve its pages, pull the rendered page PNGs, and **OCR each page
  locally** with `qwen3.8:27b` (Ollama).
- Emit one `journal` artifact **per page** (fallback: one artifact per note with `pages`
  array) to the existing ingest endpoint, landing in
  `~/.pmbrs-private/store/raw/journal/` per ADR-017.
- Be **idempotent** (manifest-diffed) and **auditable** (provenance on every artifact).
- Leave a **model slot** so a future handwriting-specific model is a config change.

## Non-goals (explicit)

- No custom BoOX app / APK / agent. No LocalSend / Syncthing / cloud.
- No books→Boox delivery. No book library management.
- No engagement telemetry (open/close/stroke). No new scheduling cron (the external
  `task-notify-android` APK is the user's only notification plane; PMBRS does not add its
  own 2 AM job *for BoOX*; the existing PMBRS batch cadence stays the sole PMBRS cadence
  authority per Constitution §14-6).
- No full-res Skia re-renderer *in Stage 1*; we keep it as a **documented escape hatch**
  enabled by a config flag (`boox.ocr.full_render: true`) that Stage 2 may implement.

---

## System layout

```
BoOX (NoteAir3, Android 12, ADB serial 4EF2D7E9)
   .ksync/document/<uuid>/             21 notes observed
   .noteCache/thumbnail/page/<pageid>/*.png
   .noteCache/thumbnail/<uuid>.png
                │
                │  adb pull (USB by default; `adb tcpip 5555` for LAN)
                ▼
PC (this dev host)
   ┌─────────────────────────────────────────────────────────────────┐
   │  pmbrs-boox-producer  (new, Python, pmbrs/src/pmbrs/...)         │
   │   1. manifest load + note-dir walk → page list + hashes          │
   │   2. pull page PNGs (idempotent, resumable)                      │
   │   3. OCR engine slot → local Ollama qwen3.8:27b                 │
   │   4. build journal artifact(s) + provenance                     │
   │   5. POST /api/v1/artifacts/sync (existing ingest)              │
   │   6. write ~/.pmbrs-private/state/boox_sync_manifest.json        │
   └─────────────────────────────────────────────────────────────────┘
                │  HTTP/JSON
                ▼
   POST /api/v1/artifacts/sync  (scripts/pmbrs_host_sync_ingest.py, port 8765,
                                 or https://mobile-sync.jjrdev.com per ADR-017)
                │
                ▼
   ~/.pmbrs-private/store/raw/journal/<artifactId>-<createdAtEpochMs>.json
   (existing record shape per ADR-017 D2 — one JSON per file)
```

---

## Components

### C1 — Manifest (idempotency)

- **Location:** `~/.pmbrs-private/state/boox_sync_manifest.json` (new file, same state
  root as ADR-017 D1; chmod 700 inherited).
- **Shape:**
  ```json
  {
    "schemaVersion": "1.0",
    "deviceSerial": "4EF2D7E9",
    "notes": {
      "<note-uuid>": {
        "noteDirMtimeMs": 1747680123456,
        "pageCount": 3,
        "pages": [
          {
            "pageId": "b852a379ba9742d584765a9ecc39084f",
            "pageOrder": 1,
            "pngRelPath": ".noteCache/thumbnail/page/b852a379…/…png",
            "pngSha256": "…",
            "pngDims": [499, 666],
            "lastOcrAtMs": 1748600123456,
            "lastOcrEngine": "qwen3.8:27b-ollama-local",
            "lastArtifactId": "boox.<uuid>.p1"
          }
        ]
      }
    }
  }
  ```
- **Skip rule:** on re-run, a page is **re-OCR'd only if** any of
  `{pngSha256, pngDims}` changed, OR the producer explicitly flags `--force`, OR the
  note-dir mtime advanced and the page list changed. This makes steady-state passes cheap
  even with 21 notes.
- **First-run:** manifest is empty; every page is newly OCR'd.

### C2 — Page resolution (note → pages)

Preferred (Stage 1, best-effort, **do not block on this**):
1. Walk `.noteCache/thumbnail/page/` and match page-dirs whose `<pageid>` appears in the
   note's `virtual/page/pb` (decode the embedded JSON; see recon). Build `pageOrder` from
   the JSON if present, else from mtime.
2. If `virtual/page/pb` is unreadable or empty for a note, fall back to:
   "**one artifact per note**" = OCR the `.noteCache/thumbnail/<note-uuid>.png` cover
   (which is the best shared-storage render for single-page notes) with `pageOrder=1`,
   `pageCount=1`. Mark `pageFallback: "cover"`.

Fallback path (used by all Stage-1 runs until decode is stable): the per-note cover PNG
at `.noteCache/thumbnail/<note-uuid>.png` is the OCR input. This works for **the sample
cases** (single-page notes are the majority in the manifest) and avoids blocking on a
full `virtual/page/pb` decoder in Stage 1. The decoder is a Stage 1 stretch target and
the documented escape-hatch input to Stage 2.

### C3 — OCR engine slot

- **Interface (Python):**
  ```python
  class OcrEngine(Protocol):
      name: str  # e.g. "qwen3.8:27b-ollama-local"
      def transcribe_page(self, png_bytes: bytes, *, prompt: str, max_tokens: int) -> str: ...
  ```
- **Default impl: `OllamaEngine`.**
  - Base URL: `http://127.0.0.1:11434` (env `PM_BRS_OCR_OLLAMA_URL`).
  - Model: `qwen3.8:27b` (env `PM_BRS_OCR_MODEL`; default
    `PM_BRS_OCR_MODEL=qwen3.8:27b`).
  - Endpoint: `POST /api/chat` (Ollama chat) with `stream:false`,
    `temperature: 0.1`, `options.num_ctx` high enough for the prompt.
    Alternative: `POST /api/generate` for a minimal call.
  - Image: PNG embedded as a base64 `data:image/png;base64,…` in the request
    (`images` array on Ollama, or content parts).
- **Prompt (canonical):**
  > You are transcribing a handwritten note on paper for archive. Transcribe ALL
  > handwriting exactly as written. Preserve line and paragraph structure. Do not
  > correct spelling. Mark words you are genuinely unsure of with a leading `[?` and a
  > closing `]`. If the page is blank, respond with the exact word BLANK. Do not add
  > commentary, no preamble.
- **Result handling:**
  - If the response (after strip) is the single word `BLANK`, treat the page as blank,
    do **not** emit a journal artifact, but DO record the page in the manifest with
    `lastOcrAtMs` and `lastOcrEngine` so it isn't retouched. This keeps the journal
    lane free of blank pages (matches the "raw artifacts are meaningful" spirit of
    §11).
  - Otherwise the full stripped string is the OCR text.
  - On HTTP/JSON error: retry 2× with backoff; on final failure, log and **skip** the
    page this pass (do NOT emit a placeholder). It will be retried next pass because no
    `lastOcrAtMs` is recorded.

### C4 — Artifact

One per **non-blank page** (per C2 preferred, or the fallback cover).

Fields to send in the ingest payload (matching ADR-017 D2 /
`scripts/pmbrs_host_sync_ingest.py`):

```json
{
  "artifactId": "boox.<note-uuid>.p<pageOrder>",
  "source": "journal",
  "payload": {
    "modality": "journal",
    "artifactKind": "handwritten_note_page",
    "noteUuid": "<note-uuid>",
    "pageOrder": 1,
    "pageCount": 3,
    "ocrText": "…transcribed text…",
    "ocrEngine": "qwen3.8:27b-ollama-local",
    "ocrModel": "qwen3.8:27b",
    "ocrPromptVersion": "v1.0",
    "pageImage": {
      "sourcePath": ".noteCache/thumbnail/page/<pageid>/<png>",
      "sha256": "…",
      "dimensions": [499, 666],
      "bytes": 42423
    },
    "deviceModel": "NoteAir3",
    "deviceSerial": "4EF2D7E9",
    "capturedAtMs": 1747680123456,   // fs mtime of the note dir
    "transcribedAtMs": 1748600123456
  },
  "createdAtEpochMs": <capturedAtMs>,
  "schemaVersion": "1.0",
  "deviceAlias": "boox-noteair3",
  "provenanceMetadataJson": {
    "producer": "pmbrs-boox-producer",
    "producerVersion": "0.1",
    "transport": "adb",
    "adbSerial": "4EF2D7E9",
    "noteDir": "/storage/emulated/0/.ksync/document/<uuid>",
    "ocrEngineImpl": "OllamaEngine",
    "ocrTemperature": 0.1,
    "ocrLatencyMs": 3210,
    "lineage": { "derivedFrom": "boox.device.note", "derivation": "llm_vision_ocr" }
  }
}
```

**Ingest contract (existing, unchanged):**
- Endpoint: `POST /api/v1/artifacts/sync`, body = `{ "artifacts": [ <row> ] }` (or a
  bare array).
- Server: `scripts/pmbrs_host_sync_ingest.py` (default `--port 8765`). Alternative
  host: `https://mobile-sync.jjrdev.com/api/v1/artifacts/sync` per ADR-017 D4.
- Outcome: `~/.pmbrs-private/store/raw/journal/<artifactId>-<createdAtEpochMs>.json`.

### C5 — Producer (CLI)

Location (proposed): `scripts/pmbrs_boox_producer.py` (sibling of
`python_gluelayer-orchestration` patterns, see `pmbrs_host_sync_ingest.py`).

```bash
python3 scripts/pmbrs_boox_producer.py \
  --adb-serial 4EF2D7E9 \
  --note-all | --note-uuid <uuid> | --note-file <path-to-note-list.txt> \
  [--force]                      # ignore manifest, force re-OCR
  [--dry-run]                    # manifest load + page list + pull, no OCR, no ingest
  [--max-notes N]                # cap for a first run
  [--ocr-url http://127.0.0.1:11434] \
  [--ocr-model qwen3.8:27b]
```

Behavior per run:
1. Load `~/.pmbrs-private/state/boox_sync_manifest.json`.
2. `adb shell ls .ksync/document/` → note ids. Intersect with user selection.
3. For each selected note: compute desired page list (C2), pull needed PNGs to a local
   working dir (`~/.cache/pmbrs-boox/<note-uuid>/<pageid>.png`), compute sha256, compare
   with manifest.
4. For each page that needs OCR (C3), call the engine and (if non-blank) build the
   artifact (C4).
5. Batch-POST all fresh artifacts in one request (keeps the ingest call count low on
   ADB-slow environments).
6. **Atomic** write of the updated manifest (write to `.tmp` then `os.replace`). This
   guarantees no half-updated manifest on crash: a page either made it to OCR + ingest,
   or the manifest isn't touched.
7. Log a run summary: `N notes, M pages, K artifacts ingested, J blank, H failed`.

### C6 — Optional: notify (Stage 1 optional, Stage 2 required)

Post-run, the caller may shell out to the existing task-notify APK trigger (a separate
command outside PMBRS, invoked by the user's shell wrapper) to post a "BoOX notes synced:
K new" notification on the user's phone. This is **explicitly optional** and **not
required** for Stage 1 correctness.

---

## Configuration (env + flag)

| Key | Default | Notes |
|---|---|---|
| `PM_BRS_OCR_OLLAMA_URL` | `http://127.0.0.1:11434` | Ollama base URL |
| `PM_BRS_OCR_MODEL` | `qwen3.8:27b` | Ollama model name; future: a fine-tuned BoOX-handwriting model |
| `PM_BRS_OCR_PROMPT_VERSION` | `v1.0` | For provenance |
| `PM_BRS_OCR_TEMPERATURE` | `0.1` | 0.0 for strict, 0.2 if we want a touch more permissiveness |
| `PM_BRS_OCR_MAX_TOKENS` | `4096` | Enough for a dense page; Ollama's `num_ctx` must cover it |
| `PM_BRS_BOOX_RAW_ROOT` | `~/.pmbrs-private` | User-data root (ADR-017 D1) |
| `PM_BRS_BOOX_WORKDIR` | `~/.cache/pmbrs-boox` | Local page-PNG scratch |

---

## Tests (Stage 1)

- **Unit (no device, no Ollama):**
  - Manifest diff logic (new / unchanged / changed pages).
  - Blank-page detection (`BLANK` → skip, manifest still updated).
  - Artifact field shape (round-trip through a stub of
    `persist_sync_batch` from `pmbrs_host_sync_ingest.py`).
  - Prompt versioning is recorded.
- **Integration (optional, if ADB + Ollama reachable in CI / dev):**
  - `--dry-run` on a known note-uuid. Assert page list + hashes in the log, no POST.
  - A single-page note end-to-end: assert the JSON file exists at
    `raw/journal/boox.<uuid>.p1-<ms>.json`, `ocrText` is non-empty, `ocrEngine` is set.
- **Regression:** re-run `--dry-run` twice; second call OCRs **zero** pages (manifest
  idempotency).

---

## Acceptance criteria

- From a clean state, `pmbrs_boox_producer.py --note-uuid <real-uuid>` produces at least
  one `journal` artifact under `raw/journal/` with non-empty `ocrText`, non-empty
  `pageImage.sha256`, and a `provenanceMetadataJson` containing `transport:"adb"` and
  `ocrEngine`.
- Re-running with the same note and no device changes produces **zero new artifacts**
  and updates no manifest fields.
- A deliberately blank page (user's existing sample note
  `59fcdd081cae4e7cb852a34c122dd521`, 2.7 KB cover) is **not** ingested as a journal
  artifact.
- No files outside `~/.pmbrs-private/` (state + store), `~/.cache/pmbrs-boox/` (scratch),
  and the PMBRS repo (`scripts/`, `docs/`) are written. (Constitution §16 local-first;
  "no files in ~ except explicit" rule.)

---

## Explicitly deferred (Stage 2+ candidates)

- **Full-res Skia re-renderer** for fine handwriting (only if Stage 1 samples fail).
- **`virtual/page/pb` decoder** as a first-class page mapper (Stage 1 uses cover PNG
  fallback; decoder is a stretch).
- **Custom BoX agent + authenticated-HTTP protocol** (scope B from the original notes)
  — only if ADB transport proves insufficient or we need background auto-sync.
- **Boox engagement telemetry** as a separate observational modality.
- **Boox→PC books delivery** (user has explicitly deferred).
- **Handwriting-specific fine-tuned model** (user-flagged future work; the engine slot
  already supports it).

---

## Open questions (to close before writing code)

1. **Engine slot default.** The user confirmed "local qwen3.8:27b" — is the default
   Ollama endpoint `http://127.0.0.1:11434` on the same box as the dev container, or do
   we need to use a host-side Ollama? (Recon shows 11434 is listening in-container, so
   `127.0.0.1:11434` should be correct; confirm once.)
2. **Which notes first?** All 21 in `document/`, or a curated list of "the interesting
   ones" the user cares about? (Recommend: all for the first real pass, so we build the
   manifest.)
3. **One artifact per note vs per page.** Spec defaults to **one-per-page** (with the
   cover fallback producing one-per-note). Is that granularity right, or does the user
   want one artifact per *note* with a `pages[]` array? (Recommending one-per-page for
   cleaner alignment / temporal windows, matching the canonical 60s-window philosophy in
   `docs/conceptual-foundation/temporal_model.md`.)
