# tests/test_meeting_location.py

"""
Tests for the per-staff meeting location setting on User
(meeting_location_type and meeting_location_value columns).

Covers:
  - Both fields default to null when not set.
  - Each of the three MeetingLocationType values can be written and read back.
"""

import uuid

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import MeetingLocationType, UserRole


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
        _ = firm.id
        return firm
    finally:
        db.close()


def _make_user(
    firm_id,
    meeting_location_type=None,
    meeting_location_value=None,
) -> User:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="not-a-real-hash",
            role=UserRole.staff,
            meeting_location_type=meeting_location_type,
            meeting_location_value=meeting_location_value,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        _ = user.id, user.meeting_location_type, user.meeting_location_value
        return user
    finally:
        db.close()


def _fetch_user(user_id) -> User:
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        _ = user.id, user.meeting_location_type, user.meeting_location_value
        return user
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMeetingLocationFields:

    def test_both_fields_default_to_null(self):
        """A User created without meeting location fields has both set to null."""
        firm = _make_firm(f"ml-null-{uuid.uuid4().hex[:6]}")
        user = _make_user(firm.id)

        fetched = _fetch_user(user.id)
        assert fetched.meeting_location_type is None, (
            "meeting_location_type must default to null when not provided"
        )
        assert fetched.meeting_location_value is None, (
            "meeting_location_value must default to null when not provided"
        )

    def test_video_location_round_trips(self):
        """meeting_location_type=video and a Zoom URL can be written and read back."""
        firm = _make_firm(f"ml-video-{uuid.uuid4().hex[:6]}")
        user = _make_user(
            firm.id,
            meeting_location_type=MeetingLocationType.video,
            meeting_location_value="https://zoom.us/j/123456789",
        )

        fetched = _fetch_user(user.id)
        assert fetched.meeting_location_type == MeetingLocationType.video, (
            f"Expected MeetingLocationType.video, got {fetched.meeting_location_type!r}"
        )
        assert fetched.meeting_location_value == "https://zoom.us/j/123456789"

    def test_phone_location_round_trips(self):
        """meeting_location_type=phone and a phone number can be written and read back."""
        firm = _make_firm(f"ml-phone-{uuid.uuid4().hex[:6]}")
        user = _make_user(
            firm.id,
            meeting_location_type=MeetingLocationType.phone,
            meeting_location_value="+1 617-555-0100",
        )

        fetched = _fetch_user(user.id)
        assert fetched.meeting_location_type == MeetingLocationType.phone
        assert fetched.meeting_location_value == "+1 617-555-0100"

    def test_office_location_round_trips(self):
        """meeting_location_type=office and an address can be written and read back."""
        firm = _make_firm(f"ml-office-{uuid.uuid4().hex[:6]}")
        user = _make_user(
            firm.id,
            meeting_location_type=MeetingLocationType.office,
            meeting_location_value="123 Main St, Suite 400, Boston MA 02110",
        )

        fetched = _fetch_user(user.id)
        assert fetched.meeting_location_type == MeetingLocationType.office
        assert fetched.meeting_location_value == "123 Main St, Suite 400, Boston MA 02110"

    def test_meeting_location_can_be_updated(self):
        """A user's meeting location type and value can be changed after creation."""
        firm = _make_firm(f"ml-update-{uuid.uuid4().hex[:6]}")
        user = _make_user(
            firm.id,
            meeting_location_type=MeetingLocationType.video,
            meeting_location_value="https://meet.google.com/old-link",
        )

        db = TestingSessionLocal()
        try:
            row = db.query(User).filter(User.id == user.id).first()
            row.meeting_location_type = MeetingLocationType.phone
            row.meeting_location_value = "+1 617-555-0199"
            db.commit()
        finally:
            db.close()

        fetched = _fetch_user(user.id)
        assert fetched.meeting_location_type == MeetingLocationType.phone
        assert fetched.meeting_location_value == "+1 617-555-0199"
