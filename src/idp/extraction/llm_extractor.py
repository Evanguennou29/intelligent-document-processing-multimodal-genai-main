"""Turn raw OCR text into a validated Pydantic document.

The original implementation simply split the model answer on ``` fences and
called ``json.loads``.  Models do not always cooperate, so this version:

* accepts a fenced block, a bare object surrounded by prose, or a plain object;
* repairs the classic trailing-comma slip;
* retries once, feeding the validation error back to the model;
* raises :class:`ExtractionError` with the offending payload when all else fails.
"""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, ValidationError

from idp.config import Settings, get_settings
from idp.errors import ExtractionError
from idp.logging_utils import get_logger
from idp.schemas import DocumentType, get_schema_model

logger = get_logger(__name__)

FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)
TRAILING_COMMA_RE = re.compile(r",\s*([}\]])")

SYSTEM_PROMPT = """You are an expert information-extraction engine.

You receive the raw OCR text of a single document and must return ONE JSON
object that strictly matches the supplied JSON Schema.

Hard rules:
- Output JSON only: no markdown, no code fence, no explanation.
- Use exactly the keys of the schema; never add or rename a key.
- A field that is absent or unreadable must be null (arrays must be []).
- Never guess a value that is not present in the OCR text.
- Keep dates as they appear on the document, preferably ISO YYYY-MM-DD.
- Numbers must be plain JSON numbers (a dot as decimal separator, no
  thousands separator, no currency symbol).
"""


# --------------------------------------------------------------------------- #
# Robust JSON extraction
# --------------------------------------------------------------------------- #
def strip_code_fence(raw: str) -> str:
    """Return the content of the first ``` block, or the input unchanged."""
    if not raw:
        return ""
    match = FENCE_RE.search(raw)
    if match:
        return match.group(1).strip()
    return raw.strip()


def first_json_object(raw: str) -> str | None:
    """Return the first balanced ``{...}`` block found in ``raw``."""
    start = raw.find("{")
    if start < 0:
        return None

    depth = 0
    in_string = False
    escaped = False

    for index in range(start, len(raw)):
        char = raw[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return raw[start : index + 1]
    return None


def _remove_trailing_commas(text: str) -> str:
    return TRAILING_COMMA_RE.sub(r"\1", text)


def extract_json_object(raw: str | None) -> dict[str, Any]:
    """Best-effort conversion of a model answer into a dictionary."""
    if raw is None or not str(raw).strip():
        raise ExtractionError("Le modele a renvoye une reponse vide.")

    text = str(raw)
    candidates: list[str] = []
    for candidate in (strip_code_fence(text), first_json_object(text), text):
        if candidate and candidate not in candidates:
            candidates.append(candidate)

    for candidate in candidates:
        for variant in (candidate, _remove_trailing_commas(candidate)):
            try:
                parsed = json.loads(variant)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(parsed, dict):
                return parsed

    preview = text if len(text) <= 2000 else text[:2000] + " ..."
    raise ExtractionError(f"Aucun objet JSON valide dans la reponse du modele :\n{preview}")


# --------------------------------------------------------------------------- #
# Extractor
# --------------------------------------------------------------------------- #
class LlmExtractor:
    """Extract a structured document from OCR text with Gemini or a local LLM."""

    def __init__(self, provider: str | None = None, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.provider = (provider or self.settings.provider).lower()
        self._client = None
        self._model = None

    # ------------------------------------------------------------- metadata --
    @property
    def model_name(self) -> str:
        if self.provider == "vertex":
            return self.settings.vertex_model
        return self.settings.ollama_text_model

    def available(self) -> tuple[bool, str]:
        if self.provider == "vertex":
            if not self.settings.vertex_configured():
                return False, "VERTEX_PROJECT_ID n'est pas renseigne dans votre fichier .env"
            try:
                import vertexai  # noqa: F401
            except ImportError:
                return False, "google-cloud-aiplatform n'est pas installe"
            return True, "ok"

        try:
            import ollama  # noqa: F401
        except ImportError:
            return False, "le paquet Python 'ollama' n'est pas installe"
        return True, "ok"

    # ------------------------------------------------------------ public API --
    def extract(self, ocr_text: str, doc_type: DocumentType | str) -> BaseModel:
        """Return a validated document, or raise :class:`ExtractionError`."""
        resolved_type = DocumentType.coerce(doc_type)
        if resolved_type is None:
            raise ExtractionError(f"Type de document inconnu : {doc_type!r}")

        schema_model = get_schema_model(resolved_type)
        system_prompt, user_prompt = self.build_prompts(resolved_type, schema_model, ocr_text)

        last_error: Exception | None = None
        for attempt in range(1, self.settings.max_retries + 1):
            try:
                raw = self._call_model(system_prompt, user_prompt, last_error)
                data = extract_json_object(raw)
                return schema_model(**data)
            except ValidationError as exc:
                last_error = exc
                logger.warning("Validation Pydantic echouee (tentative %s) : %s", attempt, exc)
            except ExtractionError as exc:
                last_error = exc
                logger.warning("JSON invalide (tentative %s) : %s", attempt, exc)

        raise ExtractionError(
            f"Extraction impossible apres {self.settings.max_retries} tentatives "
            f"({self.provider}/{self.model_name}) : {last_error}"
        )

    def build_prompts(
        self,
        doc_type: DocumentType,
        schema_model: type[BaseModel],
        ocr_text: str,
    ) -> tuple[str, str]:
        system_prompt = SYSTEM_PROMPT + f"\nTarget document type: {doc_type.value}."
        user_prompt = (
            "JSON SCHEMA:\n"
            + json.dumps(schema_model.model_json_schema(), indent=2, ensure_ascii=False)
            + "\n\nOCR TEXT:\n<<<\n"
            + (ocr_text or "").strip()
            + "\n>>>\n\nReturn the JSON object now."
        )
        return system_prompt, user_prompt

    # -------------------------------------------------------------- internal --
    def _call_model(self, system_prompt: str, user_prompt: str, last_error: Exception | None) -> str:
        correction = ""
        if last_error is not None:
            correction = (
                "\n\nYour previous answer was rejected. Fix it and return valid JSON only.\n"
                f"Error: {last_error}\n"
            )

        if self.provider == "vertex":
            return self._call_vertex(system_prompt + user_prompt + correction)
        return self._call_ollama(system_prompt, user_prompt + correction)

    def _call_vertex(self, prompt: str) -> str:
        from vertexai.generative_models import GenerativeModel

        if self._model is None:
            import vertexai

            vertexai.init(
                project=self.settings.vertex_project_id,
                location=self.settings.vertex_location,
            )
            self._model = GenerativeModel(self.settings.vertex_model)

        try:
            response = self._model.generate_content(
                prompt,
                generation_config={
                    "temperature": 0.0,
                    "response_mime_type": "application/json",
                },
            )
        except Exception as exc:
            raise ExtractionError(f"Appel Vertex AI echoue : {exc}") from exc

        return getattr(response, "text", "") or ""

    def _call_ollama(self, system_prompt: str, user_prompt: str) -> str:
        if self._client is None:
            import ollama

            self._client = ollama.Client(
                host=self.settings.ollama_host,
                timeout=self.settings.ollama_timeout_s,
            )

        try:
            response = self._client.chat(
                model=self.settings.ollama_text_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                format="json",
                options={"temperature": 0.0},
            )
        except Exception as exc:
            raise ExtractionError(f"Appel Ollama echoue : {exc}") from exc

        try:
            return response["message"]["content"] or ""
        except Exception:
            message = getattr(response, "message", None)
            return getattr(message, "content", "") or ""