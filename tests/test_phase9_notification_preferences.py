# tests/test_phase9_notification_preferences.py

"""
Phase 9 Step 3 — NotificationPreference test suite.

Covers: default channel behaviour, preference enforcement on notification
creation, API upsert/list, and tenant isolation.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import (
    UserRole,
    RecipientType,
    NotificationType,
    NotificationChannel,
    NotificationEventType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_user(slug, email, role=UserRole.firm_owner, password="testpass123"):
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Test User",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return firm.id, user.id
    finally:
        db.close()


def _login(http_client, email, password="testpass123"):
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _set_preference(firm_id, recipient_id, event_type, channel,
                    recipient_type=RecipientType.staff):
    """Insert / update a preference row directly via CRUD."""
    from app.crud import notification_preference as crud_pref
    db = TestingSessionLocal()
    try:
        crud_pref.upsert_preference(
            db,
            firm_id=firm_id,
            recipient_id=recipient_id,
            recipient_type=recipient_type,
            event_type=event_type,
            channel=channel,
        )
    finally:
        db.close()


# ===========================================================================
# GROUP 1 — Default behaviour
# ===========================================================================

def test_get_channel_for_event_returns_both_when_no_row(client):
    """When no preference row exists, get_channel_for_event returns 'both'."""
    from app.crud import notification_preference as crud_pref

    firm_id, user_id = _make_firm_and_user("pref-default-1", "prefdefault1@test.com")

    db = TestingSessionLocal()
    try:
        channel = crud_pref.get_channel_for_event(
            db,
            firm_id=firm_id,
            recipient_id=user_id,
            recipient_type=RecipientType.staff,
            event_type=NotificationEventType.task_assigned,
        )
        assert channel == NotificationChannel.both
    finally:
        db.close()


def test_create_notification_creates_in_app_record_when_channel_both(client):
    """With no preference set (default=both), create_notification creates an in-app record."""
    from app.services.notification_service import NotificationService
    from app.models.notification import Notification
    from sqlalchemy import select

    firm_id, user_id = _make_firm_and_user("pref-both-1", "prefboth1@test.com")

    db = TestingSessionLocal()
    try:
        notif = NotificationService.create_notification(
            db=db,
            firm_id=firm_id,
            recipient_id=user_id,
            recipient_type=RecipientType.staff,
            title="Test notification",
            body="Test body",
            notification_type=NotificationType.task_assigned,
        )
        assert notif is not None
        assert notif.id is not None

        stmt = select(Notification).where(Notification.id == notif.id)
        record = db.execute(stmt).scalar_one_or_none()
        assert record is not None
    finally:
        db.close()


# ===========================================================================
# GROUP 2 — Preference enforcement
# ===========================================================================

def test_channel_none_prevents_notification_creation(client):
    """Setting channel to 'none' causes create_notification to return None."""
    from app.services.notification_service import NotificationService

    firm_id, user_id = _make_firm_and_user("pref-none-1", "prefnone1@test.com")
    _set_preference(firm_id, user_id, NotificationEventType.task_assigned, NotificationChannel.none)

    db = TestingSessionLocal()
    try:
        result = NotificationService.create_notification(
            db=db,
            firm_id=firm_id,
            recipient_id=user_id,
            recipient_type=RecipientType.staff,
            title="Suppressed",
            body="Should not be stored",
            notification_type=NotificationType.task_assigned,
        )
        assert result is None
    finally:
        db.close()


def test_channel_in_app_creates_record_no_email(client):
    """Setting channel to 'in_app' creates an in-app record and does not attempt email."""
    from app.services.notification_service import NotificationService
    from app.models.notification import Notification
    from sqlalchemy import select
    from unittest.mock import patch

    firm_id, user_id = _make_firm_and_user("pref-inapp-1", "prefinapp1@test.com")
    _set_preference(firm_id, user_id, NotificationEventType.system, NotificationChannel.in_app)

    db = TestingSessionLocal()
    try:
        with patch("app.services.email_service.EmailService.send_notification_email") as mock_email:
            result = NotificationService.create_notification(
                db=db,
                firm_id=firm_id,
                recipient_id=user_id,
                recipient_type=RecipientType.staff,
                title="In-app only",
                body="No email expected",
                notification_type=NotificationType.system,
                to_email="test@example.com",
            )
            # In-app record created
            assert result is not None

            # Email not sent
            mock_email.assert_not_called()

        # Verify record in DB
        stmt = select(Notification).where(Notification.recipient_id == user_id)
        record = db.execute(stmt).scalar_one_or_none()
        assert record is not None
        assert record.title == "In-app only"
    finally:
        db.close()


def test_channel_both_creates_record(client):
    """Setting channel to 'both' explicitly creates an in-app notification record."""
    from app.services.notification_service import NotificationService
    from app.models.notification import Notification
    from sqlalchemy import select

    firm_id, user_id = _make_firm_and_user("pref-both-2", "prefboth2@test.com")
    _set_preference(firm_id, user_id, NotificationEventType.payment_due, NotificationChannel.both)

    db = TestingSessionLocal()
    try:
        result = NotificationService.create_notification(
            db=db,
            firm_id=firm_id,
            recipient_id=user_id,
            recipient_type=RecipientType.staff,
            title="Payment due",
            body="Your invoice is due",
            notification_type=NotificationType.payment_due,
        )
        assert result is not None

        stmt = select(Notification).where(Notification.recipient_id == user_id)
        record = db.execute(stmt).scalar_one_or_none()
        assert record is not None
    finally:
        db.close()


# ===========================================================================
# GROUP 3 — API
# ===========================================================================

def test_get_preferences_returns_empty_list_when_none_set(client):
    """GET /api/v1/notification-preferences/ returns [] when no preferences exist."""
    _make_firm_and_user("pref-api-1", "prefapi1@test.com")
    headers = _login(client, "prefapi1@test.com")

    r = client.get("/api/v1/notification-preferences/", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json() == []


def test_put_preference_upserts_correctly(client):
    """PUT /api/v1/notification-preferences/{event_type} creates a preference row."""
    _make_firm_and_user("pref-api-2", "prefapi2@test.com")
    headers = _login(client, "prefapi2@test.com")

    r = client.put(
        "/api/v1/notification-preferences/task_assigned",
        json={"channel": "in_app"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["event_type"] == "task_assigned"
    assert data["channel"] == "in_app"
    assert "id" in data
    assert "firm_id" in data

    # List to confirm it's stored
    r2 = client.get("/api/v1/notification-preferences/", headers=headers)
    assert r2.status_code == 200, r2.text
    items = r2.json()
    assert len(items) == 1
    assert items[0]["event_type"] == "task_assigned"
    assert items[0]["channel"] == "in_app"


def test_subsequent_put_updates_channel(client):
    """A second PUT for the same event_type updates the channel value."""
    _make_firm_and_user("pref-api-3", "prefapi3@test.com")
    headers = _login(client, "prefapi3@test.com")

    # First upsert
    r1 = client.put(
        "/api/v1/notification-preferences/system",
        json={"channel": "both"},
        headers=headers,
    )
    assert r1.status_code == 200, r1.text
    first_id = r1.json()["id"]

    # Second upsert — should update, not create a new row
    r2 = client.put(
        "/api/v1/notification-preferences/system",
        json={"channel": "none"},
        headers=headers,
    )
    assert r2.status_code == 200, r2.text
    data = r2.json()
    assert data["channel"] == "none"
    assert data["id"] == first_id  # Same row updated, not a new one

    # List to confirm only one row
    r3 = client.get("/api/v1/notification-preferences/", headers=headers)
    items = r3.json()
    assert len(items) == 1
    assert items[0]["channel"] == "none"


# ===========================================================================
# GROUP 4 — Tenant isolation
# ===========================================================================

def test_firm_a_cannot_read_firm_b_preferences(client):
    """Firm A user cannot see firm B's notification preferences."""
    firm_a_id, user_a_id = _make_firm_and_user("pref-isol-a", "prefisolA@test.com")
    firm_b_id, user_b_id = _make_firm_and_user("pref-isol-b", "prefisolB@test.com")

    # Set a preference for user_b in firm_b, but using user_a's ID as recipient
    # (simulates an attempt to plant a row visible to user_a)
    _set_preference(firm_b_id, user_a_id, NotificationEventType.system, NotificationChannel.none)

    # User A queries their own preferences — should see nothing (firm_b row excluded)
    headers_a = _login(client, "prefisolA@test.com")
    r = client.get("/api/v1/notification-preferences/", headers=headers_a)
    assert r.status_code == 200, r.text
    assert r.json() == []
