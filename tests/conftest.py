"""Shared pytest fixtures.

The tests never touch the network: OCR and LLM calls are replaced by fakes.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from idp.config import Settings  # noqa: E402
from idp.ocr.base import OcrEngine, OcrResult  # noqa: E402


@pytest.fixture()
def settings(tmp_path: Path) -> Settings:
    """A Settings object pointing every writable folder at tmp_path."""
    return Settings(
        provider="ollama",
        data_raw_dir=tmp_path / "raw",
        data_processed_dir=tmp_path / "processed",
        cache_dir=tmp_path / "cache",
        use_cache=False,
        max_retries=1,
        retry_backoff_s=0.0,
    )


@pytest.fixture()
def image_file(tmp_path: Path) -> Path:
    """A tiny placeholder standing in for a scanned document."""
    target = tmp_path / "invoice_2024.png"
    target.write_bytes(b"\x89PNG\r\n\x1a\nfake-bytes")
    return target


class FakeOcr(OcrEngine):
    """Return a canned transcription without reading the file."""

    name = "fake-ocr"

    def __init__(self, text: str = "Invoice number: INV-2024-001\nTotal: 120.00 EUR") -> None:
        self.text = text
        self.calls = 0

    def extract(self, image_path: str) -> OcrResult:
        self.calls += 1
        return OcrResult(text=self.text, engine=self.name, duration_ms=1)


class FakeExtractor:
    """Return a canned document without calling any model."""

    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload or {
            "invoice_number": "INV-2024-001",
            "date": "12/03/2024",
            "seller_name": "ACME",
            "total_amount": 120.0,
        }
        self.calls = 0

    @property
    def model_name(self) -> str:
        return "fake-model"

    def available(self) -> tuple[bool, str]:
        return True, "ok"

    def extract(self, ocr_text: str, doc_type):
        from idp.schemas import get_schema_model

        self.calls += 1
        return get_schema_model(doc_type)(**self.payload)


@pytest.fixture()
def fake_ocr() -> FakeOcr:
    return FakeOcr()


@pytest.fixture()
def fake_extractor() -> FakeExtractor:
    return FakeExtractor()