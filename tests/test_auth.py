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

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql://postgres:postgres123@localhost:5432/accounting_dev"
)
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

    login = client.post("/auth/token", data={"username": email, "password": password})
    assert login.status_code == 200
    token_data = login.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"


def test_login_invalid_credentials(client):
    """Wrong password returns 401."""
    login = client.post(
        "/auth/token",
        data={"username": "wrong@example.com", "password": "wrongpass"}
    )
    assert login.status_code in (400, 401)


def test_me_endpoint_returns_current_user(client):
    """The /users/me endpoint returns the authenticated user's info."""
    email = "metest@example.com"
    password = "mepass123"
    _create_firm_and_user(email, password)

    login = client.post("/auth/token", data={"username": email, "password": password})
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