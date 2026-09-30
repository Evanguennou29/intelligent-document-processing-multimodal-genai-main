"""Central, environment-driven configuration.

Nothing in this package hard-codes a project id, a host name or a model name:
every tunable is read from the process environment, and optionally from a
``.env`` file located at the repository root (see ``.env.example``).

This module is the single place to look when you need to know *where* a value
comes from.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Final

try:  # python-dotenv is optional: plain environment variables always work.
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - exercised only on minimal installs.

    def load_dotenv(*_args, **_kwargs) -> bool:  # type: ignore[misc]
        return False


PROJECT_ROOT: Final[Path] = Path(__file__).resolve().parents[2]
load_dotenv(PROJECT_ROOT / ".env")

PROVIDERS: Final[tuple[str, ...]] = ("vertex", "ollama")


def _raw(name: str, default: str = "") -> str:
    """Read an environment variable, treating blanks as 'unset'."""
    value = os.getenv(name)
    if value is None or not value.strip():
        return default
    return value.strip()


def _int(name: str, default: int) -> int:
    try:
        return int(_raw(name, str(default)))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(_raw(name, str(default)))
    except ValueError:
        return default


def _bool(name: str, default: bool = False) -> bool:
    return _raw(name, "true" if default else "false").lower() in {"1", "true", "yes", "y", "on"}


def _path(name: str, default: Path) -> Path:
    value = _raw(name)
    if not value:
        return default
    candidate = Path(value).expanduser()
    return candidate if candidate.is_absolute() else (PROJECT_ROOT / candidate)


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of the runtime configuration."""

    provider: str = "ollama"

    # -- Google Vertex AI -----------------------------------------------------
    vertex_project_id: str = ""
    vertex_location: str = "us-central1"
    vertex_model: str = "gemini-2.5-pro"

    # -- Local Ollama ---------------------------------------------------------
    ollama_host: str = "http://localhost:11434"
    ollama_vision_model: str = "llama3.2-vision"
    ollama_text_model: str = "llama3.2"
    ollama_timeout_s: float = 180.0
    ollama_max_image_side: int = 1024

    # -- Behaviour ------------------------------------------------------------
    max_retries: int = 2
    retry_backoff_s: float = 1.5
    use_cache: bool = True
    log_level: str = "INFO"

    # -- Storage --------------------------------------------------------------
    data_raw_dir: Path = PROJECT_ROOT / "data" / "raw"
    data_processed_dir: Path = PROJECT_ROOT / "data" / "processed"
    cache_dir: Path = PROJECT_ROOT / ".cache" / "idp"

    # -- Input limits ---------------------------------------------------------
    max_upload_mb: int = 25
    pdf_max_pages: int = 1
    pdf_dpi: int = 200

    # ------------------------------------------------------------------ API --
    @classmethod
    def from_env(cls) -> "Settings":
        provider = _raw("IDP_PROVIDER", "ollama").lower()
        if provider not in PROVIDERS:
            raise ValueError(
                f"IDP_PROVIDER='{provider}' invalide. Valeurs acceptees : {', '.join(PROVIDERS)}."
            )

        settings = cls(
            provider=provider,
            vertex_project_id=_raw("VERTEX_PROJECT_ID"),
            vertex_location=_raw("VERTEX_LOCATION", "us-central1"),
            vertex_model=_raw("VERTEX_MODEL", "gemini-2.5-pro"),
            ollama_host=_raw("OLLAMA_HOST", "http://localhost:11434"),
            ollama_vision_model=_raw("OLLAMA_VISION_MODEL", "llama3.2-vision"),
            ollama_text_model=_raw("OLLAMA_TEXT_MODEL", "llama3.2"),
            ollama_timeout_s=_float("OLLAMA_TIMEOUT", 180.0),
            ollama_max_image_side=_int("OLLAMA_MAX_IMAGE_SIDE", 1024),
            max_retries=max(1, _int("IDP_MAX_RETRIES", 2)),
            retry_backoff_s=_float("IDP_RETRY_BACKOFF", 1.5),
            use_cache=_bool("IDP_USE_CACHE", True),
            log_level=_raw("IDP_LOG_LEVEL", "INFO").upper(),
            data_raw_dir=_path("IDP_RAW_DIR", PROJECT_ROOT / "data" / "raw"),
            data_processed_dir=_path("IDP_PROCESSED_DIR", PROJECT_ROOT / "data" / "processed"),
            cache_dir=_path("IDP_CACHE_DIR", PROJECT_ROOT / ".cache" / "idp"),
            max_upload_mb=_int("IDP_MAX_UPLOAD_MB", 25),
            pdf_max_pages=max(1, _int("IDP_PDF_MAX_PAGES", 1)),
            pdf_dpi=max(72, _int("IDP_PDF_DPI", 200)),
        )
        return settings

    # -------------------------------------------------------------- helpers --
    def vertex_configured(self) -> bool:
        """True when a real project id was provided (and not a placeholder)."""
        project = self.vertex_project_id.strip()
        return bool(project) and project not in {"your_id_project", "your-project-id", "CHANGEME"}

    def describe(self) -> dict[str, str]:
        """Human-readable summary. Never leaks a secret because none is stored."""
        return {
            "provider": self.provider,
            "vertex_project_id": self.vertex_project_id or "(non configure)",
            "vertex_location": self.vertex_location,
            "vertex_model": self.vertex_model,
            "ollama_host": self.ollama_host,
            "ollama_vision_model": self.ollama_vision_model,
            "ollama_text_model": self.ollama_text_model,
            "use_cache": str(self.use_cache),
            "cache_dir": str(self.cache_dir),
            "data_raw_dir": str(self.data_raw_dir),
            "data_processed_dir": str(self.data_processed_dir),
            "log_level": self.log_level,
        }

    def ensure_directories(self) -> None:
        for directory in (self.data_raw_dir, self.data_processed_dir, self.cache_dir):
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings (cached).

    Call ``get_settings.cache_clear()`` after modifying environment variables,
    for instance in tests.
    """
    return Settings.from_env()
