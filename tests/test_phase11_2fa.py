# tests/test_phase11_2fa.py

import json
import uuid

import pytest
import pyotp

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole
from app.services.totp_service import generate_totp_secret, generate_backup_codes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_owner(email: str, password: str = "ownerpass", slug_suffix: str = "") -> dict:
    """Create a firm + firm_owner in the DB and return login info."""
    db = TestingSessionLocal()
    try:
        slug = f"2fa-firm-{email.split('@')[0]}{slug_suffix}"
        firm = Firm(name=f"2FA Firm {email}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return {"firm_id": str(firm.id), "user_id": str(user.id), "email": email, "password": password}
    finally:
        db.close()


def _make_staff(firm_id: uuid.UUID, email: str, password: str = "staffpass") -> str:
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Staff",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return str(user.id)
    finally:
        db.close()


def _login(client, email: str, password: str, totp_code=None, backup_code=None) -> dict:
    body = {"username": email, "password": password}
    if totp_code:
        body["totp_code"] = totp_code
    if backup_code:
        body["backup_code"] = backup_code
    return client.post("/auth/token", json=body)


def _token_headers(client, email: str, password: str) -> dict:
    r = _login(client, email, password)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Test 1: GET /auth/2fa/status — correct totp_enabled and is_required values
# ---------------------------------------------------------------------------
def test_2fa_status_initial(client):
    info = _make_owner("status_owner@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])
    r = client.get("/auth/2fa/status", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["totp_enabled"] is False
    assert data["is_required"] is True  # firm_owner

    # Also verify staff sees is_required=False
    firm_id = uuid.UUID(info["firm_id"])
    _make_staff(firm_id, "status_staff@2fa.com")
    staff_headers = _token_headers(client, "status_staff@2fa.com", "staffpass")
    rs = client.get("/auth/2fa/status", headers=staff_headers)
    assert rs.status_code == 200
    assert rs.json()["is_required"] is False


# ---------------------------------------------------------------------------
# Test 2: POST /auth/2fa/setup — returns secret, qr, 10 backup codes; totp_enabled still False
# ---------------------------------------------------------------------------
def test_2fa_setup(client):
    info = _make_owner("setup_owner@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])
    r = client.post("/auth/2fa/setup", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "secret" in data
    assert data["qr_code_base64"].startswith("data:image/png;base64,")
    assert len(data["backup_codes"]) == 10

    # totp_enabled must still be False (not yet verified)
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        assert user.totp_secret is not None
        assert user.totp_enabled is False
        assert user.backup_codes_hash is not None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 3: POST /auth/2fa/verify — valid code sets totp_enabled=True
# ---------------------------------------------------------------------------
def test_2fa_verify_valid(client):
    info = _make_owner("verify_owner@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])

    # Setup
    client.post("/auth/2fa/setup", headers=headers)

    # Get secret from DB
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        secret = user.totp_secret
    finally:
        db.close()

    code = pyotp.TOTP(secret).now()
    r = client.post("/auth/2fa/verify", json={"code": code}, headers=headers)
    assert r.status_code == 200
    assert r.json()["message"] == "2FA enabled successfully"

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        assert user.totp_enabled is True
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 4: POST /auth/2fa/verify — invalid code returns 400
# ---------------------------------------------------------------------------
def test_2fa_verify_invalid_code(client):
    info = _make_owner("invalid_code@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])
    client.post("/auth/2fa/setup", headers=headers)

    r = client.post("/auth/2fa/verify", json={"code": "000000"}, headers=headers)
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Test 5: Login with 2FA enabled and no totp_code → requires_2fa=True, no token
# ---------------------------------------------------------------------------
def test_login_requires_2fa_when_enabled(client):
    info = _make_owner("nototp@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])

    # Setup and enable 2FA
    client.post("/auth/2fa/setup", headers=headers)
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        secret = user.totp_secret
        user.totp_enabled = True
        db.commit()
    finally:
        db.close()

    # Login without code
    r = _login(client, info["email"], info["password"])
    assert r.status_code == 200
    data = r.json()
    assert data["requires_2fa"] is True
    assert data["access_token"] is None


# ---------------------------------------------------------------------------
# Test 6: Login with valid totp_code issues a real access token
# ---------------------------------------------------------------------------
def test_login_with_valid_totp_issues_token(client):
    info = _make_owner("totplogin@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])

    client.post("/auth/2fa/setup", headers=headers)
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        secret = user.totp_secret
        user.totp_enabled = True
        db.commit()
    finally:
        db.close()

    code = pyotp.TOTP(secret).now()
    r = _login(client, info["email"], info["password"], totp_code=code)
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert data["access_token"] is not None


# ---------------------------------------------------------------------------
# Test 7: Login with valid backup_code issues token; used code is consumed
# ---------------------------------------------------------------------------
def test_login_with_backup_code_consumes_it(client):
    info = _make_owner("backupcode@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])

    setup_r = client.post("/auth/2fa/setup", headers=headers)
    raw_backup_codes = setup_r.json()["backup_codes"]

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        user.totp_enabled = True
        db.commit()
    finally:
        db.close()

    # First use: should succeed
    code_to_use = raw_backup_codes[0]
    r1 = _login(client, info["email"], info["password"], backup_code=code_to_use)
    assert r1.status_code == 200
    assert r1.json()["access_token"] is not None

    # Second use of same code: should fail (consumed)
    r2 = _login(client, info["email"], info["password"], backup_code=code_to_use)
    assert r2.status_code == 401


# ---------------------------------------------------------------------------
# Test 8: POST /auth/2fa/disable clears totp fields
# ---------------------------------------------------------------------------
def test_2fa_disable(client):
    # Create an owner, setup + enable 2FA
    info = _make_owner("disable2fa@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])
    client.post("/auth/2fa/setup", headers=headers)

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        secret = user.totp_secret
        user.totp_enabled = True
        db.commit()
    finally:
        db.close()

    # Need to create a second firm_owner with 2FA enabled (to satisfy lockout check)
    firm_id = uuid.UUID(info["firm_id"])
    db = TestingSessionLocal()
    try:
        other_owner = User(
            firm_id=firm_id,
            email="other_owner@2fa.com",
            hashed_password=get_password_hash("pass"),
            full_name="Other Owner",
            role=UserRole.firm_owner,
            totp_enabled=True,
            totp_secret=generate_totp_secret(),
        )
        db.add(other_owner)
        db.commit()
    finally:
        db.close()

    code = pyotp.TOTP(secret).now()
    r_login = _login(client, info["email"], info["password"], totp_code=code)
    new_token = r_login.json()["access_token"]
    new_headers = {"Authorization": f"Bearer {new_token}"}

    r = client.post("/auth/2fa/disable", headers=new_headers)
    assert r.status_code == 200

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        assert user.totp_enabled is False
        assert user.totp_secret is None
        assert user.backup_codes_hash is None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Test 9: POST /auth/2fa/backup-codes/regenerate returns 10 new codes; old ones no longer work
# ---------------------------------------------------------------------------
def test_backup_codes_regenerate(client):
    info = _make_owner("regen@2fa.com")
    headers = _token_headers(client, info["email"], info["password"])

    setup_r = client.post("/auth/2fa/setup", headers=headers)
    old_codes = setup_r.json()["backup_codes"]

    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == info["email"]).first()
        user.totp_enabled = True
        db.commit()
    finally:
        db.close()

    # Regenerate
    regen_r = client.post("/auth/2fa/backup-codes/regenerate", headers=headers)
    assert regen_r.status_code == 200
    new_codes = regen_r.json()["backup_codes"]
    assert len(new_codes) == 10
    # New codes should differ from old codes
    assert set(new_codes) != set(old_codes)

    # Old code should no longer work
    r = _login(client, info["email"], info["password"], backup_code=old_codes[0])
    assert r.status_code == 401

    # New code should work
    r2 = _login(client, info["email"], info["password"], backup_code=new_codes[0])
    assert r2.status_code == 200
    assert r2.json()["access_token"] is not None
