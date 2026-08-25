"""BoOX note ingestion producer — the core run loop (ADR-019).

Pipeline per run (stage1-spec.md §C5):

    load manifest → list notes → per note → per page:
        pull page PNG → hash → manifest.needs_ocr?
            → OCR (engine slot)
            → blank?   record blank, no artifact
            → else     build journal artifact
    → single batch POST to the existing ingest endpoint
    → atomic manifest save (only pages whose ingest POST succeeded are marked)

Hard rules honored:

* The producer **never writes to the raw store directly** — it POSTs to the
  existing ``POST /api/v1/artifacts/sync`` ingest
  (``scripts/pmbrs_host_sync_ingest.py`` / ADR-017 D4 domain), the sole writer
  of ``~/.pmbrs-private/store/raw/journal/``.
* A page is marked in the manifest **only after** the ingest batch POST
  succeeded — a failed POST leaves the page unmarked so the next run retries it.
* Blank pages are recorded (``blank=True``, no artifact) so they are not
  re-OCR'd every run — the journal lane stays free of blanks.
* ``dry_run`` does everything except the OCR call and the POST (pull + hash
  still happen so the manifest gets real fingerprints).
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from pmbrs.core.artifact import Artifact

from .adb import AdbClient, AdbError, BooxCollector, PngFile
from .artifact import build_page_artifact
from .manifest import BooxSyncManifest, NoteRecord, PageRecord
from .ocr.engine import OcrEngine
from .page import NoteDir, PageRef


@dataclass
class RunSummary:
    dry_run: bool = False
    notes_total: int = 0
    pages_total: int = 0
    pages_new_ocr: int = 0
    artifacts_ingested: int = 0
    blank_pages: int = 0
    failed_pages: int = 0
    ingest_accepted: int = -1  # -1 => no ingest attempted (dry run)
    ingest_stored: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed_ms: int = 0

    def to_dict(self) -> dict:
        return {
            "dryRun": self.dry_run,
            "notesTotal": self.notes_total,
            "pagesTotal": self.pages_total,
            "pagesNewOcr": self.pages_new_ocr,
            "artifactsIngested": self.artifacts_ingested,
            "blankPages": self.blank_pages,
            "failedPages": self.failed_pages,
            "ingestAccepted": self.ingest_accepted,
            "ingestStored": self.ingest_stored,
            "errors": self.errors,
            "elapsedMs": self.elapsed_ms,
        }

    def to_json(self) -> str:
        import json

        return json.dumps(self.to_dict(), indent=2)


class IngestClient:
    """Posts an artifact batch to the existing PMBRS sync endpoint."""

    def __init__(self, url: str, timeout_s: float = 60.0) -> None:
        self.url = url
        self.timeout_s = timeout_s

    def post_batch(self, artifacts: list[Artifact]) -> tuple[int, list[str]]:
        import json
        import urllib.request
        import urllib.error

        body = json.dumps({"artifacts": [a.to_dict() for a in artifacts]}).encode("utf-8")
        req = urllib.request.Request(self.url, data=body, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", "replace")[:300]
            raise RuntimeError(f"ingest HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"ingest unreachable at {self.url}: {exc.reason}") from exc
        return (int(data.get("accepted") or 0), list(data.get("storedFiles") or []))


_PAGE_REF_CACHE_KEY = "note_uuid"


def _resolve_page_ref(uuid: str, page_rec: PageRecord, png: PngFile) -> PageRef:
    return PageRef(
        note_uuid=uuid,
        page_id=page_rec.page_id,
        page_order=page_rec.page_order,
        png_rel=page_rec.png_rel_path,
        png_bytes=png.size_bytes,
        png_sha256=png.sha256,
        png_dims=tuple(png.dims),  # type: ignore[arg-type]
        source=page_rec.source,
    )


def _note_dir_for(uuid: str, mtime_ms: int) -> NoteDir:
    return NoteDir(
        note_uuid=uuid,
        remote_path=f"/storage/emulated/0/.ksync/document/{uuid}",
        mtime_ms=mtime_ms,
    )


class BooxProducer:
    """One scheduled / manual sync pass over the BoOX note store."""

    def __init__(
        self,
        collector: BooxCollector,
        engine: OcrEngine,
        ingest: IngestClient,
        manifest: BooxSyncManifest,
        workdir: Path,
        *,
        force: bool = False,
        dry_run: bool = False,
        max_notes: int | None = None,
        device_alias: str = "boox-noteair3",
        producer_version: str = "0.1",
        ocr_temperature: float = 0.1,
        ocr_model: str = "",
        ingest_url: str = "",
    ) -> None:
        self.collector = collector
        self.engine = engine
        self.ingest = ingest
        self.manifest = manifest
        self.workdir = Path(workdir)
        self.force = force
        self.dry_run = dry_run
        self.max_notes = max_notes
        self.device_alias = device_alias
        self.producer_version = producer_version
        self.ocr_temperature = ocr_temperature
        self.ocr_model = ocr_model or "unknown"
        self.ingest_url = ingest_url or ""

    # ------------------------------------------------------------------

    def run(self, note_uuids: Iterable[str] | None = None) -> RunSummary:
        started = time.monotonic()
        summary = RunSummary(dry_run=self.dry_run)

        uuids = list(note_uuids) if note_uuids is not None else self.collector.list_notes()
        if self.max_notes is not None and self.max_notes >= 0:
            uuids = uuids[: int(self.max_notes)]
        summary.notes_total = len(uuids)

        # (artifact, note_rec, page_rec) for pages that OCR'd OK and are awaiting ingest.
        pending: list[tuple[Artifact, NoteRecord, PageRecord]] = []
        # (note_rec, page_rec) for blank pages — committed ONLY if the run's
        # ingest batch succeeds, so a failed ingest leaves NOTHING marked
        # (blank and non-blank alike) for a clean full retry.
        blank_staging: list[tuple[NoteRecord, PageRecord]] = []

        for uuid in uuids:
            note_dir_mtime = 0 if self.dry_run else self._safe_mtime(uuid)
            pages = self.collector.resolve_pages(uuid)
            summary.pages_total += len(pages)

            note_rec = self.manifest.notes.get(uuid) or NoteRecord(note_uuid=uuid)
            note_rec.note_dir_mtime_ms = note_dir_mtime
            self.manifest.notes[uuid] = note_rec

            for page_id, remote_path, order in pages:
                self._process_page(
                    uuid=uuid,
                    page_id=page_id,
                    remote_path=remote_path,
                    order=order,
                    note_rec=note_rec,
                    pending=pending,
                    blank_staging=blank_staging,
                    summary=summary,
                )

        # Ingest everything that OCR'd successfully in a single batch.
        if pending and not self.dry_run:
            try:
                accepted, stored = self.ingest.post_batch([a for a, _, _ in pending])
                summary.ingest_accepted = accepted
                summary.ingest_stored = stored
                summary.artifacts_ingested = accepted
                for artifact, note_rec, page_rec in pending:
                    self._mark_page_success(note_rec, page_rec, artifact)
                # Commit blank-page records only after the ingest batch succeeded,
                # so a failed ingest leaves nothing marked (full clean retry).
                for note_rec, page_rec in blank_staging:
                    self._mark_blank(note_rec, page_rec)
            except RuntimeError as exc:
                summary.errors.append(f"INGEST-FAILED: {exc}")
                # Leave manifest untouched for these pages -> retried next run.
                summary.artifacts_ingested = 0
                blank_staging.clear()

        if not self.dry_run:
            self.manifest.last_run_ms = int(time.time() * 1000)
            self.manifest.save()

        summary.elapsed_ms = int((time.monotonic() - started) * 1000)
        return summary

    # ------------------------------------------------------------------

    def _safe_mtime(self, uuid: str) -> int:
        try:
            return self.collector.note_dir_mtime_ms(uuid)
        except AdbError:
            return 0

    def _process_page(
        self,
        *,
        uuid: str,
        page_id: str,
        remote_path: str,
        order: int,
        note_rec: NoteRecord,
        pending: list[tuple[Artifact, NoteRecord, PageRecord]],
        blank_staging: list[tuple[NoteRecord, PageRecord]],
        summary: RunSummary,
    ) -> None:
        # 1. Pull + fingerprint.
        try:
            png = self.collector.pull_page(page_id, remote_path, self.workdir)
        except AdbError as exc:
            summary.failed_pages += 1
            summary.errors.append(f"pull {uuid}/{page_id}: {exc}")
            return

        page_rec = self._upsert_page(note_rec, page_id, order, remote_path, png)

        # 2. Manifest idempotency check (skip work if unchanged & already handled).
        if not self.dry_run and not self.manifest.needs_ocr(uuid, page_id, png.sha256, force=self.force):
            return

        # 3. OCR (skipped entirely under dry_run; we still persisted the hash above).
        #    Catch *any* error (including TimeoutError / JSON errors) so one
        #    bad page can never abort the rest of the batch.
        if self.dry_run:
            return
        try:
            result = self.engine.transcribe_page(png.local_path.read_bytes())
        except Exception as exc:  # noqa: BLE001 — deliberate: per-page isolation
            summary.failed_pages += 1
            summary.errors.append(f"ocr {uuid}/{page_id}: {type(exc).__name__}: {exc}")
            return

        # 4. Blank page: stage for commit (no artifact). Not written yet — the
        #    commit happens only after the run's ingest batch succeeds.
        if result.is_blank:
            summary.blank_pages += 1
            page_rec.blank = True  # in-memory flag; persisted at run end if ingest OK
            blank_staging.append((note_rec, page_rec))
            return

        # 5. Build artifact (held for batch ingest at the end of the run).
        summary.pages_new_ocr += 1
        artifact = build_page_artifact(
            page=_resolve_page_ref(uuid, page_rec, png),
            note_dir=_note_dir_for(uuid, note_rec.note_dir_mtime_ms),
            ocr_text=result.text,
            engine_name=self.engine.name,
            ocr_model=self.ocr_model,
            ocr_temperature=self.ocr_temperature,
            transport=self._transport_name(),
            adb_serial=self._adb_serial(),
            device_alias=self.device_alias,
            producer_version=self.producer_version,
            captured_at_ms=note_rec.note_dir_mtime_ms,
            transcribed_at_ms=int(time.time() * 1000),
            ocr_latency_ms=result.latency_ms,
            ingest_url=self.ingest_url,
        )
        pending.append((artifact, note_rec, page_rec))

    # -- manifest helpers -------------------------------------------------

    @staticmethod
    def _upsert_page(
        note_rec: NoteRecord,
        page_id: str,
        order: int,
        remote_path: str,
        png: PngFile,
    ) -> PageRecord:
        """Return the PageRecord for this page, updating it in note_rec.pages."""
        for p in note_rec.pages:
            if p.page_id == page_id:
                p.page_order = order
                p.png_rel_path = remote_path
                p.png_sha256 = png.sha256
                p.png_dims = tuple(png.dims)  # type: ignore[arg-type]
                return p
        new = PageRecord(
            page_id=page_id,
            page_order=order,
            source="cover",
            png_rel_path=remote_path,
            png_sha256=png.sha256,
            png_dims=tuple(png.dims),  # type: ignore[arg-type]
        )
        note_rec.pages.append(new)
        return new

    def _mark_blank(self, note_rec: NoteRecord, page_rec: PageRecord) -> None:
        now_ms = int(time.time() * 1000)
        page_rec.blank = True
        page_rec.last_ocr_at_ms = now_ms
        page_rec.last_ocr_engine = self.engine.name
        page_rec.last_artifact_id = ""
        if page_rec not in note_rec.pages:
            note_rec.pages.append(page_rec)

    def _mark_page_success(self, note_rec: NoteRecord, page_rec: PageRecord, artifact: Artifact) -> None:
        now_ms = int(time.time() * 1000)
        page_rec.blank = False
        page_rec.last_ocr_at_ms = now_ms
        page_rec.last_ocr_engine = self.engine.name
        page_rec.last_artifact_id = artifact.artifact_id
        if page_rec not in note_rec.pages:
            note_rec.pages.append(page_rec)

    def _transport_name(self) -> str:
        """Which collector transport this run uses (artifact provenance, ADR-020 D5)."""
        return getattr(self.collector, "transport_name", "adb")

    def _adb_serial(self) -> str:
        try:
            return self.collector.adb.serial  # type: ignore[attribute]
        except AttributeError:
            return ""


__all__ = [
    "BooxProducer",
    "IngestClient",
    "RunSummary",
]
