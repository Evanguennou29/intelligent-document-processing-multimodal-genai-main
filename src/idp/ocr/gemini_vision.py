"""Cloud OCR backend based on Gemini Vision (Google Vertex AI).

The ``vertexai`` import is intentionally deferred to call time: a user who
only wants the local Ollama backend must be able to import the package
without installing the (heavy) Google SDK.
"""

from __future__ import annotations

import time

from idp.config import Settings, get_settings
from idp.errors import OcrError
from idp.logging_utils import get_logger
from idp.ocr.base import OcrEngine, OcrResult

logger = get_logger(__name__)

OCR_PROMPT = (
    "You are a high-precision OCR system. "
    "Transcribe ALL readable text from this document. "
    "Preserve the reading order and the layout as faithfully as possible. "
    "Reproduce numbers, dates and codes exactly as printed. "
    "Never invent content: if a zone is unreadable, write [illisible]. "
    "Output the raw transcription only, without commentary."
)


class GeminiVisionOcr(OcrEngine):
    """Extract text with a Gemini multimodal model hosted on Vertex AI."""

    name = "gemini-vision"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model = None

    # ------------------------------------------------------------------ API --
    def available(self) -> tuple[bool, str]:
        if not self.settings.vertex_configured():
            return False, "VERTEX_PROJECT_ID n'est pas renseigne dans votre fichier .env"
        try:
            import vertexai  # noqa: F401
            from vertexai.generative_models import GenerativeModel  # noqa: F401
        except ImportError:
            return False, "google-cloud-aiplatform n'est pas installe (pip install -e '.[vertex]')"
        return True, "ok"

    def extract(self, image_path: str) -> OcrResult:
        ready, reason = self.available()
        if not ready:
            raise OcrError(reason)

        from vertexai.generative_models import Image, Part

        started = time.perf_counter()
        try:
            image = Image.load_from_file(image_path)
            response = self._get_model().generate_content(
                contents=[OCR_PROMPT, Part.from_image(image)],
                generation_config={"temperature": 0.0},
            )
        except Exception as exc:  # pragma: no cover - depends on the network
            raise OcrError(f"Echec de l'appel Gemini Vision : {exc}") from exc

        text = (getattr(response, "text", "") or "").strip()
        if not text:
            raise OcrError("Gemini Vision a renvoye une transcription vide.")

        duration = int((time.perf_counter() - started) * 1000)
        logger.info("OCR Gemini termine en %s ms (%s caracteres)", duration, len(text))
        return OcrResult(text=text, engine=f"{self.name}:{self.settings.vertex_model}", duration_ms=duration)

    # -------------------------------------------------------------- private --
    def _get_model(self):
        if self._model is None:
            import vertexai
            from vertexai.generative_models import GenerativeModel

            vertexai.init(
                project=self.settings.vertex_project_id,
                location=self.settings.vertex_location,
            )
            self._model = GenerativeModel(self.settings.vertex_model)
        return self._model