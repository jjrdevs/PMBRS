"""pmbrs.ingestion.boox — BoOX Note → PMBRS journal producer (ADR-019).

Layout
------
page.py      – PageRef / NoteDir data types
ocr/         – OcrEngine protocol + OllamaEngine (local qwen3.8:27b)
manifest.py  – BooxSyncManifest (idempotency across runs)
artifact.py  – build_page_artifact() (canonical 9-key journal artifact)
producer.py  – BooxProducer (pure logic: OCR → artifact → POST → manifest)
adb.py       – AdbClient / BooxCollector (device file operations)
"""
