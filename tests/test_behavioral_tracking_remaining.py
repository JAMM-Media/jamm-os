# tests/test_behavioral_tracking_remaining.py

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.engagement_service import create_engagement, update_engagement
from app.services.irs_auth_service import (
    check_expiring_authorizations,
    mark_authorization_expired,
    mark_authorization_renewed,
)


def _mock_engagement(status="in_progress", filing_deadline=None, engagement_type="1040"):
    eng = MagicMock()
    eng.id = uuid.uuid4()
    eng.firm_id = uuid.uuid4()
    eng.client_id = uuid.uuid4()
    eng.status = status
    eng.filing_deadline = filing_deadline
    eng.engagement_type = engagement_type
    eng.assigned_to = None
    eng.created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return eng


def _mock_authorization(valid_until=None, form_type="8821"):
    auth = MagicMock()
    auth.id = uuid.uuid4()
    auth.firm_id = uuid.uuid4()
    auth.client_id = uuid.uuid4()
    auth.form_type = form_type
    auth.valid_until = valid_until
    return auth


# ---------------------------------------------------------------------------
# Test 1 -- deadline_set fires when filing_deadline is present
# ---------------------------------------------------------------------------
def test_deadline_set_fires_when_filing_deadline_present():
    future_date = date.today() + timedelta(days=30)
    mock_engagement = _mock_engagement(filing_deadline=future_date)

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.return_value = 5

    with patch("app.services.engagement_service.crud_engagement.create_engagement", return_value=mock_engagement), \
         patch("app.services.engagement_service.populate_from_template"), \
         patch("app.services.engagement_service.emit_event", new_callable=AsyncMock), \
         patch("app.services.engagement_service.log_event") as mock_log:

        asyncio.run(create_engagement(
            db=mock_db,
            payload=MagicMock(),
            firm_id=mock_engagement.firm_id,
            current_user_id=uuid.uuid4(),
            background_tasks=MagicMock(),
        ))

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "engagement.deadline_set" in event_types


# ---------------------------------------------------------------------------
# Test 2 -- deadline_set does NOT fire when filing_deadline is None
# ---------------------------------------------------------------------------
def test_deadline_set_does_not_fire_when_no_deadline():
    mock_engagement = _mock_engagement(filing_deadline=None)

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.return_value = 5

    with patch("app.services.engagement_service.crud_engagement.create_engagement", return_value=mock_engagement), \
         patch("app.services.engagement_service.populate_from_template"), \
         patch("app.services.engagement_service.emit_event", new_callable=AsyncMock), \
         patch("app.services.engagement_service.log_event") as mock_log:

        asyncio.run(create_engagement(
            db=mock_db,
            payload=MagicMock(),
            firm_id=mock_engagement.firm_id,
            current_user_id=uuid.uuid4(),
            background_tasks=MagicMock(),
        ))

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "engagement.deadline_set" not in event_types


# ---------------------------------------------------------------------------
# Test 3 -- engagement.reopened fires on completed -> in_progress
# ---------------------------------------------------------------------------
def test_engagement_reopened_fires_on_completed_to_in_progress():
    old_eng = _mock_engagement(status="completed")
    updated_eng = _mock_engagement(status="in_progress", engagement_type=old_eng.engagement_type)
    updated_eng.firm_id = old_eng.firm_id
    updated_eng.id = old_eng.id
    updated_eng.created_at = old_eng.created_at

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.return_value = 0

    mock_payload = MagicMock()
    mock_payload.status = "in_progress"
    mock_payload.extended_deadline = None
    mock_payload.model_dump.return_value = {}

    with patch("app.services.engagement_service.crud_engagement.get_engagement_for_firm", return_value=old_eng), \
         patch("app.services.engagement_service.crud_engagement.update_engagement", return_value=updated_eng), \
         patch("app.services.engagement_service.emit_event", new_callable=AsyncMock), \
         patch("app.services.engagement_service.log_event") as mock_log:

        asyncio.run(update_engagement(
            db=mock_db,
            engagement_id=old_eng.id,
            payload=mock_payload,
            firm_id=old_eng.firm_id,
            current_user_id=uuid.uuid4(),
            background_tasks=MagicMock(),
        ))

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "engagement.reopened" in event_types
    reopened_call = next(c for c in mock_log.call_args_list if c.kwargs["event_type"] == "engagement.reopened")
    assert reopened_call.kwargs["metadata"]["reopened_to_status"] == "in_progress"


