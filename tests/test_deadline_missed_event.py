# tests/test_deadline_missed_event.py

"""
engagement.deadline_missed -- negative-space synthetic event added to the
existing deadline sweep. Covers: gating on the operative deadline, per-track
firing (original / extended), idempotency across repeated sweep runs, and
the one day safe_today buffer that protects against the server's UTC date
being ahead of a firm's local calendar date.
"""

import uuid
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

from freezegun import freeze_time

from app.services import deadline_scheduler


FROZEN_DATE = date(2025, 6, 15)


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

    def _fake_already_logged(db_arg, firm_id, engagement_id, deadline_type):
        return (engagement_id, deadline_type) in already_logged

    with patch.object(deadline_scheduler, "SessionLocal", return_value=db), \
         patch.object(deadline_scheduler, "_deadline_miss_already_logged", side_effect=_fake_already_logged) as mock_check, \
         patch.object(deadline_scheduler, "log_event") as mock_log, \
         patch.object(deadline_scheduler, "emit_event_sync"):
        result = deadline_scheduler.check_approaching_deadlines()

    return result, mock_log, mock_check


@freeze_time(FROZEN_DATE)
def test_no_miss_when_no_deadline_has_passed():
    eng = _mock_engagement(filing_deadline=FROZEN_DATE + timedelta(days=10))
    result, mock_log, _ = _run_sweep([eng])
    assert result["misses_emitted"] == 0
    mock_log.assert_not_called()


@freeze_time(FROZEN_DATE)
def test_original_track_fires_when_no_extension_and_deadline_passed():
    eng = _mock_engagement(filing_deadline=FROZEN_DATE - timedelta(days=5))
    result, mock_log, _ = _run_sweep([eng])

    assert result["misses_emitted"] == 1
    kwargs = mock_log.call_args.kwargs
    assert kwargs["event_type"] == "engagement.deadline_missed"
    assert kwargs["entity_id"] == eng.id
    assert kwargs["metadata"]["deadline_type"] == "original"
    # safe_today is FROZEN_DATE minus 1 day, so days_overdue is 4, not 5.
    assert kwargs["metadata"]["days_overdue"] == 4
    assert kwargs["metadata"]["form_type"] == "tax_return_1040"


@freeze_time(FROZEN_DATE)
def test_no_miss_when_extension_filed_and_extended_deadline_not_yet_passed():
    """Original date has passed but an extension pushed the operative
    deadline into the future -- must not fire an original-track miss."""
    eng = _mock_engagement(
        filing_deadline=FROZEN_DATE - timedelta(days=20),
        extended_deadline=FROZEN_DATE + timedelta(days=30),
    )
    result, mock_log, _ = _run_sweep([eng])
    assert result["misses_emitted"] == 0
    mock_log.assert_not_called()


@freeze_time(FROZEN_DATE)
def test_both_tracks_fire_when_extended_deadline_has_also_passed():
    eng = _mock_engagement(
        filing_deadline=FROZEN_DATE - timedelta(days=40),
        extended_deadline=FROZEN_DATE - timedelta(days=3),
    )
    result, mock_log, _ = _run_sweep([eng])

    assert result["misses_emitted"] == 2
    tracks_fired = {call.kwargs["metadata"]["deadline_type"] for call in mock_log.call_args_list}
    assert tracks_fired == {"original", "extended"}

    by_track = {call.kwargs["metadata"]["deadline_type"]: call.kwargs for call in mock_log.call_args_list}
    # safe_today is FROZEN_DATE minus 1 day, so days_overdue is 39 and 2, not 40 and 3.
    assert by_track["original"]["metadata"]["days_overdue"] == 39
    assert by_track["extended"]["metadata"]["days_overdue"] == 2


@freeze_time(FROZEN_DATE)
def test_track_already_logged_does_not_refire():
    eng = _mock_engagement(filing_deadline=FROZEN_DATE - timedelta(days=5))
    result, mock_log, mock_check = _run_sweep([eng], already_logged={(eng.id, "original")})

    assert result["misses_emitted"] == 0
    mock_log.assert_not_called()
    assert mock_check.called


@freeze_time(FROZEN_DATE)
def test_extended_track_fires_independently_once_original_already_logged():
    eng = _mock_engagement(
        filing_deadline=FROZEN_DATE - timedelta(days=40),
        extended_deadline=FROZEN_DATE - timedelta(days=3),
    )
    result, mock_log, _ = _run_sweep([eng], already_logged={(eng.id, "original")})

    assert result["misses_emitted"] == 1
    kwargs = mock_log.call_args.kwargs
    assert kwargs["metadata"]["deadline_type"] == "extended"


@freeze_time(FROZEN_DATE)
def test_no_miss_when_deadline_is_within_safe_today_buffer():
    """Boundary case the one day safe_today buffer exists to protect: a
    deadline of exactly FROZEN_DATE minus 1 day equals safe_today itself,
    so the operative deadline is not yet strictly before safe_today and no
    miss may be declared. This is the case where the server's UTC calendar
    date has already turned over past the deadline but a US firm's local
    calendar date genuinely has not -- firing here would fabricate a miss
    that is permanent in an append-only log. Do not remove this test to
    make it pass; if it starts failing, the buffer has been broken."""
    eng = _mock_engagement(filing_deadline=FROZEN_DATE - timedelta(days=1))
    result, mock_log, _ = _run_sweep([eng])
    assert result["misses_emitted"] == 0
    mock_log.assert_not_called()


@freeze_time(FROZEN_DATE)
def test_miss_fires_once_past_safe_today_buffer():
    """One day further back than the boundary case: a deadline of exactly
    FROZEN_DATE minus 2 days is strictly before safe_today, so the miss
    fires, with days_overdue measured against safe_today rather than the
    real today."""
    eng = _mock_engagement(filing_deadline=FROZEN_DATE - timedelta(days=2))
    result, mock_log, _ = _run_sweep([eng])

    assert result["misses_emitted"] == 1
    kwargs = mock_log.call_args.kwargs
    assert kwargs["metadata"]["deadline_type"] == "original"
    assert kwargs["metadata"]["days_overdue"] == 1
