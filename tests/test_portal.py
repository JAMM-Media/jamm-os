# tests/test_portal.py

"""
Phase 6 — Client Portal test suite.

Tests cover: auth flow, session management, scope enforcement (the security wall),
tenant isolation, dashboard data, and notification CRUD.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.portal_notification import PortalNotification
from app.models.portal_session import PortalSession
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole
from app.services.portal_auth import hash_portal_password


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_staff(slug="test-firm-cpa", staff_email="staff@testfirm.com"):
    """Insert a Firm + firm_owner user directly into the DB. Returns (firm, user)."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Test Firm CPA", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email=staff_email,
            hashed_password=get_password_hash("staffpass"),
            full_name="Staff Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        # Detach objects so they can be used after the session closes
        firm_id = firm.id
        firm_slug = firm.slug
        user_id = user.id
    finally:
        db.close()

    return firm_id, firm_slug, user_id


def _make_portal_client(firm_id, email="client@example.com", password="Password1!", enabled=True):
    """Insert a Client with portal access directly into the DB. Returns client_id."""
    db = TestingSessionLocal()
    try:
        portal_client = Client(
            firm_id=firm_id,
            name="Test Portal Client",
            email=email,
            portal_password_hash=hash_portal_password(password) if enabled else None,
            portal_access_enabled=enabled,
        )
        db.add(portal_client)
        db.commit()
        db.refresh(portal_client)
        client_id = portal_client.id
    finally:
        db.close()
    return client_id


def _portal_login(http_client, firm_slug, email, password):
    """POST /portal/auth/login and return the full response."""
    return http_client.post("/portal/auth/login", json={
        "email": email,
        "firm_slug": firm_slug,
        "password": password,
    })


def _portal_headers(token):
    return {"Authorization": f"Bearer {token}"}


def _staff_login(http_client, staff_email="staff@testfirm.com", staff_pass="staffpass"):
    r = http_client.post("/auth/token", json={"username": staff_email, "password": staff_pass})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ===========================================================================
# AUTH TESTS
# ===========================================================================

def test_portal_invite_accept(client, firm_a_owner):
    """
    Staff generates an invite token; client accepts it and activates portal access.
    """
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    # Create a client WITHOUT portal access
    db = TestingSessionLocal()
    try:
        portal_client = Client(
            firm_id=uuid.UUID(firm_id),
            name="Invite Test Client",
            email="invite@client.com",
            portal_access_enabled=False,
        )
        db.add(portal_client)
        db.commit()
        db.refresh(portal_client)
        client_id = str(portal_client.id)
    finally:
        db.close()

    # Staff generates invite
    r = client.post("/portal/admin/invite", json={"client_id": client_id, "send_email": False}, headers=headers)
    assert r.status_code == 200, r.text
    invite_token = r.json()["invite_token"]
    assert invite_token

    # Client accepts invite
    r2 = client.post("/portal/auth/invite/accept", json={"token": invite_token, "new_password": "NewPass123"})
    assert r2.status_code == 200, r2.text
    assert r2.json()["message"] == "Portal access activated"

    # Verify portal_access_enabled=True in DB
    db = TestingSessionLocal()
    try:
        updated = db.query(Client).filter(Client.id == uuid.UUID(client_id)).first()
        assert updated.portal_access_enabled is True
        assert updated.portal_password_hash is not None
        assert updated.portal_invite_token is None  # cleared after accept
    finally:
        db.close()


def test_portal_login_success(client):
    """After invite accept, client logs in and receives an access token."""
    firm_id, firm_slug, _ = _make_firm_and_staff()
    _make_portal_client(firm_id)

    r = _portal_login(client, firm_slug, "client@example.com", "Password1!")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


def test_portal_login_wrong_password(client):
    """Correct email, wrong password → 401."""
    firm_id, firm_slug, _ = _make_firm_and_staff()
    _make_portal_client(firm_id)

    r = _portal_login(client, firm_slug, "client@example.com", "WrongPassword!")
    assert r.status_code == 401, r.text


def test_portal_login_portal_disabled(client):
    """portal_access_enabled=False → 401 even with correct credentials."""
    firm_id, firm_slug, _ = _make_firm_and_staff()
    _make_portal_client(firm_id, enabled=False)

    r = _portal_login(client, firm_slug, "client@example.com", "Password1!")
    assert r.status_code == 401, r.text


