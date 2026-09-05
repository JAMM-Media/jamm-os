# tests/test_peer_network_announcement_event.py
"""
Tests for the peer_network.announcement_posted behavioral event added to
app/api/peer_network.py.

Covers:
  1. Posting to the Announcements room fires exactly one event (not one per
     recipient), with correct firm_id, entity reference, and recipient_count.
  2. Posting to a non-Announcements room does NOT fire the event.
  3. If log_event raises, the message post still succeeds and the notification
     loop still completes (fire-and-forget guarantee).
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(db):
    from app.models.firm import Firm
    firm = Firm(
        name=f"Ann Test Firm {uuid.uuid4().hex[:6]}",
        slug=f"ann-test-{uuid.uuid4().hex[:6]}",
        peer_network_enabled=True,
    )
    db.add(firm)
    db.commit()
    db.refresh(firm)
    return firm


def _make_member(db, firm_id, suffix=None, role=None):
    from app.models.user import User
    from app.models.peer_network import PeerNetworkMember
    from app.core.security import get_password_hash
    from app.core.enums import UserRole

    s = suffix or uuid.uuid4().hex[:6]
    email = f"ann-{s}@test.com"
    user = User(
        firm_id=firm_id,
        email=email,
        hashed_password=get_password_hash("testpass"),
        full_name=f"Ann User {s}",
        role=role if role is not None else UserRole.manager,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    member = PeerNetworkMember(
        user_id=user.id,
        firm_id=firm_id,
        handle=f"@ann{s}",
        is_active=True,
        terms_accepted_at=datetime.now(timezone.utc),
    )
    db.add(member)
    db.commit()
    db.refresh(member)
    return email, member


def _make_room(db, room_type="announcements", name=None):
    from app.models.peer_network import PeerNetworkRoom, PeerNetworkRoomMember
    room = PeerNetworkRoom(room_type=room_type, name=name)
    db.add(room)
    db.commit()
    db.refresh(room)
    return room


def _login(client, email):
    r = client.post("/auth/token", json={"username": email, "password": "testpass"})
    assert r.status_code == 200, f"Login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _count_events(firm_id, event_type):
    from app.models.behavioral_event import BehavioralEvent
    db = TestingSessionLocal()
    try:
        return db.query(BehavioralEvent).filter(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == event_type,
        ).count()
    finally:
        db.close()


def _get_event(firm_id, event_type):
    from app.models.behavioral_event import BehavioralEvent
    db = TestingSessionLocal()
    try:
        return db.query(BehavioralEvent).filter(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == event_type,
        ).first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Announcements post fires exactly one event with correct fields
# ---------------------------------------------------------------------------

class TestAnnouncementEventFires:

    def test_one_event_per_broadcast_not_per_recipient(self, client):
        """Posting to Announcements fires exactly one peer_network.announcement_posted
        event, regardless of how many members are in the network."""
        db = TestingSessionLocal()
        try:
            firm = _make_firm(db)
            firm_id = firm.id
            email1, member1 = _make_member(db, firm_id, "post1", role=UserRole.system_admin)
            email2, member2 = _make_member(db, firm_id, "rcpt2")
            email3, member3 = _make_member(db, firm_id, "rcpt3")
            room = _make_room(db, room_type="announcements")
            room_id = room.id
        finally:
            db.close()

        headers = _login(client, email1)
        r = client.post(
            f"/peer-network/rooms/{room_id}/messages",
            json={"body": "Hello everyone from announcements!"},
            headers=headers,
        )
        assert r.status_code == 201, f"Post failed: {r.json()}"

        count = _count_events(firm_id, "peer_network.announcement_posted")
        assert count == 1, (
            f"Expected exactly 1 peer_network.announcement_posted event, got {count}"
        )

    def test_event_has_correct_metadata(self, client):
        """The event carries firm_id, entity reference, and recipient_count."""
        db = TestingSessionLocal()
        try:
            firm = _make_firm(db)
            firm_id = firm.id
            email1, member1 = _make_member(db, firm_id, "post2a", role=UserRole.system_admin)
            email2, member2 = _make_member(db, firm_id, "rcpt2a")
            email3, member3 = _make_member(db, firm_id, "rcpt3a")
            room = _make_room(db, room_type="announcements")
            room_id = room.id
        finally:
            db.close()

        headers = _login(client, email1)
        r = client.post(
            f"/peer-network/rooms/{room_id}/messages",
            json={"body": "Announcement metadata test"},
            headers=headers,
        )
        assert r.status_code == 201, f"Post failed: {r.json()}"
        message_id = r.json().get("id")

        event = _get_event(firm_id, "peer_network.announcement_posted")
        assert event is not None, "Event must be written"
        assert str(event.firm_id) == str(firm_id)
        assert event.entity_type == "peer_network_message"
        assert event.actor_type == "staff"

        meta = event.extra_metadata or {}
        assert "room_id" in meta, f"room_id missing from metadata: {meta}"
        assert str(meta["room_id"]) == str(room_id)
        assert "recipient_count" in meta, f"recipient_count missing from metadata: {meta}"
        # 2 recipients (member2 and member3); poster (member1) excluded
        assert meta["recipient_count"] == 2, (
            f"Expected recipient_count=2, got {meta['recipient_count']}"
        )


# ---------------------------------------------------------------------------
# 2. Non-Announcements rooms do NOT fire the event
# ---------------------------------------------------------------------------

class TestNonAnnouncementsRoomNoEvent:

    def test_dm_post_does_not_fire_announcement_event(self, client):
        """Posting to a DM room must NOT fire peer_network.announcement_posted."""
        db = TestingSessionLocal()
        try:
            from app.models.peer_network import PeerNetworkRoomMember
            firm = _make_firm(db)
            firm_id = firm.id
            email1, member1 = _make_member(db, firm_id, "dm1a")
            email2, member2 = _make_member(db, firm_id, "dm1b")
            room = _make_room(db, room_type="dm")
            db.add(PeerNetworkRoomMember(room_id=room.id, member_id=member1.id))
            db.add(PeerNetworkRoomMember(room_id=room.id, member_id=member2.id))
            db.commit()
            room_id = room.id
        finally:
            db.close()

        headers = _login(client, email1)
        r = client.post(
            f"/peer-network/rooms/{room_id}/messages",
            json={"body": "Hello in DM"},
            headers=headers,
        )
        assert r.status_code == 201, f"DM post failed: {r.json()}"

        count = _count_events(firm_id, "peer_network.announcement_posted")
        assert count == 0, (
            f"DM post must not fire announcement event, but found {count}"
        )

    def test_main_room_post_does_not_fire_announcement_event(self, client):
        """Posting to the main room must NOT fire peer_network.announcement_posted."""
        db = TestingSessionLocal()
        try:
            from app.models.peer_network import PeerNetworkRoomMember
            firm = _make_firm(db)
            firm_id = firm.id
            email1, member1 = _make_member(db, firm_id, "main1a")
            room = _make_room(db, room_type="main")
            db.add(PeerNetworkRoomMember(room_id=room.id, member_id=member1.id))
            db.commit()
            room_id = room.id
        finally:
            db.close()

        headers = _login(client, email1)
        r = client.post(
            f"/peer-network/rooms/{room_id}/messages",
            json={"body": "Hello in main"},
            headers=headers,
        )
        assert r.status_code == 201, f"Main room post failed: {r.json()}"

        count = _count_events(firm_id, "peer_network.announcement_posted")
        assert count == 0, (
            f"Main room post must not fire announcement event, but found {count}"
        )


# ---------------------------------------------------------------------------
# 3. Fire-and-forget: log_event failure does not abort the message post
# ---------------------------------------------------------------------------

class TestFireAndForget:

    def test_log_event_failure_does_not_abort_message_post(self, client):
        """If log_event raises, the message is still created and the call succeeds."""
        db = TestingSessionLocal()
        try:
            firm = _make_firm(db)
            firm_id = firm.id
            email1, member1 = _make_member(db, firm_id, "faf1a", role=UserRole.system_admin)
            email2, member2 = _make_member(db, firm_id, "faf1b")
            room = _make_room(db, room_type="announcements")
            room_id = room.id
        finally:
            db.close()

        headers = _login(client, email1)

        with patch(
            "app.services.behavioral_log.log_event",
            side_effect=RuntimeError("simulated log_event failure"),
        ) as mock_log:
            r = client.post(
                f"/peer-network/rooms/{room_id}/messages",
                json={"body": "Fire and forget test"},
                headers=headers,
            )

        # The post must succeed even though log_event raised
        assert r.status_code == 201, (
            f"Message post must succeed even when log_event raises. "
            f"Got {r.status_code}: {r.json()}"
        )
        assert r.json().get("body") == "Fire and forget test"
