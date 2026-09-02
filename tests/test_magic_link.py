# tests/test_magic_link.py

"""
Session 4 — Magic-Link Client Portal Access tests.

Tests cover: send magic link (staff-side), exchange token (client-side),
expiry enforcement, and one-time-use enforcement.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from tests.conftest import TestingSessionLocal
from app.models.behavioral_event import BehavioralEvent
from app.models.client import Client
from app.models.firm import Firm
from app.models.portal_session import PortalSession
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_owner(email, slug):
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Magic Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        firm_id = firm.id

        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("password123"),
            full_name="Magic Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    return firm_id


def _make_client(firm_id, email):
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=firm_id,
            name="Magic Test Client",
            email=email,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        client_id = c.id
    finally:
        db.close()
    return client_id


def _make_session_with_magic_link(firm_id, client_id, raw_token, expires_at):
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    db = TestingSessionLocal()
    try:
        session = PortalSession(
            firm_id=firm_id,
            client_id=client_id,
            refresh_token_hash=hashlib.sha256(secrets.token_hex(32).encode()).hexdigest(),
            access_jti=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            magic_link_token_hash=token_hash,
            magic_link_expires_at=expires_at,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        session_id = session.id
    finally:
        db.close()
    return session_id


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_send_magic_link_success(client):
    """
    Staff POSTs /portal/magic-link → 201, sent=True, token stored in DB.
    """
    firm_id = _make_firm_owner(email="owner_ml1@test.com", slug="magic-firm-1")
    client_id = _make_client(firm_id, email="client_ml1@test.com")

    login = client.post("/auth/token", json={"username": "owner_ml1@test.com", "password": "password123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/portal/magic-link",
        json={"client_id": str(client_id), "expiry_hours": 48},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["sent"] is True
    assert data["expires_at"] is not None

    db = TestingSessionLocal()
    try:
        session = db.execute(
            select(PortalSession).where(PortalSession.client_id == client_id)
        ).scalar_one_or_none()
        assert session is not None
        assert session.magic_link_token_hash is not None
    finally:
        db.close()


def test_exchange_magic_link_success(client):
    """
    Valid token exchange → 200, access_token present, token cleared from DB.
    """
    firm_id = _make_firm_owner(email="owner_ml2@test.com", slug="magic-firm-2")
    client_id = _make_client(firm_id, email="client_ml2@test.com")

    raw_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    session_id = _make_session_with_magic_link(firm_id, client_id, raw_token, expires_at)

    r = client.get(f"/portal/auth?token={raw_token}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "access_token" in data

    db = TestingSessionLocal()
    try:
        s = db.get(PortalSession, session_id)
        assert s.magic_link_token_hash is None
    finally:
        db.close()


def test_exchange_magic_link_expired(client):
    """
    Expired token → 401.
    """
    firm_id = _make_firm_owner(email="owner_ml3@test.com", slug="magic-firm-3")
    client_id = _make_client(firm_id, email="client_ml3@test.com")

    raw_token = secrets.token_hex(32)
    past_expires = datetime.now(timezone.utc) - timedelta(hours=1)
    _make_session_with_magic_link(firm_id, client_id, raw_token, past_expires)

    r = client.get(f"/portal/auth?token={raw_token}")
    assert r.status_code == 401, r.text


def test_exchange_magic_link_one_time_use(client):
    """
    Second use of same token → 401 (cleared after first use).
    """
    firm_id = _make_firm_owner(email="owner_ml4@test.com", slug="magic-firm-4")
    client_id = _make_client(firm_id, email="client_ml4@test.com")

    raw_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    _make_session_with_magic_link(firm_id, client_id, raw_token, expires_at)

    r1 = client.get(f"/portal/auth?token={raw_token}")
    assert r1.status_code == 200, r1.text

    r2 = client.get(f"/portal/auth?token={raw_token}")
    assert r2.status_code == 401, r2.text


def test_exchange_magic_link_fires_first_login_and_login_events(client):
    """
    A client's first-ever magic-link exchange fires both portal.first_login
    and portal.login, and sets Client.portal_last_login_at.
    """
    firm_id = _make_firm_owner(email="owner_ml5@test.com", slug="magic-firm-5")
    client_id = _make_client(firm_id, email="client_ml5@test.com")

    raw_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    _make_session_with_magic_link(firm_id, client_id, raw_token, expires_at)

    r = client.get(f"/portal/auth?token={raw_token}")
    assert r.status_code == 200, r.text

    db = TestingSessionLocal()
    try:
        c = db.get(Client, client_id)
        assert c.portal_last_login_at is not None

        first_login = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == client_id,
                BehavioralEvent.event_type == "portal.first_login",
            )
        ).scalar_one_or_none()
        assert first_login is not None
        assert first_login.extra_metadata["login_method"] == "magic_link"

        login = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == client_id,
                BehavioralEvent.event_type == "portal.login",
            )
        ).scalar_one_or_none()
        assert login is not None
    finally:
        db.close()


def test_exchange_magic_link_repeat_login_does_not_refire_first_login(client):
    """
    A client who has already logged in once (portal_last_login_at already set)
    fires portal.login on a later magic-link exchange, but not portal.first_login again.
    """
    firm_id = _make_firm_owner(email="owner_ml6@test.com", slug="magic-firm-6")
    client_id = _make_client(firm_id, email="client_ml6@test.com")

    db = TestingSessionLocal()
    try:
        c = db.get(Client, client_id)
        c.portal_last_login_at = datetime.now(timezone.utc) - timedelta(days=3)
        db.commit()
    finally:
        db.close()

    raw_token = secrets.token_hex(32)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=48)
    _make_session_with_magic_link(firm_id, client_id, raw_token, expires_at)

    r = client.get(f"/portal/auth?token={raw_token}")
    assert r.status_code == 200, r.text

    db = TestingSessionLocal()
    try:
        first_login_count = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == client_id,
                BehavioralEvent.event_type == "portal.first_login",
            )
        ).scalars().all()
        assert len(first_login_count) == 0

        login = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == client_id,
                BehavioralEvent.event_type == "portal.login",
            )
        ).scalar_one_or_none()
        assert login is not None
    finally:
        db.close()

def test_generate_magic_link_with_multiple_existing_sessions_does_not_raise(client):
    """
    Calling generate_magic_link when the client already has multiple non-revoked
    PortalSessions must not raise MultipleResultsFound. It should return 201 and
    reuse the most recently created session.

    Regression test for the scalar_one_or_none() -> scalars().first() fix.
    """
    import secrets
    firm_id = _make_firm_owner(email="owner_ml7@test.com", slug="magic-firm-7")
    client_id = _make_client(firm_id, email="client_ml7@test.com")

    # Seed 3 non-revoked sessions to reproduce the crash condition
    db = TestingSessionLocal()
    try:
        for _ in range(3):
            session = PortalSession(
                firm_id=firm_id,
                client_id=client_id,
                refresh_token_hash=hashlib.sha256(secrets.token_hex(32).encode()).hexdigest(),
                access_jti=str(uuid.uuid4()),
                expires_at=datetime.now(timezone.utc) + timedelta(days=30),
            )
            db.add(session)
        db.commit()
    finally:
        db.close()

    # Confirm 3 sessions exist before the call
    db = TestingSessionLocal()
    try:
        from sqlalchemy import select as sa_select
        count = len(db.execute(
            sa_select(PortalSession).where(
                PortalSession.client_id == client_id,
                PortalSession.firm_id == firm_id,
                PortalSession.is_revoked.is_(False),
            )
        ).scalars().all())
        assert count == 3, f"expected 3 sessions, got {count}"
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": "owner_ml7@test.com", "password": "password123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.post(
        "/portal/magic-link",
        json={"client_id": str(client_id), "expiry_hours": 48},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["sent"] is True