# ---------------------------------------------------------------------------
# Test 4 -- engagement.reopened does NOT fire on regular status change
# ---------------------------------------------------------------------------
def test_engagement_reopened_does_not_fire_on_regular_status_change():
    old_eng = _mock_engagement(status="in_progress")
    updated_eng = _mock_engagement(status="review", engagement_type=old_eng.engagement_type)
    updated_eng.firm_id = old_eng.firm_id
    updated_eng.id = old_eng.id
    updated_eng.created_at = old_eng.created_at

    mock_db = MagicMock()
    mock_db.execute.return_value.scalar.return_value = 0

    mock_payload = MagicMock()
    mock_payload.status = "review"
    mock_payload.extended_deadline = None
    mock_payload.model_dump.return_value = {}

    with patch("app.services.engagement_service.crud_engagement.get_engagement_for_firm", return_value=old_eng), \
         patch("app.services.engagement_service.crud_engagement.update_engagement", return_value=updated_eng), \
         patch("app.services.engagement_service.emit_event", new_callable=AsyncMock), \
         patch("app.services.engagement_service.log_event") as mock_log:

        asyncio.run(update_engagement(
            db=mock_db,
            engagement_id=old_eng.id,
            payload=mock_payload,
            firm_id=old_eng.firm_id,
            current_user_id=uuid.uuid4(),
            background_tasks=MagicMock(),
        ))

    event_types = [c.kwargs["event_type"] for c in mock_log.call_args_list]
    assert "engagement.reopened" not in event_types


# ---------------------------------------------------------------------------
# Test 5 -- mark_authorization_renewed fires irs_authorization.renewed
# ---------------------------------------------------------------------------
def test_mark_authorization_renewed_fires_event():
    mock_auth = _mock_authorization(valid_until=date.today() + timedelta(days=365))

    with patch("app.services.irs_auth_service.log_event") as mock_log:
        mark_authorization_renewed(
            db=MagicMock(),
            authorization=mock_auth,
            firm_id=mock_auth.firm_id,
            actor_id=uuid.uuid4(),
        )

    assert mock_log.called
    assert mock_log.call_args.kwargs["event_type"] == "irs_authorization.renewed"


# ---------------------------------------------------------------------------
# Test 6 -- mark_authorization_expired fires irs_authorization.expired
#           and writes status, with no warning history on the row
# ---------------------------------------------------------------------------
def test_mark_authorization_expired_fires_event():
    mock_auth = _mock_authorization(valid_until=date.today() - timedelta(days=1))
    mock_auth.status = "active"

    with patch("app.services.irs_auth_service.log_event") as mock_log, \
         patch(
             "app.services.irs_auth_service.crud_warning.list_warnings_for_authorization",
             return_value=[],
         ):
        mark_authorization_expired(
            db=MagicMock(),
            authorization=mock_auth,
            firm_id=mock_auth.firm_id,
        )

    assert mock_log.called
    assert mock_log.call_args.kwargs["event_type"] == "irs_authorization.expired"

    # Phase A2: the status is real control state now, not only a log line.
    assert mock_auth.status == "expired"

    metadata = mock_log.call_args.kwargs["metadata"]
    assert metadata["warning_tiers_fired"] == 0
    assert metadata["days_since_expiry_warning"] is None


# ---------------------------------------------------------------------------
# Test 6b -- the expiry event reports real warning history when tiers fired
# ---------------------------------------------------------------------------
def test_mark_authorization_expired_reports_warning_history():
    mock_auth = _mock_authorization(valid_until=date.today() - timedelta(days=1))
    mock_auth.status = "active"

    # Most recent first, matching list_warnings_for_authorization's ordering.
    recent = MagicMock()
    recent.sent_at = datetime.now(timezone.utc) - timedelta(days=4)
    older = MagicMock()
    older.sent_at = datetime.now(timezone.utc) - timedelta(days=40)

    with patch("app.services.irs_auth_service.log_event") as mock_log, \
         patch(
             "app.services.irs_auth_service.crud_warning.list_warnings_for_authorization",
             return_value=[recent, older],
         ):
        mark_authorization_expired(
            db=MagicMock(),
            authorization=mock_auth,
            firm_id=mock_auth.firm_id,
        )

    metadata = mock_log.call_args.kwargs["metadata"]
    assert metadata["warning_tiers_fired"] == 2
    # Computed from the most recent row, not the oldest.
    assert metadata["days_since_expiry_warning"] == 4


