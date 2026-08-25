"""Shape tests for the BoOX journal artifact (ADR-019 D4)."""
from __future__ import annotations

import unittest

from pmbrs.core.artifact import strict_validate
from pmbrs.ingestion.boox.artifact import build_page_artifact
from pmbrs.ingestion.boox.page import NoteDir, PageRef


def _fixture() -> tuple[PageRef, NoteDir, dict]:
    page_ref = PageRef(
        note_uuid="abcdef0123456789abcdef0123456789",
        page_id="abcdef0123456789abcdef0123456789",
        page_order=1,
        png_rel=".noteCache/thumbnail/abc.png",
        png_bytes=42000,
        png_sha256="deadbeef1234",
        png_dims=(499, 666),
        source="cover",
    )
    note_dir = NoteDir(
        note_uuid="abcdef0123456789abcdef0123456789",
        remote_path="/storage/emulated/0/.ksync/document/abcdef0123456789abcdef0123456789",
        mtime_ms=1747680000000,
    )
    kwargs = dict(
        page=page_ref,
        note_dir=note_dir,
        ocr_text="hello world",
        engine_name="ollama:qwen3.8:27b",
        ocr_model="qwen3.8:27b",
        ocr_temperature=0.1,
        transport="adb",
        adb_serial="4EF2D7E9",
        captured_at_ms=1747680000000,
        transcribed_at_ms=1747680001000,
        ocr_latency_ms=350,
        ingest_url="http://127.0.0.1:8765/api/v1/artifacts/sync",
    )
    return page_ref, note_dir, kwargs


class BooxPageArtifactTest(unittest.TestCase):
    def test_artifact_is_canonical_and_validates(self):
        page_rec, note_dir, kwargs = _fixture()
        artifact = build_page_artifact(**kwargs)
        self.assertEqual(strict_validate(artifact.to_dict()), [])
        d = artifact.to_dict()
        self.assertEqual(d["artifactId"], "boox.abcdef0123456789abcdef0123456789.p1")
        self.assertEqual(d["source"], "journal")
        payload = artifact.payload
        self.assertEqual(payload["modality"], "journal")
        self.assertEqual(payload["artifactKind"], "handwritten_note_page")
        self.assertEqual(payload["ocrText"], "hello world")
        self.assertEqual(payload["ocrEngine"], "ollama:qwen3.8:27b")
        self.assertEqual(payload["ocrModel"], "qwen3.8:27b")
        self.assertEqual(payload["pageImage"]["sha256"], "deadbeef1234")
        self.assertEqual(payload["pageImage"]["dimensions"], [499, 666])
        self.assertEqual(payload["pageImage"]["bytes"], 42000)
        prov = artifact.provenance_metadata_json
        self.assertEqual(prov["transport"], "adb")
        self.assertEqual(prov["adb_serial"], "4EF2D7E9")
        self.assertEqual(prov["producer"], "pmbrs-boox-producer")
        self.assertEqual(prov["ocr_engine_impl"], "OllamaEngine")


if __name__ == "__main__":
    unittest.main()
