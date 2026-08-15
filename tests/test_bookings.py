# tests/test_bookings.py

"""
Tests for the Booking model (app/models/booking.py).

Covers:
  - Tenant isolation: Firm A cannot read Firm B's bookings.
  - Basic round-trip: fields written for a booking read back correctly.
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from tests.conftest import TestingSessionLocal
from app.models.booking import Booking
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import BookingStatus, UserRole


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


def _make_booking(
    firm_id,
    staff_user_id=None,
    lead_id=None,
    status: BookingStatus = BookingStatus.scheduled,
    location_snapshot: str = None,
) -> Booking:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        booking = Booking(
            firm_id=firm_id,
            lead_id=lead_id,
            staff_user_id=staff_user_id,
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, minutes=30),
            status=status,
            location_snapshot=location_snapshot,
            created_at=now,
            updated_at=now,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        _ = booking.id, booking.firm_id, booking.status
        return booking
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBookingTenantIsolation:
    """Firm A's bookings must never appear in Firm B's query results."""

    def test_firm_id_filter_excludes_other_firm_bookings(self):
        """Querying bookings for Firm A must not return Firm B's rows."""
        firm_a = _make_firm(f"book-iso-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"book-iso-b-{uuid.uuid4().hex[:6]}")

        user_a = _make_user(firm_a.id)
        user_b = _make_user(firm_b.id)

        booking_a = _make_booking(firm_a.id, staff_user_id=user_a.id)
        booking_b = _make_booking(firm_b.id, staff_user_id=user_b.id)

        db = TestingSessionLocal()
        try:
            rows_a = (
                db.query(Booking)
                .filter(Booking.firm_id == firm_a.id)
                .all()
            )
            ids_a = {r.id for r in rows_a}

            rows_b = (
                db.query(Booking)
                .filter(Booking.firm_id == firm_b.id)
                .all()
            )
            ids_b = {r.id for r in rows_b}
        finally:
            db.close()

        assert booking_a.id in ids_a, (
            "Firm A booking must appear when querying with Firm A's firm_id"
        )
        assert booking_b.id not in ids_a, (
            "Tenant isolation breach: Firm B booking appeared in Firm A query"
        )
        assert booking_b.id in ids_b, (
            "Firm B booking must appear when querying with Firm B's firm_id"
        )
        assert booking_a.id not in ids_b, (
            "Tenant isolation breach: Firm A booking appeared in Firm B query"
        )

    def test_booking_fields_round_trip(self):
        """Fields written to the model read back correctly from the database."""
        firm = _make_firm(f"book-rt-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)

        booking = _make_booking(
            firm.id,
            staff_user_id=user.id,
            status=BookingStatus.scheduled,
            location_snapshot="https://zoom.us/j/example",
        )

        db = TestingSessionLocal()
        try:
            fetched = db.query(Booking).filter(Booking.id == booking.id).first()
            assert fetched is not None
            assert fetched.firm_id == firm.id
            assert fetched.staff_user_id == user.id
            assert fetched.lead_id is None
            assert fetched.status == BookingStatus.scheduled
            assert fetched.location_snapshot == "https://zoom.us/j/example"
            assert fetched.start_time is not None
            assert fetched.end_time > fetched.start_time
        finally:
            db.close()

    def test_booking_survives_with_null_lead_id(self):
        """A booking can exist with lead_id=None (lead deleted or not yet linked)."""
        firm = _make_firm(f"book-null-lead-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)

        booking = _make_booking(firm.id, staff_user_id=user.id, lead_id=None)

        db = TestingSessionLocal()
        try:
            fetched = db.query(Booking).filter(Booking.id == booking.id).first()
            assert fetched is not None
            assert fetched.lead_id is None
        finally:
            db.close()


class TestBookingStaffRestrictConstraint:
    """Tests that staff_user_id uses ON DELETE RESTRICT at the DB level.

    A User who has booking rows pointing at them cannot be deleted.
    The DB raises an IntegrityError, not a silent SET NULL.
    A User with no bookings can still be deleted normally.
    """

    def test_deleting_staff_with_bookings_is_rejected(self):
        """Deleting a User who is referenced by a booking raises IntegrityError.

        Uses a raw SQL DELETE to bypass SQLAlchemy ORM relationship tracking
        and exercise the actual database-level RESTRICT constraint directly.
        """
        from sqlalchemy import text

        firm = _make_firm(f"restrict-a-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        _make_booking(firm.id, staff_user_id=user.id)

        db = TestingSessionLocal()
        try:
            with pytest.raises(IntegrityError):
                db.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user.id)})
                db.flush()
        finally:
            db.rollback()
            db.close()

    def test_deleting_staff_with_no_bookings_succeeds(self):
        """A User with no booking history can be deleted normally.

        RESTRICT only blocks deletion when a referencing booking row actually exists.
        """
        from sqlalchemy import text

        firm = _make_firm(f"restrict-b-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        user_id = user.id
        # No booking created for this user.

        db = TestingSessionLocal()
        try:
            db.execute(text("DELETE FROM users WHERE id = :id"), {"id": str(user_id)})
            db.commit()

            gone = db.query(User).filter(User.id == user_id).first()
            assert gone is None, (
                "User with no bookings must be deletable without error"
            )
        finally:
            db.close()
