# tests/test_invoice_update_tracking.py

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import app.services.invoice_service as invoice_service
from app.core.enums import InvoiceStatus
from app.schemas.invoice import InvoiceUpdate


def _mock_invoice(status=InvoiceStatus.sent, total_amount=Decimal("100.00"), due_date=None):
    inv = MagicMock()
    inv.id = uuid.uuid4()
    inv.firm_id = uuid.uuid4()
    inv.client_id = uuid.uuid4()
    inv.status = status
    inv.total_amount = total_amount
    inv.due_date = due_date
    return inv


# ---------------------------------------------------------------------------
# Test 1 -- status change fires invoice.status_changed with correct from/to
# ---------------------------------------------------------------------------
def test_status_change_fires_event():
    mock_db = MagicMock()
    inv = _mock_invoice(status=InvoiceStatus.sent, total_amount=Decimal("100.00"), due_date=date(2026, 1, 1))
    updated = _mock_invoice(status=InvoiceStatus.void, total_amount=Decimal("100.00"), due_date=date(2026, 1, 1))
    updated.id = inv.id
    updated.client_id = inv.client_id

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=inv), \
         patch("app.services.invoice_service.crud_invoice.update_invoice", return_value=updated), \
         patch("app.services.invoice_service.log_event") as mock_log:

        result, error = invoice_service.update_invoice_tracked(
            db=mock_db,
            invoice_id=inv.id,
            payload=InvoiceUpdate(status=InvoiceStatus.void),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert error is None
    assert result is updated
    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "invoice.status_changed" in event_types
    status_call = next(c for c in mock_log.call_args_list if c.kwargs["event_type"] == "invoice.status_changed")
    assert status_call.kwargs["metadata"]["from_status"] == str(InvoiceStatus.sent)
    assert status_call.kwargs["metadata"]["to_status"] == str(InvoiceStatus.void)


# ---------------------------------------------------------------------------
# Test 2 -- total_amount change fires invoice.amount_changed with from/to
# ---------------------------------------------------------------------------
def test_amount_change_fires_event():
    mock_db = MagicMock()
    inv = _mock_invoice(status=InvoiceStatus.draft, total_amount=Decimal("100.00"))
    updated = _mock_invoice(status=InvoiceStatus.draft, total_amount=Decimal("200.00"))
    updated.id = inv.id
    updated.client_id = inv.client_id

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=inv), \
         patch("app.services.invoice_service.crud_invoice.update_invoice", return_value=updated), \
         patch("app.services.invoice_service.log_event") as mock_log:

        result, error = invoice_service.update_invoice_tracked(
            db=mock_db,
            invoice_id=inv.id,
            payload=InvoiceUpdate(total_amount=Decimal("200.00")),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert error is None
    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "invoice.amount_changed" in event_types
    amount_call = next(c for c in mock_log.call_args_list if c.kwargs["event_type"] == "invoice.amount_changed")
    assert amount_call.kwargs["metadata"]["from_amount"] == "100.0"
    assert amount_call.kwargs["metadata"]["to_amount"] == "200.0"


# ---------------------------------------------------------------------------
# Test 3 -- non-tracked field change fires none of the three tracked events
# ---------------------------------------------------------------------------
def test_no_meaningful_change_fires_nothing():
    mock_db = MagicMock()
    inv = _mock_invoice(status=InvoiceStatus.draft, total_amount=Decimal("100.00"), due_date=date(2026, 1, 1))
    updated = _mock_invoice(status=InvoiceStatus.draft, total_amount=Decimal("100.00"), due_date=date(2026, 1, 1))
    updated.id = inv.id
    updated.client_id = inv.client_id

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=inv), \
         patch("app.services.invoice_service.crud_invoice.update_invoice", return_value=updated), \
         patch("app.services.invoice_service.log_event") as mock_log:

        result, error = invoice_service.update_invoice_tracked(
            db=mock_db,
            invoice_id=inv.id,
            payload=InvoiceUpdate(notes="Updated notes only"),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert error is None
    tracked = {"invoice.status_changed", "invoice.amount_changed", "invoice.due_date_changed"}
    fired = {c.kwargs["event_type"] for c in mock_log.call_args_list}
    assert not tracked.intersection(fired)


# ---------------------------------------------------------------------------
# Test 4 -- paid invoice returns (None, "locked") and no event fires
# ---------------------------------------------------------------------------
def test_locked_invoice_returns_error():
    mock_db = MagicMock()
    inv = _mock_invoice(status=InvoiceStatus.paid)

    with patch("app.services.invoice_service.crud_invoice.get_invoice", return_value=inv), \
         patch("app.services.invoice_service.log_event") as mock_log:

        result, error = invoice_service.update_invoice_tracked(
            db=mock_db,
            invoice_id=inv.id,
            payload=InvoiceUpdate(status=InvoiceStatus.sent),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert result is None
    assert error == "locked"
    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 -- bulk send fires invoice.status_changed once per invoice with via="bulk"
# ---------------------------------------------------------------------------
def test_bulk_send_fires_per_invoice():
    invoices = [_mock_invoice(status=InvoiceStatus.draft) for _ in range(3)]
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = invoices

    with patch("app.services.invoice_service.log_event") as mock_log:
        count, error = invoice_service.bulk_update_invoices_tracked(
            db=mock_db,
            ids=[inv.id for inv in invoices],
            action="send",
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert error is None
    assert count == 3
    assert mock_log.call_count == 3
    for call in mock_log.call_args_list:
        assert call.kwargs["event_type"] == "invoice.status_changed"
        assert call.kwargs["metadata"]["via"] == "bulk"
        assert call.kwargs["metadata"]["bulk_action"] == "send"


# ---------------------------------------------------------------------------
# Test 6 -- bad action returns (None, "bad_action") and no event fires
# ---------------------------------------------------------------------------
def test_bulk_bad_action_returns_error():
    mock_db = MagicMock()

    with patch("app.services.invoice_service.log_event") as mock_log:
        count, error = invoice_service.bulk_update_invoices_tracked(
            db=mock_db,
            ids=[],
            action="delete",
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert count is None
    assert error == "bad_action"
    mock_log.assert_not_called()
