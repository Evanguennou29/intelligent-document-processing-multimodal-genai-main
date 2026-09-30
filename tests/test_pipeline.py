"""End-to-end pipeline behaviour with fake OCR and fake LLM."""

from __future__ import annotations

import json
from pathlib import Path

from idp.pipeline import Pipeline
from idp.schemas import DocumentType, Invoice


def build_pipeline(settings, fake_ocr, fake_extractor, **kwargs) -> Pipeline:
    return Pipeline(
        provider="ollama",
        settings=settings,
        ocr=fake_ocr,
        extractor=fake_extractor,
        **kwargs,
    )


def test_process_returns_a_validated_document(settings, fake_ocr, fake_extractor, image_file) -> None:
    pipeline = build_pipeline(settings, fake_ocr, fake_extractor)
    result = pipeline.process(image_file)

    assert isinstance(result.document, Invoice)
    assert result.document.invoice_number == "INV-2024-001"
    assert result.document.date == "2024-03-12"  # normalised by the validator
    assert result.meta.provider == "ollama"
    assert result.meta.ocr_engine == "fake-ocr"
    assert result.meta.extraction_model == "fake-model"


def test_process_and_save_writes_json_with_meta(settings, fake_ocr, fake_extractor, image_file) -> None:
    pipeline = build_pipeline(settings, fake_ocr, fake_extractor)
    output = pipeline.process_and_save(image_file, out_dir=settings.data_processed_dir)

    payload = json.loads(Path(output).read_text(encoding="utf-8"))
    assert payload["invoice_number"] == "INV-2024-001"
    assert payload["_meta"]["provider"] == "ollama"
    assert Path(output).name == "invoice_2024.json"


def test_to_dict_is_flat_and_serialisable(settings, fake_ocr, fake_extractor, image_file) -> None:
    payload = build_pipeline(settings, fake_ocr, fake_extractor).process(image_file).to_dict()
    json.dumps(payload)  # must not raise
    assert set(payload) & {"invoice_number", "document_type"}
    assert "_meta" in payload


def test_cache_short_circuits_second_run(settings, image_file) -> None:
    from conftest import FakeExtractor, FakeOcr

    cached_settings = settings.__class__(**{**settings.__dict__, "use_cache": True})
    ocr = FakeOcr()
    extractor = FakeExtractor()
    pipeline = Pipeline(
        provider="ollama", settings=cached_settings, ocr=ocr, extractor=extractor, use_cache=True
    )

    first = pipeline.process(image_file)
    second = pipeline.process(image_file)

    assert first.meta.from_cache is False
    assert second.meta.from_cache is True
    assert ocr.calls == 1
    assert extractor.calls == 1


def test_unsupported_extension_is_rejected(settings, fake_ocr, fake_extractor, tmp_path) -> None:
    import pytest

    from idp.errors import UnsupportedFileError

    target = tmp_path / "notes.txt"
    target.write_text("hello", encoding="utf-8")
    pipeline = build_pipeline(settings, fake_ocr, fake_extractor)

    with pytest.raises(UnsupportedFileError):
        pipeline.process_all(target)


def test_health_reports_both_engines(settings, fake_ocr, fake_extractor) -> None:
    health = build_pipeline(settings, fake_ocr, fake_extractor).health()
    assert health["ocr"]["ok"] is True
    assert health["extractor"]["ok"] is True


def test_document_type_can_be_forced(settings, fake_ocr, fake_extractor, image_file) -> None:
    from conftest import FakeExtractor, FakeOcr

    extractor = FakeExtractor({"passport_number": "X123", "full_name": "Jane Doe"})
    pipeline = build_pipeline(settings, FakeOcr(), extractor)

    result = pipeline.process(image_file, doc_type=DocumentType.PASSPORT)
    assert result.meta.document_type == "passport"
    assert result.document.passport_number == "X123"
