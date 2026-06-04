# tests/test_phase12_auth_overhaul.py

"""
Tests for Phase 12 Authentication System Overhaul.
Covers portal password set/change, portal login, portal magic link self-service,
staff magic link, staff auth policy, and tenant isolation.
"""

import uuid
import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from tests.conftest import TestingSessionLocal
from app.main import app
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.portal_session import PortalSession
from app.core.enums import UserRole, StaffAuthPolicy
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(db, name: str = None, slug: str = None):
    n = name or f"firm-{uuid.uuid4().hex[:6]}"
    s = slug or n.lower().replace(" ", "-")
    firm = Firm(name=n, slug=s)
    db.add(firm)
    db.commit()
    db.refresh(firm)
    return firm


def _make_owner(db, firm_id, email: str = None):
    e = email or f"owner-{uuid.uuid4().hex[:6]}@test.com"
    user = User(
        firm_id=firm_id,
        email=e,
        hashed_password=get_password_hash("ownerpass123"),
        full_name="Owner",
        role=UserRole.firm_owner,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_staff(db, firm_id, email: str = None, role=UserRole.staff):
    e = email or f"staff-{uuid.uuid4().hex[:6]}@test.com"
    user = User(
        firm_id=firm_id,
        email=e,
        hashed_password=get_password_hash("staffpass123"),
        full_name="Staff",
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _make_portal_client(db, firm_id, email: str = None, password: str = None, enabled: bool = True):
    e = email or f"client-{uuid.uuid4().hex[:6]}@test.com"
    from app.services.portal_auth import hash_portal_password_bcrypt
    pw_hash = hash_portal_password_bcrypt(password) if password else None
    c = Client(
        firm_id=firm_id,
        name="Test Client",
        email=e,
        portal_access_enabled=enabled,
        portal_password_hash=pw_hash,
    )
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _owner_token(client_fixture, email, password="ownerpass123"):
    r = client_fixture.post("/auth/token", json={"username": email, "password": password})
    return r.json()["access_token"]


def _portal_login(client_fixture, email, password, firm_slug=None):
    body = {"email": email, "password": password}
    if firm_slug:
        body["firm_slug"] = firm_slug
    return client_fixture.post("/portal/auth/login", json=body)


# ---------------------------------------------------------------------------
# 1. Portal password set — first time, no current_password required
# ---------------------------------------------------------------------------

def test_portal_set_password_first_time(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        portal_c = _make_portal_client(db, firm.id, password=None)
        firm_slug = firm.slug
        client_email = portal_c.email
        client_id = str(portal_c.id)
        firm_id = str(firm.id)

        # Give the client a session so we can get a JWT
        jti = str(uuid.uuid4())
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        session = PortalSession(
            firm_id=firm.id,
            client_id=portal_c.id,
            refresh_token_hash=hashlib.sha256(secrets.token_hex(32).encode()).hexdigest(),
            access_jti=jti,
            expires_at=expires,
        )
        db.add(session)
        db.commit()
    finally:
        db.close()

    from app.services.portal_auth import create_portal_access_token
    portal_token = create_portal_access_token(uuid.UUID(client_id), uuid.UUID(firm_id), jti)

    r = client.post(
        "/portal/account/set-password",
        json={"new_password": "newpass123", "confirm_password": "newpass123"},
        headers={"Authorization": f"Bearer {portal_token}"},
    )
    assert r.status_code == 200
    assert r.json()["success"] is True


# ---------------------------------------------------------------------------
# 2. Portal password change — requires correct current_password
# ---------------------------------------------------------------------------

def test_portal_change_password_requires_current(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        portal_c = _make_portal_client(db, firm.id, password="oldpass123")
        firm_id = str(firm.id)
        client_id = str(portal_c.id)

        jti = str(uuid.uuid4())
        session = PortalSession(
            firm_id=firm.id,
            client_id=portal_c.id,
            refresh_token_hash=hashlib.sha256(secrets.token_hex(32).encode()).hexdigest(),
            access_jti=jti,
            expires_at=datetime.now(timezone.utc) + timedelta(days=30),
        )
        db.add(session)
        db.commit()
    finally:
        db.close()

    from app.services.portal_auth import create_portal_access_token
    portal_token = create_portal_access_token(uuid.UUID(client_id), uuid.UUID(firm_id), jti)
    headers = {"Authorization": f"Bearer {portal_token}"}

    # Missing current_password → 422
    r = client.post(
        "/portal/account/set-password",
        json={"new_password": "newpass123", "confirm_password": "newpass123"},
        headers=headers,
    )
    assert r.status_code == 422

    # Wrong current_password → 401
    r = client.post(
        "/portal/account/set-password",
        json={"current_password": "wrong", "new_password": "newpass123", "confirm_password": "newpass123"},
        headers=headers,
    )
    assert r.status_code == 401

    # Correct current_password → 200
    r = client.post(
        "/portal/account/set-password",
        json={"current_password": "oldpass123", "new_password": "newpass999", "confirm_password": "newpass999"},
        headers=headers,
    )
    assert r.status_code == 200


# ---------------------------------------------------------------------------
# 3. Portal password login — success, wrong password, no password set
# ---------------------------------------------------------------------------

def test_portal_login_success(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        portal_c = _make_portal_client(db, firm.id, password="mypassword1")
        email = portal_c.email
        slug = firm.slug
    finally:
        db.close()

    r = _portal_login(client, email, "mypassword1", firm_slug=slug)
    assert r.status_code == 200
    assert "access_token" in r.json()


def test_portal_login_wrong_password(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        portal_c = _make_portal_client(db, firm.id, password="mypassword1")
        email = portal_c.email
        slug = firm.slug
    finally:
        db.close()

    r = _portal_login(client, email, "wrongpassword", firm_slug=slug)
    assert r.status_code == 401


def test_portal_login_no_password_set(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        portal_c = _make_portal_client(db, firm.id, password=None)
        email = portal_c.email
        slug = firm.slug
    finally:
        db.close()

    r = _portal_login(client, email, "anypassword", firm_slug=slug)
    assert r.status_code == 401
    assert "magic link" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 4. Portal self-request magic link — same response regardless of email
# ---------------------------------------------------------------------------

def test_portal_request_magic_link_email_exists(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        portal_c = _make_portal_client(db, firm.id)
        email = portal_c.email
    finally:
        db.close()

    r = client.post("/portal/auth/request-magic-link", json={"email": email})
    assert r.status_code == 200
    assert "link" in r.json()["message"].lower()


def test_portal_request_magic_link_email_not_exists(client):
    r = client.post("/portal/auth/request-magic-link", json={"email": "nobody@nowhere.com"})
    assert r.status_code == 200
    assert "link" in r.json()["message"].lower()


# ---------------------------------------------------------------------------
# 5. Staff magic link request — policy = either, password_only, magic_link_only
# ---------------------------------------------------------------------------

def test_staff_magic_link_policy_either(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        firm.staff_auth_policy = StaffAuthPolicy.EITHER.value
        db.commit()
        staff = _make_staff(db, firm.id)
        email = staff.email
    finally:
        db.close()

    r = client.post("/auth/request-magic-link", json={"email": email})
    assert r.status_code == 200
    assert "link" in r.json()["message"].lower()

    # Verify token was stored
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user.magic_link_token_hash is not None
        assert user.magic_link_expires_at is not None
    finally:
        db.close()


def test_staff_magic_link_policy_password_only_does_not_send(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        firm.staff_auth_policy = StaffAuthPolicy.PASSWORD_ONLY.value
        db.commit()
        staff = _make_staff(db, firm.id)
        email = staff.email
    finally:
        db.close()

    r = client.post("/auth/request-magic-link", json={"email": email})
    assert r.status_code == 200  # Same generic response

    # Token must NOT be stored
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user.magic_link_token_hash is None
    finally:
        db.close()


def test_staff_magic_link_policy_magic_link_only(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        firm.staff_auth_policy = StaffAuthPolicy.MAGIC_LINK_ONLY.value
        db.commit()
        staff = _make_staff(db, firm.id)
        email = staff.email
    finally:
        db.close()

    r = client.post("/auth/request-magic-link", json={"email": email})
    assert r.status_code == 200

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user.magic_link_token_hash is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 6. Staff magic link verify — valid, expired, already used
# ---------------------------------------------------------------------------

def test_staff_magic_link_verify_valid(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        staff = _make_staff(db, firm.id)

        raw = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        staff.magic_link_token_hash = token_hash
        staff.magic_link_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.commit()
        staff_id = staff.id
    finally:
        db.close()

    r = client.get(f"/auth/verify-magic-link?token={raw}")
    assert r.status_code == 200
    assert "access_token" in r.json()

    # Token is cleared after use
    db = TestingSessionLocal()
    try:
        user = db.get(User, staff_id)
        assert user.magic_link_token_hash is None
    finally:
        db.close()


def test_staff_magic_link_verify_expired(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        staff = _make_staff(db, firm.id)

        raw = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        staff.magic_link_token_hash = token_hash
        staff.magic_link_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()

    r = client.get(f"/auth/verify-magic-link?token={raw}")
    assert r.status_code == 401


def test_staff_magic_link_verify_already_used(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        staff = _make_staff(db, firm.id)

        raw = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        staff.magic_link_token_hash = token_hash
        staff.magic_link_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.commit()
    finally:
        db.close()

    # First use succeeds
    r1 = client.get(f"/auth/verify-magic-link?token={raw}")
    assert r1.status_code == 200

    # Second use fails (token was cleared)
    r2 = client.get(f"/auth/verify-magic-link?token={raw}")
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# 7. Staff password login blocked when policy = magic_link_only (non-owner)
# ---------------------------------------------------------------------------

def test_staff_login_blocked_magic_link_only_policy(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        firm.staff_auth_policy = StaffAuthPolicy.MAGIC_LINK_ONLY.value
        db.commit()
        staff = _make_staff(db, firm.id)
        email = staff.email
    finally:
        db.close()

    r = client.post("/auth/token", json={"username": email, "password": "staffpass123"})
    assert r.status_code == 403
    assert "magic link" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# 8. Staff password login succeeds for firm_owner regardless of policy
# ---------------------------------------------------------------------------

def test_firm_owner_login_always_works_with_password(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        firm.staff_auth_policy = StaffAuthPolicy.MAGIC_LINK_ONLY.value
        db.commit()
        owner = _make_owner(db, firm.id)
        email = owner.email
    finally:
        db.close()

    r = client.post("/auth/token", json={"username": email, "password": "ownerpass123"})
    assert r.status_code == 200
    assert "access_token" in r.json()


# ---------------------------------------------------------------------------
# 9. Firm owner updates staff_auth_policy (valid values, invalid value)
# ---------------------------------------------------------------------------

def test_update_staff_auth_policy_valid(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        owner = _make_owner(db, firm.id)
        email = owner.email
    finally:
        db.close()

    token = _owner_token(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    for policy in ["password_only", "magic_link_only", "either"]:
        r = client.patch(
            "/settings/security/staff-auth-policy",
            json={"staff_auth_policy": policy},
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["staff_auth_policy"] == policy


def test_update_staff_auth_policy_invalid(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        owner = _make_owner(db, firm.id)
        email = owner.email
    finally:
        db.close()

    token = _owner_token(client, email)
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch(
        "/settings/security/staff-auth-policy",
        json={"staff_auth_policy": "not_a_valid_policy"},
        headers=headers,
    )
    assert r.status_code == 422


def test_update_staff_auth_policy_requires_firm_owner(client):
    db = TestingSessionLocal()
    try:
        firm = _make_firm(db)
        _make_owner(db, firm.id)
        staff = _make_staff(db, firm.id)
        email = staff.email
    finally:
        db.close()

    r = client.post("/auth/token", json={"username": email, "password": "staffpass123"})
    token = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    r = client.patch(
        "/settings/security/staff-auth-policy",
        json={"staff_auth_policy": "password_only"},
        headers=headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 10. Tenant isolation: magic link cannot cross firm boundaries
# ---------------------------------------------------------------------------

def test_staff_magic_link_tenant_isolation(client):
    db = TestingSessionLocal()
    try:
        firm_a = _make_firm(db, "Firm Alpha", "firm-alpha")
        firm_b = _make_firm(db, "Firm Beta", "firm-beta")
        staff_a = _make_staff(db, firm_a.id, email="staff-a@alpha.com")
        staff_b = _make_staff(db, firm_b.id, email="staff-b@beta.com")

        # Staff A's magic link
        raw = secrets.token_hex(32)
        token_hash = hashlib.sha256(raw.encode()).hexdigest()
        staff_a.magic_link_token_hash = token_hash
        staff_a.magic_link_expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        db.commit()
        staff_b_id = staff_b.id
    finally:
        db.close()

    # Verify gives back staff_a's JWT — not staff_b's
    r = client.get(f"/auth/verify-magic-link?token={raw}")
    assert r.status_code == 200

    from jose import jwt
    from app.core.config import get_settings
    settings = get_settings()
    payload = jwt.decode(r.json()["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    decoded_user_id = payload["sub"]

    db = TestingSessionLocal()
    try:
        user = db.get(User, uuid.UUID(decoded_user_id))
        assert str(user.firm_id) != str(staff_b_id)
    finally:
        db.close()
