# tests/test_behavioral_tracking_documents.py

import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.document_service import download_document, view_document
from app.services.document_request_service import send_document_request_reminder


def _mock_doc():
    doc = MagicMock()
    doc.id = uuid.uuid4()
    doc.s3_key = "firm/client/engagement/doc/test.pdf"
    doc.filename = "test.pdf"
    doc.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return doc


def _mock_doc_request(status="pending", reminder_count=0, last_reminder=None, client_id=None):
    dr = MagicMock()
    dr.status = status
    dr.reminder_count = reminder_count
    dr.last_reminder_sent_at = last_reminder
    dr.client_id = client_id or uuid.uuid4()
    dr.checklist_items = [{"id": "item-1", "label": "W2"}]
    dr.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dr.engagement_id = uuid.uuid4()
    return dr


def _reminder_db_side_effects(client, firm):
    mock_exec_client = MagicMock()
    mock_exec_client.scalar_one_or_none.return_value = client
    mock_exec_firm = MagicMock()
    mock_exec_firm.scalar_one_or_none.return_value = firm
    mock_exec_engagement = MagicMock()
    mock_exec_engagement.scalar_one_or_none.return_value = None
    return [mock_exec_client, mock_exec_firm, mock_exec_engagement]


# ---------------------------------------------------------------------------
# Test 1 -- download_document fires document.downloaded, not document.viewed
# ---------------------------------------------------------------------------
def test_download_document_fires_downloaded_event():
    mock_db = MagicMock()
    mock_doc = _mock_doc()

    with patch("app.services.document_service.crud_document.get_document", return_value=mock_doc), \
         patch("app.services.document_service.s3_service.generate_presigned_url", return_value="https://s3.example.com/signed"), \
         patch("app.services.document_service.crud_document.write_audit_log"), \
         patch("app.services.document_service.write_audit_log"), \
         patch("app.services.document_service.log_event") as mock_log:

        result_doc, result_url = download_document(
            db=mock_db,
            document_id=mock_doc.id,
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert mock_log.called
    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "document.downloaded" in event_types
    assert "document.viewed" not in event_types


# ---------------------------------------------------------------------------
# Test 2 -- view_document fires document.viewed, not document.downloaded
# ---------------------------------------------------------------------------
def test_view_document_fires_viewed_event():
    mock_db = MagicMock()
    mock_doc = _mock_doc()

    with patch("app.services.document_service.crud_document.get_document", return_value=mock_doc), \
         patch("app.services.document_service.crud_document.write_audit_log"), \
         patch("app.services.document_service.write_audit_log"), \
         patch("app.services.document_service.log_event") as mock_log:

        result = view_document(
            db=mock_db,
            document_id=mock_doc.id,
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert mock_log.called
    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "document.viewed" in event_types
    assert "document.downloaded" not in event_types


# ---------------------------------------------------------------------------
# Test 3 -- send_reminder fires document_request.reminder_sent with correct metadata
# ---------------------------------------------------------------------------
def test_send_reminder_fires_reminder_sent_event():
    mock_db = MagicMock()
    mock_dr = _mock_doc_request(status="pending", reminder_count=0)

    mock_client = MagicMock()
    mock_client.email = "client@example.com"
    mock_client.name = "Test Client"
    mock_firm = MagicMock()
    mock_firm.name = "Test Firm"

    mock_db.execute.side_effect = _reminder_db_side_effects(mock_client, mock_firm)

    with patch("app.services.document_request_service.crud.get_document_request", return_value=mock_dr), \
         patch("app.services.document_request_service.log_event") as mock_log, \
         patch("app.services.email_service.EmailService"):

        result_dr, error = send_document_request_reminder(
            db=mock_db,
            request_id=uuid.uuid4(),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert error is None
    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "document_request.reminder_sent"
    assert call_kwargs["metadata"]["reminder_number"] == 1


# ---------------------------------------------------------------------------
# Test 4 -- already completed returns error without calling log_event
# ---------------------------------------------------------------------------
def test_send_reminder_already_completed_returns_error():
    mock_db = MagicMock()
    mock_dr = _mock_doc_request(status="completed")

    with patch("app.services.document_request_service.crud.get_document_request", return_value=mock_dr), \
         patch("app.services.document_request_service.log_event") as mock_log:

        result, error = send_document_request_reminder(
            db=mock_db,
            request_id=uuid.uuid4(),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert result is None
    assert error == "already_completed"
    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 -- reminder_count incremented and last_reminder_sent_at set
# ---------------------------------------------------------------------------
def test_send_reminder_increments_reminder_count():
    mock_db = MagicMock()
    mock_dr = _mock_doc_request(status="pending", reminder_count=0, last_reminder=None)

    mock_client = MagicMock()
    mock_client.email = "client@example.com"
    mock_client.name = "Test Client"
    mock_firm = MagicMock()
    mock_firm.name = "Test Firm"

    mock_db.execute.side_effect = _reminder_db_side_effects(mock_client, mock_firm)

    with patch("app.services.document_request_service.crud.get_document_request", return_value=mock_dr), \
         patch("app.services.document_request_service.log_event"), \
         patch("app.services.email_service.EmailService"):

        send_document_request_reminder(
            db=mock_db,
            request_id=uuid.uuid4(),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    assert mock_dr.reminder_count == 1
    assert mock_dr.last_reminder_sent_at is not None
    assert isinstance(mock_dr.last_reminder_sent_at, datetime)
