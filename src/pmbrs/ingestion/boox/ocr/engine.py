"""OCR engine slot — protocol, result types, and the Ollama implementation.

The slot is deliberately narrow: one method (``transcribe_page``) that takes a
PNG and returns a normalized :class:`OcrResult`. This keeps the rest of the
pipeline (producer, manifest, artifact builders) engine-agnostic, so the
handwriting-specific model the user flagged as future work is a config change,
not a code change (ADR-019 D3).
"""
from __future__ import annotations

import base64
import json
import urllib.request
import urllib.error
import dataclasses
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

PROMPT_VERSION = "v1.0"

DEFAULT_PROMPT = (
    "You are transcribing a handwritten note for archival. "
    "Transcribe ALL text exactly as written, preserving line and paragraph "
    "structure. Do not correct spelling. If a word is genuinely uncertain, "
    "wrap it in brackets, e.g. [word?]. If the page is blank (no writing at "
    "all), respond with the single word BLANK. Do not add commentary, "
    "preamble, or markdown."
)


@dataclass(frozen=True)
class OcrResult:
    text: str
    is_blank: bool
    latency_ms: int
    engine_name: str


@runtime_checkable
class OcrEngine(Protocol):
    """Engine-agnostic OCR interface.

    Implementations must be synchronous (the producer is sync-first) and
    idempotent on the same input.
    """

    @property
    def name(self) -> str: ...

    def transcribe_page(self, png_bytes: bytes, prompt: str | None = None) -> OcrResult: ...


class OllamaEngine:
    """Local Ollama OCR client (default: qwen3.8:27b with vision).

    Uses the Ollama ``/api/generate`` endpoint with base64-embedded images —
    no extra dependencies, stdlib ``urllib`` only.

    Notes
    -----
    - Only vision-capable Qwen 3.8 models work; Qwen 3.6 entries (``my-qwen-*``)
      expose ``completion`` only and will return an error here. Callers should
      pick a model that reports the ``vision`` capability in ``/api/tags``.
    - ``base_url`` is localhost by default; override for LAN Ollama hosts.
    """

    def __init__(
        self,
        base_url: str = "http://127.0.0.1:11434",
        model: str = "qwen3.8:27b",
        *,
        temperature: float = 0.1,
        max_tokens: int = 4096,
        timeout_s: float = 300.0,
        retries: int = 2,
        retry_backoff_s: float = 2.0,
        prompt: str = DEFAULT_PROMPT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.timeout_s = timeout_s
        self.retries = max(0, int(retries))
        self.retry_backoff_s = retry_backoff_s
        self.prompt = prompt

    @property
    def name(self) -> str:
        return f"ollama:{self.model}"

    def transcribe_page(self, png_bytes: bytes, prompt: str | None = None) -> OcrResult:
        import time

        started = time.monotonic()
        images_b64 = [base64.b64encode(png_bytes).decode("latin-1")]
        body = {
            "model": self.model,
            "prompt": prompt or self.prompt,
            "images": images_b64,
            "stream": False,
            "think": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_tokens,
            },
        }
        data = json.dumps(body).encode("utf-8")
        last_err = None
        for attempt in range(self.retries + 1):
            req = urllib.request.Request(
                f"{self.base_url}/api/generate",
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                    payload = json.loads(resp.read().decode("utf-8"))
                text = (payload.get("response") or "").strip()
                latency_ms = int((time.monotonic() - started) * 1000)
                is_blank = text.upper().replace(" ", "") in {"", "BLANK"}
                return OcrResult(
                    text="" if is_blank else text,
                    is_blank=is_blank,
                    latency_ms=latency_ms,
                    engine_name=self.name,
                )
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", "replace")[:300]
                last_err = RuntimeError(f"Ollama HTTP {exc.code}: {detail}")
            except urllib.error.URLError as exc:
                last_err = RuntimeError(f"Ollama unreachable at {self.base_url}: {exc.reason}")
            except TimeoutError as exc:  # socket read timeout (NOT a URLError)
                last_err = RuntimeError(f"Ollama OCR timed out after {self.timeout_s}s on attempt {attempt + 1}")
            if attempt < self.retries:
                time.sleep(self.retry_backoff_s * (attempt + 1))
        raise last_err


__all__ = [
    "PROMPT_VERSION",
    "DEFAULT_PROMPT",
    "OcrResult",
    "OcrEngine",
    "OllamaEngine",
]
