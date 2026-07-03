# tests/test_behavioral_tracking_invoices.py

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

import app.services.invoice_service as invoice_service
from app.core.enums import InvoiceStatus


def _mock_invoice(status=InvoiceStatus.sent, reminder_count=0, sent_at=None, due_date=None):
    inv = MagicMock()
    inv.id = uuid.uuid4()
    inv.status = status
    inv.reminder_count = reminder_count
    inv.last_reminder_sent_at = None
    inv.sent_at = sent_at or datetime(2026, 6, 1, tzinfo=timezone.utc)
    inv.due_date = due_date
    inv.client_id = uuid.uuid4()
    inv.total_amount = Decimal("1000.00")
    inv.invoice_number = "INV-001"
    return inv


def _db_side_effects(client, firm):
    exec_client = MagicMock()
    exec_client.scalar_one_or_none.return_value = client
    exec_firm = MagicMock()
    exec_firm.scalar_one_or_none.return_value = firm
    return [exec_client, exec_firm]


# ---------------------------------------------------------------------------
# Test 1 -- send_invoice_reminder fires invoice.reminder_sent with correct metadata
# ---------------------------------------------------------------------------
def test_send_invoice_reminder_fires_reminder_sent_event():
    mock_db = MagicMock()
    mock_invoice = _mock_invoice(status=InvoiceStatus.sent, reminder_count=0)

    mock_client = MagicMock()
    mock_client.email = "client@example.com"
    mock_client.name = "Test Client"
    mock_firm = MagicMock()
    mock_firm.name = "Test Firm"

    mock_db.execute.side_effect = _db_side_effects(mock_client, mock_firm)

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=mock_invoice), \
         patch("app.services.invoice_service.log_event") as mock_log, \
         patch("app.services.email_service.EmailService"):

        result, error = invoice_service.send_invoice_reminder(
            db=mock_db,
            invoice_id=mock_invoice.id,
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert error is None
    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "invoice.reminder_sent"
    assert call_kwargs["metadata"]["reminder_number"] == 1


# ---------------------------------------------------------------------------
# Test 2 -- reminder_count incremented and last_reminder_sent_at set
# ---------------------------------------------------------------------------
def test_send_invoice_reminder_increments_count():
    mock_db = MagicMock()
    mock_invoice = _mock_invoice(status=InvoiceStatus.sent, reminder_count=0)

    mock_client = MagicMock()
    mock_client.email = "client@example.com"
    mock_client.name = "Test Client"
    mock_firm = MagicMock()
    mock_firm.name = "Test Firm"

    mock_db.execute.side_effect = _db_side_effects(mock_client, mock_firm)

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=mock_invoice), \
         patch("app.services.invoice_service.log_event"), \
         patch("app.services.email_service.EmailService"):

        invoice_service.send_invoice_reminder(
            db=mock_db,
            invoice_id=mock_invoice.id,
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert mock_invoice.reminder_count == 1
    assert mock_invoice.last_reminder_sent_at is not None


# ---------------------------------------------------------------------------
# Test 3 -- paid invoice returns already_paid without calling log_event
# ---------------------------------------------------------------------------
def test_send_invoice_reminder_already_paid_returns_error():
    mock_db = MagicMock()
    mock_invoice = _mock_invoice(status=InvoiceStatus.paid)

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=mock_invoice), \
         patch("app.services.invoice_service.log_event") as mock_log:

        result, error = invoice_service.send_invoice_reminder(
            db=mock_db,
            invoice_id=mock_invoice.id,
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert result is None
    assert error == "already_paid"
    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4 -- draft invoice returns not_sent_yet without calling log_event
# ---------------------------------------------------------------------------
def test_send_invoice_reminder_draft_returns_error():
    mock_db = MagicMock()
    mock_invoice = _mock_invoice(status=InvoiceStatus.draft)

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=mock_invoice), \
         patch("app.services.invoice_service.log_event") as mock_log:

        result, error = invoice_service.send_invoice_reminder(
            db=mock_db,
            invoice_id=mock_invoice.id,
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert result is None
    assert error == "not_sent_yet"
    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 -- client with no email returns no_client_email without calling log_event
# ---------------------------------------------------------------------------
def test_send_invoice_reminder_no_email_returns_error():
    mock_db = MagicMock()
    mock_invoice = _mock_invoice(status=InvoiceStatus.sent)

    mock_client = MagicMock()
    mock_client.email = None

    exec_client = MagicMock()
    exec_client.scalar_one_or_none.return_value = mock_client
    mock_db.execute.return_value = exec_client

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=mock_invoice), \
         patch("app.services.invoice_service.log_event") as mock_log:

        result, error = invoice_service.send_invoice_reminder(
            db=mock_db,
            invoice_id=mock_invoice.id,
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert result is None
    assert error == "no_client_email"
    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Test 6 -- mark_invoice_partial_payment fires invoice.partial_payment
# ---------------------------------------------------------------------------
def test_mark_invoice_partial_payment_fires_event():
    from app.services.invoice_service import mark_invoice_partial_payment

    mock_db = MagicMock()
    mock_invoice = _mock_invoice(status=InvoiceStatus.sent)

    with patch("app.services.invoice_service.log_event") as mock_log:
        result = mark_invoice_partial_payment(
            db=mock_db,
            invoice=mock_invoice,
            firm_id=uuid.uuid4(),
            amount_paid=500.0,
            remaining_balance=500.0,
        )

    assert result is None
    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "invoice.partial_payment"
    assert call_kwargs["metadata"]["amount_paid"] == 500.0
    assert call_kwargs["metadata"]["remaining_balance"] == 500.0


# ---------------------------------------------------------------------------
# Test 7 -- mark_invoice_refunded fires invoice.refunded
# ---------------------------------------------------------------------------
def test_mark_invoice_refunded_fires_event():
    from app.services.invoice_service import mark_invoice_refunded

    mock_db = MagicMock()
    mock_invoice = _mock_invoice(status=InvoiceStatus.paid)
    mock_invoice.paid_at = datetime(2026, 6, 15, tzinfo=timezone.utc)

    with patch("app.services.invoice_service.log_event") as mock_log:
        result = mark_invoice_refunded(
            db=mock_db,
            invoice=mock_invoice,
            firm_id=uuid.uuid4(),
            amount_refunded=250.0,
            reason="duplicate",
        )

    assert result is None
    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "invoice.refunded"
    assert call_kwargs["metadata"]["amount_refunded"] == 250.0
    assert call_kwargs["metadata"]["reason"] == "duplicate"
