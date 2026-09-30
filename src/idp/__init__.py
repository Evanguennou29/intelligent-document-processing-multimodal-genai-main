"""Intelligent Document Processing - multimodal GenAI toolkit.

Public surface::

    from idp import Pipeline, DocumentType

    pipeline = Pipeline(provider="ollama")
    result = pipeline.process("scan.png")
    print(result.document.model_dump())
"""

from idp.config import Settings, get_settings
from idp.errors import (
    ConfigurationError,
    ExtractionError,
    IdpError,
    OcrError,
    UnsupportedFileError,
)
from idp.pipeline import DocumentResult, Pipeline
from idp.schemas import DocumentType, ExtractionMeta, get_schema_model

__version__ = "2.0.0"

__all__ = [
    "ConfigurationError",
    "DocumentResult",
    "DocumentType",
    "ExtractionError",
    "ExtractionMeta",
    "IdpError",
    "OcrError",
    "Pipeline",
    "Settings",
    "UnsupportedFileError",
    "__version__",
    "get_schema_model",
    "get_settings",
]