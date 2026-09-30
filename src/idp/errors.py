"""Exception hierarchy used across the package.

Having dedicated types makes the CLI and the Streamlit app able to show a
useful message instead of a raw traceback.
"""

from __future__ import annotations


class IdpError(Exception):
    """Base class for every error raised by this package."""


class ConfigurationError(IdpError):
    """The environment is not usable (missing project id, bad provider, ...)."""


class OcrError(IdpError):
    """The OCR backend failed or is not reachable."""


class ExtractionError(IdpError):
    """The LLM returned something that is not a valid document."""


class UnsupportedFileError(IdpError):
    """The uploaded file is neither an image nor a PDF."""
