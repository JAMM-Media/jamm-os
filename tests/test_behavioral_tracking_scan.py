# tests/test_behavioral_tracking_scan.py

"""
Phase 7 behavioral event wiring: the approved scan candidates from the Sep 24
event sweep (rows 3, 5, 9 to 13, 18 to 20, 24 to 29, 33, 38, 39, 41, 46, 51,
ruled Oct 12, 2026).

Pinning tests come first. Each was written against the router code BEFORE
that write moved into a service, watched green there, and left unchanged
across the move. Where a pin asserts a write it reads the database directly
rather than trusting the response, which the code under test shapes.

Event tests follow, one per event. log_event is patched where the service
under test resolves it, so log_event's own error swallowing cannot make a
test unable to fail. firm.deleted is the exception: it patches
log_platform_event, because a firm that no longer exists cannot own a
behavioral_events row.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.client import Client
from app.models.firm import Firm
from app.models.user import User
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def _scalar(sql, **params):
    db = TestingSessionLocal()
    try:
        return db.execute(text(sql), params).scalar()
    finally:
        db.close()


def _row(sql, **params):
    db = TestingSessionLocal()
    try:
        return db.execute(text(sql), params).one_or_none()
    finally:
        db.close()


def _owner_id(firm_id):
    return _scalar(
        "SELECT id FROM users WHERE firm_id = CAST(:f AS uuid) AND role = 'firm_owner'",
        f=str(firm_id),
    )


def _make_user(firm_id, role, password="scanpass123"):
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"{role.value}-{uuid.uuid4().hex[:8]}@scan.com",
            hashed_password=get_password_hash(password),
            full_name=f"Scan {role.value}",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id, user.email
    finally:
        db.close()


def _login(client, email, password="scanpass123"):
    r = client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_client(firm_id, portal_access_enabled=False, email=None):
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=firm_id,
            name="Scan Client",
            email=email or f"scan-{uuid.uuid4().hex[:8]}@client.com",
            portal_access_enabled=portal_access_enabled,
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return c.id
    finally:
        db.close()


def _events(mock_log, event_type):
    return [c.kwargs for c in mock_log.call_args_list if c.kwargs.get("event_type") == event_type]


def _new_api_client(client, headers):
    r = client.post("/clients/", json={"name": "Scan API Client"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _new_envelope(client, headers, client_id):
    r = client.post("/esign/envelopes", json={"client_id": client_id, "signers": []}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _new_letter_template(client, headers, engagement_type="1040"):
    r = client.post(
        "/esign/templates",
        json={
            "name": "Scan Letter",
            "body_html": "<p>Dear {{client_name}},</p>",
            "variable_fields": ["client_name"],
            "is_active": True,
            "engagement_type": engagement_type,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _new_rule(client, headers, **overrides):
    body = {
        "name": "Scan Rule",
        "description": "scan",
        "is_enabled": False,
        "trigger_event": "engagement.created",
        "trigger_conditions": [],
        "actions": [{"type": "send_email", "config": {"to": "client"}, "order": 0}],
    }
    body.update(overrides)
    r = client.post("/automation-rules/", json=body, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ===========================================================================
# PINNING TESTS (router behavior before each move)
# ===========================================================================

# --- Row 3: DELETE /esign/envelopes/{id} -----------------------------------

def test_pin_delete_envelope_returns_deleted_true_and_row_is_gone(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    envelope_id = _new_envelope(client, headers, _new_api_client(client, headers))

    r = client.delete(f"/esign/envelopes/{envelope_id}", headers=headers)

    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert _scalar("SELECT count(*) FROM signature_envelopes WHERE id = CAST(:e AS uuid)", e=envelope_id) == 0


def test_pin_delete_other_firms_envelope_is_404_and_row_survives(client, firm_a_owner, firm_b_owner):
    headers = firm_a_owner["headers"]
    envelope_id = _new_envelope(client, headers, _new_api_client(client, headers))

    r = client.delete(f"/esign/envelopes/{envelope_id}", headers=firm_b_owner["headers"])

    assert r.status_code == 404
    assert r.json()["detail"] == "Signature envelope not found"
    assert _scalar("SELECT count(*) FROM signature_envelopes WHERE id = CAST(:e AS uuid)", e=envelope_id) == 1


# --- Row 5: DELETE /esign/templates/{id} (soft delete) ---------------------

def test_pin_delete_letter_template_soft_deletes_and_returns_deleted_true(client, firm_a_owner):
    template_id = _new_letter_template(client, firm_a_owner["headers"])

    r = client.delete(f"/esign/templates/{template_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 200
    assert r.json() == {"deleted": True}
    assert _scalar(
        "SELECT is_active FROM engagement_letter_templates WHERE id = CAST(:t AS uuid)", t=template_id
    ) is False


def test_pin_delete_other_firms_letter_template_is_404_and_stays_active(client, firm_a_owner, firm_b_owner):
    template_id = _new_letter_template(client, firm_a_owner["headers"])

    r = client.delete(f"/esign/templates/{template_id}", headers=firm_b_owner["headers"])

    assert r.status_code == 404
    assert r.json()["detail"] == "Template not found"
    assert _scalar(
        "SELECT is_active FROM engagement_letter_templates WHERE id = CAST(:t AS uuid)", t=template_id
    ) is True


# --- Row 9: POST /portal/admin/revoke/{client_id} --------------------------

def test_pin_admin_revoke_disables_access_and_revokes_sessions(client, firm_a_owner, portal_client_headers):
    client_id, portal_headers = portal_client_headers

    r = client.post(f"/portal/admin/revoke/{client_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 200, r.text
    assert r.json() == {"message": "Portal access revoked", "sessions_revoked": 1}
    assert _scalar("SELECT portal_access_enabled FROM clients WHERE id = CAST(:c AS uuid)", c=client_id) is False
    assert _scalar(
        "SELECT count(*) FROM portal_sessions WHERE client_id = CAST(:c AS uuid) AND is_revoked = false",
        c=client_id,
    ) == 0


def test_pin_admin_revoke_other_firms_client_is_404(client, firm_b_owner, portal_client_headers):
    client_id, _ = portal_client_headers

    r = client.post(f"/portal/admin/revoke/{client_id}", headers=firm_b_owner["headers"])

    assert r.status_code == 404
    assert r.json()["detail"] == "Client not found"
    assert _scalar("SELECT portal_access_enabled FROM clients WHERE id = CAST(:c AS uuid)", c=client_id) is True


# --- Row 10: GET /portal/admin/portal-access/{client_id} -------------------

def test_pin_staff_portal_access_enables_access_and_returns_url(client, firm_a_owner):
    from app.core.config import get_settings

    client_id = _make_client(firm_a_owner["firm_id"], portal_access_enabled=False)

    r = client.get(f"/portal/admin/portal-access/{client_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 200, r.text
    assert r.json()["portal_url"].startswith(f"{get_settings().FRONTEND_URL}/portal/auth?token=")
    assert _scalar("SELECT portal_access_enabled FROM clients WHERE id = CAST(:c AS uuid)", c=client_id) is True


def test_pin_staff_portal_access_other_firms_client_is_404_and_untouched(client, firm_a_owner, firm_b_owner):
    client_id = _make_client(firm_a_owner["firm_id"], portal_access_enabled=False)

    r = client.get(f"/portal/admin/portal-access/{client_id}", headers=firm_b_owner["headers"])

    assert r.status_code == 404
    assert _scalar("SELECT portal_access_enabled FROM clients WHERE id = CAST(:c AS uuid)", c=client_id) is False


# --- Row 11: POST /portal/account/set-password -----------------------------

def _portal_hash(client_id):
    return _scalar("SELECT portal_password_hash FROM clients WHERE id = CAST(:c AS uuid)", c=client_id)


def test_pin_set_password_too_short_is_422_and_hash_unchanged(client, portal_client_headers):
    client_id, portal_headers = portal_client_headers
    before = _portal_hash(client_id)

    r = client.post(
        "/portal/account/set-password",
        json={"new_password": "short", "confirm_password": "short", "current_password": "portalpass123"},
        headers=portal_headers,
    )

    assert r.status_code == 422
    assert r.json()["detail"] == "Password must be at least 8 characters."
    assert _portal_hash(client_id) == before


def test_pin_set_password_mismatch_is_422_and_hash_unchanged(client, portal_client_headers):
    client_id, portal_headers = portal_client_headers
    before = _portal_hash(client_id)

    r = client.post(
        "/portal/account/set-password",
        json={"new_password": "longenough1", "confirm_password": "longenough2", "current_password": "portalpass123"},
        headers=portal_headers,
    )

    assert r.status_code == 422
    assert r.json()["detail"] == "Passwords don't match."
    assert _portal_hash(client_id) == before


def test_pin_set_password_success_changes_hash(client, portal_client_headers):
    client_id, portal_headers = portal_client_headers
    before = _portal_hash(client_id)

    r = client.post(
        "/portal/account/set-password",
        json={"new_password": "brandnew123", "confirm_password": "brandnew123", "current_password": "portalpass123"},
        headers=portal_headers,
    )

    assert r.status_code == 200, r.text
    assert r.json() == {"success": True}
    assert _portal_hash(client_id) != before


# --- Row 12: PATCH /portal/account/profile ---------------------------------

def test_pin_profile_blank_name_is_422(client, portal_client_headers):
    _, portal_headers = portal_client_headers
    r = client.patch("/portal/account/profile", json={"name": "   "}, headers=portal_headers)
    assert r.status_code == 422
    assert r.json()["detail"] == "Name cannot be blank."


def test_pin_profile_email_in_use_is_409(client, firm_a_owner, portal_client_headers):
    _, portal_headers = portal_client_headers
    _make_client(firm_a_owner["firm_id"], email="taken@client.com")

    r = client.patch("/portal/account/profile", json={"email": "taken@client.com"}, headers=portal_headers)

    assert r.status_code == 409
    assert r.json()["detail"] == "Email is already in use."


def test_pin_profile_blank_phone_clears_to_null(client, portal_client_headers):
    client_id, portal_headers = portal_client_headers
    client.patch("/portal/account/profile", json={"phone": "555"}, headers=portal_headers)

    r = client.patch("/portal/account/profile", json={"phone": "  "}, headers=portal_headers)

    assert r.status_code == 200, r.text
    assert r.json()["phone"] is None
    assert _scalar("SELECT phone FROM clients WHERE id = CAST(:c AS uuid)", c=client_id) is None


# --- Row 26: POST /automation-rules/{id}/reset-to-default ------------------

def test_pin_reset_rule_without_defaults_is_400_and_unchanged(client, firm_a_owner):
    rule = _new_rule(client, firm_a_owner["headers"])

    r = client.post(f"/automation-rules/{rule['id']}/reset-to-default", headers=firm_a_owner["headers"])

    assert r.status_code == 400
    assert r.json()["detail"] == "No default actions stored for this rule"


def test_pin_reset_rule_restores_default_actions(client, firm_a_owner):
    from app.services.automation_presets import seed_firm_presets

    db = TestingSessionLocal()
    try:
        seed_firm_presets(firm_id=uuid.UUID(firm_a_owner["firm_id"]), db=db)
    finally:
        db.close()
    headers = firm_a_owner["headers"]
    rules = client.get("/automation-rules/?limit=200", headers=headers).json()["items"]
    preset = next(r for r in rules if r["preset_key"] is not None)
    client.patch(
        f"/automation-rules/{preset['id']}",
        json={"actions": [{"type": "send_notification", "config": {"to": "staff"}, "order": 0}]},
        headers=headers,
    )

    r = client.post(f"/automation-rules/{preset['id']}/reset-to-default", headers=headers)

    assert r.status_code == 200, r.text
    row = _row(
        "SELECT actions::text = default_actions::text, is_customized FROM automation_rules "
        "WHERE id = CAST(:r AS uuid)",
        r=preset["id"],
    )
    assert tuple(row) == (True, False)


# --- Row 29: DELETE /integrations/staff/{provider} -------------------------

def _seed_user_integration(firm_id, user_id, provider="gmail"):
    from app.crud import integration as crud_integration

    db = TestingSessionLocal()
    try:
        integ = crud_integration.create_user_integration(
            db, firm_id=uuid.UUID(str(firm_id)), user_id=user_id, provider=provider
        )
        integ.status = "connected"
        integ.encrypted_access_token = "enc-access"
        integ.encrypted_refresh_token = "enc-refresh"
        integ.scopes = "scope-a"
        integ.external_account_id = "someone@example.com"
        db.commit()
        return integ.id
    finally:
        db.close()


def test_pin_staff_disconnect_wipes_tokens_and_sets_disconnected(client, firm_a_owner):
    integ_id = _seed_user_integration(firm_a_owner["firm_id"], _owner_id(firm_a_owner["firm_id"]))

    r = client.delete("/integrations/staff/gmail", headers=firm_a_owner["headers"])

    assert r.status_code == 204
    row = _row(
        "SELECT status, encrypted_access_token, encrypted_refresh_token, scopes, "
        "external_account_id, connected_at FROM integrations WHERE id = CAST(:i AS uuid)",
        i=str(integ_id),
    )
    assert tuple(row) == ("disconnected", None, None, None, None, None)


def test_pin_staff_disconnect_without_integration_is_404(client, firm_a_owner):
    r = client.delete("/integrations/staff/gmail", headers=firm_a_owner["headers"])
    assert r.status_code == 404
    assert r.json()["detail"] == "Integration not found"


# --- Row 33: GET /stripe/callback ------------------------------------------

def _stripe_stubs(monkeypatch):
    from app.services import stripe_service

    monkeypatch.setattr(
        stripe_service, "exchange_connect_code",
        lambda code: {"stripe_account_id": "acct_scan123", "stripe_publishable_key": "pk_test_scan"},
    )
    monkeypatch.setattr(
        stripe_service, "get_account_details",
        lambda account_id: {
            "country": "US", "default_currency": "usd",
            "charges_enabled": True, "payouts_enabled": False, "details_submitted": True,
        },
    )


def test_pin_stripe_callback_creates_connection_and_redirects(client, firm_a_owner, monkeypatch):
    from app.core.config import get_settings

    _stripe_stubs(monkeypatch)
    firm_id = firm_a_owner["firm_id"]

    r = client.get(f"/stripe/callback?code=abc&state={firm_id}", follow_redirects=False)

    assert r.status_code in (302, 307)
    assert r.headers["location"] == f"{get_settings().FRONTEND_URL}/settings/billing?connected=stripe"
    row = _row(
        "SELECT stripe_account_id, charges_enabled, payouts_enabled, details_submitted, country "
        "FROM stripe_connections WHERE firm_id = CAST(:f AS uuid)",
        f=firm_id,
    )
    assert tuple(row) == ("acct_scan123", True, False, True, "US")


def test_pin_stripe_callback_already_connected_redirects_with_error(client, firm_a_owner, monkeypatch):
    from app.core.config import get_settings

    _stripe_stubs(monkeypatch)
    firm_id = firm_a_owner["firm_id"]
    client.get(f"/stripe/callback?code=abc&state={firm_id}", follow_redirects=False)

    r = client.get(f"/stripe/callback?code=abc&state={firm_id}", follow_redirects=False)

    assert r.headers["location"] == (
        f"{get_settings().FRONTEND_URL}/settings/billing?error=stripe_already_connected"
    )
    assert _scalar("SELECT count(*) FROM stripe_connections WHERE firm_id = CAST(:f AS uuid)", f=firm_id) == 1


def test_pin_stripe_callback_bad_state_redirects_with_failure(client):
    from app.core.config import get_settings

    r = client.get("/stripe/callback?code=abc&state=not-a-uuid", follow_redirects=False)

    assert r.headers["location"] == f"{get_settings().FRONTEND_URL}/settings/billing?error=stripe_failed"


# --- Row 46: DELETE /firms/{firm_id} ---------------------------------------

def _make_bare_firm(name="Doomed Firm"):
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=f"doomed-{uuid.uuid4().hex[:8]}")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm.id
    finally:
        db.close()


@pytest.fixture
def system_admin_headers(client):
    home_firm = _make_bare_firm(name="Admin Home")
    _, email = _make_user(home_firm, UserRole.system_admin)
    return _login(client, email)


def test_pin_delete_firm_by_system_admin_is_204_and_row_is_gone(client, system_admin_headers):
    doomed = _make_bare_firm()

    r = client.delete(f"/firms/{doomed}", headers=system_admin_headers)

    assert r.status_code == 204
    assert _scalar("SELECT count(*) FROM firms WHERE id = CAST(:f AS uuid)", f=str(doomed)) == 0


def test_pin_delete_missing_firm_is_404(client, system_admin_headers):
    r = client.delete(f"/firms/{uuid.uuid4()}", headers=system_admin_headers)
    assert r.status_code == 404
    assert r.json()["detail"] == "Firm not found"


def test_pin_delete_firm_by_firm_owner_is_403(client, firm_a_owner):
    doomed = _make_bare_firm()

    r = client.delete(f"/firms/{doomed}", headers=firm_a_owner["headers"])

    assert r.status_code == 403
    assert _scalar("SELECT count(*) FROM firms WHERE id = CAST(:f AS uuid)", f=str(doomed)) == 1


# ===========================================================================
# EVENT TESTS (one per event)
# ===========================================================================

# --- Row 3: engagement_letter.deleted --------------------------------------

def test_delete_envelope_fires_engagement_letter_deleted(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _new_api_client(client, headers)
    envelope_id = _new_envelope(client, headers, client_id)

    with patch("app.services.esign_service.log_event") as mock_log:
        r = client.delete(f"/esign/envelopes/{envelope_id}", headers=headers)

    assert r.status_code == 200
    events = _events(mock_log, "engagement_letter.deleted")
    assert len(events) == 1
    e = events[0]
    assert e["entity_type"] == "signature_envelope"
    assert str(e["entity_id"]) == envelope_id
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"client_id": client_id, "engagement_id": None, "status": "draft"}


# --- Row 5: letter_template.deleted ----------------------------------------

def test_delete_letter_template_fires_letter_template_deleted(client, firm_a_owner):
    template_id = _new_letter_template(client, firm_a_owner["headers"], engagement_type="1040")

    with patch("app.services.esign_service.log_event") as mock_log:
        r = client.delete(f"/esign/templates/{template_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 200
    events = _events(mock_log, "letter_template.deleted")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == template_id
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"engagement_type": "1040"}


# --- Row 9: client.portal_access_changed via admin_revoke ------------------

def test_admin_revoke_fires_portal_access_changed(client, firm_a_owner, portal_client_headers):
    client_id, _ = portal_client_headers

    with patch("app.services.portal_service.log_event") as mock_log:
        r = client.post(f"/portal/admin/revoke/{client_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 200, r.text
    events = _events(mock_log, "client.portal_access_changed")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == client_id
    assert e["actor_type"] == "staff"
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {
        "from_enabled": True, "to_enabled": False, "via": "admin_revoke", "sessions_revoked": 1,
    }


# --- Row 10: client.portal_access_changed via staff_preview ----------------

def test_staff_preview_fires_portal_access_changed_only_when_it_flips(client, firm_a_owner):
    client_id = _make_client(firm_a_owner["firm_id"], portal_access_enabled=False)

    with patch("app.services.portal_service.log_event") as mock_log:
        first = client.get(f"/portal/admin/portal-access/{client_id}", headers=firm_a_owner["headers"])
        second = client.get(f"/portal/admin/portal-access/{client_id}", headers=firm_a_owner["headers"])

    assert first.status_code == 200 and second.status_code == 200
    events = _events(mock_log, "client.portal_access_changed")
    assert len(events) == 1
    e = events[0]
    assert e["entity_id"] == client_id
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"from_enabled": False, "to_enabled": True, "via": "staff_preview"}


# --- Row 11: portal.password_changed ---------------------------------------

def test_set_password_fires_password_changed_with_no_credential_material(client, portal_client_headers):
    client_id, portal_headers = portal_client_headers

    with patch("app.services.portal_service.log_event") as mock_log:
        r = client.post(
            "/portal/account/set-password",
            json={"new_password": "brandnew123", "confirm_password": "brandnew123", "current_password": "portalpass123"},
            headers=portal_headers,
        )

    assert r.status_code == 200, r.text
    events = _events(mock_log, "portal.password_changed")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == client_id
    assert e["actor_type"] == "client"
    assert e["metadata"] == {"first_set": False}
    assert "brandnew123" not in str(e) and "portalpass123" not in str(e)


# --- Row 12: client.updated with actor_type client -------------------------

def test_profile_update_fires_client_updated_as_client(client, portal_client_headers):
    client_id, portal_headers = portal_client_headers

    with patch("app.services.portal_service.log_event") as mock_log:
        r = client.patch("/portal/account/profile", json={"name": "Renamed Client"}, headers=portal_headers)

    assert r.status_code == 200, r.text
    events = _events(mock_log, "client.updated")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == client_id
    assert e["actor_type"] == "client"
    assert str(e["actor_id"]) == client_id
    assert e["metadata"] == {
        "changed_fields": {"name": {"from": "Portal Test Client", "to": "Renamed Client"}},
    }


# --- Row 13: portal.session_revoked ----------------------------------------

def test_revoke_own_session_fires_session_revoked(client, portal_client_headers):
    _, portal_headers = portal_client_headers
    session_id = client.get("/portal/account/sessions", headers=portal_headers).json()[0]["id"]

    with patch("app.services.portal_service.log_event") as mock_log:
        r = client.delete(f"/portal/account/sessions/{session_id}", headers=portal_headers)

    assert r.status_code == 204
    events = _events(mock_log, "portal.session_revoked")
    assert len(events) == 1
    e = events[0]
    assert e["entity_type"] == "portal_session"
    assert str(e["entity_id"]) == session_id
    assert e["actor_type"] == "client"
    assert e["metadata"] == {"session_id": session_id}


# --- Rows 18, 19, 20: Peer Network consent records -------------------------

PEER_LOG = "app.services.peer_network_service.log_event"


def test_opt_in_fires_firm_opted_in_once(client, firm_a_owner):
    with patch(PEER_LOG) as mock_log:
        first = client.post("/peer-network/opt-in", headers=firm_a_owner["headers"])
        second = client.post("/peer-network/opt-in", headers=firm_a_owner["headers"])

    assert first.status_code == 200 and second.status_code == 200
    events = _events(mock_log, "peer_network.firm_opted_in")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == firm_a_owner["firm_id"]
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"owner_member_created": True}
    assert first.json()["handle"] not in str(e)


def test_grant_access_fires_access_granted_once(client, firm_a_owner):
    manager_id, _ = _make_user(firm_a_owner["firm_id"], UserRole.manager)
    client.post("/peer-network/opt-in", headers=firm_a_owner["headers"])

    with patch(PEER_LOG) as mock_log:
        first = client.post(f"/peer-network/members/{manager_id}/grant", headers=firm_a_owner["headers"])
        second = client.post(f"/peer-network/members/{manager_id}/grant", headers=firm_a_owner["headers"])

    assert first.status_code == 200 and second.json()["already_existed"] is True
    events = _events(mock_log, "peer_network.access_granted")
    assert len(events) == 1
    e = events[0]
    assert e["entity_type"] == "peer_network_member"
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"target_user_id": str(manager_id), "target_role": "manager"}
    assert first.json()["handle"] not in str(e)


def test_accept_terms_fires_terms_accepted_once(client, firm_a_owner):
    client.post("/peer-network/opt-in", headers=firm_a_owner["headers"])

    with patch(PEER_LOG) as mock_log:
        first = client.post("/peer-network/accept-terms", headers=firm_a_owner["headers"])
        second = client.post("/peer-network/accept-terms", headers=firm_a_owner["headers"])

    assert first.status_code == 200 and second.status_code == 200
    events = _events(mock_log, "peer_network.terms_accepted")
    assert len(events) == 1
    e = events[0]
    assert e["entity_type"] == "peer_network_member"
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"role": "firm_owner"}


# --- Rows 24, 25, 26: automation create / delete / reset -------------------

AUTOMATION_LOG = "app.services.automation_rule_service.log_event"


def test_create_rule_fires_automation_created(client, firm_a_owner):
    with patch(AUTOMATION_LOG) as mock_log:
        rule = _new_rule(client, firm_a_owner["headers"], name="Created Rule")

    events = _events(mock_log, "firm.automation_created")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == rule["id"]
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {
        "rule_name": "Created Rule", "trigger_event": "engagement.created", "is_preset": False,
    }


def test_delete_rule_fires_automation_deleted(client, firm_a_owner):
    rule = _new_rule(client, firm_a_owner["headers"], name="Doomed Rule")

    with patch(AUTOMATION_LOG) as mock_log:
        r = client.delete(f"/automation-rules/{rule['id']}", headers=firm_a_owner["headers"])

    assert r.status_code == 204
    events = _events(mock_log, "firm.automation_deleted")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == rule["id"]
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {
        "rule_name": "Doomed Rule", "trigger_event": "engagement.created", "is_preset": False,
    }


def test_reset_rule_fires_automation_reset(client, firm_a_owner):
    from app.services.automation_presets import seed_firm_presets

    db = TestingSessionLocal()
    try:
        seed_firm_presets(firm_id=uuid.UUID(firm_a_owner["firm_id"]), db=db)
    finally:
        db.close()
    headers = firm_a_owner["headers"]
    preset = next(
        r for r in client.get("/automation-rules/?limit=200", headers=headers).json()["items"]
        if r["preset_key"] is not None
    )

    with patch(AUTOMATION_LOG) as mock_log:
        r = client.post(f"/automation-rules/{preset['id']}/reset-to-default", headers=headers)

    assert r.status_code == 200, r.text
    events = _events(mock_log, "firm.automation_reset")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == preset["id"]
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"rule_name": preset["name"], "trigger_event": preset["trigger_event"]}


# --- Row 27: integration.connected from the QuickBooks callback ------------

def test_quickbooks_callback_fires_integration_connected(client, firm_a_owner):
    from unittest.mock import MagicMock

    firm_id = firm_a_owner["firm_id"]

    def _token_ok(*args, **kwargs):
        resp = MagicMock()
        resp.json.return_value = {"access_token": "fake_access", "refresh_token": "fake_refresh", "expires_in": 3600}
        resp.raise_for_status.return_value = None
        return resp

    with patch("requests.post", side_effect=_token_ok), \
         patch("app.services.quickbooks_service.log_event") as mock_log:
        r = client.get(f"/integrations/quickbooks/callback?code=c&realmId=realm-9&state={firm_id}")

    assert r.status_code == 200, r.text
    events = _events(mock_log, "integration.connected")
    assert len(events) == 1
    e = events[0]
    assert str(e["firm_id"]) == firm_id
    assert e["entity_type"] == "integration"
    assert e["actor_type"] == "system"
    assert e["metadata"] == {"provider": "quickbooks"}
    assert "fake_access" not in str(e) and "realm-9" not in str(e)


# --- Rows 28, 29: integration.disconnected ---------------------------------

def test_firm_disconnect_fires_integration_disconnected(client, firm_a_owner):
    from app.crud import integration as crud_integration

    db = TestingSessionLocal()
    try:
        integ = crud_integration.create_integration(
            db, firm_id=uuid.UUID(firm_a_owner["firm_id"]), provider="quickbooks"
        )
        integ_id = integ.id
    finally:
        db.close()

    with patch("app.services.integration_service.log_event") as mock_log:
        r = client.delete("/integrations/quickbooks", headers=firm_a_owner["headers"])

    assert r.status_code == 204
    events = _events(mock_log, "integration.disconnected")
    assert len(events) == 1
    e = events[0]
    assert e["entity_id"] == integ_id
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"provider": "quickbooks"}


def test_staff_disconnect_fires_integration_disconnected(client, firm_a_owner):
    owner = _owner_id(firm_a_owner["firm_id"])
    integ_id = _seed_user_integration(firm_a_owner["firm_id"], owner)

    with patch("app.services.integration_service.log_event") as mock_log:
        r = client.delete("/integrations/staff/gmail", headers=firm_a_owner["headers"])

    assert r.status_code == 204
    events = _events(mock_log, "integration.disconnected")
    assert len(events) == 1
    e = events[0]
    assert e["entity_id"] == integ_id
    assert e["actor_id"] == owner
    assert e["metadata"] == {"provider": "gmail", "user_id": str(owner)}
    assert "enc-access" not in str(e)


# --- Row 33: stripe.account_connected --------------------------------------

def test_stripe_callback_fires_account_connected(client, firm_a_owner, monkeypatch):
    _stripe_stubs(monkeypatch)
    firm_id = firm_a_owner["firm_id"]

    with patch("app.services.stripe_service.log_event") as mock_log:
        r = client.get(f"/stripe/callback?code=abc&state={firm_id}", follow_redirects=False)

    assert r.status_code in (302, 307)
    events = _events(mock_log, "stripe.account_connected")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == firm_id
    assert e["metadata"] == {
        "charges_enabled": True, "payouts_enabled": False, "details_submitted": True, "country": "US",
    }
    assert "acct_scan123" not in str(e) and "pk_test_scan" not in str(e)


# --- Row 38: document_request.deleted --------------------------------------

def test_delete_document_request_fires_deleted(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _new_api_client(client, headers)
    r = client.post("/engagements/", json={"name": "DR Events", "client_id": client_id}, headers=headers)
    assert r.status_code == 201, r.text
    engagement_id = r.json()["id"]
    r = client.post(
        "/document-requests/",
        json={
            "client_id": client_id,
            "engagement_id": engagement_id,
            "title": "Tax Docs",
            "checklist_items": [{"id": "i1", "label": "W-2", "is_required": True, "status": "pending"}],
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    request_id = r.json()["id"]

    with patch("app.services.document_request_service.log_event") as mock_log:
        r = client.delete(f"/document-requests/{request_id}", headers=headers)

    assert r.status_code == 204
    events = _events(mock_log, "document_request.deleted")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == request_id
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {"client_id": client_id, "engagement_id": engagement_id}


# --- Row 39: user.password_reset_completed ---------------------------------

def test_password_reset_completion_fires_event_with_role_only(firm_a_owner):
    import hashlib
    from datetime import datetime, timedelta, timezone

    from app.services import password_reset_service

    raw_token = "scan-reset-token-0123456789"
    owner = _owner_id(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        user = db.get(User, owner)
        user.password_reset_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        db.commit()

        with patch("app.services.password_reset_service.log_event") as mock_log:
            ok, err = password_reset_service.reset_password(raw_token, "newpassword123", db)
    finally:
        db.close()

    assert (ok, err) == (True, None)
    events = _events(mock_log, "user.password_reset_completed")
    assert len(events) == 1
    e = events[0]
    assert e["entity_id"] == owner
    assert e["actor_id"] == owner
    assert e["metadata"] == {"role": "firm_owner"}
    assert raw_token not in str(e) and "newpassword123" not in str(e)


# --- Row 41: user.login via magic link -------------------------------------

def test_magic_link_login_fires_user_login_with_method(firm_a_owner):
    import hashlib
    from datetime import datetime, timedelta, timezone

    from app.services import staff_magic_link

    raw_token = "scan-magic-token-0123456789"
    owner = _owner_id(firm_a_owner["firm_id"])
    db = TestingSessionLocal()
    try:
        user = db.get(User, owner)
        user.magic_link_token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
        user.magic_link_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        db.commit()

        with patch("app.services.staff_magic_link.log_event") as mock_log:
            result, err = staff_magic_link.verify_staff_magic_link(raw_token, db)
    finally:
        db.close()

    assert err is None and result["access_token"]
    events = _events(mock_log, "user.login")
    assert len(events) == 1
    e = events[0]
    assert e["entity_id"] == owner
    assert e["actor_id"] == owner
    assert set(e["metadata"]) == {"time_of_day", "day_of_week", "method"}
    assert e["metadata"]["method"] == "magic_link"
    assert raw_token not in str(e)


# --- Row 46: firm.deleted through log_platform_event -----------------------

def test_delete_firm_fires_firm_deleted_on_platform_events(client, system_admin_headers):
    doomed = _make_bare_firm(name="Gone Firm")

    # log_event is patched where firm_service resolves it. Patching it at
    # behavioral_log instead left this assertion unable to fail: a stray
    # log_event call in firm_service went straight past that patch (found by
    # the negative control, Oct 13, 2026).
    with patch("app.services.firm_service.log_platform_event") as mock_platform, \
         patch("app.services.firm_service.log_event") as mock_behavioral:
        r = client.delete(f"/firms/{doomed}", headers=system_admin_headers)

    assert r.status_code == 204
    events = _events(mock_platform, "firm.deleted")
    assert len(events) == 1
    e = events[0]
    assert e["entity_type"] == "firm"
    assert e["entity_id"] == doomed
    assert e["metadata"] == {"firm_id": str(doomed), "firm_name": "Gone Firm"}
    assert "firm_id" not in e
    assert _events(mock_behavioral, "firm.deleted") == []


# --- Row 51: pricing.option_price_set --------------------------------------

def test_option_price_set_fires_event_and_keeps_null_versus_zero(client, firm_a_owner):
    from app.core.enums import DimensionKind, EngagementType
    from app.models.complexity_dimension import ComplexityDimension
    from app.models.complexity_flag import ComplexityFlag
    from app.models.complexity_flag_engagement_type import ComplexityFlagEngagementType
    from app.models.complexity_vocabulary_option import ComplexityVocabularyOption

    db = TestingSessionLocal()
    try:
        flag = ComplexityFlag(key="crypto", name="Crypto activity")
        db.add(flag)
        db.commit()
        db.add(ComplexityFlagEngagementType(flag_id=flag.id, engagement_type=EngagementType.tax_return_1040.value))
        dim = ComplexityDimension(
            flag_id=flag.id, key="wallet_type", kind=DimensionKind.categorical,
            hierarchy_rank=20, linkable=True,
        )
        db.add(dim)
        db.commit()
        option = ComplexityVocabularyOption(dimension_id=dim.id, key="custodial", label="Custodial")
        db.add(option)
        db.commit()
        option_id = str(option.id)
    finally:
        db.close()

    with patch("app.services.pricing_config_service.log_event") as mock_log:
        zero = client.put(
            "/api/pricing/option-prices",
            json={"option_id": option_id, "price": "0.00"},
            headers=firm_a_owner["headers"],
        )
        unpriced = client.put(
            "/api/pricing/option-prices",
            json={"option_id": option_id, "price": None},
            headers=firm_a_owner["headers"],
        )

    assert zero.status_code == 200, zero.text
    assert unpriced.status_code == 200, unpriced.text
    events = _events(mock_log, "pricing.option_price_set")
    assert len(events) == 2
    owner = _owner_id(firm_a_owner["firm_id"])
    assert all(e["actor_id"] == owner for e in events)
    assert events[0]["metadata"] == {
        "dimension_key": "wallet_type", "option_key": "custodial",
        "from_price": None, "to_price": "0.00",
        "scope": "blanket", "service_catalog_entry_id": None, "created": True,
    }
    assert events[1]["metadata"] == {
        "dimension_key": "wallet_type", "option_key": "custodial",
        "from_price": "0.00", "to_price": None,
        "scope": "blanket", "service_catalog_entry_id": None, "created": False,
    }
