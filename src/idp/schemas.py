"""Pydantic models describing every document type the pipeline understands.

The JSON schema produced by these models is injected verbatim into the LLM
prompt, so adding a field here is enough to make the model extract it.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class DocumentType(str, Enum):
    """Document families supported out of the box."""

    INVOICE = "invoice"
    PRESCRIPTION = "prescription"
    ID_CARD = "id_card"
    PASSPORT = "passport"
    GENERIC_FORM = "generic_form"
    CERTIFICATE = "certificate"

    @classmethod
    def values(cls) -> list[str]:
        return [member.value for member in cls]

    @classmethod
    def coerce(cls, value: "str | DocumentType | None") -> "DocumentType | None":
        """Best-effort conversion from a free-form string."""
        if value is None:
            return None
        if isinstance(value, cls):
            return value
        text = str(value).strip().lower().replace("-", "_").replace(" ", "_")
        aliases = {
            "id": cls.ID_CARD,
            "idcard": cls.ID_CARD,
            "identity_card": cls.ID_CARD,
            "form": cls.GENERIC_FORM,
            "generic": cls.GENERIC_FORM,
            "receipt": cls.INVOICE,
            "facture": cls.INVOICE,
            "ordonnance": cls.PRESCRIPTION,
            "certificat": cls.CERTIFICATE,
            "passeport": cls.PASSPORT,
        }
        if text in aliases:
            return aliases[text]
        try:
            return cls(text)
        except ValueError:
            return None


# --------------------------------------------------------------------------- #
# Nested value objects
# --------------------------------------------------------------------------- #
class InvoiceItem(BaseModel):
    description: str = ""
    quantity: float | None = None
    unit_price: float | None = None
    total_price: float | None = None


class PrescriptionItem(BaseModel):
    drug_name: str | None = None
    dosage: str | None = None
    frequency: str | None = None
    duration: str | None = None


# --------------------------------------------------------------------------- #
# Document models
# --------------------------------------------------------------------------- #
class Invoice(BaseModel):
    document_type: DocumentType = DocumentType.INVOICE
    invoice_number: str | None = None
    date: str | None = None
    seller_name: str | None = None
    seller_address: str | None = None
    buyer_name: str | None = None
    buyer_address: str | None = None
    items: list[InvoiceItem] = Field(default_factory=list)
    subtotal: float | None = None
    tax_amount: float | None = None
    total_amount: float | None = None
    currency: str | None = None
    language: str | None = None


class IDCard(BaseModel):
    document_type: DocumentType = DocumentType.ID_CARD
    full_name: str | None = None
    date_of_birth: str | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    document_number: str | None = None
    expiration_date: str | None = None
    issuing_authority: str | None = None
    address: str | None = None
    language: str | None = None


class Passport(BaseModel):
    document_type: DocumentType = DocumentType.PASSPORT
    full_name: str | None = None
    nationality: str | None = None
    date_of_birth: str | None = None
    place_of_birth: str | None = None
    passport_number: str | None = None
    issue_date: str | None = None
    expiration_date: str | None = None
    issuing_country: str | None = None
    language: str | None = None


class Prescription(BaseModel):
    document_type: DocumentType = DocumentType.PRESCRIPTION
    patient_name: str | None = None
    patient_date_of_birth: str | None = None
    doctor_name: str | None = None
    doctor_registration_number: str | None = None
    date: str | None = None
    items: list[PrescriptionItem] = Field(default_factory=list)
    notes: str | None = None
    language: str | None = None


class GenericForm(BaseModel):
    document_type: DocumentType = DocumentType.GENERIC_FORM
    title: str | None = None
    fields: dict[str, Any] = Field(default_factory=dict)
    language: str | None = None


class Certificate(BaseModel):
    document_type: DocumentType = DocumentType.CERTIFICATE
    title: str | None = None
    person_name: str | None = None
    issue_date: str | None = None
    issuing_authority: str | None = None
    details: str | None = None
    language: str | None = None


# --------------------------------------------------------------------------- #
# Result wrapper
# --------------------------------------------------------------------------- #
class ExtractionMeta(BaseModel):
    """Provenance information attached to every extraction result."""

    provider: str = ""
    ocr_engine: str = ""
    extraction_model: str = ""
    source_file: str = ""
    document_type: str = ""
    processed_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    duration_ms: int = 0
    from_cache: bool = False
    page: int | None = None
    warnings: list[str] = Field(default_factory=list)


SCHEMA_REGISTRY: dict[DocumentType, type[BaseModel]] = {
    DocumentType.INVOICE: Invoice,
    DocumentType.ID_CARD: IDCard,
    DocumentType.PASSPORT: Passport,
    DocumentType.PRESCRIPTION: Prescription,
    DocumentType.GENERIC_FORM: GenericForm,
    DocumentType.CERTIFICATE: Certificate,
}


def get_schema_model(doc_type: "DocumentType | str") -> type[BaseModel]:
    """Return the Pydantic model class bound to ``doc_type``."""
    resolved = DocumentType.coerce(doc_type)
    if resolved is None or resolved not in SCHEMA_REGISTRY:
        raise ValueError(
            f"Type de document non supporte : {doc_type!r}. "
            f"Valeurs possibles : {', '.join(DocumentType.values())}."
        )
    return SCHEMA_REGISTRY[resolved]
