# tests/test_deadline_mutation_tracking.py

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.api.engagements import bulk_update_engagements
from app.api.extensions import update_extension
from app.schemas.engagement import BulkEngagementUpdate, BulkEngagementFieldUpdate
from app.schemas.extension import ExtensionUpdate
from app.services import recurring_engagement_service


def _mock_engagement(status="in_progress", filing_deadline=None, extended_deadline=None):
    eng = MagicMock()
    eng.id = uuid.uuid4()
    eng.status = status
    eng.filing_deadline = filing_deadline
    eng.extended_deadline = extended_deadline
    return eng


def _mock_firm():
    firm = MagicMock()
    firm.id = uuid.uuid4()
    return firm


def _db_returning(engagements):
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = engagements
    return db


# ---------------------------------------------------------------------------
# Test 1 -- bulk deadline push fires engagement.deadline_changed per engagement
# ---------------------------------------------------------------------------
def test_bulk_deadline_push_fires_deadline_changed():
    eng1 = _mock_engagement(filing_deadline=date(2026, 4, 15))
    eng2 = _mock_engagement(filing_deadline=date(2026, 5, 1))
    db = _db_returning([eng1, eng2])
    firm = _mock_firm()

    payload = BulkEngagementUpdate(
        ids=[eng1.id, eng2.id],
        update=BulkEngagementFieldUpdate(deadline_push_days=7),
    )

    with patch("app.services.behavioral_log.log_event") as mock_log:
        bulk_update_engagements(payload=payload, db=db, current_firm=firm, _=None)

    assert mock_log.call_count == 2
    for call in mock_log.call_args_list:
        kwargs = call.kwargs
        assert kwargs["event_type"] == "engagement.deadline_changed"
        assert kwargs["metadata"]["via"] == "bulk"
        assert kwargs["metadata"]["push_days"] == 7

    assert eng1.filing_deadline == date(2026, 4, 22)
    assert mock_log.call_args_list[0].kwargs["metadata"]["from_filing_deadline"] == "2026-04-15"
    assert mock_log.call_args_list[0].kwargs["metadata"]["to_filing_deadline"] == "2026-04-22"


# ---------------------------------------------------------------------------
# Test 2 -- bulk status change fires engagement.status_changed
# ---------------------------------------------------------------------------
def test_bulk_status_change_fires_status_changed():
    eng = _mock_engagement(status="in_progress")
    db = _db_returning([eng])
    firm = _mock_firm()

    payload = BulkEngagementUpdate(
        ids=[eng.id],
        update=BulkEngagementFieldUpdate(status="completed"),
    )

    with patch("app.services.behavioral_log.log_event") as mock_log:
        bulk_update_engagements(payload=payload, db=db, current_firm=firm, _=None)

    assert mock_log.call_count == 1
    kwargs = mock_log.call_args.kwargs
    assert kwargs["event_type"] == "engagement.status_changed"
    assert kwargs["metadata"]["via"] == "bulk"
    assert kwargs["metadata"]["from_status"] == "in_progress"
    assert kwargs["metadata"]["to_status"] == "completed"


# ---------------------------------------------------------------------------
# Test 3 -- bulk update with no status/deadline change fires nothing
# ---------------------------------------------------------------------------
def test_bulk_no_change_fires_nothing():
    eng = _mock_engagement(status="in_progress", filing_deadline=date(2026, 4, 15))
    db = _db_returning([eng])
    firm = _mock_firm()

    payload = BulkEngagementUpdate(
        ids=[eng.id],
        update=BulkEngagementFieldUpdate(),
    )

    with patch("app.services.behavioral_log.log_event") as mock_log:
        bulk_update_engagements(payload=payload, db=db, current_firm=firm, _=None)

    mock_log.assert_not_called()


