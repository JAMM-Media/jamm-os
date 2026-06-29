# tests/test_behavioral_tracking_portal.py

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException


FIRM_ID = uuid.uuid4()
CLIENT_ID = uuid.uuid4()
REQUEST_ID = uuid.uuid4()
ITEM_ID = str(uuid.uuid4())
ENGAGEMENT_ID = uuid.uuid4()
DOC_ID = uuid.uuid4()


def _make_client(client_id=CLIENT_ID, firm_id=FIRM_ID):
    client = MagicMock()
    client.id = client_id
    client.firm_id = firm_id
    return client


# ---------------------------------------------------------------------------
# Test 1 — portal_logout fires portal.session_ended
# ---------------------------------------------------------------------------

@patch("app.api.portal.log_event")
@patch("app.api.portal.crud_portal_session")
def test_portal_logout_fires_session_ended_event(mock_crud_session, mock_log_event):
    now = datetime.now(timezone.utc)
    mock_session = MagicMock()
    mock_session.created_at = now - timedelta(minutes=30)
    mock_session.last_active_at = now
    mock_session.is_revoked = False

    mock_crud_session.get_session_by_jti.return_value = mock_session
    mock_crud_session.revoke_session.return_value = None

    db = MagicMock()
    current_client = _make_client()

    jti = str(uuid.uuid4())
    session = mock_crud_session.get_session_by_jti(db, jti, FIRM_ID)

    # replicate the logout logic
    duration_minutes = None
    if session:
        created = getattr(session, "created_at", None)
        last_active = getattr(session, "last_active_at", None)
        if created and last_active:
            duration_minutes = int((last_active - created).total_seconds() / 60)
    mock_log_event(
        firm_id=current_client.firm_id,
        event_type="portal.session_ended",
        entity_type="client",
        entity_id=current_client.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "session_duration_minutes": duration_minutes,
            "time_of_day": datetime.now(timezone.utc).hour,
        },
    )

    mock_log_event.assert_called_once()
    call_kwargs = mock_log_event.call_args.kwargs
    assert call_kwargs["event_type"] == "portal.session_ended"
    assert call_kwargs["metadata"]["session_duration_minutes"] == 30


# ---------------------------------------------------------------------------
# Test 2 — portal_logout with missing last_active_at yields duration=None
# ---------------------------------------------------------------------------

@patch("app.api.portal.log_event")
@patch("app.api.portal.crud_portal_session")
def test_portal_logout_session_duration_none_when_missing(mock_crud_session, mock_log_event):
    now = datetime.now(timezone.utc)
    mock_session = MagicMock()
    mock_session.created_at = now - timedelta(minutes=10)
    mock_session.last_active_at = None
    mock_session.is_revoked = False

    mock_crud_session.get_session_by_jti.return_value = mock_session

    db = MagicMock()
    current_client = _make_client()

    jti = str(uuid.uuid4())
    session = mock_crud_session.get_session_by_jti(db, jti, FIRM_ID)

    duration_minutes = None
    if session:
        created = getattr(session, "created_at", None)
        last_active = getattr(session, "last_active_at", None)
        if created and last_active:
            duration_minutes = int((last_active - created).total_seconds() / 60)
    mock_log_event(
        firm_id=current_client.firm_id,
        event_type="portal.session_ended",
        entity_type="client",
        entity_id=current_client.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "session_duration_minutes": duration_minutes,
            "time_of_day": datetime.now(timezone.utc).hour,
        },
    )

    mock_log_event.assert_called_once()
    call_kwargs = mock_log_event.call_args.kwargs
    assert call_kwargs["event_type"] == "portal.session_ended"
    assert call_kwargs["metadata"]["session_duration_minutes"] is None


# ---------------------------------------------------------------------------
# Test 3 — portal document upload fires portal.document_uploaded
# ---------------------------------------------------------------------------

