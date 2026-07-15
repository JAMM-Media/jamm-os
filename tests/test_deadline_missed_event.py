# tests/test_deadline_missed_event.py

"""
engagement.deadline_missed -- negative-space synthetic event added to the
existing deadline sweep. Covers: gating on the operative deadline, per-track
firing (original / extended), and idempotency across repeated sweep runs.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from app.services import deadline_scheduler


def _mock_engagement(status="active", filing_deadline=None, extended_deadline=None):
    eng = MagicMock()
    eng.id = uuid.uuid4()
    eng.firm_id = uuid.uuid4()
    eng.client_id = uuid.uuid4()
    eng.status = status
    eng.engagement_type = "tax_return_1040"
    eng.filing_deadline = filing_deadline
    eng.extended_deadline = extended_deadline
    return eng


def _run_sweep(engagements, already_logged=()):
    """Run check_approaching_deadlines against a mocked engagement list,
    with mocked SessionLocal and a controllable idempotency check."""
    db = MagicMock()
    db.execute.return_value.scalars.return_value.all.return_value = engagements

    def _fake_already_logged(db_arg, engagement_id, deadline_type):
        return (engagement_id, deadline_type) in already_logged

    with patch.object(deadline_scheduler, "SessionLocal", return_value=db), \
         patch.object(deadline_scheduler, "_deadline_miss_already_logged", side_effect=_fake_already_logged) as mock_check, \
         patch.object(deadline_scheduler, "log_event") as mock_log, \
         patch.object(deadline_scheduler, "emit_event_sync"):
        result = deadline_scheduler.check_approaching_deadlines()

    return result, mock_log, mock_check


today = date.today()


def test_no_miss_when_no_deadline_has_passed():
    eng = _mock_engagement(filing_deadline=today + timedelta(days=10))
    result, mock_log, _ = _run_sweep([eng])
    assert result["misses_emitted"] == 0
    mock_log.assert_not_called()


def test_original_track_fires_when_no_extension_and_deadline_passed():
    eng = _mock_engagement(filing_deadline=today - timedelta(days=5))
    result, mock_log, _ = _run_sweep([eng])

    assert result["misses_emitted"] == 1
    kwargs = mock_log.call_args.kwargs
    assert kwargs["event_type"] == "engagement.deadline_missed"
    assert kwargs["entity_id"] == eng.id
    assert kwargs["metadata"]["deadline_type"] == "original"
    assert kwargs["metadata"]["days_overdue"] == 5
    assert kwargs["metadata"]["form_type"] == "tax_return_1040"


def test_no_miss_when_extension_filed_and_extended_deadline_not_yet_passed():
    """Original date has passed but an extension pushed the operative
    deadline into the future -- must not fire an original-track miss."""
    eng = _mock_engagement(
        filing_deadline=today - timedelta(days=20),
        extended_deadline=today + timedelta(days=30),
    )
    result, mock_log, _ = _run_sweep([eng])
    assert result["misses_emitted"] == 0
    mock_log.assert_not_called()


def test_both_tracks_fire_when_extended_deadline_has_also_passed():
    eng = _mock_engagement(
        filing_deadline=today - timedelta(days=40),
        extended_deadline=today - timedelta(days=3),
    )
    result, mock_log, _ = _run_sweep([eng])

    assert result["misses_emitted"] == 2
    tracks_fired = {call.kwargs["metadata"]["deadline_type"] for call in mock_log.call_args_list}
    assert tracks_fired == {"original", "extended"}

    by_track = {call.kwargs["metadata"]["deadline_type"]: call.kwargs for call in mock_log.call_args_list}
    assert by_track["original"]["metadata"]["days_overdue"] == 40
    assert by_track["extended"]["metadata"]["days_overdue"] == 3


def test_track_already_logged_does_not_refire():
    eng = _mock_engagement(filing_deadline=today - timedelta(days=5))
    result, mock_log, mock_check = _run_sweep([eng], already_logged={(eng.id, "original")})

    assert result["misses_emitted"] == 0
    mock_log.assert_not_called()
    assert mock_check.called


def test_extended_track_fires_independently_once_original_already_logged():
    eng = _mock_engagement(
        filing_deadline=today - timedelta(days=40),
        extended_deadline=today - timedelta(days=3),
    )
    result, mock_log, _ = _run_sweep([eng], already_logged={(eng.id, "original")})

    assert result["misses_emitted"] == 1
    kwargs = mock_log.call_args.kwargs
    assert kwargs["metadata"]["deadline_type"] == "extended"
