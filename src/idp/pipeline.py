"""End-to-end orchestration: file -> OCR -> LLM -> validated JSON.

The pipeline is deliberately dependency-injectable (``ocr`` / ``extractor``
arguments) which is what makes it testable without any network call.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from pathlib import Path

from pydantic import BaseModel

from idp.config import Settings, get_settings
from idp.errors import UnsupportedFileError
from idp.extraction import LlmExtractor
from idp.logging_utils import get_logger
from idp.ocr import OcrEngine, get_ocr_engine
from idp.pdf import is_pdf, is_supported, rasterise_pdf
from idp.routing import route
from idp.schemas import DocumentType, ExtractionMeta, get_schema_model
from idp.validation import validate_and_warn

logger = get_logger(__name__)


@dataclass
class DocumentResult:
    """A validated document plus its provenance metadata."""

    document: BaseModel
    meta: ExtractionMeta

    def to_dict(self) -> dict:
        """Flat payload: document fields + ``_meta`` (backward compatible)."""
        payload = self.document.model_dump()
        payload["_meta"] = self.meta.model_dump()
        return payload

    @classmethod
    def from_payload(cls, payload: dict) -> "DocumentResult":
        data = dict(payload)
        meta_data = data.pop("_meta", None) or {}
        known = {key: value for key, value in meta_data.items() if key in ExtractionMeta.model_fields}
        meta = ExtractionMeta(**known)
        model = get_schema_model(meta.document_type or data.get("document_type"))
        return cls(document=model(**data), meta=meta)


class Pipeline:
    """Run the full extraction chain for one provider."""

    def __init__(
        self,
        provider: str | None = None,
        settings: Settings | None = None,
        ocr: OcrEngine | None = None,
        extractor: LlmExtractor | None = None,
        use_cache: bool | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.provider = (provider or self.settings.provider).lower()
        self.ocr = ocr or get_ocr_engine(self.provider, self.settings)
        self.extractor = extractor or LlmExtractor(self.provider, self.settings)
        self.use_cache = self.settings.use_cache if use_cache is None else use_cache

    # ------------------------------------------------------------------ Info --
    def health(self) -> dict[str, dict]:
        """Non-destructive capability report used by the CLI and the web UI."""
        ocr_ok, ocr_reason = self.ocr.available()
        extractor_ok, extractor_reason = self.extractor.available()
        return {
            "provider": {"ok": True, "detail": self.provider},
            "ocr": {"ok": ocr_ok, "detail": ocr_reason, "engine": getattr(self.ocr, "name", "?")},
            "extractor": {
                "ok": extractor_ok,
                "detail": extractor_reason,
                "model": self.extractor.model_name,
            },
        }

    # --------------------------------------------------------------- Caching --
    def _cache_key(self, path: Path, doc_type: DocumentType | None) -> str:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        label = doc_type.value if doc_type else "auto"
        return hashlib.sha256(f"{digest}|{self.provider}|{label}".encode()).hexdigest()

    def _cache_path(self, key: str) -> Path:
        return self.settings.cache_dir / f"{key}.json"

    def _cache_read(self, key: str) -> dict | None:
        target = self._cache_path(key)
        if not target.exists():
            return None
        try:
            return json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None

    def _cache_write(self, key: str, payload: dict) -> None:
        try:
            target = self._cache_path(key)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
        except OSError as exc:  # a read-only cache must never break a run
            logger.warning("Cache non inscriptible (%s) : %s", self._cache_path(key), exc)

    # ------------------------------------------------------------ Processing --
    def process(self, image_path: str | Path, doc_type: DocumentType | str | None = None) -> DocumentResult:
        """Process one file. A PDF is handled page by page; the first page is returned."""
        if is_pdf(image_path):
            results = self.process_all(image_path, doc_type=doc_type)
            return results[0]
        return self._process_image(Path(image_path), doc_type=doc_type)

    def process_all(
        self,
        image_path: str | Path,
        doc_type: DocumentType | str | None = None,
    ) -> list[DocumentResult]:
        """Process every page of a PDF, or the single image given."""
        path = Path(image_path)
        if not path.exists():
            raise UnsupportedFileError(f"Fichier introuvable : {path}")
        if not is_supported(path):
            raise UnsupportedFileError(
                f"Format non supporte : {path.suffix or '(sans extension)'}. "
                "Formats acceptes : PNG, JPG, JPEG, WEBP, TIFF, PDF."
            )

        if not is_pdf(path):
            return [self._process_image(path, doc_type=doc_type)]

        pages = rasterise_pdf(
            path,
            self.settings.cache_dir / "pdf",
            dpi=self.settings.pdf_dpi,
            max_pages=self.settings.pdf_max_pages,
        )
        return [
            self._process_image(page, doc_type=doc_type, page_number=index + 1, source_name=path.name)
            for index, page in enumerate(pages)
        ]

    def process_and_save(
        self,
        image_path: str | Path,
        out_dir: str | Path | None = None,
    ) -> str:
        """Process a file and write its JSON. Returns the path of the first output."""
        return self.process_and_save_all(image_path, out_dir)[0]

    def process_and_save_all(
        self,
        image_path: str | Path,
        out_dir: str | Path | None = None,
    ) -> list[str]:
        """Process a file and write one JSON per page. Returns every written path."""
        source = Path(image_path)
        target_dir = Path(out_dir) if out_dir else self.settings.data_processed_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        written: list[str] = []
        for result in self.process_all(source):
            suffix = f"-p{result.meta.page}" if result.meta.page else ""
            out_path = target_dir / f"{source.stem}{suffix}.json"
            out_path.write_text(
                json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
            written.append(str(out_path))
            logger.info("Resultat ecrit : %s", out_path)
        return written

    # -------------------------------------------------------------- internal --
    def _process_image(
        self,
        image_path: Path,
        doc_type: DocumentType | str | None = None,
        page_number: int | None = None,
        source_name: str | None = None,
    ) -> DocumentResult:
        if not image_path.exists():
            raise UnsupportedFileError(f"Fichier introuvable : {image_path}")

        requested_type = DocumentType.coerce(doc_type)
        started = time.perf_counter()

        cache_key = None
        if self.use_cache:
            try:
                cache_key = self._cache_key(image_path, requested_type)
            except OSError:
                cache_key = None
            if cache_key:
                cached = self._cache_read(cache_key)
                if cached is not None:
                    result = DocumentResult.from_payload(cached)
                    result.meta.from_cache = True
                    logger.info("Cache utilise pour %s", image_path.name)
                    return result

        ocr_result = self.ocr.extract(str(image_path))
        resolved_type = route(
            filename=source_name or image_path.name,
            text=ocr_result.text,
            override=requested_type,
        )

        document = self.extractor.extract(ocr_result.text, resolved_type)
        document, warnings = validate_and_warn(document)

        meta = ExtractionMeta(
            provider=self.provider,
            ocr_engine=ocr_result.engine,
            extraction_model=self.extractor.model_name,
            source_file=source_name or image_path.name,
            document_type=resolved_type.value,
            duration_ms=int((time.perf_counter() - started) * 1000),
            page=page_number,
            warnings=warnings,
        )
        result = DocumentResult(document=document, meta=meta)

        if cache_key:
            self._cache_write(cache_key, result.to_dict())
        return result