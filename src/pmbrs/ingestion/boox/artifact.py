"""Build the canonical 9-key PMBRS raw artifact for one BoOX note page.

Uses ``pmbrs.core.artifact.Artifact`` so this module stays consistent with the
existing raw-record contract (ADR-017 D2). The producer POSTs this via the
existing ingest endpoint (``POST /api/v1/artifacts/sync``) — we do not write to
the raw store directly (the ingest server is the sole writer).
"""
from __future__ import annotations

import time
from typing import Any

from pmbrs.core.artifact import Artifact

from .ocr.engine import PROMPT_VERSION
from .page import NoteDir, PageRef


def build_page_artifact(
    *,
    page: PageRef,
    note_dir: NoteDir,
    ocr_text: str,
    engine_name: str,
    ocr_model: str,
    ocr_temperature: float,
    transport: str = "adb",
    adb_serial: str = "",
    device_alias: str = "boox-noteair3",
    producer_version: str = "0.1",
    captured_at_ms: int = 0,
    transcribed_at_ms: int = 0,
    ocr_latency_ms: int = 0,
    ingest_url: str = "",
) -> Artifact:
    """Construct the journal artifact for one OCR'd page."""
    artifact_id = f"boox.{page.note_uuid}.p{page.page_order}"
    payload: dict[str, Any] = {
        "kind": "journal",
        "modality": "journal",
        "artifactKind": "handwritten_note_page",
        "noteUuid": page.note_uuid,
        "pageOrder": page.page_order,
        "ocrText": ocr_text,
        "ocrEngine": engine_name,
        "ocrModel": ocr_model,
        "ocrPromptVersion": PROMPT_VERSION,
        "pageImage": {
            "sourcePath": page.png_rel,
            "source": page.source,
            "sha256": page.png_sha256,
            "dimensions": list(page.png_dims),
            "bytes": page.png_bytes,
        },
        "deviceAlias": device_alias,
        "capturedAtMs": captured_at_ms,
        "transcribedAtMs": transcribed_at_ms,
    }

    provenance: dict[str, Any] = {
        "producer": "pmbrs-boox-producer",
        "producer_version": producer_version,
        "transport": transport,
        "adb_serial": adb_serial,
        "note_dir": note_dir.remote_path,
        "ocr_engine_impl": "OllamaEngine",
        "ocr_model": ocr_model,
        "ocr_temperature": ocr_temperature,
        "ocr_prompt_version": PROMPT_VERSION,
        "ocr_latency_ms": ocr_latency_ms,
        "ingest_endpoint": ingest_url or "(local)",
        "lineage": {
            "derived_from": f"boox.device.note:{page.note_uuid}",
            "derivation": "llm_vision_ocr",
        },
    }

    return Artifact(
        artifact_id=artifact_id,
        source="journal",
        payload=payload,
        created_at_epoch_ms=int(captured_at_ms) or int(transcribed_at_ms) or int(time.time() * 1000),
        schema_version="1.0",
        device_alias=device_alias,
        provenance_metadata_json=provenance,
        ingested_at_epoch_ms=0,  # server stamps on ingest
        ingest_status="pending",
    )


__all__ = ["build_page_artifact"]
