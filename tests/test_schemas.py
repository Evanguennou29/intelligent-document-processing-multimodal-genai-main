"""Schema registry and enum coercion."""

from __future__ import annotations

import pytest

from idp.schemas import (
    DocumentType,
    GenericForm,
    Invoice,
    Passport,
    get_schema_model,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("invoice", DocumentType.INVOICE),
        ("INVOICE", DocumentType.INVOICE),
        ("id_card", DocumentType.ID_CARD),
        ("id", DocumentType.ID_CARD),
        ("ID Card", DocumentType.ID_CARD),
        ("form", DocumentType.GENERIC_FORM),
        ("passport", DocumentType.PASSPORT),
        ("nonsense", None),
        (None, None),
        (DocumentType.INVOICE, DocumentType.INVOICE),
    ],
)
def test_document_type_coerce(raw, expected) -> None:
    assert DocumentType.coerce(raw) is expected


def test_get_schema_model_returns_the_right_class() -> None:
    assert get_schema_model("passport") is Passport
    assert get_schema_model(DocumentType.INVOICE) is Invoice


def test_get_schema_model_rejects_unknown_type() -> None:
    with pytest.raises(ValueError):
        get_schema_model("bogus")


def test_models_accept_partial_payloads() -> None:
    assert Invoice().items == []
    assert GenericForm().fields == {}
    assert Passport().passport_number is None


def test_json_schema_is_generated_for_every_type() -> None:
    for document_type in DocumentType:
        schema = get_schema_model(document_type).model_json_schema()
        assert schema["type"] == "object"
        assert "properties" in schema
