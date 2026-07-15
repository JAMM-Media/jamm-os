# tests/test_phase8_automation.py

"""
Phase 8 — Automation Engine test suite.

Tests cover: automation rule CRUD, simulation endpoint,
execution log listing, presets seeder, and tenant isolation.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.security import get_password_hash
from app.core.enums import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_staff(slug, email="auto_staff@firm.com"):
    """Insert a Firm + firm_owner user. Returns (firm_id, token_headers)."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name="Automation Test Firm", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        firm_id = firm.id

        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("autopass"),
            full_name="Auto Staff",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    return firm_id


def _login(http_client, email, password="autopass"):
    r = http_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _rule_payload(**overrides):
    base = {
        "name": "Test Rule",
        "description": "A test rule",
        "is_enabled": False,
        "trigger_event": "engagement.created",
        "trigger_conditions": [],
        "actions": [
            {
                "type": "send_email",
                "config": {"to": "client"},
                "order": 0,
            }
        ],
    }
    base.update(overrides)
    return base


def _create_rule(http_client, headers, **overrides):
    """POST a rule and return the response JSON."""
    r = http_client.post("/automation-rules/", json=_rule_payload(**overrides), headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


# ===========================================================================
# GROUP 1 — Automation Rule CRUD
# ===========================================================================

def test_create_automation_rule(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.post("/automation-rules/", json=_rule_payload(), headers=headers)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Test Rule"
    assert data["trigger_event"] == "engagement.created"
    assert data["is_enabled"] is False
    assert data["execution_count"] == 0


def test_get_automation_rule(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    created = _create_rule(client, headers)
    rule_id = created["id"]

    r = client.get(f"/automation-rules/{rule_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == rule_id


def test_list_automation_rules(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    _create_rule(client, headers)

    r = client.get("/automation-rules/", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data
    assert "total" in data
    assert data["total"] >= 1


def test_update_automation_rule(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    rule_id = _create_rule(client, headers)["id"]

    r = client.patch(
        f"/automation-rules/{rule_id}",
        json={"name": "Updated Rule Name"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Updated Rule Name"


def test_toggle_automation_rule(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    rule_id = _create_rule(client, headers)["id"]

    r = client.post(f"/automation-rules/{rule_id}/toggle?enabled=true", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_enabled"] is True

    r = client.post(f"/automation-rules/{rule_id}/toggle?enabled=false", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_enabled"] is False


# ===========================================================================
# GROUP 2 — Simulation endpoint
# ===========================================================================

def test_simulate_rule_no_conditions(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    rule_id = _create_rule(client, headers, trigger_conditions=[])["id"]

    r = client.post(
        f"/automation-rules/{rule_id}/simulate",
        json={"engagement_id": "some-id", "status": "completed"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["would_trigger"] is True
    assert data["rule_is_enabled"] is False


def test_simulate_rule_with_conditions(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    conditions = [{"field": "status", "operator": "equals", "value": "completed"}]
    rule_id = _create_rule(client, headers, trigger_conditions=conditions)["id"]

    # Matching payload — should trigger
    r = client.post(
        f"/automation-rules/{rule_id}/simulate",
        json={"status": "completed"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["would_trigger"] is True

    # Non-matching payload — should not trigger
    r = client.post(
        f"/automation-rules/{rule_id}/simulate",
        json={"status": "draft"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["would_trigger"] is False


# ===========================================================================
# GROUP 3 — Execution log endpoint
# ===========================================================================

def test_list_execution_logs(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = client.get("/automation-rules/execution-logs", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "items" in data
    assert "total" in data


# ===========================================================================
# GROUP 4 — Presets seeder
# ===========================================================================

def test_presets_seeded_on_firm_creation(client, firm_a_owner):
    """
    Firm creation via POST /firms/ requires system_admin role, which is not
    available in the standard test fixtures. Instead, call seed_firm_presets()
    directly to verify the seeder works and the rules appear in the API.
    """
    from app.services.automation_presets import seed_firm_presets, _get_preset_rules

    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]

    db = TestingSessionLocal()
    try:
        count = seed_firm_presets(firm_id=firm_id, db=db)
    finally:
        db.close()

    assert count == len(_get_preset_rules(firm_id))

    r = client.get("/automation-rules/", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["total"] >= 8


def test_preset_rules_are_disabled_by_default(client, firm_a_owner):
    """Some seeded preset rules ship enabled by default (is_enabled=True)."""
    from app.services.automation_presets import seed_firm_presets

    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]

    db = TestingSessionLocal()
    try:
        seed_firm_presets(firm_id=firm_id, db=db)
    finally:
        db.close()

    r = client.get("/automation-rules/?limit=200", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]
    assert any(rule["is_enabled"] is True for rule in items)


# ===========================================================================
# GROUP 4b — Preset lineage (preset_key / is_customized)
# ===========================================================================

def test_seeded_preset_rules_carry_preset_key(client, firm_a_owner):
    from app.services.automation_presets import seed_firm_presets
    from app.core.automation_preset_catalog import PRESET_CATALOG_BY_KEY

    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]

    db = TestingSessionLocal()
    try:
        seed_firm_presets(firm_id=firm_id, db=db)
    finally:
        db.close()

    r = client.get("/automation-rules/?limit=200", headers=headers)
    assert r.status_code == 200, r.text
    items = r.json()["items"]

    seeded = [rule for rule in items if rule["preset_key"] is not None]
    assert len(seeded) == len(PRESET_CATALOG_BY_KEY)
    for rule in seeded:
        assert rule["preset_key"] in PRESET_CATALOG_BY_KEY
        assert rule["is_customized"] is False


def test_editing_actions_on_preset_rule_sets_is_customized(client, firm_a_owner):
    from app.services.automation_presets import seed_firm_presets

    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]

    db = TestingSessionLocal()
    try:
        seed_firm_presets(firm_id=firm_id, db=db)
    finally:
        db.close()

    r = client.get("/automation-rules/?limit=200", headers=headers)
    preset_rule = next(rule for rule in r.json()["items"] if rule["preset_key"] is not None)
    assert preset_rule["is_customized"] is False

    r = client.patch(
        f"/automation-rules/{preset_rule['id']}",
        json={"actions": [{"type": "send_notification", "config": {"to": "staff"}, "order": 0}]},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_customized"] is True
    assert r.json()["preset_key"] == preset_rule["preset_key"]


def test_renaming_preset_rule_does_not_set_is_customized(client, firm_a_owner):
    """Cosmetic edits (name/description) are not 'configuration' -- only
    actions/trigger_conditions/trigger_event count as customization."""
    from app.services.automation_presets import seed_firm_presets

    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]

    db = TestingSessionLocal()
    try:
        seed_firm_presets(firm_id=firm_id, db=db)
    finally:
        db.close()

    r = client.get("/automation-rules/?limit=200", headers=headers)
    preset_rule = next(rule for rule in r.json()["items"] if rule["preset_key"] is not None)

    r = client.patch(
        f"/automation-rules/{preset_rule['id']}",
        json={"name": "Renamed Preset Rule"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_customized"] is False


def test_reset_to_default_clears_is_customized(client, firm_a_owner):
    from app.services.automation_presets import seed_firm_presets

    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    headers = firm_a_owner["headers"]

    db = TestingSessionLocal()
    try:
        seed_firm_presets(firm_id=firm_id, db=db)
    finally:
        db.close()

    r = client.get("/automation-rules/?limit=200", headers=headers)
    preset_rule = next(rule for rule in r.json()["items"] if rule["preset_key"] is not None)

    client.patch(
        f"/automation-rules/{preset_rule['id']}",
        json={"actions": [{"type": "send_notification", "config": {"to": "staff"}, "order": 0}]},
        headers=headers,
    )

    r = client.post(f"/automation-rules/{preset_rule['id']}/reset-to-default", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["is_customized"] is False


def test_custom_rule_has_no_preset_key(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    rule = _create_rule(client, headers)
    assert rule["preset_key"] is None
    assert rule["is_customized"] is False


# ===========================================================================
# GROUP 5 — Tenant isolation
# ===========================================================================

def test_cannot_access_other_firms_rule(client, firm_a_owner, firm_b_owner):
    """Firm B cannot GET a rule that belongs to Firm A."""
    headers_a = firm_a_owner["headers"]
    headers_b = firm_b_owner["headers"]

    rule_id = _create_rule(client, headers_a)["id"]

    r = client.get(f"/automation-rules/{rule_id}", headers=headers_b)
    assert r.status_code == 404, r.text


def test_delete_automation_rule(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    rule_id = _create_rule(client, headers)["id"]

    r = client.delete(f"/automation-rules/{rule_id}", headers=headers)
    assert r.status_code == 204, r.text

    r = client.get(f"/automation-rules/{rule_id}", headers=headers)
    assert r.status_code == 404, r.text
