"""Small logging helpers shared by the CLI, the pipeline and the web app."""

from __future__ import annotations

import logging
import os
import sys

_CONFIGURED = False
_FORMAT = "%(asctime)s | %(levelname)-7s | %(name)-22s | %(message)s"
_DATEFMT = "%H:%M:%S"


def setup_logging(level: str | None = None, force: bool = False) -> None:
    """Configure the root logger once, unless ``force`` is set."""
    global _CONFIGURED
    if _CONFIGURED and not force:
        return

    resolved = (level or os.getenv("IDP_LOG_LEVEL") or "INFO").upper()
    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(logging.Formatter(_FORMAT, datefmt=_DATEFMT))

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, resolved, logging.INFO))

    # These libraries are extremely chatty at DEBUG level.
    for noisy in ("urllib3", "google.auth", "google.api_core", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)