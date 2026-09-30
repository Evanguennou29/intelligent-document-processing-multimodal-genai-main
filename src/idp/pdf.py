"""Optional PDF support, backed by PyMuPDF.

``pymupdf`` was already listed in the original requirements but never used.
A scanned PDF is rasterised into PNG pages that the ordinary image pipeline
can then process.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from idp.errors import UnsupportedFileError
from idp.logging_utils import get_logger

logger = get_logger(__name__)

IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
PDF_SUFFIXES = {".pdf"}


def is_pdf(path: "str | Path") -> bool:
    return Path(path).suffix.lower() in PDF_SUFFIXES


def is_image(path: "str | Path") -> bool:
    return Path(path).suffix.lower() in IMAGE_SUFFIXES


def is_supported(path: "str | Path") -> bool:
    return is_pdf(path) or is_image(path)


def rasterise_pdf(
    pdf_path: "str | Path",
    out_dir: "str | Path",
    dpi: int = 200,
    max_pages: int = 1,
) -> list[Path]:
    """Render the first ``max_pages`` pages of ``pdf_path`` to PNG files.

    Returns the list of generated image paths, in page order.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        raise UnsupportedFileError(f"PDF introuvable : {pdf_path}")

    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise UnsupportedFileError(
            "Le support PDF necessite PyMuPDF (pip install -e '.[pdf]')."
        ) from exc

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    digest = hashlib.sha1(str(pdf_path.resolve()).encode("utf-8")).hexdigest()[:10]
    zoom = max(1.0, dpi / 72.0)
    matrix = fitz.Matrix(zoom, zoom)

    pages: list[Path] = []
    with fitz.open(pdf_path) as document:
        total = document.page_count
        limit = min(total, max(1, max_pages))
        if total > limit:
            logger.info(
                "PDF de %s pages : seules les %s premieres seront traitees (IDP_PDF_MAX_PAGES).",
                total,
                limit,
            )
        for index in range(limit):
            page = document.load_page(index)
            pixmap = page.get_pixmap(matrix=matrix, alpha=False)
            target = out_dir / f"{pdf_path.stem}-{digest}-p{index + 1}.png"
            pixmap.save(str(target))
            pages.append(target)

    if not pages:
        raise UnsupportedFileError(f"Le PDF ne contient aucune page exploitable : {pdf_path}")
    return pages