# ---------------------------------------------------------------------------
# Test 7 -- the lapsed query, not the warning window, drives expiry
#
# Rewritten in Phase A2. The old version patched
# get_authorizations_expiring_soon, a single window query that filtered to
# valid_until >= today and so could never return a lapsed row. That made the
# expiry branch it asserted on unreachable in production. The sweep now runs
# two separate queries and this test pins that split.
# ---------------------------------------------------------------------------
def test_expired_check_fires_in_scheduler_when_past_due():
    yesterday = date.today() - timedelta(days=1)
    lapsed_auth = _mock_authorization(valid_until=yesterday)

    mock_db = MagicMock()

    with patch("app.db.session.SessionLocal", return_value=mock_db), \
         patch(
             "app.services.irs_auth_service.crud_auth.get_authorizations_in_warning_window",
             return_value=[],
         ), \
         patch(
             "app.services.irs_auth_service.crud_auth.get_lapsed_active_authorizations",
             return_value=[lapsed_auth],
         ), \
         patch("app.services.event_bus.emit_event_sync"), \
         patch("app.services.irs_auth_service.log_event"), \
         patch("app.services.irs_auth_service.mark_authorization_expired") as mock_expired:

        result = check_expiring_authorizations()

    mock_expired.assert_called_once()
    assert mock_expired.call_args.kwargs["authorization"] is lapsed_auth
    assert result["expired"] == 1


# ---------------------------------------------------------------------------
# Test 7b -- an authorization still inside the window is warned, not expired,
#            and it is warned at its most urgent applicable tier
# ---------------------------------------------------------------------------
def test_warning_window_authorization_is_warned_not_expired():
    # Anchored on the sweep's own reference date, not on date.today().
    # date.today() is the server's LOCAL date while the sweep reasons in
    # cutoff terms, so a fixture built from it lands on the wrong tier
    # whenever the two calendars disagree.
    from app.crud.irs_authorization import compute_expiry_cutoff_date

    cutoff = compute_expiry_cutoff_date()
    upcoming_auth = _mock_authorization(valid_until=cutoff + timedelta(days=30))

    mock_db = MagicMock()

    with patch("app.db.session.SessionLocal", return_value=mock_db), \
         patch(
             "app.services.irs_auth_service.crud_auth.get_authorizations_in_warning_window",
             return_value=[upcoming_auth],
         ), \
         patch(
             "app.services.irs_auth_service.crud_auth.get_lapsed_active_authorizations",
             return_value=[],
         ), \
         patch("app.services.event_bus.emit_event_sync"), \
         patch("app.services.irs_auth_service.log_event"), \
         patch(
             "app.services.irs_auth_service.crud_warning.get_warning_for_threshold",
             return_value=None,
         ), \
         patch(
             "app.services.irs_auth_service._deliver_expiry_warning",
             return_value=True,
         ), \
         patch("app.services.irs_auth_service._record_warning_sent") as mock_record, \
         patch("app.services.irs_auth_service.mark_authorization_expired") as mock_expired:

        result = check_expiring_authorizations()

    mock_expired.assert_not_called()
    assert result["expired"] == 0

    # 30 days out: applicable tiers are 60 and 30, most urgent is 30.
    mock_record.assert_called_once()
    assert mock_record.call_args.kwargs["threshold_days"] == 30
    assert result["alerts_emitted"] == 1


# ---------------------------------------------------------------------------
# Test 7c -- a tier already recorded does not fire again
# ---------------------------------------------------------------------------
def test_recorded_tier_does_not_fire_again():
    from app.crud.irs_authorization import compute_expiry_cutoff_date

    cutoff = compute_expiry_cutoff_date()
    upcoming_auth = _mock_authorization(valid_until=cutoff + timedelta(days=30))

    mock_db = MagicMock()

    with patch("app.db.session.SessionLocal", return_value=mock_db), \
         patch(
             "app.services.irs_auth_service.crud_auth.get_authorizations_in_warning_window",
             return_value=[upcoming_auth],
         ), \
         patch(
             "app.services.irs_auth_service.crud_auth.get_lapsed_active_authorizations",
             return_value=[],
         ), \
         patch("app.services.event_bus.emit_event_sync"), \
         patch("app.services.irs_auth_service.log_event"), \
         patch(
             "app.services.irs_auth_service.crud_warning.get_warning_for_threshold",
             return_value=MagicMock(),  # a row already exists for this tier
         ), \
         patch("app.services.irs_auth_service._deliver_expiry_warning") as mock_deliver:

        result = check_expiring_authorizations()

    mock_deliver.assert_not_called()
    assert result["alerts_emitted"] == 0