def test_portal_login_wrong_firm_slug(client):
    """Correct credentials but non-existent firm slug → 404."""
    firm_id, firm_slug, _ = _make_firm_and_staff()
    _make_portal_client(firm_id)

    r = _portal_login(client, "no-such-firm", "client@example.com", "Password1!")
    assert r.status_code == 404, r.text


def test_portal_logout(client):
    """
    Client logs in, then logs out.
    Using the same access token after logout → 401 (session revoked).
    """
    firm_id, firm_slug, _ = _make_firm_and_staff()
    _make_portal_client(firm_id)

    login_r = _portal_login(client, firm_slug, "client@example.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]
    headers = _portal_headers(token)

    # Logout
    r_out = client.post("/portal/auth/logout", headers=headers)
    assert r_out.status_code == 200, r_out.text

    # Same token should now be rejected
    r_dash = client.get("/portal/dashboard", headers=headers)
    assert r_dash.status_code == 401, r_dash.text


# ===========================================================================
# SESSION TESTS
# ===========================================================================

def test_session_inactivity_timeout(client):
    """
    Session with last_active_at > 30 min ago is treated as inactive → 401.
    """
    firm_id, firm_slug, _ = _make_firm_and_staff()
    _make_portal_client(firm_id)

    login_r = _portal_login(client, firm_slug, "client@example.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]
    headers = _portal_headers(token)

    # Manually rewind last_active_at to 31 minutes ago
    stale_time = datetime.now(timezone.utc) - timedelta(minutes=31)
    db = TestingSessionLocal()
    try:
        session = db.query(PortalSession).filter(PortalSession.firm_id == firm_id).first()
        assert session is not None
        session.last_active_at = stale_time
        db.commit()
    finally:
        db.close()

    r = client.get("/portal/dashboard", headers=headers)
    assert r.status_code == 401, r.text
    assert "Session expired or inactive" in r.json()["detail"]


def test_session_hard_expiry(client):
    """
    Session with expires_at in the past → treated as expired (revoked by cleanup or check).
    """
    firm_id, firm_slug, _ = _make_firm_and_staff()
    _make_portal_client(firm_id)

    login_r = _portal_login(client, firm_slug, "client@example.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]
    headers = _portal_headers(token)

    # Also rewind last_active_at to keep inactivity check from triggering first,
    # but actually we want expires_at to be in the past — set both
    past_time = datetime.now(timezone.utc) - timedelta(days=1)
    db = TestingSessionLocal()
    try:
        session = db.query(PortalSession).filter(PortalSession.firm_id == firm_id).first()
        assert session is not None
        session.expires_at = past_time
        session.is_revoked = True
        session.revoked_at = past_time
        session.revoked_by = "system"
        db.commit()
    finally:
        db.close()

    r = client.get("/portal/dashboard", headers=headers)
    assert r.status_code == 401, r.text


def test_revoke_all_sessions(client, firm_a_owner):
    """
    Staff revokes all portal sessions for a client → existing portal token → 401.
    """
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    # Create a portal client under firm A
    db = TestingSessionLocal()
    try:
        portal_client = Client(
            firm_id=uuid.UUID(firm_id),
            name="Revoke Test Client",
            email="revoke@client.com",
            portal_password_hash=hash_portal_password("Password1!"),
            portal_access_enabled=True,
        )
        db.add(portal_client)
        db.commit()
        db.refresh(portal_client)
        client_id = str(portal_client.id)
        firm_slug = db.query(Firm).filter(Firm.id == uuid.UUID(firm_id)).first().slug
    finally:
        db.close()

    # Client logs in
    login_r = _portal_login(client, firm_slug, "revoke@client.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    portal_token = login_r.json()["access_token"]
    portal_hdrs = _portal_headers(portal_token)

    # Verify dashboard works
    assert client.get("/portal/dashboard", headers=portal_hdrs).status_code == 200

    # Staff revokes all sessions
    r_revoke = client.post(f"/portal/admin/revoke/{client_id}", headers=headers)
    assert r_revoke.status_code == 200, r_revoke.text
    assert r_revoke.json()["sessions_revoked"] >= 1

    # Portal token is now invalid
    r_dash = client.get("/portal/dashboard", headers=portal_hdrs)
    assert r_dash.status_code == 401, r_dash.text


# ===========================================================================
# SCOPE ENFORCEMENT TESTS
# ===========================================================================

def test_staff_token_rejected_on_portal_endpoint(client):
    """
    A valid staff JWT MUST be rejected on portal endpoints.
    The scope="client_portal" claim is the enforcement wall.
    """
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="scope-test-firm", staff_email="scope_staff@firm.com")

    # Get staff JWT
    staff_headers = _staff_login(client, staff_email="scope_staff@firm.com")

    # Use staff token on a portal endpoint → must be 401, not 200
    r = client.get("/portal/dashboard", headers=staff_headers)
    assert r.status_code == 401, r.text


def test_portal_token_rejected_on_staff_endpoint(client):
    """
    A valid portal JWT MUST be rejected on staff endpoints.
    Staff endpoints expect a user token (scope != "client_portal").
    """
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="scope-test-firm2", staff_email="scope_staff2@firm.com")
    _make_portal_client(firm_id, email="scope_client@example.com")

    # Get portal JWT
    login_r = _portal_login(client, firm_slug, "scope_client@example.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    portal_token = login_r.json()["access_token"]
    portal_hdrs = _portal_headers(portal_token)

    # Use portal token on a staff endpoint → must be 401
    r = client.get("/clients/", headers=portal_hdrs)
    assert r.status_code == 401, r.text


# ===========================================================================
# TENANT ISOLATION TESTS
# ===========================================================================

def test_client_cannot_access_other_clients_engagement(client):
    """
    Client A cannot read Client B's engagement — even in the same firm.
    """
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="isolation-firm", staff_email="iso_staff@firm.com")

    client_a_id = _make_portal_client(firm_id, email="client_a@example.com", password="PassA1!")
    client_b_id = _make_portal_client(firm_id, email="client_b@example.com", password="PassB1!")

    # Create an engagement for Client B
    db = TestingSessionLocal()
    try:
        eng = Engagement(
            firm_id=firm_id,
            client_id=client_b_id,
            name="Client B Engagement",
            status="active",
        )
        db.add(eng)
        db.commit()
        db.refresh(eng)
        engagement_b_id = str(eng.id)
    finally:
        db.close()

    # Client A logs in and tries to read Client B's engagement
    login_r = _portal_login(client, firm_slug, "client_a@example.com", "PassA1!")
    assert login_r.status_code == 200, login_r.text
    token_a = login_r.json()["access_token"]

    r = client.get(f"/portal/engagements/{engagement_b_id}", headers=_portal_headers(token_a))
    assert r.status_code == 404, r.text


def test_cross_firm_portal_isolation(client):
    """
    A client from Firm X cannot log in using Firm Y's slug — even with valid credentials.
    """
    firm_x_id, firm_x_slug, _ = _make_firm_and_staff(slug="firm-x", staff_email="staff@firmx.com")
    firm_y_id, firm_y_slug, _ = _make_firm_and_staff(slug="firm-y", staff_email="staff@firmy.com")

    # Create a client under Firm X
    _make_portal_client(firm_x_id, email="client@firmx.com", password="Password1!")

    # Try to log in using Firm Y's slug → 401 (client doesn't exist under firm Y)
    r = _portal_login(client, firm_y_slug, "client@firmx.com", "Password1!")
    assert r.status_code == 401, r.text


# ===========================================================================
# DASHBOARD TESTS
# ===========================================================================

def test_portal_dashboard_returns_correct_data(client):
    """
    Dashboard includes the client's active engagements.
    """
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="dashboard-firm", staff_email="dash_staff@firm.com")
    client_id = _make_portal_client(firm_id, email="dash_client@example.com")

    # Create an engagement for this client
    db = TestingSessionLocal()
    try:
        eng = Engagement(
            firm_id=firm_id,
            client_id=client_id,
            name="Tax Return 2025",
            status="active",
        )
        db.add(eng)
        db.commit()
        db.refresh(eng)
        eng_id = str(eng.id)
    finally:
        db.close()

    login_r = _portal_login(client, firm_slug, "dash_client@example.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]

    r = client.get("/portal/dashboard", headers=_portal_headers(token))
    assert r.status_code == 200, r.text
    data = r.json()

    ids = [e["id"] for e in data["active_engagements"]]
    assert eng_id in ids


def test_portal_dashboard_hides_internal_notes(client):
    """
    Engagement detail endpoint exposes notes_client_visible but NEVER notes (internal).
    """
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="notes-firm", staff_email="notes_staff@firm.com")
    client_id = _make_portal_client(firm_id, email="notes_client@example.com")

    db = TestingSessionLocal()
    try:
        eng = Engagement(
            firm_id=firm_id,
            client_id=client_id,
            name="Notes Test Engagement",
            status="active",
            notes="secret staff note",
            notes_client_visible="visible to client",
        )
        db.add(eng)
        db.commit()
        db.refresh(eng)
        eng_id = str(eng.id)
    finally:
        db.close()

    login_r = _portal_login(client, firm_slug, "notes_client@example.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]

    r = client.get(f"/portal/engagements/{eng_id}", headers=_portal_headers(token))
    assert r.status_code == 200, r.text
    data = r.json()

    # Internal notes must NOT appear
    assert "secret staff note" not in str(data)
    assert "notes" not in data or data.get("notes") is None  # key absent or null

    # Client-visible notes MUST appear
    assert data.get("notes_client_visible") == "visible to client"


# ===========================================================================
# NOTIFICATION TESTS
# ===========================================================================

def test_create_notification_appears_in_feed(client):
    """A notification created directly in the DB appears in GET /portal/notifications."""
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="notif-firm", staff_email="notif_staff@firm.com")
    client_id = _make_portal_client(firm_id, email="notif_client@example.com")

    # Insert notification directly
    db = TestingSessionLocal()
    try:
        notif = PortalNotification(
            firm_id=firm_id,
            client_id=client_id,
            title="Your document is ready",
            notification_type="document_request",
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        notif_id = str(notif.id)
    finally:
        db.close()

    login_r = _portal_login(client, firm_slug, "notif_client@example.com", "Password1!")
    assert login_r.status_code == 200, login_r.text
    token = login_r.json()["access_token"]

    r = client.get("/portal/notifications", headers=_portal_headers(token))
    assert r.status_code == 200, r.text
    ids = [n["id"] for n in r.json()]
    assert notif_id in ids


def test_mark_single_notification_read(client):
    """PATCH /portal/notifications/{id}/read sets is_read=True and read_at."""
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="read-firm", staff_email="read_staff@firm.com")
    client_id = _make_portal_client(firm_id, email="read_client@example.com")

    db = TestingSessionLocal()
    try:
        notif = PortalNotification(
            firm_id=firm_id,
            client_id=client_id,
            title="Sign your engagement letter",
            notification_type="signature_needed",
        )
        db.add(notif)
        db.commit()
        db.refresh(notif)
        notif_id = str(notif.id)
    finally:
        db.close()

    login_r = _portal_login(client, firm_slug, "read_client@example.com", "Password1!")
    token = login_r.json()["access_token"]

    r = client.patch(f"/portal/notifications/{notif_id}/read", headers=_portal_headers(token))
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["is_read"] is True
    assert data["read_at"] is not None


def test_mark_all_notifications_read(client):
    """POST /portal/notifications/read-all marks all unread and returns count=3."""
    firm_id, firm_slug, _ = _make_firm_and_staff(slug="readall-firm", staff_email="readall_staff@firm.com")
    client_id = _make_portal_client(firm_id, email="readall_client@example.com")

    db = TestingSessionLocal()
    try:
        for i in range(3):
            notif = PortalNotification(
                firm_id=firm_id,
                client_id=client_id,
                title=f"Notification {i}",
                notification_type="system",
            )
            db.add(notif)
        db.commit()
    finally:
        db.close()

    login_r = _portal_login(client, firm_slug, "readall_client@example.com", "Password1!")
    token = login_r.json()["access_token"]

    r = client.post("/portal/notifications/read-all", headers=_portal_headers(token))
    assert r.status_code == 200, r.text
    assert r.json()["marked_read"] == 3

    # Verify in DB — all three should be read
    db = TestingSessionLocal()
    try:
        unread = db.query(PortalNotification).filter(
            PortalNotification.client_id == client_id,
            PortalNotification.is_read.is_(False),
        ).count()
        assert unread == 0
    finally:
        db.close()
