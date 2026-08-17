# tests/test_slot_computation.py

"""
Tests for slot_computation_service.compute_available_slots.

GUARD TEST: test_partial_buffer_overlap_excludes_slot
Watched-fail cycle: temporarily changes the overlap check from "any overlap"
to "fully contained", runs a test where a slot partially overlaps a buffer
window, confirms it wrongly gets offered (red), restores, confirms it is
correctly excluded (green).
"""

import uuid
from datetime import date, datetime, time, timedelta, timezone

from tests.conftest import TestingSessionLocal
from app.models.availability_window import AvailabilityWindow
from app.models.booking import Booking
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import BookingStatus, UserRole
from app.services.slot_computation_service import compute_available_slots


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
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


def _make_window(
    firm_id,
    user_id,
    day_of_week: int,
    start_time: time,
    end_time: time,
    meeting_duration_minutes: int = 30,
    buffer_before_minutes: int = 0,
    buffer_after_minutes: int = 0,
    daily_cap: int | None = None,
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
            meeting_duration_minutes=meeting_duration_minutes,
            buffer_before_minutes=buffer_before_minutes,
            buffer_after_minutes=buffer_after_minutes,
            daily_cap=daily_cap,
            created_at=now,
            updated_at=now,
        )
        db.add(window)
        db.commit()
        db.refresh(window)
        _ = window.id
        return window
    finally:
        db.close()


def _make_booking(
    firm_id,
    staff_user_id,
    start_time: datetime,
    end_time: datetime,
    status: BookingStatus = BookingStatus.scheduled,
) -> Booking:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        booking = Booking(
            firm_id=firm_id,
            staff_user_id=staff_user_id,
            start_time=start_time,
            end_time=end_time,
            status=status,
            created_at=now,
            updated_at=now,
        )
        db.add(booking)
        db.commit()
        db.refresh(booking)
        _ = booking.id
        return booking
    finally:
        db.close()


def _run(staff_user_id, firm_id, target_date: date, now: datetime = None) -> list[dict]:
    """Call compute_available_slots for a single day with a fresh DB session."""
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


def _dt(d: date, h: int, m: int = 0) -> datetime:
    """Build a UTC-aware datetime for a given date and hour:minute."""
    return datetime(d.year, d.month, d.day, h, m, tzinfo=timezone.utc)


