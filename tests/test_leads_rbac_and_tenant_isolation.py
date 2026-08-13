# tests/test_leads_rbac_and_tenant_isolation.py

"""
RBAC and tenant-isolation tests for app/api/leads.py.

All five endpoints require require_staff_or_above. Cross-tenant lookups
return 404 (not 403) -- returning 404 prevents an attacker from confirming
a record exists across tenants, confirmed by reading get_lead_for_firm in
app/crud/lead.py which filters by firm_id before returning any row.

Guard test: test_firm_b_cannot_get_firm_a_lead. See TestLeadsTenantIsolation
for the red/green cycle instructions Ben will run to verify it independently.
"""

import uuid
import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEAD_PAYLOAD = {"name": "RBAC Test Lead", "provenance": "firm_entered"}


def _make_portal_user_headers(client, owner_fixture):
    """Create a client_portal_user in the owner's firm and return their auth headers.
    Follows the exact pattern from test_tasks.py::test_client_cannot_list_tasks.
    """
    email = f"portal-{uuid.uuid4()}@rbac-test.example.com"
    portal_user = {
        "email": email,
        "password": "portalpass123",
        "full_name": "Portal User",
        "role": "client_portal_user",
        "firm_id": owner_fixture["firm_id"],
    }
    r = client.post("/users/", json=portal_user, headers=owner_fixture["headers"])
    assert r.status_code == 201, f"Portal user creation failed: {r.json()}"
    login = client.post("/auth/token", json={"username": email, "password": "portalpass123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_lead(client, headers) -> str:
    """Create a lead and return its id."""
    r = client.post("/api/v1/leads/", json=_LEAD_PAYLOAD, headers=headers)
    assert r.status_code == 201, f"Lead creation failed: {r.json()}"
    return r.json()["id"]


# ---------------------------------------------------------------------------
# RBAC: portal user is blocked on every endpoint
# ---------------------------------------------------------------------------

class TestLeadsRBAC:
    def test_portal_user_cannot_create_lead(self, client, firm_a_owner):
        portal_headers = _make_portal_user_headers(client, firm_a_owner)
        r = client.post("/api/v1/leads/", json=_LEAD_PAYLOAD, headers=portal_headers)
        assert r.status_code == 403

    def test_portal_user_cannot_list_leads(self, client, firm_a_owner):
        portal_headers = _make_portal_user_headers(client, firm_a_owner)
        r = client.get("/api/v1/leads/", headers=portal_headers)
        assert r.status_code == 403

    def test_portal_user_cannot_get_lead(self, client, firm_a_owner):
        portal_headers = _make_portal_user_headers(client, firm_a_owner)
        # Auth check fires before the DB lookup, so any UUID works.
        r = client.get(f"/api/v1/leads/{uuid.uuid4()}", headers=portal_headers)
        assert r.status_code == 403

    def test_portal_user_cannot_update_lead(self, client, firm_a_owner):
        portal_headers = _make_portal_user_headers(client, firm_a_owner)
        r = client.patch(
            f"/api/v1/leads/{uuid.uuid4()}",
            json={"name": "Should Fail"},
            headers=portal_headers,
        )
        assert r.status_code == 403

    def test_portal_user_cannot_transition_lead(self, client, firm_a_owner):
        portal_headers = _make_portal_user_headers(client, firm_a_owner)
        r = client.post(
            f"/api/v1/leads/{uuid.uuid4()}/transition",
            json={"new_stage": "contacted"},
            headers=portal_headers,
        )
        assert r.status_code == 403

    def test_staff_can_list_leads(self, client, firm_a_staff):
        r = client.get("/api/v1/leads/", headers=firm_a_staff["headers"])
        assert r.status_code == 200
        assert "items" in r.json()

    def test_staff_can_create_lead(self, client, firm_a_staff):
        r = client.post("/api/v1/leads/", json=_LEAD_PAYLOAD, headers=firm_a_staff["headers"])
        assert r.status_code == 201
        assert r.json()["name"] == "RBAC Test Lead"


# ---------------------------------------------------------------------------
# Tenant isolation: Firm B cannot access any Firm A lead
#
# GUARD TEST: test_firm_b_cannot_get_firm_a_lead
#
# To run the red/green cycle:
#   Break: in app/crud/lead.py, edit get_lead_for_firm to remove the
#          'Lead.firm_id == firm_id' filter (leave just 'Lead.id == lead_id').
#   Run:   .venv/bin/pytest tests/test_leads_rbac_and_tenant_isolation.py::TestLeadsTenantIsolation::test_firm_b_cannot_get_firm_a_lead -v
#   Expect RED: status was 200 (Firm B received Firm A's lead data)
#   Restore: git checkout app/crud/lead.py
#   Rerun:  confirm GREEN
# ---------------------------------------------------------------------------

class TestLeadsTenantIsolation:
    def test_firm_b_cannot_get_firm_a_lead(self, client, firm_a_owner, firm_b_owner):
        """Firm B's token cannot retrieve a lead that belongs to Firm A.
        The endpoint returns 404, not 403, to avoid confirming the record exists.
        """
        lead_id = _create_lead(client, firm_a_owner["headers"])

        r = client.get(f"/api/v1/leads/{lead_id}", headers=firm_b_owner["headers"])
        assert r.status_code == 404, (
            f"Tenant isolation breach: Firm B received Firm A's lead. "
            f"Status={r.status_code}, body={r.json()}"
        )

    def test_firm_b_cannot_patch_firm_a_lead(self, client, firm_a_owner, firm_b_owner):
        lead_id = _create_lead(client, firm_a_owner["headers"])

        r = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"name": "Firm B Overwrote This"},
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404, (
            f"Tenant isolation breach: Firm B could patch Firm A's lead. "
            f"Status={r.status_code}"
        )

    def test_firm_b_cannot_transition_firm_a_lead(self, client, firm_a_owner, firm_b_owner):
        lead_id = _create_lead(client, firm_a_owner["headers"])

        r = client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "contacted"},
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404, (
            f"Tenant isolation breach: Firm B could transition Firm A's lead. "
            f"Status={r.status_code}"
        )

    def test_firm_b_list_never_includes_firm_a_leads(self, client, firm_a_owner, firm_b_owner):
        """Firm A's leads never appear in Firm B's list response.
        Asserts on the real response body, not just the status code.
        """
        # Create two leads under Firm A.
        _create_lead(client, firm_a_owner["headers"])
        _create_lead(client, firm_a_owner["headers"])

        # Firm B lists leads -- should see none.
        r = client.get("/api/v1/leads/", headers=firm_b_owner["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0, (
            f"Tenant isolation breach: Firm B's list returned {body['total']} leads "
            f"(should be 0). Items: {body['items']}"
        )
        assert body["items"] == [], (
            "Tenant isolation breach: Firm B's items list is not empty"
        )
