"""Decide which schema should be used for a document.

Routing combines three signals, in increasing order of trust:

1. the file name (``invoice_2024.png``);
2. keywords found in the OCR text;
3. an explicit override coming from the UI or the CLI.
"""

from __future__ import annotations

import re

from idp.schemas import DocumentType

# Ordered: the first matching entry wins, so put the most specific first.
FILENAME_RULES: tuple[tuple[tuple[str, ...], DocumentType], ...] = (
    (("invoice", "facture", "receipt", "bill", "ticket"), DocumentType.INVOICE),
    (("passport", "passeport"), DocumentType.PASSPORT),
    (("id_card", "idcard", "identity", "carte_identite", "cni", "cin"), DocumentType.ID_CARD),
    (("prescription", "ordo", "ordonnance", "pharmacy"), DocumentType.PRESCRIPTION),
    (("certificate", "certificat", "diploma", "attestation"), DocumentType.CERTIFICATE),
    (("form", "formulaire", "application"), DocumentType.GENERIC_FORM),
)

TEXT_RULES: tuple[tuple[tuple[str, ...], DocumentType], ...] = (
    (
        ("invoice number", "tax invoice", "total due", "subtotal", "vat", "facture n"),
        DocumentType.INVOICE,
    ),
    (
        ("passport", "passeport", "republic of", "code of issuing state", "machine readable"),
        DocumentType.PASSPORT,
    ),
    (
        ("identity card", "carte nationale", "date of expiry", "holder's signature"),
        DocumentType.ID_CARD,
    ),
    (
        ("prescription", "ordonnance", "dosage", "prescriber", "pharmacie"),
        DocumentType.PRESCRIPTION,
    ),
    (
        ("certificate", "certificat", "hereby certify", "attestation", "diploma"),
        DocumentType.CERTIFICATE,
    ),
)


def _tokenize(value: str) -> str:
    """Lower-case a string and isolate tokens so 'id' no longer matches 'video'."""
    return " " + re.sub(r"[^a-z0-9]+", " ", value.lower()).strip() + " "


def _matches(haystack: str, needles: tuple[str, ...]) -> bool:
    return any(needle in haystack for needle in needles)


def simple_routing_from_filename(filename: str) -> DocumentType:
    """Guess the document type from a file name.

    Unlike the original implementation this is word-boundary aware, so
    ``video.mp4`` or ``candidate.png`` no longer route to *id_card*.
    """
    haystack = _tokenize(filename or "")
    for needles, doc_type in FILENAME_RULES:
        if _matches(haystack, needles):
            return doc_type
    return DocumentType.GENERIC_FORM


def detect_document_type_from_text(
    text: str, default: DocumentType = DocumentType.GENERIC_FORM
) -> DocumentType:
    """Guess the document type from the OCR text itself."""
    haystack = _tokenize(text or "")
    if not haystack.strip():
        return default
    for needles, doc_type in TEXT_RULES:
        if _matches(haystack, needles):
            return doc_type
    return default


def route(
    filename: str | None = None,
    text: str | None = None,
    override: "DocumentType | str | None" = None,
) -> DocumentType:
    """Resolve the document type from an explicit override, the text then the name."""
    explicit = DocumentType.coerce(override)
    if explicit is not None:
        return explicit

    from_text = detect_document_type_from_text(text or "")
    if from_text is not DocumentType.GENERIC_FORM:
        return from_text

    if filename:
        from_name = simple_routing_from_filename(filename)
        if from_name is not DocumentType.GENERIC_FORM:
            return from_name

    return DocumentType.GENERIC_FORM