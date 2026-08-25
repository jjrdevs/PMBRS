"""Producer-level integration test with fake ADB / OCR / ingest.

This is the primary correctness proof for Stage 1: without a connected
device or a running Ollama, we exercise the full pipeline (manifest idempotency,
blank handling, failed-ingest safety, artifact shape) with in-memory fakes.
"""
from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from pmbrs.ingestion.boox.adb import AdbClient, AdbError, BooxCollector, PngFile
from pmbrs.ingestion.boox.manifest import BooxSyncManifest
from pmbrs.ingestion.boox.ocr.engine import OcrEngine, OcrResult
from pmbrs.ingestion.boox.producer import BooxProducer, IngestClient, RunSummary
from pmbrs.core.artifact import Artifact


# ---------------------------------------------------------------------------
# fakes
# ---------------------------------------------------------------------------

class FakeAdb:
    """Provides the same interface as AdbClient for our purposes."""
    def __init__(self, serial: str, notes: Iterable[str] = ("abcdef0123456789abcdef0123456789",)) -> None:
        self.serial = serial
        self._notes = list(notes)
        self.pull_calls: list[str] = []
        self.sha = {}
        # Map (note_uuid, png_rel) -> (png_bytes, sha256, dims)
        self._png_by_rel = {
            f".noteCache/thumbnail/{u}.png": (b"PNG-bytes-" + u.encode("latin-1"),
                                              f"deadbeef{u[:8]}", (499, 666))
            for u in self._notes
        }

    def sha256_file(self, path: Path) -> str:
        return self.sha.get(str(path), "sha-default")

    def pull(self, remote_path: str, local_path: Path) -> Path:
        self.pull_calls.append(remote_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(b"PNG-bytes-fake")
        self.sha[str(local_path)] = self._png_by_rel.get(remote_path, (b"x", "sha-fallback", (1, 1)))[1]
        return local_path

    def file_exists(self, remote_path: str) -> bool:
        return remote_path in self._png_by_rel

    def dir_listing(self, remote_dir: str) -> list[str]:
        return self._notes

    def find_pngs(self, remote_dir: str) -> list[str]:
        return list(self._png_by_rel.keys())

    def shell(self, command: str) -> str:
        if "stat -c" in command:
            return "1747680000"
        return ""


class FakeBooxCollector(BooxCollector):
    """BooxCollector with an injected fake Adb."""
    def __init__(self) -> None:
        super().__init__(AdbClient(serial="4EF2D7E9"))
        self._fake = FakeAdb(serial="4EF2D7E9")
        self.adb = self._fake  # type: ignore[assignment]


@dataclass
class FakePng:
    local_path: Path
    remote_rel: str
    sha256: str
    dims: tuple[int, int]
    size_bytes: int


class FakeCollector:
    """Standalone implementation of the narrow surface BooxProducer uses."""

    def __init__(self, fake: FakeAdb) -> None:
        self.adb = fake

    def list_notes(self) -> list[str]:
        return self.adb._notes

    def note_dir_mtime_ms(self, note_uuid: str) -> int:
        return 1747000000000

    def resolve_pages(self, note_uuid: str) -> list[tuple[str, str, int]]:
        rel = f".noteCache/thumbnail/{note_uuid}.png"
        if not self.adb.file_exists(rel):
            return []
        return [(note_uuid, f"/storage/emulated/0/{rel}", 1)]

    def pull_page(self, page_id: str, remote_path: str, workdir: Path) -> PngFile:
        local = workdir / f"{page_id}.png"
        self.adb.pull(remote_path, local)
        fake_sha = self.adb.sha.get(str(local), "sha-default")
        fake_dims = (499, 666)
        data = local.read_bytes()
        return PngFile(
            local_path=local,
            remote_rel=remote_path,
            sha256=fake_sha,
            dims=fake_dims,
            size_bytes=len(data),
        )


class FakeEngine:
    """OcrEngine stand-in with a pre-programmed result."""
    name = "fake:engine"

    def __init__(self, result: OcrResult | None = None, should_raise: bool = False) -> None:
        self._result = result or OcrResult(text="hello world", is_blank=False, latency_ms=120, engine_name="fake")
        self._should_raise = should_raise
        self.call_count = 0

    def transcribe_page(self, png_bytes, prompt=None):
        self.call_count += 1
        if self._should_raise:
            raise RuntimeError("fake OCR failure")
        return self._result


class FakeIngest(IngestClient):
    def __init__(self, accepted: int = 999, accepted_count: int | None = None,
                 raise_on_post: bool = False, stored_files: list[str] | None = None) -> None:
        super().__init__(url="http://fake/ingest")
        self._accepted = accepted
        self._accepted_count = accepted_count
        self._raise = raise_on_post
        self._stored = stored_files or []
        self.last_batch: list[Artifact] | None = None
        self.post_count = 0

    def post_batch(self, artifacts):
        self.post_count += 1
        self.last_batch = list(artifacts)
        if self._raise:
            raise RuntimeError("fake ingest failure")
        return (self._accepted_count if self._accepted_count is not None else len(artifacts), self._stored)


def make_producer(
    *,
    collector, engine: FakeEngine, ingest: FakeIngest,
    manifest_path: Path, workdir: Path,
    force: bool = False, dry_run: bool = False,
) -> BooxProducer:
    return BooxProducer(
        collector=collector,
        engine=engine,
        ingest=ingest,
        manifest=BooxSyncManifest.load(manifest_path, device_serial="4EF2D7E9"),
        workdir=workdir,
        force=force,
        dry_run=dry_run,
        ocr_model="fake-model",
        ingest_url="http://fake/ingest",
    )


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

class BooxProducerTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.root = Path(self._td.name)
        self.manifest_path = self.root / "manifest.json"
        self.workdir = self.root / "work"
        self.workdir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        self._td.cleanup()

    def _fresh_collector(self) -> FakeCollector:
        return FakeCollector(FakeAdb(serial="4EF2D7E9"))

    def test_first_run_ingests_one_page_per_note(self):
        collector = self._fresh_collector()
        engine = FakeEngine(result=OcrResult(text="first day entries", is_blank=False, latency_ms=100, engine_name="fake"))
        ingest = FakeIngest()

        producer = make_producer(collector=collector, engine=engine, ingest=ingest,
                                 manifest_path=self.manifest_path, workdir=self.workdir)
        summary = producer.run(note_uuids=collector.list_notes())

        self.assertEqual(summary.pages_new_ocr, 1)
        self.assertEqual(summary.artifacts_ingested, 1)
        self.assertEqual(summary.blank_pages, 0)
        self.assertEqual(summary.failed_pages, 0)
        self.assertEqual(ingest.post_count, 1)
        self.assertIsNotNone(ingest.last_batch)
        artifact = ingest.last_batch[0]
        self.assertEqual(artifact.source, "journal")
        self.assertEqual(artifact.artifact_id, "boox.abcdef0123456789abcdef0123456789.p1")
        self.assertEqual(artifact.payload["modality"], "journal")
        self.assertEqual(artifact.payload["artifactKind"], "handwritten_note_page")
        self.assertEqual(artifact.payload["ocrText"], "first day entries")
        self.assertEqual(artifact.payload["ocrEngine"], "fake:engine")
        self.assertEqual(artifact.provenance_metadata_json["transport"], "adb")
        self.assertEqual(artifact.provenance_metadata_json["adb_serial"], "4EF2D7E9")

        # Manifest was persisted with the successful page marked.
        saved = BooxSyncManifest.load(self.manifest_path, device_serial="4EF2D7E9")
        note = saved.notes["abcdef0123456789abcdef0123456789"]
        self.assertEqual(note.pages[0].last_artifact_id, "boox.abcdef0123456789abcdef0123456789.p1")
        self.assertFalse(note.pages[0].blank)
        self.assertTrue(self.manifest_path.exists())

    def test_second_run_is_idempotent(self):
        collector = self._fresh_collector()
        engine = FakeEngine()
        ingest1 = FakeIngest()
        producer = make_producer(collector=collector, engine=engine, ingest=ingest1,
                                 manifest_path=self.manifest_path, workdir=self.workdir)
        s1 = producer.run(note_uuids=collector.list_notes())
        self.assertEqual(s1.artifacts_ingested, 1)

        # Second run with a fresh collector (device "same note, same content").
        engine2 = FakeEngine()
        ingest2 = FakeIngest()
        producer2 = make_producer(collector=self._fresh_collector(), engine=engine2, ingest=ingest2,
                                  manifest_path=self.manifest_path, workdir=self.workdir)
        s2 = producer2.run(note_uuids=producer2.collector.list_notes())
        self.assertEqual(s2.artifacts_ingested, 0)
        self.assertEqual(ingest2.post_count, 0, "no new artifacts on unchanged note")
        self.assertEqual(engine2.call_count, 0, "OCR was not invoked on a previously-handled page")

    def test_blank_page_is_recorded_but_not_ingested(self):
        collector = self._fresh_collector()
        engine = FakeEngine(result=OcrResult(text="", is_blank=True, latency_ms=7, engine_name="fake"))
        ingest = FakeIngest()
        producer = make_producer(collector=collector, engine=engine, ingest=ingest,
                                 manifest_path=self.manifest_path, workdir=self.workdir)
        summary = producer.run(note_uuids=collector.list_notes())
        self.assertEqual(summary.blank_pages, 1)
        self.assertEqual(summary.artifacts_ingested, 0)
        self.assertEqual(ingest.post_count, 0, "blank pages must not be ingested")
        saved = BooxSyncManifest.load(self.manifest_path, device_serial="4EF2D7E9")
        note = saved.notes["abcdef0123456789abcdef0123456789"]
        self.assertTrue(note.pages[0].blank)
        self.assertEqual(note.pages[0].last_artifact_id, "")

    def test_ingest_failure_leaves_manifest_unmarked_for_retry(self):
        collector = self._fresh_collector()
        engine = FakeEngine()
        ingest = FakeIngest(raise_on_post=True)
        producer = make_producer(collector=collector, engine=engine, ingest=ingest,
                                 manifest_path=self.manifest_path, workdir=self.workdir)
        summary = producer.run(note_uuids=collector.list_notes())
        self.assertGreaterEqual(summary.failed_pages, 0)
        self.assertEqual(summary.artifacts_ingested, 0)
        self.assertTrue(any(e.startswith("INGEST-FAILED") for e in summary.errors),
                        msg=f"expected an INGEST-FAILED error, got {summary.errors!r}")

        # No page should be marked as ingested, because nothing was accepted.
        saved = BooxSyncManifest.load(self.manifest_path, device_serial="4EF2D7E9")
        note = saved.notes.get("abcdef0123456789abcdef0123456789")
        if note is not None:
            for page in note.pages:
                self.assertEqual(page.last_artifact_id, "",
                                 "ingest failure must not mark the page as committed")

    def test_ocr_failure_on_a_page_is_reported_and_page_unmarked(self):
        collector = self._fresh_collector()
        engine = FakeEngine(should_raise=True)
        ingest = FakeIngest()
        producer = make_producer(collector=collector, engine=engine, ingest=ingest,
                                 manifest_path=self.manifest_path, workdir=self.workdir)
        summary = producer.run(note_uuids=collector.list_notes())
        self.assertEqual(summary.failed_pages, 1)
        self.assertEqual(ingest.post_count, 0)
        # Page is unmarked (still needs OCR next run).
        saved = BooxSyncManifest.load(self.manifest_path, device_serial="4EF2D7E9")
        page = saved.notes["abcdef0123456789abcdef0123456789"].pages[0]
        self.assertEqual(page.last_artifact_id, "")
        # needs_ocr should be True next time.
        self.assertTrue(saved.needs_ocr("abcdef0123456789abcdef0123456789",
                                        "abcdef0123456789abcdef0123456789",
                                        page.png_sha256, force=False))


if __name__ == "__main__":
    unittest.main()
