# tests/test_lead_events.py
"""
Tests for lead behavioral events:
  - lead.stage_changed fires on non-named stage transitions
  - lead.updated fires on field changes via the PATCH endpoint

Covers:
  1. identified -> contacted fires lead.stage_changed with correct metadata.
  2. contacted -> call_booked (another generic transition) fires lead.stage_changed.
  3. won, lost, and lost->reopened transitions do NOT also fire lead.stage_changed.
  4. PATCH with hot=True fires lead.updated with correct changed_fields delta.
  5. No Lead fields are sensitive-named, so changed_fields shows actual values.
  6. PATCH that changes nothing (same value) does NOT fire lead.updated.
  7. write_audit_log (audit log) and log_event (behavioral log) both fire on
     the same update, independently, serving their separate purposes.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal
from app.models.lead import Lead
from app.models.behavioral_event import BehavioralEvent
from app.core.enums import LeadProvenance, LeadStage


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LEAD_BASE = {
    "name": "Stage Event Test Lead",
    "email": None,
    "provenance": "firm_entered",
}


def _count_events(firm_id, event_type, entity_id=None) -> int:
    db = TestingSessionLocal()
    try:
        q = db.query(BehavioralEvent).filter(
            BehavioralEvent.firm_id == uuid.UUID(str(firm_id)),
            BehavioralEvent.event_type == event_type,
        )
        if entity_id is not None:
            q = q.filter(BehavioralEvent.entity_id == uuid.UUID(str(entity_id)))
        return q.count()
    finally:
        db.close()


def _get_event(firm_id, event_type, entity_id=None):
    db = TestingSessionLocal()
    try:
        q = db.query(BehavioralEvent).filter(
            BehavioralEvent.firm_id == uuid.UUID(str(firm_id)),
            BehavioralEvent.event_type == event_type,
        )
        if entity_id is not None:
            q = q.filter(BehavioralEvent.entity_id == uuid.UUID(str(entity_id)))
        return q.first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1 & 2. Generic stage transitions fire lead.stage_changed
# ---------------------------------------------------------------------------

class TestStageChangedEvent:

    def test_identified_to_contacted_fires_stage_changed(self, client, firm_a_owner):
        """identified -> contacted fires lead.stage_changed with correct from/to."""
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]
        assert r.json()["stage"] == "identified"

        r2 = client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "contacted"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["stage"] == "contacted"

        event = _get_event(firm_id, "lead.stage_changed", lead_id)
        assert event is not None, "lead.stage_changed event must be written"
        assert event.extra_metadata["from_stage"] == "identified"
        assert event.extra_metadata["to_stage"] == "contacted"
        assert event.entity_type == "lead"
        assert str(event.entity_id) == lead_id

    def test_contacted_to_call_booked_fires_stage_changed(self, client, firm_a_owner):
        """contacted -> call_booked also fires lead.stage_changed."""
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]

        client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "contacted"},
            headers=headers,
        )
        r2 = client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "call_booked"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text

        events = []
        db = TestingSessionLocal()
        try:
            events = db.query(BehavioralEvent).filter(
                BehavioralEvent.firm_id == uuid.UUID(firm_id),
                BehavioralEvent.event_type == "lead.stage_changed",
                BehavioralEvent.entity_id == uuid.UUID(lead_id),
            ).all()
        finally:
            db.close()

        assert len(events) == 2, f"Expected 2 lead.stage_changed events, got {len(events)}"
        to_stages = {e.extra_metadata["to_stage"] for e in events}
        assert "call_booked" in to_stages


# ---------------------------------------------------------------------------
# 3. Named-event transitions do NOT also fire lead.stage_changed
# ---------------------------------------------------------------------------

class TestNamedTransitionsNoDoubleEvent:

    def test_won_transition_does_not_fire_stage_changed(self, client, firm_a_owner):
        """won transition fires lead.converted, NOT lead.stage_changed."""
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post(
            "/api/v1/leads/",
            json={**_LEAD_BASE, "email": f"won-{uuid.uuid4().hex[:6]}@example.com"},
            headers=headers,
        )
        assert r.status_code == 201
        lead_id = r.json()["id"]

        r2 = client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "won"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text

        assert _count_events(firm_id, "lead.converted", lead_id) == 1
        assert _count_events(firm_id, "lead.stage_changed", lead_id) == 0, (
            "won transition must not also fire lead.stage_changed"
        )

    def test_lost_transition_does_not_fire_stage_changed(self, client, firm_a_owner):
        """lost transition fires lead.lost, NOT lead.stage_changed."""
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]

        r2 = client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "lost", "lost_reason": "unresponsive"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text

        assert _count_events(firm_id, "lead.lost", lead_id) == 1
        assert _count_events(firm_id, "lead.stage_changed", lead_id) == 0, (
            "lost transition must not also fire lead.stage_changed"
        )

    def test_reopened_transition_does_not_fire_stage_changed(self, client, firm_a_owner):
        """lost -> reopened fires lead.reopened, NOT lead.stage_changed."""
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]

        client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "lost", "lost_reason": "unresponsive"},
            headers=headers,
        )
        r2 = client.post(
            f"/api/v1/leads/{lead_id}/transition",
            json={"new_stage": "contacted"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text

        assert _count_events(firm_id, "lead.reopened", lead_id) == 1
        assert _count_events(firm_id, "lead.stage_changed", lead_id) == 0, (
            "reopened transition must not also fire lead.stage_changed"
        )


# ---------------------------------------------------------------------------
# 4. PATCH fires lead.updated with correct changed_fields
# ---------------------------------------------------------------------------

class TestLeadUpdatedEvent:

    def test_patch_hot_fires_lead_updated_with_correct_delta(self, client, firm_a_owner):
        """Setting hot=True via PATCH fires lead.updated with from/to in changed_fields."""
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]
        assert r.json()["hot"] is False

        r2 = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"hot": True},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
        assert r2.json()["hot"] is True

        event = _get_event(firm_id, "lead.updated", lead_id)
        assert event is not None, "lead.updated behavioral event must be written"
        changed = event.extra_metadata.get("changed_fields", {})
        assert "hot" in changed, f"'hot' must be in changed_fields, got {changed}"
        assert changed["hot"]["from"] is False, f"from must be False, got {changed['hot']}"
        assert changed["hot"]["to"] is True, f"to must be True, got {changed['hot']}"

    # -----------------------------------------------------------------------
    # 5. No Lead fields are sensitive, so values appear unredacted
    # -----------------------------------------------------------------------

    def test_non_sensitive_field_shows_actual_values_not_redacted(self, client, firm_a_owner):
        """Lead fields are not sensitive-named, so changed_fields shows actual values.

        Confirmed during VERIFY BEFORE ACT: no Lead field name contains ssn, ein,
        tax_id, bank, routing, or account_number. This test asserts that a plain
        field update (name) shows the real before/after values in the event.
        """
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post(
            "/api/v1/leads/",
            json={**_LEAD_BASE, "name": "Original Name"},
            headers=headers,
        )
        assert r.status_code == 201
        lead_id = r.json()["id"]

        r2 = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"name": "Updated Name"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text

        event = _get_event(firm_id, "lead.updated", lead_id)
        assert event is not None
        changed = event.extra_metadata.get("changed_fields", {})
        assert "name" in changed
        assert changed["name"]["from"] == "Original Name", (
            f"Expected 'Original Name', got {changed['name']['from']!r}"
        )
        assert changed["name"]["to"] == "Updated Name", (
            f"Expected 'Updated Name', got {changed['name']['to']!r}"
        )
        assert changed["name"]["from"] != "redacted", "Non-sensitive field must not be redacted"

    # -----------------------------------------------------------------------
    # 6. PATCH that changes nothing does NOT fire lead.updated
    # -----------------------------------------------------------------------

    def test_patch_no_actual_change_does_not_fire_lead_updated(self, client, firm_a_owner):
        """Sending the same value as already stored does not fire lead.updated."""
        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post(
            "/api/v1/leads/",
            json={**_LEAD_BASE, "name": "Same Name"},
            headers=headers,
        )
        assert r.status_code == 201
        lead_id = r.json()["id"]

        r2 = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"name": "Same Name"},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text

        assert _count_events(firm_id, "lead.updated", lead_id) == 0, (
            "lead.updated must not fire when no field actually changed"
        )

    # -----------------------------------------------------------------------
    # 7. write_audit_log and log_event both fire independently
    # -----------------------------------------------------------------------

    def test_both_audit_log_and_behavioral_log_fire_on_update(self, client, firm_a_owner):
        """PATCH fires both write_audit_log (audit) and log_event (behavioral) independently."""
        from app.models.audit_log import AuditLog

        headers = firm_a_owner["headers"]
        firm_id = firm_a_owner["firm_id"]

        r = client.post("/api/v1/leads/", json=_LEAD_BASE, headers=headers)
        assert r.status_code == 201
        lead_id = r.json()["id"]

        r2 = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"hot": True},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text

        # Behavioral log entry
        b_event = _get_event(firm_id, "lead.updated", lead_id)
        assert b_event is not None, "Behavioral log event lead.updated must be written"

        # Audit log entry
        db = TestingSessionLocal()
        try:
            a_log = db.query(AuditLog).filter(
                AuditLog.firm_id == uuid.UUID(firm_id),
                AuditLog.action == "lead.updated",
                AuditLog.entity_id == uuid.UUID(lead_id),
            ).first()
        finally:
            db.close()

        assert a_log is not None, "Audit log entry lead.updated must also be written"
        assert str(b_event.entity_id) == lead_id
        assert str(a_log.entity_id) == lead_id