# ---------------------------------------------------------------------------
# Test 4 -- extension update with a new extended_deadline fires deadline_changed
# ---------------------------------------------------------------------------
def test_extension_update_fires_deadline_changed():
    ext = MagicMock()
    ext.id = uuid.uuid4()
    ext.engagement_id = uuid.uuid4()

    engagement = _mock_engagement(extended_deadline=date(2026, 4, 15))
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = engagement
    firm = _mock_firm()

    payload = ExtensionUpdate(extended_deadline=date(2026, 10, 15))

    with patch("app.api.extensions.crud_extension.get_extension", return_value=ext), \
         patch("app.api.extensions.crud_extension.update_extension", return_value=ext), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_extension(ext_id=ext.id, payload=payload, db=db, current_firm=firm, _=None)

    assert mock_log.call_count == 1
    kwargs = mock_log.call_args.kwargs
    assert kwargs["event_type"] == "engagement.deadline_changed"
    assert kwargs["metadata"]["via"] == "extension_update"
    assert kwargs["metadata"]["from_extended_deadline"] == "2026-04-15"
    assert kwargs["metadata"]["to_extended_deadline"] == "2026-10-15"
    assert kwargs["metadata"]["extension_id"] == str(ext.id)


# ---------------------------------------------------------------------------
# Test 5 -- extension update with the same extended_deadline fires nothing
# ---------------------------------------------------------------------------
def test_extension_update_same_deadline_fires_nothing():
    ext = MagicMock()
    ext.id = uuid.uuid4()
    ext.engagement_id = uuid.uuid4()

    same_deadline = date(2026, 4, 15)
    engagement = _mock_engagement(extended_deadline=same_deadline)
    db = MagicMock()
    db.execute.return_value.scalars.return_value.first.return_value = engagement
    firm = _mock_firm()

    payload = ExtensionUpdate(extended_deadline=same_deadline)

    with patch("app.api.extensions.crud_extension.get_extension", return_value=ext), \
         patch("app.api.extensions.crud_extension.update_extension", return_value=ext), \
         patch("app.services.behavioral_log.log_event") as mock_log:

        update_extension(ext_id=ext.id, payload=payload, db=db, current_firm=firm, _=None)

    mock_log.assert_not_called()


def _mock_template(engagement_type=None, task_templates=None, document_checklist=None):
    template = MagicMock()
    template.id = uuid.uuid4()
    template.firm_id = uuid.uuid4()
    template.recurrence_cadence = "monthly"
    template.recurrence_day = 1
    template.recurrence_month = None
    template.engagement_type = engagement_type
    template.name = "Monthly Bookkeeping"
    template.task_templates = task_templates or []
    template.document_checklist = document_checklist or []
    template.last_spawned_at = None
    return template


def _run_spawn(template):
    client = MagicMock()
    client.id = uuid.uuid4()

    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = [client]

    with patch.object(recurring_engagement_service, "SessionLocal", return_value=db), \
         patch.object(recurring_engagement_service, "list_active_recurring_templates", return_value=[template]), \
         patch.object(recurring_engagement_service, "should_spawn", return_value=True), \
         patch.object(recurring_engagement_service, "write_audit_log"), \
         patch.object(recurring_engagement_service, "log_event") as mock_log:

        recurring_engagement_service.spawn_recurring_engagements()

    return mock_log


# ---------------------------------------------------------------------------
# Test 6 -- spawned engagement with a filing_deadline fires engagement.deadline_set
# ---------------------------------------------------------------------------
def test_spawn_deadline_set_fires():
    template = _mock_template(engagement_type="1040")

    with patch.object(recurring_engagement_service, "get_filing_deadline", return_value=(12, 31)):
        mock_log = _run_spawn(template)

    deadline_set_calls = [
        call for call in mock_log.call_args_list
        if call.kwargs["event_type"] == "engagement.deadline_set"
    ]
    assert len(deadline_set_calls) == 1
    kwargs = deadline_set_calls[0].kwargs
    assert kwargs["metadata"]["via"] == "recurring_spawn"
    assert kwargs["metadata"]["deadline_type"] == "filing_deadline"


# ---------------------------------------------------------------------------
# Test 7 -- spawned engagement with no filing_deadline does not fire deadline_set
# ---------------------------------------------------------------------------
def test_spawn_no_deadline_fires_no_deadline_set():
    template = _mock_template(engagement_type=None)

    mock_log = _run_spawn(template)

    deadline_set_calls = [
        call for call in mock_log.call_args_list
        if call.kwargs["event_type"] == "engagement.deadline_set"
    ]
    assert len(deadline_set_calls) == 0

    spawned_calls = [
        call for call in mock_log.call_args_list
        if call.kwargs["event_type"] == "engagement.recurring_spawned"
    ]
    assert len(spawned_calls) == 1
