import json
import tempfile
import unittest
from pathlib import Path

from pmbrs.ingestion.boox.manifest import (
    BooxSyncManifest,
    NoteRecord,
    PageRecord,
)


class BooxSyncManifestTest(unittest.TestCase):
    def test_first_load_returns_empty_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            m = BooxSyncManifest.load(path, device_serial="serial-x")
            self.assertEqual(m.notes, {})
            self.assertEqual(m.device_serial, "serial-x")
            self.assertEqual(m.last_run_ms, 0)
            self.assertFalse(path.exists())

    def test_save_then_load_round_trips_pages(self):
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "manifest.json"
            m = BooxSyncManifest.load(path, device_serial="serial-x")
            note = NoteRecord(note_uuid="abcdef0123456789abcdef0123456789")
            note.note_dir_mtime_ms = 1234567890123
            page = PageRecord(
                page_id="abcdef0123456789abcdef0123456789",
                page_order=1,
                source="cover",
                png_rel_path="/storage/emulated/0/.noteCache/thumbnail/x.png",
                png_sha256="deadbeef",
                png_dims=(499, 666),
                last_ocr_at_ms=1234,
                last_ocr_engine="ollama:qwen3.8:27b",
                last_artifact_id="boox.abcdef.p1",
            )
            note.pages.append(page)
            m.notes["abcdef0123456789abcdef0123456789"] = note
            m.last_run_ms = 1234567890123
            m.save()

            re_loaded = BooxSyncManifest.load(path, device_serial="serial-x")
            self.assertEqual(set(re_loaded.notes), {"abcdef0123456789abcdef0123456789"})
            self.assertEqual(re_loaded.last_run_ms, 1234567890123)
            rec = re_loaded.notes["abcdef0123456789abcdef0123456789"]
            self.assertEqual(rec.pages[0].page_id, "abcdef0123456789abcdef0123456789")
            self.assertEqual(rec.pages[0].png_dims, (499, 666))
            self.assertEqual(rec.pages[0].last_ocr_engine, "ollama:qwen3.8:27b")
            self.assertEqual(rec.pages[0].last_artifact_id, "boox.abcdef.p1")

    def test_needs_ocr_is_true_for_new_page(self):
        with tempfile.TemporaryDirectory() as td:
            m = BooxSyncManifest.load(Path(td) / "manifest.json", device_serial="s")
            self.assertTrue(m.needs_ocr("uuid-a", "page-1", "sha256-new", force=False))
            self.assertTrue(m.needs_ocr("uuid-a", "page-1", "sha256-any", force=True))

    def test_needs_ocr_is_false_for_unchanged_handled_page(self):
        with tempfile.TemporaryDirectory() as td:
            m = BooxSyncManifest.load(Path(td) / "manifest.json", device_serial="s")
            note = NoteRecord(note_uuid="uuid-a")
            page = PageRecord(
                page_id="page-1", page_order=1, source="cover",
                png_rel_path=".noteCache/thumbnail/x.png",
                png_sha256="sha256-A", png_dims=(499, 666),
                last_ocr_at_ms=1234, last_ocr_engine="e", last_artifact_id="boox.x.p1",
            )
            page.blank = False
            note.pages.append(page)
            m.notes["uuid-a"] = note
            self.assertFalse(m.needs_ocr("uuid-a", "page-1", "sha256-A", force=False))
            # Force overrides.
            self.assertTrue(m.needs_ocr("uuid-a", "page-1", "sha256-A", force=True))
            # Changed png => re-ocr.
            self.assertTrue(m.needs_ocr("uuid-a", "page-1", "sha256-B", force=False))

    def test_needs_ocr_is_true_when_prior_run_failed_to_ocr(self):
        with tempfile.TemporaryDirectory() as td:
            m = BooxSyncManifest.load(Path(td) / "manifest.json", device_serial="s")
            note = NoteRecord(note_uuid="uuid-a")
            page = PageRecord(
                page_id="page-1", page_order=1, source="cover",
                png_rel_path=".noteCache/x.png",
                png_sha256="sha256-A", png_dims=(499, 666),
                last_ocr_at_ms=1234, last_ocr_engine="e", last_artifact_id="",
            )
            page.blank = False
            note.pages.append(page)
            m.notes["uuid-a"] = note
            # Same hash, blank=False, but no artifact recorded -> previous attempt failed.
            self.assertTrue(m.needs_ocr("uuid-a", "page-1", "sha256-A", force=False))


if __name__ == "__main__":
    unittest.main()
