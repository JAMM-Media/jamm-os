# tests/test_referral_partners_rbac_and_tenant_isolation.py

"""
RBAC and tenant-isolation tests for app/api/referral_partners.py.

Read-only endpoints (list, get single) require require_staff_or_above.
Write endpoints (create, update, delete) require require_manager_or_above.

Cross-tenant lookups return 404 -- confirmed by reading
get_referral_partner_for_firm in app/crud/referral_partner.py, which filters
by firm_id before returning any row. The router raises 404 if the row is not
found, preventing Firm B from learning whether Firm A's record exists.
"""

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PARTNER_PAYLOAD = {"name": "RBAC Test Partner"}

_LEAD_PAYLOAD = {"name": "RBAC Test Lead", "provenance": "firm_entered"}


def _create_partner(client, headers) -> str:
    """Create a referral partner (manager-only) and return its id."""
    r = client.post("/api/v1/referral-partners/", json=_PARTNER_PAYLOAD, headers=headers)
    assert r.status_code == 201, f"Partner creation failed: {r.json()}"
    return r.json()["id"]


def _create_lead_with_partner(client, headers, partner_id: str) -> str:
    """Create a lead referencing the given partner and return the lead id."""
    payload = {**_LEAD_PAYLOAD, "referral_partner_id": partner_id}
    r = client.post("/api/v1/leads/", json=payload, headers=headers)
    assert r.status_code == 201, f"Lead creation failed: {r.json()}"
    return r.json()["id"]


# ---------------------------------------------------------------------------
# RBAC: staff is blocked on write endpoints, allowed on read endpoints
# ---------------------------------------------------------------------------

class TestReferralPartnersRBAC:
    def test_staff_cannot_create_partner(self, client, firm_a_staff):
        r = client.post("/api/v1/referral-partners/", json=_PARTNER_PAYLOAD, headers=firm_a_staff["headers"])
        assert r.status_code == 403

    def test_staff_cannot_update_partner(self, client, firm_a_owner, firm_a_staff):
        partner_id = _create_partner(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/referral-partners/{partner_id}",
            json={"name": "Staff Attempted Edit"},
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 403

    def test_staff_cannot_delete_partner(self, client, firm_a_owner, firm_a_staff):
        partner_id = _create_partner(client, firm_a_owner["headers"])
        r = client.delete(f"/api/v1/referral-partners/{partner_id}", headers=firm_a_staff["headers"])
        assert r.status_code == 403

    def test_staff_can_list_partners(self, client, firm_a_staff):
        r = client.get("/api/v1/referral-partners/", headers=firm_a_staff["headers"])
        assert r.status_code == 200
        assert "items" in r.json()

    def test_staff_can_get_single_partner(self, client, firm_a_owner, firm_a_staff):
        partner_id = _create_partner(client, firm_a_owner["headers"])
        r = client.get(f"/api/v1/referral-partners/{partner_id}", headers=firm_a_staff["headers"])
        assert r.status_code == 200
        assert r.json()["id"] == partner_id

    def test_owner_can_create_partner(self, client, firm_a_owner):
        r = client.post("/api/v1/referral-partners/", json=_PARTNER_PAYLOAD, headers=firm_a_owner["headers"])
        assert r.status_code == 201
        assert r.json()["name"] == "RBAC Test Partner"

    def test_owner_can_update_partner(self, client, firm_a_owner):
        partner_id = _create_partner(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/referral-partners/{partner_id}",
            json={"name": "Updated Name"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Updated Name"

    def test_owner_can_delete_partner(self, client, firm_a_owner):
        partner_id = _create_partner(client, firm_a_owner["headers"])
        r = client.delete(f"/api/v1/referral-partners/{partner_id}", headers=firm_a_owner["headers"])
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# Tenant isolation: Firm B cannot access any Firm A referral partner
# ---------------------------------------------------------------------------

class TestReferralPartnersTenantIsolation:
    def test_firm_b_cannot_get_firm_a_partner(self, client, firm_a_owner, firm_b_owner):
        partner_id = _create_partner(client, firm_a_owner["headers"])

        r = client.get(f"/api/v1/referral-partners/{partner_id}", headers=firm_b_owner["headers"])
        assert r.status_code == 404, (
            f"Tenant isolation breach: Firm B received Firm A's partner. "
            f"Status={r.status_code}, body={r.json()}"
        )

    def test_firm_b_cannot_update_firm_a_partner(self, client, firm_a_owner, firm_b_owner):
        partner_id = _create_partner(client, firm_a_owner["headers"])

        r = client.patch(
            f"/api/v1/referral-partners/{partner_id}",
            json={"name": "Firm B Overwrote This"},
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404, (
            f"Tenant isolation breach: Firm B could update Firm A's partner. "
            f"Status={r.status_code}"
        )

    def test_firm_b_cannot_delete_firm_a_partner(self, client, firm_a_owner, firm_b_owner):
        partner_id = _create_partner(client, firm_a_owner["headers"])

        r = client.delete(f"/api/v1/referral-partners/{partner_id}", headers=firm_b_owner["headers"])
        assert r.status_code == 404, (
            f"Tenant isolation breach: Firm B could delete Firm A's partner. "
            f"Status={r.status_code}"
        )

    def test_firm_b_list_never_includes_firm_a_partners(self, client, firm_a_owner, firm_b_owner):
        """Firm A's partners never appear in Firm B's list response.
        Asserts on the real response body, not just the status code.
        """
        _create_partner(client, firm_a_owner["headers"])
        _create_partner(client, firm_a_owner["headers"])

        r = client.get("/api/v1/referral-partners/", headers=firm_b_owner["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == 0, (
            f"Tenant isolation breach: Firm B's list returned {body['total']} partners "
            f"(should be 0). Items: {body['items']}"
        )
        assert body["items"] == [], (
            "Tenant isolation breach: Firm B's items list is not empty"
        )


# ---------------------------------------------------------------------------
# Active-lead guard: cannot delete a partner that has live leads
# ---------------------------------------------------------------------------

class TestReferralPartnerActiveLeadGuard:
    def test_delete_blocked_when_lead_references_partner(self, client, firm_a_owner):
        """Deleting a partner with a real lead referencing it returns 409.

        Uses a real created Lead and real created ReferralPartner. The
        has_active_leads check in crud/referral_partner.py blocks the delete.
        """
        partner_id = _create_partner(client, firm_a_owner["headers"])
        _create_lead_with_partner(client, firm_a_owner["headers"], partner_id)

        r = client.delete(f"/api/v1/referral-partners/{partner_id}", headers=firm_a_owner["headers"])
        assert r.status_code == 409, (
            f"Expected 409 when partner has leads referencing it, got {r.status_code}. "
            f"Body: {r.json()}"
        )

    def test_delete_succeeds_when_no_leads_reference_partner(self, client, firm_a_owner):
        """A partner with no leads referencing it can be deleted cleanly."""
        partner_id = _create_partner(client, firm_a_owner["headers"])

        r = client.delete(f"/api/v1/referral-partners/{partner_id}", headers=firm_a_owner["headers"])
        assert r.status_code == 204
