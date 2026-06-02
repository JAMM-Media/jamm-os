# tests/test_password_reset.py

import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


@pytest.fixture
def test_user(client):
    """Creates a firm + staff user and returns (email, password, user_id)."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Reset Test Firm", slug="reset-test-firm")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email="resetuser@example.com",
            hashed_password=get_password_hash("oldpassword1"),
            full_name="Reset User",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = user.id
    finally:
        db.close()

    return {"email": "resetuser@example.com", "password": "oldpassword1", "user_id": user_id}


def test_forgot_password_known_email(client, test_user):
    r = client.post("/auth/forgot-password", json={"email": test_user["email"]})
    assert r.status_code == 200
    body = r.json()
    assert "message" in body

    db = TestingSessionLocal()
    try:
        user = db.get(User, test_user["user_id"])
        assert user.password_reset_token_hash is not None
    finally:
        db.close()


def test_forgot_password_unknown_email(client):
    r = client.post("/auth/forgot-password", json={"email": "nobody@nowhere.com"})
    assert r.status_code == 200
    assert "message" in r.json()


def test_reset_password_valid_token(client, test_user):
    raw_token = secrets.token_hex(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    db = TestingSessionLocal()
    try:
        user = db.get(User, test_user["user_id"])
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expires_at
        db.commit()
    finally:
        db.close()

    r = client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "newpassword123",
    })
    assert r.status_code == 200

    # Verify login with new password works
    login_r = client.post("/auth/token", json={
        "username": test_user["email"],
        "password": "newpassword123",
    })
    assert login_r.status_code == 200
    assert "access_token" in login_r.json()

    # Verify token hash is cleared
    db = TestingSessionLocal()
    try:
        user = db.get(User, test_user["user_id"])
        assert user.password_reset_token_hash is None
    finally:
        db.close()


def test_reset_password_invalid_token(client):
    r = client.post("/auth/reset-password", json={
        "token": "badtoken",
        "new_password": "newpassword123",
    })
    assert r.status_code == 400


def test_reset_password_expired_token(client, test_user):
    raw_token = secrets.token_hex(32)
    token_hash = _hash_token(raw_token)
    expired_at = datetime.now(timezone.utc) - timedelta(hours=2)

    db = TestingSessionLocal()
    try:
        user = db.get(User, test_user["user_id"])
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expired_at
        db.commit()
    finally:
        db.close()

    r = client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "newpassword123",
    })
    assert r.status_code == 400


def test_reset_password_token_version_incremented(client, test_user):
    db = TestingSessionLocal()
    try:
        user = db.get(User, test_user["user_id"])
        version_before = user.token_version or 0
    finally:
        db.close()

    raw_token = secrets.token_hex(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=1)

    db = TestingSessionLocal()
    try:
        user = db.get(User, test_user["user_id"])
        user.password_reset_token_hash = token_hash
        user.password_reset_expires_at = expires_at
        db.commit()
    finally:
        db.close()

    r = client.post("/auth/reset-password", json={
        "token": raw_token,
        "new_password": "newpassword123",
    })
    assert r.status_code == 200

    db = TestingSessionLocal()
    try:
        user = db.get(User, test_user["user_id"])
        assert (user.token_version or 0) > version_before
    finally:
        db.close()
