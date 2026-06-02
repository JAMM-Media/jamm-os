# tests/test_phase9_notifications.py

"""
Phase 9 — Notification system test suite.

Covers: create, list, unread count, mark as read, tenant isolation,
and automation engine integration.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole, RecipientType, NotificationType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_user(slug, email, role=UserRole.firm_owner, password="testpass123"):
    """Create a Firm + User in the DB. Returns (firm_id, user_id)."""
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


def _create_notification_directly(firm_id, recipient_id, recipient_type=RecipientType.staff,
                                   notification_type=NotificationType.system,
                                   title="Test Notification", body="Test body",
                                   is_read=False):
    """Insert a Notification directly into the DB for test setup."""
    from app.models.notification import Notification
    db = TestingSessionLocal()
    try:
        n = Notification(
            firm_id=firm_id,
            recipient_id=recipient_id,
            recipient_type=recipient_type,
            title=title,
            body=body,
            notification_type=notification_type,
            is_read=is_read,
        )
        db.add(n)
        db.commit()
        db.refresh(n)
        return str(n.id)
    finally:
        db.close()


# ===========================================================================
# GROUP 1 — Create notification
# ===========================================================================

def test_create_notification_for_staff_recipient(client):
    """Directly creating a notification for a staff recipient succeeds."""
    from app.models.notification import Notification
    from app.services.notification_service import NotificationService

    firm_id, user_id = _make_firm_and_user("notif-staff-1", "staff1@test.com")

    db = TestingSessionLocal()
    try:
        n = NotificationService.create_notification(
            db=db,
            firm_id=firm_id,
            recipient_id=user_id,
            recipient_type=RecipientType.staff,
            title="Task assigned to you",
            body="Please complete the tax return.",
            notification_type=NotificationType.task_assigned,
        )
        assert n.id is not None
        assert n.firm_id == firm_id
        assert n.recipient_id == user_id
        assert n.recipient_type == RecipientType.staff
        assert n.title == "Task assigned to you"
        assert n.is_read is False
        assert n.read_at is None
    finally:
        db.close()


def test_create_notification_for_client_recipient(client):
    """Directly creating a notification for a client recipient succeeds."""
    from app.services.notification_service import NotificationService

    firm_id, _ = _make_firm_and_user("notif-client-1", "clientowner@test.com")
    client_recipient_id = uuid.uuid4()  # Soft reference — no FK

    db = TestingSessionLocal()
    try:
        n = NotificationService.create_notification(
            db=db,
            firm_id=firm_id,
            recipient_id=client_recipient_id,
            recipient_type=RecipientType.client,
            title="Your document is ready",
            body="Please review your document.",
            notification_type=NotificationType.doc_request_ready,
        )
        assert n.id is not None
        assert n.recipient_type == RecipientType.client
        assert n.recipient_id == client_recipient_id
    finally:
        db.close()


# ===========================================================================
# GROUP 2 — List and count
# ===========================================================================

def test_list_notifications_returns_only_current_recipient(client):
    """GET /api/v1/notifications/ returns only the authenticated user's notifications."""
    firm_id, user_id = _make_firm_and_user("notif-list-1", "list1@test.com")
    other_user_id = uuid.uuid4()

    # Create 2 notifications for our user, 1 for another recipient
    _create_notification_directly(firm_id, user_id, title="For me 1")
    _create_notification_directly(firm_id, user_id, title="For me 2")
    _create_notification_directly(firm_id, other_user_id, title="Not for me")

    headers = _login(client, "list1@test.com")
    r = client.get("/api/v1/notifications/", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 2
    assert len(data["items"]) == 2
    titles = {item["title"] for item in data["items"]}
    assert "For me 1" in titles
    assert "For me 2" in titles
    assert "Not for me" not in titles


def test_unread_count_returns_correct_number(client):
    """GET /api/v1/notifications/unread-count returns correct unread count."""
    firm_id, user_id = _make_firm_and_user("notif-count-1", "count1@test.com")

    _create_notification_directly(firm_id, user_id, title="Unread 1", is_read=False)
    _create_notification_directly(firm_id, user_id, title="Unread 2", is_read=False)
    _create_notification_directly(firm_id, user_id, title="Read already", is_read=True)

    headers = _login(client, "count1@test.com")
    r = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["count"] == 2


def test_unread_only_filter_returns_only_unread(client):
    """GET /api/v1/notifications/?unread_only=true returns only unread notifications."""
    firm_id, user_id = _make_firm_and_user("notif-unread-1", "unread1@test.com")

    _create_notification_directly(firm_id, user_id, title="Unread", is_read=False)
    _create_notification_directly(firm_id, user_id, title="Read", is_read=True)

    headers = _login(client, "unread1@test.com")
    r = client.get("/api/v1/notifications/?unread_only=true", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["title"] == "Unread"
    assert data["items"][0]["is_read"] is False


# ===========================================================================
# GROUP 3 — Mark as read
# ===========================================================================

def test_mark_single_notification_as_read(client):
    """PATCH /api/v1/notifications/{id}/read sets is_read=True and read_at."""
    firm_id, user_id = _make_firm_and_user("notif-read-1", "read1@test.com")
    notif_id = _create_notification_directly(firm_id, user_id, title="Mark me read")

    headers = _login(client, "read1@test.com")
    r = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_read"] is True
    assert data["read_at"] is not None


def test_mark_all_as_read_updates_all_unread(client):
    """PATCH /api/v1/notifications/read-all updates all unread for recipient."""
    firm_id, user_id = _make_firm_and_user("notif-readall-1", "readall1@test.com")

    _create_notification_directly(firm_id, user_id, title="Unread 1", is_read=False)
    _create_notification_directly(firm_id, user_id, title="Unread 2", is_read=False)
    _create_notification_directly(firm_id, user_id, title="Already read", is_read=True)

    headers = _login(client, "readall1@test.com")
    r = client.patch("/api/v1/notifications/read-all", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["updated"] == 2

    # Verify unread count is now 0
    r2 = client.get("/api/v1/notifications/unread-count", headers=headers)
    assert r2.json()["count"] == 0


def test_cannot_mark_another_recipients_notification_as_read(client):
    """PATCH /{id}/read returns 404 when notification belongs to a different recipient."""
    firm_id, user_a_id = _make_firm_and_user("notif-cross-1", "cross1@test.com")

    # Create user_b in the same firm
    db = TestingSessionLocal()
    try:
        user_b = User(
            firm_id=firm_id,
            email="cross2@test.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="User B",
            role=UserRole.staff,
        )
        db.add(user_b)
        db.commit()
    finally:
        db.close()

    # Create a notification for user_a
    notif_id = _create_notification_directly(firm_id, user_a_id, title="User A's notification")

    # Log in as user_b and try to mark user_a's notification as read
    headers_b = _login(client, "cross2@test.com")
    r = client.patch(f"/api/v1/notifications/{notif_id}/read", headers=headers_b)
    assert r.status_code == 404, r.text


# ===========================================================================
# GROUP 4 — Tenant isolation
# ===========================================================================

def test_firm_a_cannot_see_firm_b_notifications(client):
    """Notifications from firm B are not visible to firm A users."""
    firm_a_id, user_a_id = _make_firm_and_user("notif-isol-a", "isola@test.com")
    firm_b_id, user_b_id = _make_firm_and_user("notif-isol-b", "isolb@test.com")

    # Create a notification in firm B
    _create_notification_directly(firm_b_id, user_a_id, title="Firm B notification for A's ID")

    headers_a = _login(client, "isola@test.com")
    r = client.get("/api/v1/notifications/", headers=headers_a)
    assert r.status_code == 200, r.text
    data = r.json()
    # Firm A user should see 0 notifications (even though recipient_id matches,
    # the firm_id filter ensures tenant isolation)
    assert data["total"] == 0


# ===========================================================================
# GROUP 5 — Automation engine integration
# ===========================================================================

def test_send_notification_action_creates_notification_record(client):
    """send_notification automation action creates a Notification record in the DB."""
    from app.services import automation_actions
    from app.models.notification import Notification
    from sqlalchemy import select

    firm_id, user_id = _make_firm_and_user("notif-auto-1", "auto1@test.com")

    payload = {
        "firm_id": str(firm_id),
        "recipient_id": str(user_id),
        "recipient_type": "staff",
        "title": "Automation triggered notification",
        "body": "This was sent by an automation rule.",
        "notification_type": "task_assigned",
    }

    # Execute the action directly — it creates its own DB session internally
    result = automation_actions._handle_send_notification(
        config={},
        payload=payload,
        db=None,  # handler creates its own session
    )
    assert "sent" in result.lower() or str(user_id) in result

    # Verify the record exists in the DB
    db = TestingSessionLocal()
    try:
        stmt = select(Notification).where(
            Notification.firm_id == firm_id,
            Notification.recipient_id == user_id,
        )
        record = db.execute(stmt).scalar_one_or_none()
        assert record is not None
        assert record.title == "Automation triggered notification"
        assert record.recipient_type == RecipientType.staff
    finally:
        db.close()


def test_send_notification_action_skips_when_missing_recipient(client):
    """send_notification returns a skip message when recipient_id is missing."""
    from app.services import automation_actions

    result = automation_actions._handle_send_notification(
        config={},
        payload={"firm_id": str(uuid.uuid4()), "title": "Has title but no recipient"},
        db=None,
    )
    assert "skipped" in result.lower()


def test_send_notification_action_skips_when_missing_title(client):
    """send_notification returns a skip message when title is missing."""
    from app.services import automation_actions

    result = automation_actions._handle_send_notification(
        config={},
        payload={"firm_id": str(uuid.uuid4()), "recipient_id": str(uuid.uuid4())},
        db=None,
    )
    assert "skipped" in result.lower()
