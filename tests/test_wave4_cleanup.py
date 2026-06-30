# tests/test_wave4_cleanup.py

import uuid
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.document_request_service import (
    update_checklist_item_status,
    update_document_request,
)
from app.services.engagement_service import update_complexity_flags


def _mock_doc_request(item_id="item-1", item_status="pending"):
    dr = MagicMock()
    dr.id = uuid.uuid4()
    dr.firm_id = uuid.uuid4()
    dr.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    dr.checklist_items = [{"id": item_id, "label": "W2", "status": item_status}]
    return dr


# ---------------------------------------------------------------------------
# Test 1 -- "approved" transition fires document_request.item_approved
# ---------------------------------------------------------------------------
def test_approved_fires_item_approved():
    mock_db = MagicMock()
    mock_dr = _mock_doc_request()
    mock_updated = MagicMock()

    with patch("app.services.document_request_service.crud.get_document_request", return_value=mock_dr), \
         patch("app.services.document_request_service.crud.update_checklist_item_status", return_value=mock_updated), \
         patch("app.services.document_request_service.log_event") as mock_log:

        result, error = update_checklist_item_status(
            db=mock_db,
            request_id=mock_dr.id,
            item_id="item-1",
            new_status="approved",
            firm_id=mock_dr.firm_id,
            current_user_id=uuid.uuid4(),
        )

    assert error is None
    assert mock_log.called
    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "document_request.item_approved" in event_types


# ---------------------------------------------------------------------------
# Test 2 -- item_approved only fires for "approved", not other transitions
# ---------------------------------------------------------------------------
def test_approved_only_fires_for_approved():
    mock_db = MagicMock()
    mock_dr = _mock_doc_request()
    mock_updated = MagicMock()

    with patch("app.services.document_request_service.crud.get_document_request", return_value=mock_dr), \
         patch("app.services.document_request_service.crud.update_checklist_item_status", return_value=mock_updated), \
         patch("app.services.document_request_service.log_event") as mock_log:

        update_checklist_item_status(
            db=mock_db,
            request_id=mock_dr.id,
            item_id="item-1",
            new_status="pending",
            firm_id=mock_dr.firm_id,
            current_user_id=uuid.uuid4(),
        )

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "document_request.item_approved" not in event_types


# ---------------------------------------------------------------------------
# Test 3 -- due date change fires document_request.due_date_changed with from/to
# ---------------------------------------------------------------------------
def test_due_date_change_fires_event():
    mock_db = MagicMock()
    old_request = MagicMock()
    old_request.status = "pending"
    old_request.due_date = date(2026, 1, 1)

    updated_request = MagicMock()
    updated_request.id = uuid.uuid4()
    updated_request.firm_id = uuid.uuid4()
    updated_request.status = "pending"
    updated_request.due_date = date(2026, 2, 1)
    updated_request.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    updated_request.checklist_items = []

    with patch("app.services.document_request_service.crud.get_document_request", return_value=old_request), \
         patch("app.services.document_request_service.crud.update_document_request", return_value=updated_request), \
         patch("app.services.document_request_service.log_event") as mock_log:

        update_document_request(
            db=mock_db,
            request_id=uuid.uuid4(),
            payload=MagicMock(),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "document_request.due_date_changed" in event_types

    due_date_call = next(
        c for c in mock_log.call_args_list
        if c.kwargs["event_type"] == "document_request.due_date_changed"
    )
    assert due_date_call.kwargs["metadata"]["from_due_date"] == "2026-01-01"
    assert due_date_call.kwargs["metadata"]["to_due_date"] == "2026-02-01"


# ---------------------------------------------------------------------------
# Test 4 -- unchanged due date fires nothing
# ---------------------------------------------------------------------------
def test_due_date_unchanged_fires_nothing():
    mock_db = MagicMock()
    old_request = MagicMock()
    old_request.status = "pending"
    old_request.due_date = date(2026, 1, 1)

    updated_request = MagicMock()
    updated_request.id = uuid.uuid4()
    updated_request.firm_id = uuid.uuid4()
    updated_request.status = "pending"
    updated_request.due_date = date(2026, 1, 1)
    updated_request.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    updated_request.checklist_items = []

    with patch("app.services.document_request_service.crud.get_document_request", return_value=old_request), \
         patch("app.services.document_request_service.crud.update_document_request", return_value=updated_request), \
         patch("app.services.document_request_service.log_event") as mock_log:

        update_document_request(
            db=mock_db,
            request_id=uuid.uuid4(),
            payload=MagicMock(),
            firm_id=uuid.uuid4(),
            current_user_id=uuid.uuid4(),
        )

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "document_request.due_date_changed" not in event_types


# ---------------------------------------------------------------------------
# Test 5 -- complexity flags update captures both from_flags and to_flags
# ---------------------------------------------------------------------------
def test_complexity_flags_captures_old():
    mock_db = MagicMock()
    mock_engagement = MagicMock()
    mock_engagement.id = uuid.uuid4()
    mock_engagement.engagement_type = "1040"
    mock_engagement.complexity_flags = {"multi_state": False}

    with patch("app.services.engagement_service.crud_engagement.get_engagement_for_firm", return_value=mock_engagement), \
         patch("app.services.engagement_service.log_event") as mock_log:

        update_complexity_flags(
            db=mock_db,
            engagement_id=mock_engagement.id,
            firm_id=uuid.uuid4(),
            flags={"multi_state": True, "k1_count": 3},
            current_user_id=uuid.uuid4(),
        )

    assert mock_log.called
    metadata = mock_log.call_args.kwargs["metadata"]
    assert metadata["from_flags"] == {"multi_state": False}
    assert metadata["to_flags"] == {"multi_state": True, "k1_count": 3}
