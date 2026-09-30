"""Contract shared by every OCR backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OcrResult:
    """Text extracted from one image, plus provenance."""

    text: str
    engine: str
    duration_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)


class OcrEngine(ABC):
    """A backend able to turn an image into text."""

    name: str = "base"

    @abstractmethod
    def extract(self, image_path: str) -> OcrResult:
        """Extract the text of ``image_path``. Raises :class:`OcrError` on failure."""

    def available(self) -> tuple[bool, str]:
        """Cheap capability probe, used by the UI to grey out unusable engines."""
        return True, "ok"