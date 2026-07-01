# tests/test_dark_zone_wiring.py

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.api.tasks import bulk_update_tasks
from app.api.engagements import bulk_create_engagements
from app.schemas.task import BulkTaskUpdate, BulkTaskFieldUpdate, TaskStatus
from app.schemas.engagement import BulkEngagementCreate
from app.services.anniversary_service import check_document_expiries, check_client_anniversaries


def _mock_task(status=TaskStatus.TODO, assigned_to=None, due_date=None):
    task = MagicMock()
    task.id = uuid.uuid4()
    task.status = status
    task.assigned_to = assigned_to
    task.due_date = due_date
    return task


def _mock_firm():
    firm = MagicMock()
    firm.id = uuid.uuid4()
    return firm


def _mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


# ---------------------------------------------------------------------------
# Test 1 -- bulk task status change fires task.status_changed with via="bulk"
# ---------------------------------------------------------------------------
def test_bulk_task_status_change_fires():
    task = _mock_task(status=TaskStatus.TODO)
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [task]
    current_firm = _mock_firm()

    payload = BulkTaskUpdate(ids=[task.id], update=BulkTaskFieldUpdate(status=TaskStatus.DONE))

    with patch("app.services.behavioral_log.log_event") as mock_log:
        bulk_update_tasks(payload=payload, db=mock_db, current_firm=current_firm, _=None)

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "task.status_changed" in event_types
    status_call = next(c for c in mock_log.call_args_list if c.kwargs["event_type"] == "task.status_changed")
    assert status_call.kwargs["metadata"]["via"] == "bulk"


# ---------------------------------------------------------------------------
# Test 2 -- bulk task assignment change fires task.assigned with via="bulk"
# ---------------------------------------------------------------------------
def test_bulk_task_assignment_fires():
    old_assignee = uuid.uuid4()
    new_assignee = uuid.uuid4()
    task = _mock_task(assigned_to=old_assignee)
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [task]
    current_firm = _mock_firm()

    payload = BulkTaskUpdate(ids=[task.id], update=BulkTaskFieldUpdate(assigned_to=new_assignee))

    with patch("app.services.behavioral_log.log_event") as mock_log:
        bulk_update_tasks(payload=payload, db=mock_db, current_firm=current_firm, _=None)

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "task.assigned" in event_types
    assigned_call = next(c for c in mock_log.call_args_list if c.kwargs["event_type"] == "task.assigned")
    assert assigned_call.kwargs["metadata"]["via"] == "bulk"


# ---------------------------------------------------------------------------
# Test 3 -- bulk task update with unchanged values fires nothing
# ---------------------------------------------------------------------------
def test_bulk_task_no_change_fires_nothing():
    same_assignee = uuid.uuid4()
    same_due_date = date.today() + timedelta(days=10)
    task = _mock_task(status=TaskStatus.TODO, assigned_to=same_assignee, due_date=same_due_date)
    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [task]
    current_firm = _mock_firm()

    payload = BulkTaskUpdate(
        ids=[task.id],
        update=BulkTaskFieldUpdate(status=TaskStatus.TODO, assigned_to=same_assignee, due_date=same_due_date),
    )

    with patch("app.services.behavioral_log.log_event") as mock_log:
        bulk_update_tasks(payload=payload, db=mock_db, current_firm=current_firm, _=None)

    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4 -- bulk create engagement with filing_deadline fires created + deadline_set
