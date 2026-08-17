# tests/test_slot_timezone.py
"""
Tests proving that AvailabilityWindow times are localized using Firm.timezone
before being converted to UTC -- not treated as UTC directly.

GUARD TEST: test_la_firm_9am_window_produces_17_utc_slots
Watched-fail cycle: with UTC treatment (hardcoded before the fix), a 9:00 AM
window produces a 9:00 UTC slot. After the fix with America/Los_Angeles, the
same window produces a 17:00 UTC slot (January = PST = UTC-8). The test
asserts 17:00 UTC and would fail if UTC treatment were restored.
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.models.availability_window import AvailabilityWindow
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import UserRole
from app.services.slot_computation_service import compute_available_slots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_with_tz(slug: str, firm_timezone: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone=firm_timezone)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
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
        _ = user.id
        return user
    finally:
        db.close()


def _make_window(firm_id, user_id, day_of_week, start_time, end_time,
                 meeting_duration_minutes=30) -> AvailabilityWindow:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        win = AvailabilityWindow(
            firm_id=firm_id,
            user_id=user_id,
            day_of_week=day_of_week,
            start_time=start_time,
            end_time=end_time,
            meeting_duration_minutes=meeting_duration_minutes,
            created_at=now,
            updated_at=now,
        )
        db.add(win)
        db.commit()
        db.refresh(win)
        _ = win.id
        return win
    finally:
        db.close()


def _run(staff_user_id, firm_id, target_date, now=None) -> list[dict]:
    if now is None:
        now = datetime(2020, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    db = TestingSessionLocal()
    try:
        return compute_available_slots(
            db=db,
            staff_user_id=staff_user_id,
            firm_id=firm_id,
            start_date=target_date,
            end_date=target_date,
            now=now,
        )
    finally:
        db.close()


# 2025-01-06 is a Monday. January is PST (UTC-8).
MONDAY_JAN = date(2025, 1, 6)

# 2025-07-07 is a Monday. July is PDT (UTC-7).
MONDAY_JUL = date(2025, 7, 7)


# ---------------------------------------------------------------------------
# GUARD TEST: LA timezone 9:00 AM window -> 17:00 UTC slot (January = PST)
# ---------------------------------------------------------------------------

class TestLATimezoneWindowsProduceCorrectUTCSlots:
    """
    GUARD TEST with watched-fail description:

    Without the fix (treating window times as UTC):
      9:00 AM window -> slot at 9:00 UTC.
      The test asserts slot at 17:00 UTC -> FAILS (red).

    With the fix (localizing window times using America/Los_Angeles):
      9:00 AM PST (January, UTC-8) -> slot at 17:00 UTC -> PASSES (green).

    To verify red: temporarily remove the ZoneInfo localization step in
    _generate_candidate_slots (use tzinfo=timezone.utc directly instead).
    The assertion `assert slot_hour == 17` will fail with 9 instead.
    """

    def test_la_firm_9am_window_january_produces_17_utc_slot(self):
        """9:00 AM window in America/Los_Angeles in January (PST=UTC-8) -> 17:00 UTC slot."""
        firm = _make_firm_with_tz(
            f"la-jan-{uuid.uuid4().hex[:6]}",
            firm_timezone='America/Los_Angeles',
        )
        user = _make_user(firm.id)
        _make_window(
            firm.id, user.id,
            day_of_week=MONDAY_JAN.weekday(),
            start_time=time(9, 0),
            end_time=time(9, 30),
            meeting_duration_minutes=30,
        )

        slots = _run(user.id, firm.id, MONDAY_JAN)

        assert len(slots) == 1, (
            f"Expected exactly 1 slot, got {len(slots)}: {slots}"
        )
        slot_utc = slots[0]['start_time']
        assert slot_utc.hour == 17, (
            f"9:00 AM PST (January, UTC-8) must be 17:00 UTC. "
            f"Got {slot_utc.strftime('%H:%M')} UTC. "
            f"If this is 09:00 UTC, the window time is being treated as UTC rather than local time."
        )
        assert slot_utc.minute == 0

    def test_la_firm_9am_window_july_produces_16_utc_slot(self):
        """9:00 AM window in America/Los_Angeles in July (PDT=UTC-7) -> 16:00 UTC slot."""
        firm = _make_firm_with_tz(
            f"la-jul-{uuid.uuid4().hex[:6]}",
            firm_timezone='America/Los_Angeles',
        )
        user = _make_user(firm.id)
        _make_window(
            firm.id, user.id,
            day_of_week=MONDAY_JUL.weekday(),
            start_time=time(9, 0),
            end_time=time(9, 30),
            meeting_duration_minutes=30,
        )

        slots = _run(user.id, firm.id, MONDAY_JUL)

        assert len(slots) == 1, (
            f"Expected exactly 1 slot, got {len(slots)}: {slots}"
        )
        slot_utc = slots[0]['start_time']
        assert slot_utc.hour == 16, (
            f"9:00 AM PDT (July, UTC-7) must be 16:00 UTC. "
            f"Got {slot_utc.strftime('%H:%M')} UTC."
        )
        assert slot_utc.minute == 0

    def test_new_york_firm_9am_window_january_produces_14_utc_slot(self):
        """9:00 AM window in America/New_York in January (EST=UTC-5) -> 14:00 UTC slot."""
        firm = _make_firm_with_tz(
            f"ny-jan-{uuid.uuid4().hex[:6]}",
            firm_timezone='America/New_York',
        )
        user = _make_user(firm.id)
        _make_window(
            firm.id, user.id,
            day_of_week=MONDAY_JAN.weekday(),
            start_time=time(9, 0),
            end_time=time(9, 30),
            meeting_duration_minutes=30,
        )

        slots = _run(user.id, firm.id, MONDAY_JAN)

        assert len(slots) == 1, (
            f"Expected exactly 1 slot, got {len(slots)}: {slots}"
        )
        slot_utc = slots[0]['start_time']
        assert slot_utc.hour == 14, (
            f"9:00 AM EST (January, UTC-5) must be 14:00 UTC. "
            f"Got {slot_utc.strftime('%H:%M')} UTC."
        )

    def test_utc_firm_9am_window_produces_9_utc_slot(self):
        """9:00 AM window in UTC timezone -> 9:00 UTC slot (no shift)."""
        firm = _make_firm_with_tz(
            f"utc-{uuid.uuid4().hex[:6]}",
            firm_timezone='UTC',
        )
        user = _make_user(firm.id)
        _make_window(
            firm.id, user.id,
            day_of_week=MONDAY_JAN.weekday(),
            start_time=time(9, 0),
            end_time=time(9, 30),
            meeting_duration_minutes=30,
        )

        slots = _run(user.id, firm.id, MONDAY_JAN)

        assert len(slots) == 1
        slot_utc = slots[0]['start_time']
        assert slot_utc.hour == 9, (
            f"9:00 AM UTC must be 9:00 UTC. Got {slot_utc.strftime('%H:%M')} UTC."
        )

    def test_chicago_firm_9am_window_january_produces_15_utc_slot(self):
        """9:00 AM window in America/Chicago in January (CST=UTC-6) -> 15:00 UTC slot."""
        firm = _make_firm_with_tz(
            f"chi-jan-{uuid.uuid4().hex[:6]}",
            firm_timezone='America/Chicago',
        )
        user = _make_user(firm.id)
        _make_window(
            firm.id, user.id,
            day_of_week=MONDAY_JAN.weekday(),
            start_time=time(9, 0),
            end_time=time(9, 30),
            meeting_duration_minutes=30,
        )

        slots = _run(user.id, firm.id, MONDAY_JAN)

        assert len(slots) == 1
        slot_utc = slots[0]['start_time']
        assert slot_utc.hour == 15, (
            f"9:00 AM CST (January, UTC-6) must be 15:00 UTC. "
            f"Got {slot_utc.strftime('%H:%M')} UTC."
        )
