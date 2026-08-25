# Storage & Persistence Layer — Architecture

## Overview

Defines the physical layout of PMBRS's artifact store using SQLite + filesystem as our dual persistence mechanism, per **ADR-001** (Storage Backend) and **ADR-010** (Storage Layout). SQLite handles metadata / indexing / lineage tracking; the filesystem stores raw binary artifacts directly on local disk. This design is intended to preserve reproducibility, lineage, and user control over historical evidence. It should support reprocessing, retraining, and long-term interpretation without allowing derived outputs to overwrite authoritative source artifacts.

The raw layer of record is **plain JSON artifacts on the filesystem** (one artifact per file), per **ADR-017 D2**. The JSONL + SQLite index layer described below is the **target for derived / aligned / feature / embedding artifact types** once the `StorageAdapter` protocol from `docs/module-contracts.md` is implemented.

## Directory Structure (current, reflects reality on 2026-08-19)

The single user-data root is `~/.pmbrs-private` (aka `/home/jjrdev/.pmbrs-private`). It is declared in `config/external_data_policy.json`, used by every runtime script, and is `chmod 700` protected. The XDG-style `~/.local/share/pmbrs` path that some earlier drafts of this doc referenced is **retired** (see ADR-017 D1) — all code and config use the `.pmbrs-private` root.

```
~/.pmbrs-private/                        # chmod 700 — single user-data root
│
├── state/                               # runtime + scheduler state (JSON, one per file)
│   ├── pmbrs_runtime.json               # runtime metadata (policy snapshot)
│   ├── scheduler_state.json             # nightly scheduler checkpoint (last/next run)
│   └── hermes_snapshot.json             # published snapshot payload (read-only mirror)
│
├── hermes-readonly/                     # Hermes-facing read-only snapshot (chmod 555, files 444)
│   └── pmbrs_summary.json               # the single snapshot file Hermes is allowed to read
│
├── checkpoints/                         # module checkpoints (declared in config; grows as pipeline runs)
│   └── (one JSON per module per run)
│
└── store/
    │
    ├── raw/                             # authoritative raw artifacts — one JSON per file (ADR-017 D2)
    │   ├── browser/                     # browser source (canonical; legacy browser_* names normalize here)
    │   ├── desktop/                     # desktop source
    │   ├── journal/                     # user-declared journal entries (origin: user, not observation)
    │   ├── mobile/                      # Android app sync batch artifacts
    │   ├── other/                       # unclassified / legacy
    │   └── (future: wearable/, calendar/ when their adapters land)
    │
    ├── pending/                         # ingest queue (declared in config; exercised when batch sync runs)
    │   └── (one JSON per queued artifact)
    │
    ├── summary/                         # timestamped read-only snapshots (publishes here before hermes-readonly)
    │   └── pmbrs_summary_<epoch_ms>.json
    │
    └── (future: alignment_maps/, features/, embeddings/, experiments/)
        # Derived / aligned / feature / experiment artifacts.
        # Format for these layers is JSONL + SQLite (events.db) per ADR-001 / ADR-010,
        # deferred until the `StorageAdapter` protocol (docs/module-contracts.md) is implemented.
```

**File-per-artifact vs JSONL** — the **raw** layer uses one-JSON-per-file (the format that `scripts/pmbrs_host_sync_ingest.py` writes today and that the 5 initial `sample.json` files confirm). Derived / aligned / feature / embedding layers use JSONL per file per modality (high-volume, columnar-friendly), indexed by `events.db` SQLite for range + lineage queries. The **single consumer-facing abstraction** for both is the `StorageAdapter` protocol from `docs/module-contracts.md`; no downstream module opens a raw file path or a direct DB connection.

## Artifact Record Shape (raw layer)

One JSON object per file under `raw/<source>/`. Fields written by `scripts/pmbrs_host_sync_ingest.py` (§11 — immutable, never rewritten in place; user-requested deletions follow the "Deletion & Lineage" section below):