# ---------------------------------------------------------------------------
def test_bulk_create_engagement_fires_created_and_deadline():
    client_id = uuid.uuid4()
    mock_client = MagicMock()
    mock_client.id = client_id

    deadline = date.today() + timedelta(days=45)
    mock_engagement = MagicMock()
    mock_engagement.id = uuid.uuid4()
    mock_engagement.engagement_type = None
    mock_engagement.client_id = client_id
    mock_engagement.filing_deadline = deadline

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.first.return_value = mock_client
    current_firm = _mock_firm()
    current_user = _mock_user()

    payload = BulkEngagementCreate(client_ids=[client_id], name="Bulk Eng", filing_deadline=deadline)

    with patch("app.crud.engagement.create_engagement", return_value=mock_engagement), \
         patch("app.services.audit_service.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        bulk_create_engagements(payload=payload, db=mock_db, current_firm=current_firm, current_user=current_user, _=None)

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "engagement.created" in event_types
    assert "engagement.deadline_set" in event_types
    for c in mock_log.call_args_list:
        assert c.kwargs["metadata"]["via"] == "bulk_create"


# ---------------------------------------------------------------------------
# Test 5 -- bulk create engagement without filing_deadline fires created only
# ---------------------------------------------------------------------------
def test_bulk_create_no_deadline_no_deadline_set():
    client_id = uuid.uuid4()
    mock_client = MagicMock()
    mock_client.id = client_id

    mock_engagement = MagicMock()
    mock_engagement.id = uuid.uuid4()
    mock_engagement.engagement_type = None
    mock_engagement.client_id = client_id
    mock_engagement.filing_deadline = None

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.first.return_value = mock_client
    current_firm = _mock_firm()
    current_user = _mock_user()

    payload = BulkEngagementCreate(client_ids=[client_id], name="Bulk Eng No Deadline")

    with patch("app.crud.engagement.create_engagement", return_value=mock_engagement), \
         patch("app.services.audit_service.write_audit_log"), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        bulk_create_engagements(payload=payload, db=mock_db, current_firm=current_firm, current_user=current_user, _=None)

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "engagement.created" in event_types
    assert "engagement.deadline_set" not in event_types


# ---------------------------------------------------------------------------
# Test 6 -- document expiry scheduler fires document_expiry.alerted
# ---------------------------------------------------------------------------
def test_document_expiry_alert_fires():
    firm_id = uuid.uuid4()
    client_id = uuid.uuid4()

    mock_expiry = MagicMock()
    mock_expiry.firm_id = firm_id
    mock_expiry.client_id = client_id
    mock_expiry.document_type = "passport"
    mock_expiry.expires_on = date.today() + timedelta(days=15)
    mock_expiry.expiry_notification_sent = False

    mock_recipient = MagicMock()

    mock_db = MagicMock()
    mock_db.execute.return_value.scalars.return_value.all.return_value = [mock_recipient]

    with patch("app.db.session.SessionLocal", return_value=mock_db), \
         patch("app.crud.document_expiry.get_expiring_soon", return_value=[mock_expiry]), \
         patch("app.services.notification_service.NotificationService.create_notification"), \
         patch("app.services.anniversary_service.log_event") as mock_log:

        check_document_expiries()

    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "document_expiry.alerted"
    assert call_kwargs["firm_id"] == firm_id
    assert call_kwargs["entity_id"] == client_id
    assert call_kwargs["metadata"]["recipient_count"] == 1
    assert mock_expiry.expiry_notification_sent is True


# ---------------------------------------------------------------------------
# Test 7 -- client dormancy scheduler fires client.dormancy_alerted
# ---------------------------------------------------------------------------
def test_client_dormancy_alert_fires():
    firm_id = uuid.uuid4()
    client_id = uuid.uuid4()

    mock_client = MagicMock()
    mock_client.id = client_id
    mock_client.firm_id = firm_id
    mock_client.name = "Dormant Client"

    last_engagement = datetime.now(timezone.utc) - timedelta(days=305)
    mock_recipient = MagicMock()

    flagged_result = MagicMock()
    flagged_result.all.return_value = [(mock_client, last_engagement)]

    recipients_result = MagicMock()
    recipients_result.scalars.return_value.all.return_value = [mock_recipient]

    mock_db = MagicMock()
    mock_db.execute.side_effect = [flagged_result, recipients_result]

    with patch("app.services.anniversary_service.SessionLocal", return_value=mock_db), \
         patch("app.services.notification_service.NotificationService.create_notification"), \
         patch("app.services.anniversary_service.log_event") as mock_log:

        check_client_anniversaries()

    assert mock_log.called
    call_kwargs = mock_log.call_args.kwargs
    assert call_kwargs["event_type"] == "client.dormancy_alerted"
    assert call_kwargs["firm_id"] == firm_id
    assert call_kwargs["entity_id"] == client_id
    assert call_kwargs["metadata"]["recipient_count"] == 1
