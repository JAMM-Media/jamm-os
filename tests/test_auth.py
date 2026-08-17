# tests/test_auth.py

"""
Auth tests — updated for Phase 1 multi-tenancy.

Users now require a firm to exist before they can be created.
These tests use the DB fixtures from conftest.py to set up firms directly.
"""

from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os

# No fallback default here, deliberately. This module builds its own engine
# rather than using conftest's, so a default would be free to disagree with the
# database the rest of the suite runs against. The previous default did, twice
# over: it named accounting_dev rather than the test database, and it used a
# plain postgresql:// prefix, which selects psycopg2 instead of psycopg 3 and
# silently kills every sqlstate error-code guard. conftest.py loads .env.test
# before any test module imports, so DATABASE_URL is always set by this point.
# A KeyError here is the correct, loud outcome if it ever is not.
DATABASE_URL = os.environ["DATABASE_URL"]
engine = create_engine(DATABASE_URL)
TestingSessionLocal = sessionmaker(bind=engine)


def _create_firm_and_user(email: str, password: str, role=UserRole.firm_owner):
    """Helper: directly insert a firm and user into the DB for auth testing."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Auth Test Firm", slug=f"auth-test-{email.split('@')[0]}")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Auth Test User",
            role=role,
        )
        db.add(user)
        db.commit()
        return firm.id, user.id
    finally:
        db.close()


def test_user_login_success(client):
    """A user with valid credentials receives a JWT."""
    email = "logintest@example.com"
    password = "secure123"
    _create_firm_and_user(email, password)

    login = client.post("/auth/token", json={"username": email, "password": password})
    assert login.status_code == 200
    token_data = login.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    """Wrong password returns 401."""
    login = client.post(
        "/auth/token",
        json={"username": "wrong@example.com", "password": "wrongpass"}
    )
    assert login.status_code in (400, 401)


def test_me_endpoint_returns_current_user(client):
    """The /users/me endpoint returns the authenticated user's info."""
    email = "metest@example.com"
    password = "mepass123"
    _create_firm_and_user(email, password)

    login = client.post("/auth/token", json={"username": email, "password": password})
    token = login.json()["access_token"]

    r = client.get("/users/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == email


def test_me_endpoint_rejects_invalid_token(client):
    """A tampered or invalid JWT must be rejected with 401."""
    r = client.get("/users/me", headers={"Authorization": "Bearer this-is-not-a-real-token"})
    assert r.status_code == 401


def test_protected_endpoint_requires_auth(client):
    """Calling a protected endpoint without a token returns 401."""
    r = client.get("/clients/")
    assert r.status_code == 401


def test_logout_clears_refresh_token(client):
    """Logout endpoint revokes the staff refresh token in the database."""
    email = "logout_test@example.com"
    password = "logoutpass123"
    firm_id, user_id = _create_firm_and_user(email, password)

    login = client.post("/auth/token", json={"username": email, "password": password})
    assert login.status_code == 200
    token = login.json()["access_token"]

    # Manually set a refresh token hash on the user record
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        user.staff_refresh_token_hash = "test_hash_value"
        db.commit()
    finally:
        db.close()

    r = client.post("/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200

    # Verify the refresh token hash was cleared
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.id == user_id).first()
        assert user.staff_refresh_token_hash is None
    finally:
        db.close()