"""Post-extraction validation and normalisation.

The first version of this module was a no-op that returned the model it
received.  It now genuinely inspects the extracted document:

* it normalises the dates it can safely rewrite to ISO ``YYYY-MM-DD``;
* it recomputes invoice line totals and detects arithmetic inconsistencies;
* it flags expired identity documents and empty generic forms;
* it never raises: problems are reported as human-readable warnings so a
  partially-wrong extraction stays usable instead of crashing the pipeline.
"""

from __future__ import annotations

import re
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel

from idp.schemas import (
    Certificate,
    GenericForm,
    IDCard,
    Invoice,
    Passport,
    Prescription,
)

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CURRENCY_CODE = re.compile(r"^[A-Z]{3}$")

DATE_FIELD_NAMES: tuple[str, ...] = (
    "date",
    "issue_date",
    "expiration_date",
    "date_of_birth",
    "patient_date_of_birth",
)

DATE_FORMATS: tuple[str, ...] = (
    "%Y-%m-%d",
    "%d/%m/%Y",
    "%d-%m-%Y",
    "%d.%m.%Y",
    "%Y/%m/%d",
    "%m/%d/%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%B %d, %Y",
)

MONEY_TOLERANCE = 0.02  # two cents


# --------------------------------------------------------------------------- #
# Date handling
# --------------------------------------------------------------------------- #
def normalise_date(value: Any) -> str | None:
    """Return an ISO date string, or ``None`` when the value is unusable."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None
    if ISO_DATE.match(text):
        return text

    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _normalise_document_dates(document: BaseModel) -> list[str]:
    warnings: list[str] = []
    fields = type(document).model_fields

    for field_name in DATE_FIELD_NAMES:
        if field_name not in fields:
            continue
        raw_value = getattr(document, field_name, None)
        if raw_value in (None, ""):
            continue

        iso = normalise_date(raw_value)
        if iso is None:
            warnings.append(f"{field_name} : date illisible, conservee telle quelle ({raw_value!r})")
        elif iso != raw_value:
            warnings.append(f"{field_name} : normalisee {raw_value!r} -> {iso}")
            setattr(document, field_name, iso)

    return warnings


# --------------------------------------------------------------------------- #
# Per-document checks
# --------------------------------------------------------------------------- #
def _relative_tolerance(reference: float) -> float:
    return max(MONEY_TOLERANCE, abs(reference) * 0.01)


def _check_invoice(invoice: Invoice) -> list[str]:
    warnings: list[str] = []

    if invoice.currency:
        if CURRENCY_CODE.match(invoice.currency.upper()):
            invoice.currency = invoice.currency.upper()
        else:
            warnings.append(f"currency : {invoice.currency!r} n'est pas un code ISO 4217 (3 lettres)")

    computed_line_total = 0.0
    has_line_total = False

    for index, item in enumerate(invoice.items):
        label = f"items[{index}]"
        if item.quantity is not None and item.unit_price is not None:
            expected = round(item.quantity * item.unit_price, 2)
            if item.total_price is None:
                item.total_price = expected
                warnings.append(f"{label}.total_price absent -> calcule ({expected})")
            elif abs(item.total_price - expected) > MONEY_TOLERANCE:
                warnings.append(
                    f"{label}.total_price ({item.total_price}) != quantity x unit_price ({expected})"
                )
        if item.total_price is not None:
            computed_line_total += item.total_price
            has_line_total = True
        if item.quantity is not None and item.quantity < 0:
            warnings.append(f"{label}.quantity est negatif ({item.quantity})")

    if has_line_total and invoice.subtotal is not None:
        if abs(computed_line_total - invoice.subtotal) > _relative_tolerance(invoice.subtotal):
            warnings.append(
                f"subtotal ({invoice.subtotal}) != somme des lignes ({round(computed_line_total, 2)})"
            )

    if invoice.subtotal is not None and invoice.tax_amount is not None and invoice.total_amount is not None:
        expected_total = round(invoice.subtotal + invoice.tax_amount, 2)
        if abs(expected_total - invoice.total_amount) > _relative_tolerance(invoice.total_amount):
            warnings.append(
                f"total_amount ({invoice.total_amount}) != subtotal + tax ({expected_total})"
            )

    if invoice.total_amount is not None and invoice.total_amount < 0:
        warnings.append("total_amount est negatif")

    missing = [
        name
        for name in ("invoice_number", "date", "seller_name", "total_amount")
        if getattr(invoice, name, None) in (None, "")
    ]
    if missing:
        warnings.append("champs cles manquants : " + ", ".join(missing))

    return warnings


def _check_expiry(document: BaseModel) -> list[str]:
    expiry = getattr(document, "expiration_date", None)
    if not expiry:
        return []
    iso = normalise_date(expiry)
    if not iso:
        return []
    try:
        if date.fromisoformat(iso) < date.today():
            return [f"document expire depuis le {iso}"]
    except ValueError:
        return []
    return []


def _check_generic_form(form: GenericForm) -> list[str]:
    warnings: list[str] = []
    if not form.fields:
        warnings.append("aucun champ extrait (fields est vide)")
    if not form.title:
        warnings.append("titre du document absent")
    return warnings


def _check_prescription(prescription: Prescription) -> list[str]:
    warnings: list[str] = []
    if not prescription.items:
        warnings.append("aucun medicament extrait (items est vide)")
    for index, item in enumerate(prescription.items):
        if not item.drug_name:
            warnings.append(f"items[{index}].drug_name est vide")
    if not prescription.doctor_name:
        warnings.append("nom du prescripteur absent")
    return warnings


def _check_certificate(certificate: Certificate) -> list[str]:
    warnings: list[str] = []
    if not certificate.person_name:
        warnings.append("nom du titulaire absent")
    if not certificate.issuing_authority:
        warnings.append("autorite emettrice absente")
    return warnings


_CHECKERS = {
    Invoice: _check_invoice,
    Prescription: _check_prescription,
    GenericForm: _check_generic_form,
    Certificate: _check_certificate,
}


# --------------------------------------------------------------------------- #
# Public API
# --------------------------------------------------------------------------- #
def check(document: BaseModel) -> list[str]:
    """Inspect ``document`` in place and return the list of warnings found."""
    warnings = _normalise_document_dates(document)

    for model_class, checker in _CHECKERS.items():
        if isinstance(document, model_class):
            warnings.extend(checker(document))  # type: ignore[arg-type]
            break

    if isinstance(document, (Passport, IDCard)):
        warnings.extend(_check_expiry(document))

    return warnings


def validate_document(model: BaseModel) -> BaseModel:
    """Backward-compatible alias kept for the original notebook/API.

    Prefer :func:`validate_and_warn` when you also want the diagnostics.
    """
    check(model)
    return model


def validate_and_warn(document: BaseModel) -> tuple[BaseModel, list[str]]:
    """Validate ``document`` and return ``(document, warnings)``."""
    return document, check(document)
