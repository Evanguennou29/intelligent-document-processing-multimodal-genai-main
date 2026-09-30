"""The validation module used to be a no-op; make sure it now works."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from idp.schemas import Invoice, InvoiceItem, Passport
from idp.validation import check, normalise_date, validate_and_warn


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("2024-03-12", "2024-03-12"),
        ("12/03/2024", "2024-03-12"),
        ("12-03-2024", "2024-03-12"),
        ("12.03.2024", "2024-03-12"),
        ("2024/03/12", "2024-03-12"),
        ("12 March 2024", "2024-03-12"),
        ("", None),
        (None, None),
        ("not a date", None),
    ],
)
def test_normalise_date(raw, expected) -> None:
    assert normalise_date(raw) == expected


def test_dates_are_rewritten_in_place() -> None:
    invoice = Invoice(date="12/03/2024")
    warnings = check(invoice)
    assert invoice.date == "2024-03-12"
    assert any("normalisee" in warning for warning in warnings)


def test_unreadable_date_keeps_original_value() -> None:
    invoice = Invoice(date="illegible")
    warnings = check(invoice)
    assert invoice.date == "illegible"
    assert any("illisible" in warning for warning in warnings)


def test_line_total_is_computed_when_missing() -> None:
    invoice = Invoice(items=[InvoiceItem(description="Widget", quantity=2, unit_price=10.5)])
    warnings = check(invoice)
    assert invoice.items[0].total_price == 21.0
    assert any("calcule" in warning for warning in warnings)


def test_consistent_invoice_produces_no_arithmetic_warning() -> None:
    invoice = Invoice(
        invoice_number="INV-1",
        date="2024-03-12",
        seller_name="ACME",
        currency="eur",
        items=[InvoiceItem(description="Widget", quantity=2, unit_price=50.0, total_price=100.0)],
        subtotal=100.0,
        tax_amount=20.0,
        total_amount=120.0,
    )
    warnings = check(invoice)
    assert invoice.currency == "EUR"
    assert not any("total_amount" in warning for warning in warnings)
    assert not any("subtotal" in warning for warning in warnings)
    assert warnings == []


def test_inconsistent_total_is_reported() -> None:
    invoice = Invoice(
        invoice_number="INV-1",
        seller_name="ACME",
        subtotal=100.0,
        tax_amount=20.0,
        total_amount=999.0,
    )
    warnings = check(invoice)
    assert any("total_amount" in warning for warning in warnings)


def test_expired_passport_is_flagged() -> None:
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    passport = Passport(passport_number="X1", expiration_date=yesterday)
    warnings = check(passport)
    assert any("expire depuis" in warning for warning in warnings)


def test_future_passport_is_not_flagged() -> None:
    tomorrow = (date.today() + timedelta(days=30)).isoformat()
    passport = Passport(passport_number="X1", expiration_date=tomorrow)
    assert not any("expire depuis" in warning for warning in check(passport))


def test_validate_and_warn_returns_both() -> None:
    document, warnings = validate_and_warn(Invoice())
    assert document is not None
    assert isinstance(warnings, list)