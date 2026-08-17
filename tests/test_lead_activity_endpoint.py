# tests/test_lead_activity_endpoint.py

"""
Tests for GET /api/v1/leads/{lead_id}/activity.

Guards:
1. Tenant isolation: Firm B cannot fetch Firm A's lead activity (returns 404).
2. Combined sources: both LeadMessage and BehavioralEvent rows appear.
3. Sort order: results are newest first (descending by occurred_at).
4. RBAC: portal users are blocked (403).
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest


_LEAD_PAYLOAD = {"name": "Activity Test Lead", "provenance": "firm_entered"}


def _create_lead(client, headers) -> str:
    r = client.post("/api/v1/leads/", json=_LEAD_PAYLOAD, headers=headers)
    assert r.status_code == 201, f"Lead creation failed: {r.json()}"
    return r.json()["id"]


def _make_portal_headers(client, owner_fixture) -> dict:
    email = f"portal-{uuid.uuid4()}@activity-test.example.com"
    r = client.post(
        "/users/",
        json={
            "email": email,
            "password": "portalpass123",
            "full_name": "Portal User",
            "role": "client_portal_user",
            "firm_id": owner_fixture["firm_id"],
        },
        headers=owner_fixture["headers"],
    )
    assert r.status_code == 201
    login = client.post("/auth/token", json={"username": email, "password": "portalpass123"})
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestLeadActivityTenantIsolation:
    def test_firm_b_cannot_fetch_firm_a_lead_activity(
        self, client, firm_a_owner, firm_b_owner
    ):
        """Firm B gets 404, not 200, for Firm A's lead activity."""
        lead_id = _create_lead(client, firm_a_owner["headers"])
        r = client.get(
            f"/api/v1/leads/{lead_id}/activity",
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404, (
            f"Tenant isolation breach on activity endpoint: status={r.status_code}, "
            f"body={r.json()}"
        )


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

class TestLeadActivityRBAC:
    def test_portal_user_cannot_fetch_activity(self, client, firm_a_owner):
        portal_headers = _make_portal_headers(client, firm_a_owner)
        lead_id = _create_lead(client, firm_a_owner["headers"])
        r = client.get(
            f"/api/v1/leads/{lead_id}/activity",
            headers=portal_headers,
        )
        assert r.status_code == 403

    def test_staff_can_fetch_activity(self, client, firm_a_staff):
        lead_id = _create_lead(client, firm_a_staff["headers"])
        r = client.get(
            f"/api/v1/leads/{lead_id}/activity",
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 200
        assert isinstance(r.json(), list)


# ---------------------------------------------------------------------------
# Combined sources and sort order
# ---------------------------------------------------------------------------

class TestLeadActivityContent:
    def test_behavioral_event_appears_in_activity(
        self, client, firm_a_owner
    ):
        """A BehavioralEvent with entity_type='lead' shows up in the timeline."""
        from tests.conftest import TestingSessionLocal
        from app.models.behavioral_event import BehavioralEvent

        lead_id = _create_lead(client, firm_a_owner["headers"])
        firm_id = firm_a_owner["firm_id"]

        db = TestingSessionLocal()
        try:
            evt = BehavioralEvent(
                firm_id=uuid.UUID(firm_id),
                event_type="lead.email_replied",
                entity_type="lead",
                entity_id=uuid.UUID(lead_id),
            )
            db.add(evt)
            db.commit()
        finally:
            db.close()

        r = client.get(
            f"/api/v1/leads/{lead_id}/activity",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        items = r.json()
        source_types = [i["source_type"] for i in items]
        assert "lead.email_replied" in source_types, (
            f"BehavioralEvent not found in activity. source_types={source_types}"
        )

    def test_lead_message_appears_in_activity(
        self, client, firm_a_owner
    ):
        """A LeadMessage row shows up in the timeline."""
        from tests.conftest import TestingSessionLocal
        from app.models.lead_message import LeadMessage

        lead_id = _create_lead(client, firm_a_owner["headers"])
        firm_id = firm_a_owner["firm_id"]

        db = TestingSessionLocal()
        try:
            msg = LeadMessage(
                firm_id=uuid.UUID(firm_id),
                lead_id=uuid.UUID(lead_id),
                sender_role="lead",
                body="Hello, I have a question.",
                source="inbound_email",
            )
            db.add(msg)
            db.commit()
        finally:
            db.close()

        r = client.get(
            f"/api/v1/leads/{lead_id}/activity",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        items = r.json()
        types = [i["type"] for i in items]
        assert "message" in types, f"LeadMessage not in activity. types={types}"

    def test_activity_includes_both_sources(
        self, client, firm_a_owner
    ):
        """Both LeadMessage and BehavioralEvent rows appear in the same response."""
        from tests.conftest import TestingSessionLocal
        from app.models.behavioral_event import BehavioralEvent
        from app.models.lead_message import LeadMessage

        lead_id = _create_lead(client, firm_a_owner["headers"])
        firm_id = firm_a_owner["firm_id"]

        db = TestingSessionLocal()
        try:
            db.add(BehavioralEvent(
                firm_id=uuid.UUID(firm_id),
                event_type="lead.call_booked",
                entity_type="lead",
                entity_id=uuid.UUID(lead_id),
            ))
            db.add(LeadMessage(
                firm_id=uuid.UUID(firm_id),
                lead_id=uuid.UUID(lead_id),
                sender_role="staff",
                body="Following up on your enquiry.",
                source="staff_note",
            ))
            db.commit()
        finally:
            db.close()

        r = client.get(
            f"/api/v1/leads/{lead_id}/activity",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        items = r.json()
        item_types = {i["type"] for i in items}
        assert "event" in item_types, "No behavioral event in combined response"
        assert "message" in item_types, "No message in combined response"

    def test_activity_is_sorted_newest_first(
        self, client, firm_a_owner
    ):
        """Items are returned newest first (descending by occurred_at)."""
        from tests.conftest import TestingSessionLocal
        from app.models.behavioral_event import BehavioralEvent

        lead_id = _create_lead(client, firm_a_owner["headers"])
        firm_id = firm_a_owner["firm_id"]

        now = datetime.now(timezone.utc)
        older = now - timedelta(days=5)
        newer = now - timedelta(days=1)

        db = TestingSessionLocal()
        try:
            db.add(BehavioralEvent(
                firm_id=uuid.UUID(firm_id),
                event_type="lead.created",
                entity_type="lead",
                entity_id=uuid.UUID(lead_id),
                occurred_at=older,
            ))
            db.add(BehavioralEvent(
                firm_id=uuid.UUID(firm_id),
                event_type="lead.email_replied",
                entity_type="lead",
                entity_id=uuid.UUID(lead_id),
                occurred_at=newer,
            ))
            db.commit()
        finally:
            db.close()

        r = client.get(
            f"/api/v1/leads/{lead_id}/activity",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        items = r.json()
        assert len(items) >= 2, f"Expected at least 2 items, got {len(items)}"
        timestamps = [i["occurred_at"] for i in items]
        assert timestamps == sorted(timestamps, reverse=True), (
            f"Activity not sorted newest first. occurred_at values: {timestamps}"
        )