# A fixed Monday in the past so slots are never filtered as "past".
MONDAY = date(2025, 1, 6)   # Monday
TUESDAY = date(2025, 1, 7)  # Tuesday
# now set far in the past so nothing is filtered.
PAST_NOW = datetime(2020, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# GUARD TEST: partial buffer overlap excludes slot
# ---------------------------------------------------------------------------

class TestPartialBufferOverlapGuard:
    """GUARD TEST with watched-fail cycle.

    A slot that partially overlaps a booking's buffer window must be excluded.
    The wrong "fully contained" check would wrongly offer it.

    Setup:
      - Window: 09:00-11:00, 30-minute slots, 15-min buffer before and after
      - Existing booking: 10:00-10:30
      - Protected window: 09:45-10:45
      - Candidate slot 09:30-10:00: partially overlaps the protected window
        (the tail 09:45-10:00 falls inside it). Must be excluded.
    """

    def test_partial_buffer_overlap_excludes_slot(self):
        """A slot whose tail partially overlaps the buffer window is excluded."""
        firm = _make_firm(f"guard-buf-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        day = MONDAY
        _make_window(
            firm.id, user.id,
            day_of_week=day.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
            meeting_duration_minutes=30,
            buffer_before_minutes=15,
            buffer_after_minutes=15,
        )
        # Existing booking at 10:00-10:30. Protected window: 09:45-10:45.
        _make_booking(firm.id, user.id, _dt(day, 10, 0), _dt(day, 10, 30))

        slots = _run(user.id, firm.id, day, now=PAST_NOW)
        start_times = [s["start_time"].hour * 60 + s["start_time"].minute for s in slots]

        # 09:30 slot: 09:30-10:00 overlaps 09:45-10:45. Must NOT be offered.
        assert 9 * 60 + 30 not in start_times, (
            "Slot 09:30-10:00 partially overlaps the buffer window (09:45-10:45) "
            "and must be excluded. Got slots: "
            + str([s["start_time"].strftime("%H:%M") for s in slots])
        )
        # 10:45 slot: 10:45-11:15 -- beyond window end. Must not exist.
        # 09:00 slot: 09:00-09:30 does NOT overlap 09:45-10:45. Must be offered.
        assert 9 * 60 + 0 in start_times, (
            "Slot 09:00-09:30 does not overlap the buffer window and must be offered. "
            "Got slots: " + str([s["start_time"].strftime("%H:%M") for s in slots])
        )


# ---------------------------------------------------------------------------
# No availability window -> zero slots
# ---------------------------------------------------------------------------

class TestNoWindow:

    def test_no_window_for_day_produces_zero_slots(self):
        """A day with no AvailabilityWindow for that day_of_week produces zero slots."""
        firm = _make_firm(f"no-win-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        # Monday window only -- query Tuesday
        _make_window(
            firm.id, user.id,
            day_of_week=MONDAY.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
        )
        slots = _run(user.id, firm.id, TUESDAY, now=PAST_NOW)
        assert slots == [], (
            f"Tuesday has no window; expected zero slots, got {len(slots)}"
        )


# ---------------------------------------------------------------------------
# Daily cap
# ---------------------------------------------------------------------------

class TestDailyCap:

    def test_daily_cap_reached_produces_zero_slots(self):
        """When active bookings equal the daily_cap, zero slots are returned."""
        firm = _make_firm(f"cap-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        day = MONDAY
        _make_window(
            firm.id, user.id,
            day_of_week=day.weekday(),
            start_time=time(9, 0),
            end_time=time(17, 0),
            daily_cap=2,
        )
        # Two scheduled bookings -- cap reached.
        _make_booking(firm.id, user.id, _dt(day, 9, 0), _dt(day, 9, 30))
        _make_booking(firm.id, user.id, _dt(day, 10, 0), _dt(day, 10, 30))

        slots = _run(user.id, firm.id, day, now=PAST_NOW)
        assert slots == [], (
            f"Daily cap of 2 reached; expected zero slots, got {len(slots)}"
        )

    def test_canceled_booking_does_not_count_against_cap(self):
        """A canceled booking does not count toward the daily cap."""
        firm = _make_firm(f"cap-cancel-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        day = MONDAY
        _make_window(
            firm.id, user.id,
            day_of_week=day.weekday(),
            start_time=time(9, 0),
            end_time=time(11, 0),
            meeting_duration_minutes=30,
            daily_cap=1,
        )
        # One canceled booking (does NOT count) + zero active bookings = cap not reached.
        _make_booking(
            firm.id, user.id,
            _dt(day, 9, 0), _dt(day, 9, 30),
            status=BookingStatus.canceled,
        )

        slots = _run(user.id, firm.id, day, now=PAST_NOW)
        assert len(slots) > 0, (
            "Cap=1 with only a canceled booking; should still have open slots but got zero"
        )

    def test_canceled_booking_does_not_block_any_slot(self):
        """A canceled booking does not block any time slot via conflict check."""
        firm = _make_firm(f"cancel-block-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        day = MONDAY
        _make_window(
            firm.id, user.id,
            day_of_week=day.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            meeting_duration_minutes=30,
        )
        # Canceled booking at 09:00-09:30.
        _make_booking(
            firm.id, user.id,
            _dt(day, 9, 0), _dt(day, 9, 30),
            status=BookingStatus.canceled,
        )

        slots = _run(user.id, firm.id, day, now=PAST_NOW)
        start_times = [s["start_time"].hour * 60 + s["start_time"].minute for s in slots]
        assert 9 * 60 + 0 in start_times, (
            "09:00 slot must be available -- canceled bookings must not block slots. "
            "Got: " + str([s["start_time"].strftime("%H:%M") for s in slots])
        )


# ---------------------------------------------------------------------------
# Buffer stacking
# ---------------------------------------------------------------------------

class TestBufferStacking:

    def test_two_adjacent_bookings_buffers_stack(self):
        """Two back-to-back bookings' buffers combine, blocking more time than either alone.

        Setup:
          Window: 09:00-13:00, 30-min slots, 15 min buffer before and after.
          Booking A: 09:30-10:00. Protected: 09:15-10:15.
          Booking B: 10:30-11:00. Protected: 10:15-11:15.
          The gap between A's after-buffer end (10:15) and B's before-buffer start (10:15)
          is exactly zero -- any 30-min slot starting in [09:15, 10:15) or [09:45, 11:15)
          is blocked. The combined blocked region spans 09:15-11:15.

        Surviving slots: 09:00-09:15 is not a full 30-min slot so not offered.
        Only 11:15 start or later qualify, i.e. 11:00... wait, let me recalculate.

        Window: 09:00-13:00, 30-min slots starting at 09:00, 09:30, 10:00, 10:30, 11:00, 11:30, 12:00, 12:30.
        Booking A: 09:30-10:00. Protected A: 09:15-10:15.
        Booking B: 10:30-11:00. Protected B: 10:15-11:15.

        09:00-09:30: overlaps Protected A (09:00 < 10:15 AND 09:30 > 09:15) -> blocked.
        09:30-10:00: overlaps Protected A -> blocked.
        10:00-10:30: overlaps Protected A (10:00 < 10:15) AND overlaps Protected B (10:30 > 10:15) -> blocked.
        10:30-11:00: overlaps Protected B -> blocked.
        11:00-11:30: 11:00 < 11:15 -> overlaps Protected B -> blocked.
        11:30-12:00: 11:30 >= 11:15 -> NOT blocked. Offered.
        12:00-12:30: not blocked. Offered.
        12:30-13:00: not blocked. Offered.
        """
        firm = _make_firm(f"buf-stack-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        day = MONDAY
        _make_window(
            firm.id, user.id,
            day_of_week=day.weekday(),
            start_time=time(9, 0),
            end_time=time(13, 0),
            meeting_duration_minutes=30,
            buffer_before_minutes=15,
            buffer_after_minutes=15,
        )
        _make_booking(firm.id, user.id, _dt(day, 9, 30), _dt(day, 10, 0))
        _make_booking(firm.id, user.id, _dt(day, 10, 30), _dt(day, 11, 0))

        slots = _run(user.id, firm.id, day, now=PAST_NOW)
        start_minutes = [s["start_time"].hour * 60 + s["start_time"].minute for s in slots]

        # These slots must be blocked due to stacked buffers.
        for blocked_hm in [(9, 0), (9, 30), (10, 0), (10, 30), (11, 0)]:
            assert blocked_hm[0] * 60 + blocked_hm[1] not in start_minutes, (
                f"Slot {blocked_hm[0]:02d}:{blocked_hm[1]:02d} must be blocked by stacked buffers. "
                f"Got slots: {[s['start_time'].strftime('%H:%M') for s in slots]}"
            )

        # These slots must be available after the combined blocked region clears.
        for avail_hm in [(11, 30), (12, 0), (12, 30)]:
            assert avail_hm[0] * 60 + avail_hm[1] in start_minutes, (
                f"Slot {avail_hm[0]:02d}:{avail_hm[1]:02d} must be available after stacked buffers. "
                f"Got slots: {[s['start_time'].strftime('%H:%M') for s in slots]}"
            )


# ---------------------------------------------------------------------------
# Slot fragment too short
# ---------------------------------------------------------------------------

class TestSlotFragments:

    def test_leftover_fragment_shorter_than_duration_not_offered(self):
        """A window fragment shorter than meeting_duration_minutes is not offered.

        Window: 09:00-10:15, 30-min slots.
        Slots: 09:00-09:30 (full), 09:30-10:00 (full). Remaining: 10:00-10:15 (15 min = fragment).
        The 10:00-10:15 fragment must NOT be offered.
        """
        firm = _make_firm(f"frag-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        day = MONDAY
        _make_window(
            firm.id, user.id,
            day_of_week=day.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 15),
            meeting_duration_minutes=30,
        )

        slots = _run(user.id, firm.id, day, now=PAST_NOW)
        start_minutes = [s["start_time"].hour * 60 + s["start_time"].minute for s in slots]

        assert 10 * 60 + 0 not in start_minutes, (
            "10:00 fragment (15 min < 30 min duration) must not be offered as a slot"
        )
        assert 9 * 60 + 0 in start_minutes, "09:00 full slot must be offered"
        assert 9 * 60 + 30 in start_minutes, "09:30 full slot must be offered"
        assert len(slots) == 2, (
            f"Expected exactly 2 full slots, got {len(slots)}: "
            + str([s["start_time"].strftime("%H:%M") for s in slots])
        )


# ---------------------------------------------------------------------------
# Past slot filtering
# ---------------------------------------------------------------------------

class TestPastSlotFiltering:

    def test_slots_starting_before_now_are_excluded(self):
        """Slots that start before now must never be returned."""
        firm = _make_firm(f"past-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)
        day = MONDAY
        _make_window(
            firm.id, user.id,
            day_of_week=day.weekday(),
            start_time=time(9, 0),
            end_time=time(12, 0),
            meeting_duration_minutes=30,
        )
        # now = 10:00 on this day -- slots before 10:00 must be excluded.
        now = _dt(day, 10, 0)

        slots = _run(user.id, firm.id, day, now=now)
        for slot in slots:
            assert slot["start_time"] >= now, (
                f"Slot {slot['start_time']} starts before now ({now}) and must be excluded"
            )

        start_times = [s["start_time"].hour * 60 + s["start_time"].minute for s in slots]
        assert 9 * 60 + 0 not in start_times, "09:00 slot is before now, must be excluded"
        assert 9 * 60 + 30 not in start_times, "09:30 slot is before now, must be excluded"
        assert 10 * 60 + 0 in start_times, "10:00 slot starts at now, must be included"


# ---------------------------------------------------------------------------
# Multi-day range
# ---------------------------------------------------------------------------

class TestMultiDayRange:

    def test_slots_computed_correctly_across_multiple_days(self):
        """Slots are returned for each day that has a window and open time."""
        firm = _make_firm(f"multi-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)

        # Monday window: 09:00-10:00, 30-min slots = 2 slots.
        _make_window(
            firm.id, user.id,
            day_of_week=MONDAY.weekday(),
            start_time=time(9, 0),
            end_time=time(10, 0),
            meeting_duration_minutes=30,
        )
        # Tuesday: no window.
        # Wednesday: window 14:00-15:30, 30-min slots = 3 slots.
        wednesday = date(2025, 1, 8)
        _make_window(
            firm.id, user.id,
            day_of_week=wednesday.weekday(),
            start_time=time(14, 0),
            end_time=time(15, 30),
            meeting_duration_minutes=30,
        )

        db = TestingSessionLocal()
        try:
            slots = compute_available_slots(
                db=db,
                staff_user_id=user.id,
                firm_id=firm.id,
                start_date=MONDAY,
                end_date=wednesday,
                now=PAST_NOW,
            )
        finally:
            db.close()

        # Monday: 09:00 and 09:30.
        monday_slots = [s for s in slots if s["start_time"].date() == MONDAY]
        assert len(monday_slots) == 2, (
            f"Expected 2 Monday slots, got {len(monday_slots)}"
        )

        # Tuesday: zero slots (no window).
        tuesday_slots = [s for s in slots if s["start_time"].date() == TUESDAY]
        assert len(tuesday_slots) == 0, (
            f"Expected 0 Tuesday slots, got {len(tuesday_slots)}"
        )

        # Wednesday: 14:00, 14:30, 15:00.
        wed_slots = [s for s in slots if s["start_time"].date() == wednesday]
        assert len(wed_slots) == 3, (
            f"Expected 3 Wednesday slots, got {len(wed_slots)}"
        )