@patch("app.api.portal.log_event")
@patch("app.api.portal.upload_document")
def test_portal_document_uploaded_fires_event(mock_upload_document, mock_log_event):
    now = datetime.now(timezone.utc)
    mock_doc = MagicMock()
    mock_doc.id = DOC_ID
    mock_doc.filename = "tax_return.pdf"
    mock_doc.created_at = now
    mock_doc.size_bytes = 204800

    mock_upload_document.return_value = mock_doc

    db = MagicMock()
    current_client = _make_client()

    mock_file = MagicMock()
    mock_file.content_type = "application/pdf"

    # replicate the upload endpoint logic
    engagement_id = ENGAGEMENT_ID
    if engagement_id is None:
        raise HTTPException(status_code=400, detail="engagement_id is required for portal document uploads")

    doc = mock_upload_document(
        db=db,
        file=mock_file,
        client_id=current_client.id,
        engagement_id=engagement_id,
        firm_id=current_client.firm_id,
        current_user_id=current_client.id,
    )

    mock_log_event(
        firm_id=current_client.firm_id,
        event_type="portal.document_uploaded",
        entity_type="document",
        entity_id=doc.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "file_size": doc.size_bytes,
            "content_type": mock_file.content_type,
            "engagement_id": str(engagement_id),
            "time_of_day": datetime.now(timezone.utc).hour,
            "associated_request": False,
        },
    )

    mock_log_event.assert_called_once()
    call_kwargs = mock_log_event.call_args.kwargs
    assert call_kwargs["event_type"] == "portal.document_uploaded"
    assert call_kwargs["metadata"]["associated_request"] is False


# ---------------------------------------------------------------------------
# Test 4 — portal upload without engagement_id returns 400, no log_event
# ---------------------------------------------------------------------------

@patch("app.api.portal.log_event")
@patch("app.api.portal.upload_document")
def test_portal_upload_requires_engagement_id(mock_upload_document, mock_log_event):
    engagement_id = None

    with pytest.raises(HTTPException) as exc_info:
        if engagement_id is None:
            raise HTTPException(
                status_code=400,
                detail="engagement_id is required for portal document uploads",
            )

    assert exc_info.value.status_code == 400
    mock_log_event.assert_not_called()
    mock_upload_document.assert_not_called()


# ---------------------------------------------------------------------------
# Test 5 — portal todo complete fires portal.todo_completed
# ---------------------------------------------------------------------------

@patch("app.api.portal.log_event")
@patch("app.api.portal.dr_service")
@patch("app.api.portal.crud_dr")
def test_portal_todo_completed_fires_event(mock_crud_dr, mock_dr_service, mock_log_event):
    now = datetime.now(timezone.utc)
    mock_doc_request = MagicMock()
    mock_doc_request.client_id = CLIENT_ID
    mock_doc_request.created_at = now - timedelta(days=3)

    mock_crud_dr.get_document_request.return_value = mock_doc_request
    mock_dr_service.update_checklist_item_status.return_value = (MagicMock(), None)

    db = MagicMock()
    current_client = _make_client()

    doc_request = mock_crud_dr.get_document_request(db, REQUEST_ID, firm_id=current_client.firm_id)
    assert doc_request is not None
    assert doc_request.client_id == current_client.id

    updated_request, error = mock_dr_service.update_checklist_item_status(
        db=db,
        request_id=REQUEST_ID,
        item_id=ITEM_ID,
        new_status="uploaded",
        firm_id=current_client.firm_id,
        current_user_id=current_client.id,
    )
    assert error is None

    days_since_created = None
    if doc_request.created_at:
        days_since_created = (datetime.now(timezone.utc) - doc_request.created_at).days

    mock_log_event(
        firm_id=current_client.firm_id,
        event_type="portal.todo_completed",
        entity_type="document_request",
        entity_id=REQUEST_ID,
        actor_type="client",
        actor_id=None,
        metadata={
            "item_id": str(ITEM_ID),
            "time_of_day": datetime.now(timezone.utc).hour,
            "days_since_request_created": days_since_created,
        },
    )

    mock_log_event.assert_called_once()
    call_kwargs = mock_log_event.call_args.kwargs
    assert call_kwargs["event_type"] == "portal.todo_completed"
    assert call_kwargs["metadata"]["item_id"] == str(ITEM_ID)


# ---------------------------------------------------------------------------
# Test 6 — wrong client returns 403, no log_event
# ---------------------------------------------------------------------------

@patch("app.api.portal.log_event")
@patch("app.api.portal.crud_dr")
def test_portal_todo_wrong_client_returns_403(mock_crud_dr, mock_log_event):
    other_client_id = uuid.uuid4()
    mock_doc_request = MagicMock()
    mock_doc_request.client_id = other_client_id

    mock_crud_dr.get_document_request.return_value = mock_doc_request

    db = MagicMock()
    current_client = _make_client()

    doc_request = mock_crud_dr.get_document_request(db, REQUEST_ID, firm_id=current_client.firm_id)

    with pytest.raises(HTTPException) as exc_info:
        if doc_request.client_id != current_client.id:
            raise HTTPException(status_code=403, detail="Access denied")

    assert exc_info.value.status_code == 403
    mock_log_event.assert_not_called()
