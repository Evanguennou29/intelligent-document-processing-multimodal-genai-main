"""Routing must be precise: the original version matched 'id' anywhere."""

from __future__ import annotations

import pytest

from idp.routing import (
    detect_document_type_from_text,
    route,
    simple_routing_from_filename,
)
from idp.schemas import DocumentType


@pytest.mark.parametrize(
    ("filename", "expected"),
    [
        ("invoice_2024.png", DocumentType.INVOICE),
        ("facture-mars.pdf", DocumentType.INVOICE),
        ("my_passport.jpg", DocumentType.PASSPORT),
        ("cni_recto.png", DocumentType.ID_CARD),
        ("ordonnance_dupont.jpg", DocumentType.PRESCRIPTION),
        ("certificat_scolarite.png", DocumentType.CERTIFICATE),
        ("formulaire_inscription.png", DocumentType.GENERIC_FORM),
        ("random_scan_001.png", DocumentType.GENERIC_FORM),
    ],
)
def test_filename_routing(filename: str, expected: DocumentType) -> None:
    assert simple_routing_from_filename(filename) is expected


@pytest.mark.parametrize("filename", ["video.mp4", "candidate.png", "videogame.jpg", "void.png"])
def test_id_does_not_match_inside_another_word(filename: str) -> None:
    """Regression test: the old 'if "id" in name' rule routed these to id_card."""
    assert simple_routing_from_filename(filename) is DocumentType.GENERIC_FORM


def test_text_detection_for_invoice() -> None:
    text = "TAX INVOICE\nInvoice Number: 42\nSubtotal 100.00\nVAT 20.00\nTotal due 120.00"
    assert detect_document_type_from_text(text) is DocumentType.INVOICE


def test_text_detection_is_case_and_punctuation_insensitive() -> None:
    assert detect_document_type_from_text("PASSEPORT / REPUBLIQUE") is DocumentType.PASSPORT


def test_route_prefers_explicit_override() -> None:
    result = route(filename="invoice_2024.png", text="passport", override="certificate")
    assert result is DocumentType.CERTIFICATE


def test_route_prefers_text_over_filename() -> None:
    result = route(filename="scan_0001.png", text="TAX INVOICE total due")
    assert result is DocumentType.INVOICE


def test_route_falls_back_to_filename_then_generic() -> None:
    assert route(filename="passport_john.png", text="") is DocumentType.PASSPORT
    assert route(filename="scan.png", text="") is DocumentType.GENERIC_FORM
