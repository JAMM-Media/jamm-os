# tests/test_fix_paid_invoice_amount_paid.py
"""
Tests for scripts/fix_paid_invoice_amount_paid.py.

Verifies the script's narrow filter: only invoices with status=paid AND
paid_at IS NOT NULL AND amount_paid=0 are touched. All other rows are left
exactly as found.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.client import Client
from app.models.invoice import Invoice
from app.core.enums import InvoiceStatus


def _setup_firm_and_client():
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Fix Script Test Firm", slug=f"fix-script-{uuid.uuid4().hex[:8]}")
        db.add(firm)
        db.flush()
        client = Client(firm_id=firm.id, name="Fix Script Test Client")
        db.add(client)
        db.commit()
        db.refresh(firm)
        db.refresh(client)
        return firm.id, client.id
    finally:
        db.close()


def _create_invoice(firm_id, client_id, status, amount_paid, total_amount="1200.00", paid_at=None):
    db = TestingSessionLocal()
    try:
        inv = Invoice(
            firm_id=firm_id,
            client_id=client_id,
            invoice_number=f"TEST-{uuid.uuid4().hex[:8]}",
            subtotal=Decimal(total_amount),
            tax_rate=Decimal("0"),
            tax_amount=Decimal("0"),
            total_amount=Decimal(total_amount),
            status=status,
            amount_paid=Decimal(str(amount_paid)),
            paid_at=paid_at,
        )
        db.add(inv)
        db.commit()
        db.refresh(inv)
        return inv.id
    finally:
        db.close()


def _get_amount_paid(invoice_id):
    db = TestingSessionLocal()
    try:
        inv = db.get(Invoice, invoice_id)
        return Decimal(str(inv.amount_paid))
    finally:
        db.close()


def test_fix_sets_amount_paid_for_target_rows_only(monkeypatch):
    """Script touches only status=paid AND paid_at IS NOT NULL AND amount_paid=0."""
    import scripts.fix_paid_invoice_amount_paid as fix_module
    monkeypatch.setattr(fix_module, "SessionLocal", TestingSessionLocal)

    firm_id, client_id = _setup_firm_and_client()
    now = datetime.now(timezone.utc)

    # Rows that should be fixed
    target_1 = _create_invoice(firm_id, client_id, InvoiceStatus.paid, 0, "1200.00", paid_at=now)
    target_2 = _create_invoice(firm_id, client_id, InvoiceStatus.paid, 0, "750.00", paid_at=now)
    target_3 = _create_invoice(firm_id, client_id, InvoiceStatus.paid, 0, "1200.00", paid_at=now)

    # Control: paid with a real nonzero amount_paid -- must NOT change
    control_nonzero = _create_invoice(firm_id, client_id, InvoiceStatus.paid, "800.00", "800.00", paid_at=now)

    # Control: paid with amount_paid=0 but paid_at=None -- must NOT change
    control_no_paid_at = _create_invoice(firm_id, client_id, InvoiceStatus.paid, 0, "500.00", paid_at=None)

    # Control: draft with amount_paid=0 -- must NOT change
    control_draft = _create_invoice(firm_id, client_id, InvoiceStatus.draft, 0, "500.00")

    fix_module.main()

    assert _get_amount_paid(target_1) == Decimal("1200.00")
    assert _get_amount_paid(target_2) == Decimal("750.00")
    assert _get_amount_paid(target_3) == Decimal("1200.00")
    assert _get_amount_paid(control_nonzero) == Decimal("800.00")
    assert _get_amount_paid(control_no_paid_at) == Decimal("0")
    assert _get_amount_paid(control_draft) == Decimal("0")


def test_dry_run_writes_nothing(monkeypatch):
    """With dry_run=True, all rows remain unchanged."""
    import scripts.fix_paid_invoice_amount_paid as fix_module
    monkeypatch.setattr(fix_module, "SessionLocal", TestingSessionLocal)

    firm_id, client_id = _setup_firm_and_client()
    now = datetime.now(timezone.utc)

    target = _create_invoice(firm_id, client_id, InvoiceStatus.paid, 0, "1000.00", paid_at=now)

    fix_module.main(dry_run=True)

    assert _get_amount_paid(target) == Decimal("0")
