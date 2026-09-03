# tests/test_portal_preview.py

"""
Portal staff preview tests.

Covers:
  1. Token generation authorization (firm_owner only)
  2. Token scope: preview tokens rejected by real portal write endpoints
  3. Real portal tokens rejected by preview endpoints
  4. Tenant isolation: preview token from firm A cannot be used to read firm B data
  5. Token expiry: expired preview tokens are rejected with 401
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt

from tests.conftest import TestingSessionLocal
from app.models.client import Client
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole
from app.core.config import get_settings
from app.services.portal_auth import (
    create_preview_access_token,
    hash_portal_password,
)

settings = get_settings()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_with_portal_client(slug: str, staff_email: str, client_email: str):
    """
    Insert a Firm + firm_owner + portal-enabled Client into the DB.
    Returns (firm_id, user_id, client_id).
    """
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Preview Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        user = User(
            firm_id=firm.id,
            email=staff_email,
            hashed_password=get_password_hash("staffpass"),
            full_name="Preview Staff",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

        portal_client = Client(
            firm_id=firm.id,
            name="Preview Client",
            email=client_email,
            portal_password_hash=hash_portal_password("Password1!"),
            portal_access_enabled=True,
        )
        db.add(portal_client)
        db.commit()
        db.refresh(portal_client)

        firm_id = firm.id
        user_id = user.id
        client_id = portal_client.id
    finally:
        db.close()

    return firm_id, user_id, client_id


def _staff_headers(http_client, email: str, password: str = "staffpass") -> dict:
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# 1. Token generation authorization
# ---------------------------------------------------------------------------

def test_preview_token_requires_auth(client):
    """Unauthenticated POST /portal-preview/token returns 401 or 403."""
    r = client.post("/portal-preview/token")
    assert r.status_code in (401, 403), r.text


def test_preview_token_staff_role_rejected(client, firm_a_staff):
    """Staff-role user (not firm_owner) cannot generate a preview token."""
    r = client.post("/portal-preview/token", headers=firm_a_staff["headers"])
    assert r.status_code == 403, r.text


def test_preview_token_no_portal_clients_returns_404(client):
    """Firm with no portal-enabled clients gets 404 from token endpoint."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Empty Preview Firm", slug="empty-preview-firm")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        user = User(
            firm_id=firm.id,
            email="empty@previewfirm.com",
            hashed_password=get_password_hash("staffpass"),
            full_name="Empty Staff",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    headers = _staff_headers(client, "empty@previewfirm.com")
    r = client.post("/portal-preview/token", headers=headers)
    assert r.status_code == 404, r.text


def test_preview_token_generation_success(client):
    """firm_owner generates a preview token; response includes preview_token and expires_in."""
    firm_id, _, _ = _make_firm_with_portal_client(
        slug="gen-preview-firm",
        staff_email="genowner@previewfirm.com",
        client_email="genclient@previewfirm.com",
    )

    headers = _staff_headers(client, "genowner@previewfirm.com")
    r = client.post("/portal-preview/token", headers=headers)
    assert r.status_code == 200, r.text

    data = r.json()
    assert "preview_token" in data
    assert data["expires_in"] == 600

    # Decode and verify scope and firm_id claims
    payload = jwt.decode(
        data["preview_token"],
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
    )
    assert payload["scope"] == "portal_staff_preview"
    assert payload["firm_id"] == str(firm_id)


# ---------------------------------------------------------------------------
# 2. Scope enforcement: preview token rejected by write endpoints
# ---------------------------------------------------------------------------

def test_preview_token_rejected_by_portal_write_endpoint(client):
    """
    A preview token (scope=portal_staff_preview) must be rejected by any
    endpoint that calls get_current_portal_client (scope=client_portal).

    PATCH /portal/account/profile is a representative write endpoint.
    """
    firm_id, _, client_id = _make_firm_with_portal_client(
        slug="scope-test-firm",
        staff_email="scopeowner@scopefirm.com",
        client_email="scopeclient@scopefirm.com",
    )

    # Create a real preview token directly via the service function
    preview_token = create_preview_access_token(client_id, firm_id)
    preview_headers = {"Authorization": f"Bearer {preview_token}"}

    # Attempt a write on the real portal endpoint
    r = client.patch(
        "/portal/account/profile",
        json={"name": "Hacked Name"},
        headers=preview_headers,
    )
    # Must be 401 — scope mismatch causes decode_portal_access_token to reject it
    assert r.status_code == 401, (
        f"Preview token should be rejected by portal write endpoint, got {r.status_code}: {r.text}"
    )


def test_preview_token_rejected_by_portal_dashboard(client):
    """
    The real portal dashboard (GET /portal/dashboard) requires scope=client_portal.
    A preview token must be rejected.
    """
    firm_id, _, client_id = _make_firm_with_portal_client(
        slug="scope-dash-firm",
        staff_email="dashouner@dashfirm.com",
        client_email="dashclient@dashfirm.com",
    )
    preview_token = create_preview_access_token(client_id, firm_id)
    r = client.get(
        "/portal/dashboard",
        headers={"Authorization": f"Bearer {preview_token}"},
    )
    assert r.status_code == 401, r.text


# ---------------------------------------------------------------------------
# 3. Real portal access token rejected by preview endpoints
# ---------------------------------------------------------------------------

def test_real_portal_token_rejected_by_preview_me(client):
    """
    A real portal access token (scope=client_portal) must be rejected by
    GET /portal-preview/me, which requires scope=portal_staff_preview.
    """
    firm_id, _, client_id = _make_firm_with_portal_client(
        slug="reverse-scope-firm",
        staff_email="rowner@reversefirm.com",
        client_email="rclient@reversefirm.com",
    )

    # Build a real-scope portal token directly
    from app.services.portal_auth import create_portal_access_token
    real_token = create_portal_access_token(client_id, firm_id, jti=str(uuid.uuid4()))
    r = client.get(
        "/portal-preview/me",
        headers={"Authorization": f"Bearer {real_token}"},
    )
    assert r.status_code == 401, (
        f"Real portal token should be rejected by preview endpoint, got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# 4. Tenant isolation
# ---------------------------------------------------------------------------

def test_preview_tenant_isolation(client):
    """
    A preview token issued for Firm A carries Firm A's firm_id in the JWT.
    When used on GET /portal-preview/me, the returned data belongs to Firm A,
    not Firm B — and a token forged with Firm A's client_id but Firm B's
    firm_id returns 401 because no client exists at that (client_id, firm_id) pair.
    """
    firm_a_id, _, client_a_id = _make_firm_with_portal_client(
        slug="iso-firm-a",
        staff_email="aowner@isofirm.com",
        client_email="aclient@isofirm.com",
    )
    firm_b_id, _, client_b_id = _make_firm_with_portal_client(
        slug="iso-firm-b",
        staff_email="bowner@isofirm.com",
        client_email="bclient@isofirm.com",
    )

    # Firm A's real preview token
    token_a = create_preview_access_token(client_a_id, firm_a_id)

    # Using Firm A's token on /portal-preview/me returns Firm A data
    r = client.get("/portal-preview/me", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["client_id"] == str(client_a_id)

    # Forge a token with Firm A's client but Firm B's firm_id — no matching DB row
    now = datetime.now(timezone.utc)
    forged_payload = {
        "sub": str(client_a_id),
        "firm_id": str(firm_b_id),  # wrong firm for this client
        "scope": "portal_staff_preview",
        "exp": now + timedelta(minutes=10),
    }
    forged_token = jwt.encode(forged_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    r2 = client.get("/portal-preview/me", headers={"Authorization": f"Bearer {forged_token}"})
    assert r2.status_code == 401, (
        f"Cross-firm token must be rejected by preview endpoint, got {r2.status_code}: {r2.text}"
    )


# ---------------------------------------------------------------------------
# 5. Token expiry
# ---------------------------------------------------------------------------

def test_expired_preview_token_rejected(client):
    """A preview token whose exp is in the past is rejected with 401."""
    firm_id, _, client_id = _make_firm_with_portal_client(
        slug="expiry-firm",
        staff_email="eowner@expiryfirm.com",
        client_email="eclient@expiryfirm.com",
    )

    # Forge an already-expired token
    now = datetime.now(timezone.utc)
    expired_payload = {
        "sub": str(client_id),
        "firm_id": str(firm_id),
        "scope": "portal_staff_preview",
        "exp": now - timedelta(minutes=5),  # already expired
    }
    expired_token = jwt.encode(
        expired_payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )

    r = client.get(
        "/portal-preview/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert r.status_code == 401, (
        f"Expired preview token should return 401, got {r.status_code}: {r.text}"
    )


def test_preview_token_expiry_is_ten_minutes(client):
    """
    A freshly generated preview token has exp within ~10 minutes of now.
    This verifies the intended expiry is enforced, not a longer window.
    """
    _make_firm_with_portal_client(
        slug="expiry-check-firm",
        staff_email="checkowner@expiryfirm.com",
        client_email="checkclient@expiryfirm.com",
    )
    headers = _staff_headers(client, "checkowner@expiryfirm.com")
    r = client.post("/portal-preview/token", headers=headers)
    assert r.status_code == 200, r.text

    token = r.json()["preview_token"]
    payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])

    exp_dt = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
    now = datetime.now(timezone.utc)
    minutes_until_exp = (exp_dt - now).total_seconds() / 60

    # Allow a small clock-skew window: between 9 and 11 minutes
    assert 9 <= minutes_until_exp <= 11, (
        f"Preview token expiry should be ~10 minutes, got {minutes_until_exp:.1f}m"
    )
