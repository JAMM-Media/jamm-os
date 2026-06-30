# tests/test_session_jti.py

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from tests.conftest import TestingSessionLocal
from app.core.config import get_settings
from app.core.enums import UserRole
from app.core.security import (
    get_password_hash,
    generate_staff_refresh_token,
    hash_staff_refresh_token,
)
from app.models.firm import Firm
from app.models.user import User
from app.services.staff_refresh_service import refresh_staff_access_token

settings = get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_user(email: str, password: str = "testpass123", session_jti: str = None) -> tuple:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"JTI Test Firm {uuid.uuid4().hex[:6]}", slug=f"jti-{uuid.uuid4().hex[:6]}")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="JTI Test User",
            role=UserRole.firm_owner,
            current_session_jti=session_jti,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return firm.id, user.id
    finally:
        db.close()


def _set_refresh_token(user_id, raw_token: str):
    db = TestingSessionLocal()
    try:
        user = db.get(User, user_id)
        user.staff_refresh_token_hash = hash_staff_refresh_token(raw_token)
        user.staff_refresh_expires_at = datetime.now(timezone.utc) + timedelta(hours=8)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 1: Login token contains a jti claim that is a valid UUID
# ---------------------------------------------------------------------------

def test_login_token_contains_jti(client):
    email = f"jti-login-{uuid.uuid4().hex[:6]}@test.com"
    password = "testpass123"
    _make_firm_and_user(email, password)

    resp = client.post("/auth/token", json={"username": email, "password": password})
    assert resp.status_code == 200, resp.json()

    token = resp.json()["access_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert "jti" in payload, "jti claim missing from access token"
    jti = payload["jti"]
    parsed = uuid.UUID(jti)
    assert str(parsed) == jti


# ---------------------------------------------------------------------------
# Test 2: jti is stable across a token refresh (carried forward, not regenerated)
# ---------------------------------------------------------------------------

def test_jti_stable_across_refresh():
    known_jti = str(uuid.uuid4())
    email = f"jti-refresh-{uuid.uuid4().hex[:6]}@test.com"
    _, user_id = _make_firm_and_user(email, session_jti=known_jti)

    raw_token = generate_staff_refresh_token()
    _set_refresh_token(user_id, raw_token)

    db = TestingSessionLocal()
    try:
        result = refresh_staff_access_token(raw_token, db)
    finally:
        db.close()

    assert result is not None, "refresh returned None"
    payload = jwt.decode(result["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    assert payload.get("jti") == known_jti, (
        f"Expected jti={known_jti!r}, got {payload.get('jti')!r}"
    )


# ---------------------------------------------------------------------------
# Test 3: Legacy session (current_session_jti=None) heals forward on refresh
# ---------------------------------------------------------------------------

def test_legacy_session_without_jti_heals():
    email = f"jti-heal-{uuid.uuid4().hex[:6]}@test.com"
    _, user_id = _make_firm_and_user(email, session_jti=None)

    raw_token = generate_staff_refresh_token()
    _set_refresh_token(user_id, raw_token)

    db = TestingSessionLocal()
    try:
        result = refresh_staff_access_token(raw_token, db)
    finally:
        db.close()

    assert result is not None, "refresh returned None"
    payload = jwt.decode(result["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    new_jti = payload.get("jti")
    assert new_jti is not None, "jti should have been minted for legacy session"
    uuid.UUID(new_jti)  # must be a valid UUID

    # Verify the user record was also updated
    db2 = TestingSessionLocal()
    try:
        user = db2.get(User, user_id)
        assert user.current_session_jti == new_jti, "user.current_session_jti not updated"
    finally:
        db2.close()


# ---------------------------------------------------------------------------
# Test 4: Adding jti did not break token_version invalidation
# ---------------------------------------------------------------------------

def test_token_version_still_validates(client):
    email = f"jti-version-{uuid.uuid4().hex[:6]}@test.com"
    password = "testpass123"
    _, user_id = _make_firm_and_user(email, password)

    # Obtain a valid token
    resp = client.post("/auth/token", json={"username": email, "password": password})
    assert resp.status_code == 200, resp.json()
    token = resp.json()["access_token"]

    # Confirm it works
    me = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200

    # Increment token_version in the DB to invalidate existing tokens
    db = TestingSessionLocal()
    try:
        user = db.get(User, user_id)
        user.token_version += 1
        db.commit()
    finally:
        db.close()

    # Old token must now be rejected
    me2 = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me2.status_code == 401, (
        f"Expected 401 after token_version bump, got {me2.status_code}"
    )
