"""OCR backends and the factory used to select one."""

from __future__ import annotations

from idp.config import Settings, get_settings
from idp.errors import ConfigurationError
from idp.ocr.base import OcrEngine, OcrResult
from idp.ocr.gemini_vision import GeminiVisionOcr
from idp.ocr.ollama_vision import OllamaVisionOcr

__all__ = [
    "OcrEngine",
    "OcrResult",
    "GeminiVisionOcr",
    "OllamaVisionOcr",
    "get_ocr_engine",
]

_ENGINES: dict[str, type[OcrEngine]] = {
    "vertex": GeminiVisionOcr,
    "ollama": OllamaVisionOcr,
}


def get_ocr_engine(provider: str | None = None, settings: Settings | None = None) -> OcrEngine:
    """Instantiate the OCR backend bound to ``provider``."""
    settings = settings or get_settings()
    resolved = (provider or settings.provider).lower()
    if resolved not in _ENGINES:
        raise ConfigurationError(
            f"Provider '{resolved}' inconnu. Valeurs acceptees : {', '.join(sorted(_ENGINES))}."
        )
    return _ENGINES[resolved](settings)