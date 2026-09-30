"""Local, offline OCR backend powered by Ollama vision models."""

from __future__ import annotations

import io
import time

from idp.config import Settings, get_settings
from idp.errors import OcrError
from idp.logging_utils import get_logger
from idp.ocr.base import OcrEngine, OcrResult

logger = get_logger(__name__)

OCR_PROMPT = (
    "Extract ALL the text from this image exactly as written. "
    "Do not summarise, do not translate, do not comment. "
    "Reproduce numbers and dates exactly. Output raw text only."
)


def prepare_image(image_path: str, max_side: int) -> bytes:
    """Downscale an image so a local model stays responsive.

    Ollama encodes the picture into image tokens: capping the long side at
    ~1024 px typically divides the inference time by three to five with no
    measurable loss of accuracy on scanned documents.
    """
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover
        raise OcrError("Pillow n'est pas installe (pip install pillow).") from exc

    try:
        with Image.open(image_path) as image:
            rgb = image.convert("RGB")
            if max(rgb.size) > max_side:
                rgb.thumbnail((max_side, max_side), Image.LANCZOS)
            buffer = io.BytesIO()
            rgb.save(buffer, format="PNG", optimize=True)
            return buffer.getvalue()
    except OcrError:
        raise
    except Exception as exc:
        raise OcrError(f"Image illisible ({image_path}) : {exc}") from exc


def _message_content(response) -> str:
    """Ollama returns dict-like objects whose shape changed across releases."""
    try:
        return (response["message"]["content"] or "").strip()
    except Exception:
        message = getattr(response, "message", None)
        return (getattr(message, "content", "") or "").strip()


class OllamaVisionOcr(OcrEngine):
    """Extract text with a vision model served by a local Ollama instance."""

    name = "ollama-vision"

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._client = None

    # ------------------------------------------------------------------ API --
    @property
    def client(self):
        if self._client is None:
            try:
                import ollama
            except ImportError as exc:
                raise OcrError("Le paquet 'ollama' n'est pas installe (pip install -e '.[ollama]').") from exc
            self._client = ollama.Client(
                host=self.settings.ollama_host,
                timeout=self.settings.ollama_timeout_s,
            )
        return self._client

    def available(self) -> tuple[bool, str]:
        try:
            import ollama  # noqa: F401
        except ImportError:
            return False, "le paquet Python 'ollama' n'est pas installe"
        try:
            self.client.list()
        except Exception as exc:
            return False, f"Ollama est injoignable sur {self.settings.ollama_host} ({exc})"
        return True, "ok"

    def extract(self, image_path: str) -> OcrResult:
        payload = prepare_image(image_path, self.settings.ollama_max_image_side)

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            started = time.perf_counter()
            try:
                response = self.client.chat(
                    model=self.settings.ollama_vision_model,
                    messages=[{"role": "user", "content": OCR_PROMPT, "images": [payload]}],
                    options={"temperature": 0.0},
                )
                text = _message_content(response)
                if not text:
                    raise OcrError("Ollama a renvoye une transcription vide.")

                duration = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "OCR Ollama termine en %s ms (tentative %s, %s caracteres)",
                    duration,
                    attempt,
                    len(text),
                )
                return OcrResult(
                    text=text,
                    engine=f"{self.name}:{self.settings.ollama_vision_model}",
                    duration_ms=duration,
                )
            except Exception as exc:
                last_error = exc
                logger.warning("Tentative OCR %s/%s echouee : %s", attempt, self.settings.max_retries, exc)
                if attempt < self.settings.max_retries:
                    time.sleep(self.settings.retry_backoff_s * attempt)

        raise OcrError(
            f"OCR Ollama a echoue apres {self.settings.max_retries} tentatives "
            f"(modele '{self.settings.ollama_vision_model}') : {last_error}"
        )
