# tests/test_irs_auth_expiry_sweep.py

"""
Calendar-boundary behaviour of the IRS authorization expiry sweep.

The server runs on UTC and every US firm is behind it, so for part of each
UTC day the server's calendar date is ahead of the firm's. Marking an
authorization expired in that window would revoke transcript access while
the authorization is still valid where the firm actually is, and
status = "expired" does not revert.

compute_expiry_cutoff_date rolls back to the westernmost US offset so the
sweep only ever acts on a calendar date that has arrived everywhere in the
ICP. These tests pin that boundary at both a pre-cutoff hour and the
scheduled hour, because the safety has to hold on an off-schedule run too.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

from freezegun import freeze_time

from tests.conftest import TestingSessionLocal


EXPIRY_DATE = date(2026, 9, 8)

# 18:00 on 8 September in Hawaii-Aleutian (UTC-10). The authorization is
# still valid where the firm is, even though the server already says the 9th.
BEFORE_CUTOFF_UTC = "2026-09-09 04:00:00"

# 00:01 on 9 September in Hawaii. The 8th has now ended everywhere in the US.
AT_CUTOFF_UTC = "2026-09-09 10:01:00"


def _mk_client(db, firm_id):
    from app.models.client import Client
    c = Client(firm_id=uuid.UUID(firm_id), name="Acme Construction")
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _mk_auth(db, firm_id, client_id, valid_until, form_type="8821"):
    from app.models.irs_authorization import IrsAuthorization
    a = IrsAuthorization(
        firm_id=uuid.UUID(firm_id), client_id=client_id, form_type=form_type,
        status="active", tax_years=[2024], valid_until=valid_until,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _run_sweep():
    from app.services.irs_auth_service import check_expiring_authorizations
    with patch("app.db.session.SessionLocal", TestingSessionLocal):
        return check_expiring_authorizations()


def test_not_expired_before_the_cutoff_hour(firm_a_owner):
    """
    04:00 UTC on the 9th is still the 8th in Hawaii. An authorization
    expiring on the 8th must not be expired yet, however the sweep is
    triggered.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, EXPIRY_DATE)

        with freeze_time(BEFORE_CUTOFF_UTC):
            result = _run_sweep()

        db.expire_all()
        db.refresh(auth)
        assert auth.status == "active", (
            "expired while still valid in a western US timezone"
        )
        assert result["expired"] == 0
    finally:
        db.close()


def test_expired_at_the_cutoff_hour(firm_a_owner):
    """10:01 UTC on the 9th: the 8th has ended everywhere in the US."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, EXPIRY_DATE)

        with freeze_time(AT_CUTOFF_UTC):
            result = _run_sweep()

        db.expire_all()
        db.refresh(auth)
        assert auth.status == "expired"
        assert result["expired"] == 1
    finally:
        db.close()


def test_manual_trigger_before_cutoff_matches_scheduled_run(firm_a_owner):
    """
    The safety lives in the cutoff, not in the schedule. Running the sweep
    at 04:00 must leave the row in the same state a 04:00 run always would,
    and a later scheduled run must then expire it. This is the case
    POST /irs-authorizations/run-expiry-check exposes.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, EXPIRY_DATE)

        with freeze_time(BEFORE_CUTOFF_UTC):
            _run_sweep()
        db.expire_all()
        db.refresh(auth)
        assert auth.status == "active"

        with freeze_time(AT_CUTOFF_UTC):
            _run_sweep()
        db.expire_all()
        db.refresh(auth)
        assert auth.status == "expired"
    finally:
        db.close()


def _query_sets(db, as_of):
    from app.crud import irs_authorization as crud_auth
    window = {
        a.id for a in crud_auth.get_authorizations_in_warning_window(
            db, max_days=60, as_of=as_of
        )
    }
    lapsed = {
        a.id for a in crud_auth.get_lapsed_active_authorizations(db, as_of=as_of)
    }
    return window, lapsed


def test_query_sets_disjoint_and_jointly_complete_at_both_hours(firm_a_owner):
    """
    No active authorization inside the horizon may fall into neither set.
    A row in neither set is invisible to the sweep, which is the exact
    failure this feature exists to eliminate. Checked at both hours because
    the boundary is where a gap would open.
    """
    from app.crud import irs_authorization as crud_auth

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)

        # Dense coverage around the boundary, plus a long-lapsed row and a
        # row beyond the 60 day horizon.
        offsets = [-400, -2, -1, 0, 1, 2, 7, 30, 59, 60]
        auths = {
            offset: _mk_auth(db, firm_id, cl.id, EXPIRY_DATE + timedelta(days=offset))
            for offset in offsets
        }
        beyond = _mk_auth(db, firm_id, cl.id, EXPIRY_DATE + timedelta(days=400))
        indefinite = _mk_auth(db, firm_id, cl.id, None)

        for frozen in (BEFORE_CUTOFF_UTC, AT_CUTOFF_UTC):
            with freeze_time(frozen):
                as_of = crud_auth.compute_expiry_cutoff_date()
                window, lapsed = _query_sets(db, as_of)

            assert window.isdisjoint(lapsed), (
                f"a row was in both sets at {frozen}"
            )

            for offset, auth in auths.items():
                expected_in_horizon = auth.valid_until <= as_of + timedelta(days=60)
                if expected_in_horizon:
                    assert auth.id in window or auth.id in lapsed, (
                        f"row at offset {offset} was invisible to the sweep at {frozen}"
                    )

            # Beyond the horizon and indefinite rows belong to neither set.
            assert beyond.id not in window and beyond.id not in lapsed
            assert indefinite.id not in window and indefinite.id not in lapsed
    finally:
        db.close()


def test_cutoff_rolls_back_ten_hours_from_utc():
    """The constant is the westernmost US offset, not an arbitrary margin."""
    from app.crud.irs_authorization import (
        compute_expiry_cutoff_date,
        WESTERNMOST_US_UTC_OFFSET_HOURS,
    )

    assert WESTERNMOST_US_UTC_OFFSET_HOURS == 10

    with freeze_time(BEFORE_CUTOFF_UTC):
        assert datetime.now(timezone.utc).date() == date(2026, 9, 9)
        assert compute_expiry_cutoff_date() == date(2026, 9, 8)

    with freeze_time(AT_CUTOFF_UTC):
        assert compute_expiry_cutoff_date() == date(2026, 9, 9)

    # Exactly 10:00 UTC is the first instant the new date has arrived
    # everywhere in the ICP.
    with freeze_time("2026-09-09 09:59:00"):
        assert compute_expiry_cutoff_date() == date(2026, 9, 8)
    with freeze_time("2026-09-09 10:00:00"):
        assert compute_expiry_cutoff_date() == date(2026, 9, 9)
