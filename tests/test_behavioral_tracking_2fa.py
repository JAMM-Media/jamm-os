# tests/test_behavioral_tracking_2fa.py

"""
Phase 7 behavioral event wiring: self-service 2FA disable.

Pinning tests were written against the router code BEFORE the write moved
into totp_service.disable_2fa_for_user, watched green there, and left
unchanged across the move. They read the users row directly.

The event is 2fa.disabled, the mirror of 2fa.enabled: same entity, the user
acting on themselves, payload {role} only. No TOTP secret or backup code
material ever reaches it. Ruled Oct 12, 2026.
"""

import uuid
from unittest.mock import patch

from sqlalchemy import text

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.firm import Firm
from app.models.user import User
from app.services.totp_service import generate_totp_secret
from tests.conftest import TestingSessionLocal


def _make_firm():
    db = TestingSessionLocal()
    try:
        firm = Firm(name="2FA Events Firm", slug=f"2fa-events-{uuid.uuid4().hex[:8]}")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm.id
    finally:
        db.close()


def _make_user(firm_id, role, totp_enabled):
    """Creates a user with 2FA material in place. Returns (user_id, email)."""
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@2fa-events.com"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("pass12345"),
            full_name="2FA User",
            role=role,
            totp_enabled=totp_enabled,
            totp_secret=generate_totp_secret() if totp_enabled else None,
            backup_codes_hash='["x"]' if totp_enabled else None,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, email
    finally:
        db.close()


def _headers_for(user_id):
    """Token minted directly: logging in a 2FA-enabled user would need a live
    TOTP code, and the login path is not what these tests are about."""
    from app.core.security import create_access_token

    db = TestingSessionLocal()
    try:
        user = db.get(User, user_id)
        token = create_access_token(data={
            "sub": str(user.id),
            "firm_id": str(user.firm_id),
            "token_version": user.token_version,
        })
    finally:
        db.close()
    return {"Authorization": f"Bearer {token}"}


def _totp_state(user_id):
    db = TestingSessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT totp_enabled, totp_secret IS NOT NULL, backup_codes_hash IS NOT NULL "
                "FROM users WHERE id = CAST(:u AS uuid)"
            ),
            {"u": str(user_id)},
        ).one()
    finally:
        db.close()
    return tuple(row)


# ---------------------------------------------------------------------------
# Pinning tests: behavior before the service move
# ---------------------------------------------------------------------------

def test_pin_sole_2fa_owner_cannot_disable_and_nothing_changes(client):
    firm_id = _make_firm()
    owner_id, _ = _make_user(firm_id, UserRole.firm_owner, totp_enabled=True)

    r = client.post("/auth/2fa/disable", headers=_headers_for(owner_id))

    assert r.status_code == 400
    assert r.json()["detail"] == (
        "Cannot disable 2FA: you are the only firm_owner with 2FA enabled. "
        "Another firm_owner must enable 2FA first to prevent lockout."
    )
    assert _totp_state(owner_id) == (True, True, True)


def test_pin_staff_can_disable_without_the_owner_check(client):
    firm_id = _make_firm()
    staff_id, _ = _make_user(firm_id, UserRole.staff, totp_enabled=True)

    r = client.post("/auth/2fa/disable", headers=_headers_for(staff_id))

    assert r.status_code == 200, r.text
    assert r.json() == {"message": "2FA disabled"}
    assert _totp_state(staff_id) == (False, False, False)


# ---------------------------------------------------------------------------
# Event test: 2fa.disabled from totp_service
# ---------------------------------------------------------------------------

def test_disable_fires_2fa_disabled_with_role_only(client):
    firm_id = _make_firm()
    owner_id, _ = _make_user(firm_id, UserRole.firm_owner, totp_enabled=True)
    _make_user(firm_id, UserRole.firm_owner, totp_enabled=True)

    db = TestingSessionLocal()
    try:
        secret = db.get(User, owner_id).totp_secret
    finally:
        db.close()

    with patch("app.services.totp_service.log_event") as mock_log:
        r = client.post("/auth/2fa/disable", headers=_headers_for(owner_id))

    assert r.status_code == 200, r.text
    events = [c.kwargs for c in mock_log.call_args_list if c.kwargs.get("event_type") == "2fa.disabled"]
    assert len(events) == 1
    e = events[0]
    assert e["firm_id"] == firm_id
    assert e["entity_type"] == "user"
    assert e["entity_id"] == owner_id
    assert e["actor_type"] == "staff"
    assert e["actor_id"] == owner_id
    assert e["metadata"] == {"role": "firm_owner"}
    assert secret not in str(e)