| Field                     | Type       | Description                                                                  |
|---------------------------|------------|------------------------------------------------------------------------------|
| `artifactId`              | string     | Globally unique identifier (UUID or content-hash; see ADR-003).               |
| `source`                  | string     | Enum: `mobile` \| `browser` \| `desktop` \| `journal` \| `other`.             |
| `payload`                 | object     | Source-specific body (varies by source; see modality specs under `docs/`).   |
| `createdAtEpochMs`        | int        | Creation time (ms epoch UTC) — never retroactively changed unless corrected by user per §9. |
| `schemaVersion`           | string     | SemVer schema version for this artifact type.                                 |
| `deviceAlias`             | string     | Originating device id (default: `"unknown"`); used for cross-device lineage. |
| `provenanceMetadataJson`  | object     | Extra provenance (collector, transport, checksums) if provided by the source.|
| `ingestedAtEpochMs`       | int        | When the host ingest endpoint accepted the artifact (ms epoch UTC).           |
| `ingestStatus`            | string     | `accepted` \| `rejected` \| `quarantined` etc.                                |

Payloads are inline within the JSON object (small-to-medium, <256 KB typical). Larger binaries are content-hashed references per ADR-003, but **have not shipped yet** per §7 — no high-resolution audio/video capture is in scope.

## JSONL + SQLite Layer (Target — ADR-001 / ADR-010)

Once the `StorageAdapter` protocol is implemented, the derived / aligned /
feature / embedding layers will be JSONL + SQLite:

- One file per modality per canonical window grid per day (e.g.
  `features/2026-08-19.browser.jsonl`, `features/2026-08-19.mobile.jsonl`).
- One `events.db` SQLite index holding artifact metadata, lineage DAG edges
  (`derive_from` from the module contract), and range-scannable indexes on
  `(source, createdAtEpochMs)` and `(canonical_window_id)`.
- This layer is **where "windowed queries" become cheap** — the Streamlit /
  (later Electron) dashboard reads these tables via the `StorageAdapter`;
  it never reads the JSONL directly in production.

## Deletion & Lineage Invalidation on User Request

When an authoritative artifact (user-declared or observational evidence) is
explicitly deleted by the user:

1. The original artifact's status is set to `deleted` for audit-trail
   purposes, while the content is zeroed or encrypted locally and not
   recoverable in normal operation.
2. Downstream derived artifacts that trace back to this parent are marked
   `invalidated`. They remain stored for historical integrity but are flagged
   so downstream consumers know that the derivation chain is now questionable
   or broken.
3. An orphan-detection sweep runs after the migration to find artifacts whose
   only dependency on the deleted authority is through invalidation; these may
   be cleaned up by the user during scheduled maintenance windows if desired.

## Encryption at Rest (ADR pending)

All files under `~/.pmbrs-private/` are **unencrypted locally** for
performance. Baseline protection is filesystem permissions: `chmod 700` on
the root, `chmod 555` + `chmod 444` on the Hermes read-only snapshot
directory/files (`pmbrs_publish_summary_to_hermes.sh`), OS-level owner-only
access on the rest. This is consistent with §7 (privacy-first) and §16
(local-first).

Three paths remain open for stronger at-rest protection (an ADR should pick
one when the choice becomes load-bearing):

- **Option A — kernel-level volume encryption** (Linux LUKS / macOS FileVault
  / Windows BitLocker). Zero application cost; OS-managed; best for
  "we don't want to think about it in the app".
- **Option B — application-level AES** (transparent
  `cryptography` Fernet / AES-GCM wrapper around the JSON artifact files and
  SQLite index). Adds CPU and key-management cost; survives volume format
  changes.
- **Option C — SQLCipher-style encrypted SQLite** for the index layer only
  (raw JSON files stay plaintext on disk; only the SQLite index is
  encrypted). Middle path.

The decision is deferred — it is not required for the dashboard or the
training pipeline to function, and the local-permissions baseline meets §16
today.

---

> **Constitution References** — §5 (batch-first), §7 (privacy-first; raw
> browser URLs excluded, domain_hash only; no screen capture), §8 (modality
> taxonomy), §9 (interpretability; associational, not causal), §11 (artifact
> architecture; raw is authoritative), §14 (scheduling & evaluation), §15
> (visualization is replaceable), §16 (local-first, single-user). This design
> keeps all user data on the local machine directly under user control, which
> is the §16 requirement.

> **ADR Cross-References** — ADR-017 (this store's format reality,
> 2026-08-19) is the current ground truth and **closes ADR-010** (Storage
> Layout; see `docs/adr/ADR-010.md`). ADR-001 (Storage Backend) remains open
> and will be closed when the `StorageAdapter` protocol is implemented and the
> JSONL + SQLite target is built.
