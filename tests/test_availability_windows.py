# tests/test_availability_windows.py

"""
Tests for the AvailabilityWindow model (app/models/availability_window.py).

Covers:
  - Tenant isolation: Firm A cannot read Firm B's availability windows.
  - Basic round-trip: a window written for a staff member is readable by
    querying that firm and user.
"""

import uuid
from datetime import datetime, time, timezone

from tests.conftest import TestingSessionLocal
from app.models.availability_window import AvailabilityWindow
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.slug
        return firm
    finally:
        db.close()


def _make_user(firm_id) -> User:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="not-a-real-hash",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        _ = user.id, user.firm_id
        return user
    finally:
        db.close()


def _make_window(
    firm_id,
    user_id,
    day_of_week: int = 0,
    start_time: time = time(9, 0),
    end_time: time = time(17, 0),
    meeting_duration_minutes: int = 30,
) -> AvailabilityWindow:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        window = AvailabilityWindow(
            firm_id=firm_id,
            user_id=user_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            buffer_before_minutes=5,
            buffer_after_minutes=5,
            meeting_duration_minutes=meeting_duration_minutes,
            daily_cap=4,
            created_at=now,
            updated_at=now,
        )
        db.add(window)
        db.commit()
        db.refresh(window)
        _ = window.id, window.firm_id, window.user_id, window.day_of_week
        return window
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAvailabilityWindowTenantIsolation:
    """Firm A's availability windows must never appear in Firm B's query results."""

    def test_firm_id_filter_excludes_other_firm_windows(self):
        """Querying availability windows for Firm A must not return Firm B's rows."""
        firm_a = _make_firm(f"avail-iso-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"avail-iso-b-{uuid.uuid4().hex[:6]}")

        user_a = _make_user(firm_a.id)
        user_b = _make_user(firm_b.id)

        window_a = _make_window(firm_a.id, user_a.id, day_of_week=0)
        window_b = _make_window(firm_b.id, user_b.id, day_of_week=0)

        db = TestingSessionLocal()
        try:
            rows_for_a = (
                db.query(AvailabilityWindow)
                .filter(AvailabilityWindow.firm_id == firm_a.id)
                .all()
            )
            ids_for_a = {r.id for r in rows_for_a}

            rows_for_b = (
                db.query(AvailabilityWindow)
                .filter(AvailabilityWindow.firm_id == firm_b.id)
                .all()
            )
            ids_for_b = {r.id for r in rows_for_b}
        finally:
            db.close()

        assert window_a.id in ids_for_a, (
            "Firm A window must appear when querying with Firm A's firm_id"
        )
        assert window_b.id not in ids_for_a, (
            "Tenant isolation breach: Firm B window appeared in Firm A query"
        )
        assert window_b.id in ids_for_b, (
            "Firm B window must appear when querying with Firm B's firm_id"
        )
        assert window_a.id not in ids_for_b, (
            "Tenant isolation breach: Firm A window appeared in Firm B query"
        )

    def test_user_id_and_firm_id_filter_together(self):
        """Querying by both firm_id and user_id returns only that staff member's windows."""
        firm = _make_firm(f"avail-user-{uuid.uuid4().hex[:6]}")
        user_x = _make_user(firm.id)
        user_y = _make_user(firm.id)

        window_x_mon = _make_window(firm.id, user_x.id, day_of_week=0)
        window_x_tue = _make_window(firm.id, user_x.id, day_of_week=1)
        window_y_mon = _make_window(firm.id, user_y.id, day_of_week=0)

        db = TestingSessionLocal()
        try:
            rows = (
                db.query(AvailabilityWindow)
                .filter(
                    AvailabilityWindow.firm_id == firm.id,
                    AvailabilityWindow.user_id == user_x.id,
                )
                .all()
            )
            ids = {r.id for r in rows}
        finally:
            db.close()

        assert window_x_mon.id in ids, "User X Monday window must be returned"
        assert window_x_tue.id in ids, "User X Tuesday window must be returned"
        assert window_y_mon.id not in ids, (
            "User Y window must not appear in User X's scoped query"
        )

    def test_window_fields_round_trip(self):
        """Fields written to the model read back correctly from the database."""
        firm = _make_firm(f"avail-rt-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)

        window = _make_window(
            firm.id,
            user.id,
            day_of_week=2,
            start_time=time(10, 30),
            end_time=time(16, 0),
            meeting_duration_minutes=45,
        )

        db = TestingSessionLocal()
        try:
            fetched = db.query(AvailabilityWindow).filter(
                AvailabilityWindow.id == window.id
            ).first()
            assert fetched is not None
            assert fetched.firm_id == firm.id
            assert fetched.user_id == user.id
            assert fetched.day_of_week == 2
            assert fetched.start_time == time(10, 30)
            assert fetched.end_time == time(16, 0)
            assert fetched.meeting_duration_minutes == 45
            assert fetched.buffer_before_minutes == 5
            assert fetched.buffer_after_minutes == 5
            assert fetched.daily_cap == 4
        finally:
            db.close()


class TestAvailabilityWindowDuplicateDayGuard:
    """
    GUARD TEST: creating a second window for the same user on the same
    day_of_week must raise ValueError (which the router converts to a 409),
    never let a raw IntegrityError escape as an unhandled 500.

    Real bug this guards against (found by Andrew, confirmed against psycopg3):
    the duplicate-day check originally read exc.orig.pgcode, a psycopg2-only
    attribute that does not exist on a psycopg3 exception. psycopg3 carries
    sqlstate instead. With the old code, this check always evaluated to
    None == "23505" -> False, so the guard never fired and a real duplicate-day
    attempt fell through to an unhandled 500 instead of a clean 409.

    To watch this test fail: temporarily revert app/crud/availability_window.py
    to read only exc.orig.pgcode instead of exc.orig.sqlstate, rerun this test,
    and confirm it fails with an unhandled psycopg.errors.UniqueViolation
    instead of a caught ValueError.
    """

    def test_duplicate_day_for_same_user_raises_value_error_not_raw_integrity_error(self):
        from app.crud.availability_window import create_window
        from app.schemas.availability_window import AvailabilityWindowCreate

        firm = _make_firm(f"avail-dup-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)

        # Existing window already occupies day_of_week=2 for this user.
        _make_window(firm.id, user.id, day_of_week=2)

        db = TestingSessionLocal()
        try:
            duplicate_in = AvailabilityWindowCreate(
                user_id=user.id,
                day_of_week=2,
                start_time=time(10, 0),
                end_time=time(14, 0),
                buffer_before_minutes=0,
                buffer_after_minutes=0,
                meeting_duration_minutes=30,
                daily_cap=None,
            )
            try:
                create_window(db, user.id, firm.id, duplicate_in)
                assert False, (
                    "Expected ValueError for duplicate day_of_week, but create_window "
                    "succeeded instead. The unique constraint or the guard is not working."
                )
            except ValueError as exc:
                assert "already exists" in str(exc), (
                    f"Got a ValueError, but not the expected duplicate-day message: {exc}"
                )
            except Exception as exc:
                assert False, (
                    f"Expected a caught ValueError (409 path), but got an unhandled "
                    f"{type(exc).__name__} instead: {exc}. This means the sqlstate/pgcode "
                    f"guard is not catching the real driver's exception shape."
                )
        finally:
            db.close()
