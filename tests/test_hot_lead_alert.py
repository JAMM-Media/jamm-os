# tests/test_hot_lead_alert.py
"""
Tests for the hot lead immediate alert (Contract section 7.5).

When a lead's hot flag is set (via staff PATCH or staff POST), the firm owner
receives an immediate notification. The nurture sequence continues unchanged.

Covers:
  1. Marking a lead hot via PATCH fires exactly one alert to the firm owner.
  2. A lead never marked hot generates no alert.
  3. Tenant isolation: the alert goes to the correct firm's owner only.
  4. Creating a lead already hot fires the alert at creation time.
  5. Marking a lead hot twice does not double-fire (second PATCH is a no-op).

NOTE: The "lead_hot_alert" notification type is a proposed name pending
Andrew's sign-off (Contract section 9.1: event names freeze once a firm
goes live).

INTAKE FORM GAP (reported, not built here):
The intake form (POST /intake/{slug}/submit) has no code path that sets
lead.hot = True from the form's urgency/timeline question. The urgency field
is captured as text but the hot flag is never set automatically. Setting hot
from the intake form requires a separate, explicitly-scoped build task.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import NotificationType, UserRole
from app.models.lead import Lead
from app.models.notification import Notification
from app.models.user import User
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEAD_BASE = {
    "name": "Hot Alert Test Lead",
    "provenance": "firm_entered",
}


def _count_hot_alerts(firm_id, lead_id=None) -> int:
    db = TestingSessionLocal()
    try:
        q = db.query(Notification).filter(
            Notification.firm_id == firm_id,
            Notification.notification_type == NotificationType.lead_hot_alert.value,
        )
        if lead_id is not None:
            q = q.filter(Notification.related_entity_id == lead_id)
        return q.count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. PATCH marks lead hot -> exactly one alert to firm owner
# ---------------------------------------------------------------------------

class TestHotLeadAlertOnUpdate:

    def test_patch_hot_true_fires_one_alert(self, client, firm_a_owner):
        """Setting hot=True via PATCH fires exactly one notification to firm_a_owner."""
        headers = firm_a_owner["headers"]

        # Create a cold lead.
        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]
        firm_id = uuid.UUID(firm_a_owner["firm_id"])

        assert _count_hot_alerts(firm_id, uuid.UUID(lead_id)) == 0

        # Mark it hot.
        r2 = client.patch(f"/api/v1/leads/{lead_id}", json={"hot": True}, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["hot"] is True

        assert _count_hot_alerts(firm_id, uuid.UUID(lead_id)) == 1, (
            "Expected exactly one hot_lead_alert notification after marking lead hot"
        )

    def test_patch_without_hot_fires_no_alert(self, client, firm_a_owner):
        """A PATCH that does not set hot fires no hot lead alert."""
        headers = firm_a_owner["headers"]
        firm_id = uuid.UUID(firm_a_owner["firm_id"])

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]

        # Update something other than hot.
        r2 = client.patch(f"/api/v1/leads/{lead_id}", json={"name": "Updated Name"}, headers=headers)
        assert r2.status_code == 200

        assert _count_hot_alerts(firm_id) == 0

    def test_lead_never_marked_hot_no_alert(self, client, firm_a_owner):
        """A lead that is never marked hot generates no hot lead alert."""
        headers = firm_a_owner["headers"]
        firm_id = uuid.UUID(firm_a_owner["firm_id"])

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201

        assert _count_hot_alerts(firm_id) == 0


# ---------------------------------------------------------------------------
# 2. Marking hot twice does not double-fire (idempotent on subsequent PATCHes)
# ---------------------------------------------------------------------------

class TestHotAlertIdempotent:

    def test_second_hot_patch_does_not_fire_again(self, client, firm_a_owner):
        """A second PATCH setting hot=True on an already-hot lead fires no extra alert."""
        headers = firm_a_owner["headers"]
        firm_id = uuid.UUID(firm_a_owner["firm_id"])

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        lead_id = r.json()["id"]

        # First mark: alert fires.
        client.patch(f"/api/v1/leads/{lead_id}", json={"hot": True}, headers=headers)
        assert _count_hot_alerts(firm_id, uuid.UUID(lead_id)) == 1

        # Second mark: no new alert.
        client.patch(f"/api/v1/leads/{lead_id}", json={"hot": True}, headers=headers)
        assert _count_hot_alerts(firm_id, uuid.UUID(lead_id)) == 1, (
            "Second hot=True PATCH must not fire a second notification"
        )


# ---------------------------------------------------------------------------
# 3. POST with hot=True fires the alert at creation
# ---------------------------------------------------------------------------

class TestHotLeadAlertOnCreate:

    def test_create_with_hot_fires_alert(self, client, firm_a_owner):
        """Creating a lead already marked hot fires the alert at creation time."""
        headers = firm_a_owner["headers"]
        firm_id = uuid.UUID(firm_a_owner["firm_id"])

        payload = {**_LEAD_BASE, "hot": True}
        r = client.post("/api/v1/leads/", json=payload, headers=headers)
        assert r.status_code == 201
        assert r.json()["hot"] is True
        lead_id = r.json()["id"]

        assert _count_hot_alerts(firm_id, uuid.UUID(lead_id)) == 1, (
            "Creating a lead with hot=True must fire one hot lead alert"
        )

    def test_create_without_hot_no_alert(self, client, firm_a_owner):
        """Creating a lead without hot fires no alert."""
        headers = firm_a_owner["headers"]
        firm_id = uuid.UUID(firm_a_owner["firm_id"])

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        assert r.json()["hot"] is False

        assert _count_hot_alerts(firm_id) == 0


# ---------------------------------------------------------------------------
# 4. Tenant isolation: alert goes to the correct firm owner only
# ---------------------------------------------------------------------------

class TestHotAlertTenantIsolation:

    def test_hot_alert_scoped_to_correct_firm(self, client, firm_a_owner, firm_b_owner):
        """Hot lead alert in Firm A does not appear for Firm B's owner."""
        headers_a = firm_a_owner["headers"]
        firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
        firm_b_id = uuid.UUID(firm_b_owner["firm_id"])

        # Create and mark hot in Firm A.
        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers_a)
        lead_id = r.json()["id"]
        client.patch(f"/api/v1/leads/{lead_id}", json={"hot": True}, headers=headers_a)

        # Firm A gets one alert.
        assert _count_hot_alerts(firm_a_id) == 1

        # Firm B gets zero alerts.
        assert _count_hot_alerts(firm_b_id) == 0, (
            "Firm B must have no hot lead alerts when a lead in Firm A is marked hot"
        )
