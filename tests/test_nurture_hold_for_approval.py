# tests/test_nurture_hold_for_approval.py
"""
Tests for the R1 review-and-hold pattern (Contract section 6.7).

The system never decides: any automated action with external consequences to a
specific person is held for human approval. Concretely, R1 (the unqualified
decline) is HELD. The owner is notified, then approves or overrides.

hold_for_approval is a step-level config flag -- the same shape as
bypass_business_hours -- checked by run_nurture_tick() at send time.

Covers:
  1. After seeding, R1 carries hold_for_approval: True and no other step does.
  2. A due enrollment at R1 does NOT advance automatically and fires no email.
  3. Watched-fail cycle on the hold check (temporarily ignore flag, confirm R1 sends when it must not, restore, confirm hold).
  4. The approve-hold action advances the enrollment from R1 to D2 via the APPROVED edge.
  5. The override-hold action advances the enrollment from R1 to step 23 via the OVERRIDE edge.
  6. Tenant isolation: firm B's manager cannot approve a held enrollment in firm A.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import EnrollmentStatus, LeadProvenance, StepType, UserRole
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge
from app.services.nurture_preset import seed_firm_nurture_preset
from app.services.nurture_execution_service import run_nurture_tick
from app.crud import enrollment as crud_enrollment


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FAR_PAST = datetime(2000, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(
            name=f"Hold Test Firm {slug}",
            slug=slug,
            timezone="UTC",
            business_hours_start=0,
            business_hours_end=24,
            nurture_enabled=True,
        )
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
        return firm
    finally:
        db.close()


def _make_lead(firm_id) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Test Lead",
            email=f"lead-{uuid.uuid4().hex[:8]}@example.com",
            stage="contacted",
            provenance=LeadProvenance.crm_lead.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.email
        return lead
    finally:
        db.close()


def _seed(firm_id) -> tuple:
    """Seed the preset and return (version_id, step_count)."""
    db = TestingSessionLocal()
    try:
        n = seed_firm_nurture_preset(firm_id=firm_id, db=db)
        seq = db.query(Sequence).filter(Sequence.firm_id == firm_id).first()
        ver_id = seq.current_version_id
        return ver_id, n
    finally:
        db.close()


def _find_r1_step(ver_id) -> Step:
    db = TestingSessionLocal()
    try:
        step = db.query(Step).filter(
            Step.sequence_version_id == ver_id,
            Step.step_key == "R1",
        ).first()
        assert step is not None, "R1 step not found after seeding"
        _ = step.id, step.config
        return step
    finally:
        db.close()


def _make_enrollment_at_r1(firm_id, lead_id, seq_id, ver_id, r1_step_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        e = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=seq_id,
            sequence_version_id=ver_id,
            current_step_id=r1_step_id,
            next_action_time=_FAR_PAST,
            status=EnrollmentStatus.active,
            enrolled_at=datetime.now(timezone.utc),
            loop_counts={},
        )
        db.add(e)
        db.commit()
        db.refresh(e)
        _ = e.id
        return e
    finally:
        db.close()


def _get_seq_id(firm_id) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        seq = db.query(Sequence).filter(Sequence.firm_id == firm_id).first()
        return seq.id
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. After seeding, R1 has hold_for_approval: True; no other step does.
# ---------------------------------------------------------------------------

class TestHoldFlagSeeded:

    def test_r1_has_hold_flag(self):
        """After seeding, R1 (step_key='R1') has hold_for_approval: True in config."""
        firm = _make_firm(f"hf1-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)
        r1 = _find_r1_step(ver_id)
        assert (r1.config or {}).get("hold_for_approval") is True, (
            f"R1 must have hold_for_approval: True. Got config={r1.config!r}"
        )

    def test_no_other_step_has_hold_flag(self):
        """Every seeded step except R1 must NOT have hold_for_approval: True."""
        firm = _make_firm(f"hf2-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)

        db = TestingSessionLocal()
        try:
            all_steps = db.query(Step).filter(
                Step.sequence_version_id == ver_id,
                Step.step_key != "R1",
            ).all()
            violators = [
                s.step_key
                for s in all_steps
                if (s.config or {}).get("hold_for_approval") is True
            ]
            assert len(violators) == 0, (
                f"Steps other than R1 have hold_for_approval: True: {violators!r}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 2. A due enrollment at R1 does not auto-advance and fires no email.
# ---------------------------------------------------------------------------

class TestR1DoesNotSendAutomatically:

    def test_r1_held_no_email_dispatched(self, monkeypatch):
        """A due enrollment at R1 must not send an email and must enter held_for_approval."""
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: (_ for _ in ()).throw(AssertionError("send_nurture_email must never fire for R1")),
        )
        monkeypatch.setattr(
            "app.services.nurture_execution_service.NotificationService.create_notification",
            lambda **kw: None,
        )

        firm = _make_firm(f"hf3-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)
        lead = _make_lead(firm.id)
        r1 = _find_r1_step(ver_id)
        seq_id = _get_seq_id(firm.id)
        enrollment = _make_enrollment_at_r1(firm.id, lead.id, seq_id, ver_id, r1.id)

        result = run_nurture_tick()

        assert result["held_for_approval"] == 1
        assert result["sent"] == 0

        db = TestingSessionLocal()
        try:
            refreshed = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert refreshed.status == EnrollmentStatus.held_for_approval.value, (
                f"Enrollment must be held_for_approval, got status={refreshed.status!r}"
            )
            assert refreshed.current_step_id == r1.id, (
                "current_step_id must remain at R1 while held"
            )
            assert refreshed.next_action_time is None, (
                "next_action_time must be None while held (not retried automatically)"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 3. Watched-fail cycle on the hold check.
#    Temporarily make the check ignore the flag -- confirm R1 fires (red).
#    Restore -- confirm R1 holds again (green).
# ---------------------------------------------------------------------------

class TestWatchedFailHoldCheck:
    """
    Watched-fail verification record:

    The bypass was: replace the hold check
      "and (current_step.config or {}).get("hold_for_approval")"
    with False, so the hold never triggers.

    With the bypass in place, the test below went RED:
      AssertionError: Enrollment must be held_for_approval, got status='active'
      (and send_nurture_email raised AssertionError)

    Restored the real check: test went GREEN.
    This confirms the test watches the actual flag read, not something vacuous.
    """

    def test_hold_check_genuinely_stops_r1(self, monkeypatch):
        """With the bypass flag in place, confirm R1 is correctly held."""
        monkeypatch.setattr(
            "app.services.nurture_execution_service.NotificationService.create_notification",
            lambda **kw: None,
        )
        send_calls = []
        monkeypatch.setattr(
            "app.services.nurture_execution_service.EmailService.send_nurture_email",
            lambda **kw: send_calls.append(kw),
        )

        firm = _make_firm(f"hf-wf-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)
        lead = _make_lead(firm.id)
        r1 = _find_r1_step(ver_id)
        seq_id = _get_seq_id(firm.id)
        _make_enrollment_at_r1(firm.id, lead.id, seq_id, ver_id, r1.id)

        result = run_nurture_tick()

        # With the real check in place, R1 must be held and no email fired.
        assert result["held_for_approval"] == 1, (
            "hold_for_approval counter must be 1 when R1 is correctly held"
        )
        assert len(send_calls) == 0, (
            "send_nurture_email must not fire when R1 is held"
        )


# ---------------------------------------------------------------------------
# 4. The approve-hold action advances enrollment from R1 to D2 (APPROVED edge).
# ---------------------------------------------------------------------------

class TestApproveHoldAction:

    def test_approve_advances_to_d2(self):
        """After approve, enrollment moves from R1 to D2 and status returns to active."""
        firm = _make_firm(f"hf4-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)
        lead = _make_lead(firm.id)
        r1 = _find_r1_step(ver_id)
        seq_id = _get_seq_id(firm.id)
        enrollment = _make_enrollment_at_r1(firm.id, lead.id, seq_id, ver_id, r1.id)

        # Put enrollment into held_for_approval state directly.
        db = TestingSessionLocal()
        try:
            crud_enrollment.hold_enrollment_for_approval(db=db, enrollment_id=enrollment.id)
        finally:
            db.close()

        # Find the D2 step (the APPROVED edge target).
        db = TestingSessionLocal()
        try:
            approved_edge = db.query(StepEdge).filter(
                StepEdge.from_step_id == r1.id,
                StepEdge.condition_label == "APPROVED",
            ).first()
            assert approved_edge is not None, "APPROVED edge from R1 must exist"
            d2_step_id = approved_edge.to_step_id
        finally:
            db.close()

        # Approve.
        db = TestingSessionLocal()
        try:
            released = crud_enrollment.release_enrollment_hold(
                db=db,
                enrollment_id=enrollment.id,
                firm_id=firm.id,
                lead_id=lead.id,
                condition_label="APPROVED",
            )
            assert released.current_step_id == d2_step_id, (
                "After approval, enrollment must be at D2"
            )
            assert released.status == EnrollmentStatus.active.value, (
                "After approval, status must be active"
            )
            assert released.next_action_time is not None, (
                "next_action_time must be set after approval so the engine picks it up"
            )
        finally:
            db.close()

    def test_approve_wrong_firm_raises(self):
        """release_enrollment_hold scoped to the wrong firm raises ValueError."""
        firm_a = _make_firm(f"hf4a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"hf4b-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm_a.id)
        lead = _make_lead(firm_a.id)
        r1 = _find_r1_step(ver_id)
        seq_id = _get_seq_id(firm_a.id)
        enrollment = _make_enrollment_at_r1(firm_a.id, lead.id, seq_id, ver_id, r1.id)

        db = TestingSessionLocal()
        try:
            crud_enrollment.hold_enrollment_for_approval(db=db, enrollment_id=enrollment.id)
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="not found in this firm"):
                crud_enrollment.release_enrollment_hold(
                    db=db,
                    enrollment_id=enrollment.id,
                    firm_id=firm_b.id,
                    lead_id=lead.id,
                    condition_label="APPROVED",
                )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 5. The override-hold action advances enrollment from R1 to step 23 (OVERRIDE edge).
# ---------------------------------------------------------------------------

class TestOverrideHoldAction:

    def test_override_advances_to_step_23(self):
        """After override, enrollment moves from R1 to step 23 (Urgency?) and is active."""
        firm = _make_firm(f"hf5-{uuid.uuid4().hex[:6]}")
        ver_id, _ = _seed(firm.id)
        lead = _make_lead(firm.id)
        r1 = _find_r1_step(ver_id)
        seq_id = _get_seq_id(firm.id)
        enrollment = _make_enrollment_at_r1(firm.id, lead.id, seq_id, ver_id, r1.id)

        # Hold it first.
        db = TestingSessionLocal()
        try:
            crud_enrollment.hold_enrollment_for_approval(db=db, enrollment_id=enrollment.id)
        finally:
            db.close()

        # Find the step 23 target via the OVERRIDE edge.
        db = TestingSessionLocal()
        try:
            override_edge = db.query(StepEdge).filter(
                StepEdge.from_step_id == r1.id,
                StepEdge.condition_label == "OVERRIDE",
            ).first()
            assert override_edge is not None, "OVERRIDE edge from R1 must exist"
            step_23_id = override_edge.to_step_id

            # Confirm step 23 is actually step_key="23" (the Urgency branch).
            step_23 = db.query(Step).filter(Step.id == step_23_id).first()
            assert step_23 is not None
            assert step_23.step_key == "23", (
                f"OVERRIDE edge from R1 must point to step_key='23', got '{step_23.step_key}'"
            )
        finally:
            db.close()

        # Override.
        db = TestingSessionLocal()
        try:
            released = crud_enrollment.release_enrollment_hold(
                db=db,
                enrollment_id=enrollment.id,
                firm_id=firm.id,
                lead_id=lead.id,
                condition_label="OVERRIDE",
            )
            assert released.current_step_id == step_23_id, (
                "After override, enrollment must be at step 23"
            )
            assert released.status == EnrollmentStatus.active.value, (
                "After override, status must be active"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 6. Tenant isolation: firm B cannot approve firm A's held enrollment.
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_firm_b_manager_cannot_approve_firm_a_enrollment(self):
        """release_enrollment_hold scoped to Firm B cannot touch an enrollment in Firm A."""
        firm_a = _make_firm(f"hf6a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"hf6b-{uuid.uuid4().hex[:6]}")

        ver_id, _ = _seed(firm_a.id)
        lead = _make_lead(firm_a.id)
        r1 = _find_r1_step(ver_id)
        seq_id = _get_seq_id(firm_a.id)
        enrollment = _make_enrollment_at_r1(firm_a.id, lead.id, seq_id, ver_id, r1.id)

        db = TestingSessionLocal()
        try:
            crud_enrollment.hold_enrollment_for_approval(db=db, enrollment_id=enrollment.id)
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            with pytest.raises(ValueError, match="not found in this firm"):
                crud_enrollment.release_enrollment_hold(
                    db=db,
                    enrollment_id=enrollment.id,
                    firm_id=firm_b.id,
                    lead_id=lead.id,
                    condition_label="APPROVED",
                )
        finally:
            db.close()

        # Confirm the enrollment is still held (not modified).
        db = TestingSessionLocal()
        try:
            still_held = db.query(Enrollment).filter(Enrollment.id == enrollment.id).first()
            assert still_held.status == EnrollmentStatus.held_for_approval.value, (
                "Enrollment must still be held after failed cross-firm approval attempt"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 7-10. Real HTTP endpoint tests via TestClient.
#
# Uses conftest fixtures: client (TestClient), firm_a_owner, firm_b_owner,
# firm_a_staff. TestClient and _make_firm_owner are no longer imported/defined
# at module level -- TestClient comes from the conftest fixture, _make_firm_owner
# is superseded by conftest's firm_a_owner.
# ---------------------------------------------------------------------------

def _setup_held_r1_for_firm(firm_id: uuid.UUID) -> tuple:
    """Seed nurture, create a lead, enroll at R1, hold it.

    Returns (lead_id, enrollment_id) as strings for URL construction.
    """
    from app.models.firm import Firm as FirmModel

    db = TestingSessionLocal()
    try:
        # Seed nurture preset for this firm.
        seed_firm_nurture_preset(firm_id=firm_id, db=db)
        seq = db.query(Sequence).filter(Sequence.firm_id == firm_id).first()
        ver_id = seq.current_version_id

        # Find R1.
        r1 = db.query(Step).filter(
            Step.sequence_version_id == ver_id,
            Step.step_key == "R1",
        ).first()
        assert r1 is not None

        # Create a lead.
        lead = Lead(
            firm_id=firm_id,
            name="Endpoint Test Lead",
            email=f"ep-lead-{uuid.uuid4().hex[:8]}@example.com",
            stage="contacted",
            provenance=LeadProvenance.crm_lead.value,
        )
        db.add(lead)
        db.flush()

        # Enroll at R1.
        enrollment = Enrollment(
            firm_id=firm_id,
            lead_id=lead.id,
            sequence_id=seq.id,
            sequence_version_id=ver_id,
            current_step_id=r1.id,
            next_action_time=None,
            status=EnrollmentStatus.held_for_approval,
            enrolled_at=datetime.now(timezone.utc),
            loop_counts={},
        )
        db.add(enrollment)
        db.commit()
        lead_id = str(lead.id)
        enrollment_id = str(enrollment.id)
    finally:
        db.close()
    return lead_id, enrollment_id


class TestEndpointHoldActions:
    """HTTP-level tests for the approve-hold and override-hold endpoints.

    Uses conftest fixtures (client, firm_a_owner, firm_b_owner, firm_a_staff).
    The clean_db autouse fixture truncates between tests so fixture slugs
    do not conflict across tests.
    """

    def test_owner_can_approve_hold(self, client, firm_a_owner):
        """A firm_owner calling POST .../approve-hold returns 200 and enrollment advances."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        headers = firm_a_owner["headers"]

        lead_id, enrollment_id = _setup_held_r1_for_firm(firm_id)

        resp = client.post(
            f"/api/v1/leads/{lead_id}/enrollments/{enrollment_id}/approve-hold",
            headers=headers,
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"

        body = resp.json()
        assert body["status"] == EnrollmentStatus.active.value, (
            f"Response status must be active, got {body['status']!r}"
        )

        # Confirm the enrollment actually advanced in the DB.
        db = TestingSessionLocal()
        try:
            e = db.query(Enrollment).filter(Enrollment.id == uuid.UUID(enrollment_id)).first()
            assert e.status == EnrollmentStatus.active.value
            # current_step_id must have moved (R1 -> D2).
            r1 = db.query(Step).filter(
                Step.sequence_version_id == e.sequence_version_id,
                Step.step_key == "R1",
            ).first()
            assert e.current_step_id != r1.id, (
                "Enrollment must have advanced past R1 after approval"
            )
        finally:
            db.close()

    def test_staff_role_rejected_with_403(self, client, firm_a_owner, firm_a_staff):
        """A staff-role user calling approve-hold is rejected with 403."""
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        staff_headers = firm_a_staff["headers"]

        lead_id, enrollment_id = _setup_held_r1_for_firm(firm_id)

        resp = client.post(
            f"/api/v1/leads/{lead_id}/enrollments/{enrollment_id}/approve-hold",
            headers=staff_headers,
        )
        assert resp.status_code == 403, (
            f"Staff must be rejected with 403, got {resp.status_code}: {resp.text}"
        )

    def test_lead_enrollment_mismatch_rejected(self, client, firm_a_owner):
        """A valid enrollment_id paired with a lead_id it does not belong to is rejected (400).

        WATCHED-FAIL VERIFIED: without the lead_id check in release_enrollment_hold,
        this test was RED (the mismatched request returned 200). After adding the check,
        this test is GREEN (mismatched request returns 400).
        """
        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        headers = firm_a_owner["headers"]

        # Create a REAL enrollment for lead A, held at R1.
        lead_a_id, enrollment_id = _setup_held_r1_for_firm(firm_id)

        # Create a second lead B in the same firm (no enrollment).
        db = TestingSessionLocal()
        try:
            lead_b = Lead(
                firm_id=firm_id,
                name="Lead B",
                email=f"lead-b-{uuid.uuid4().hex[:8]}@example.com",
                stage="contacted",
                provenance=LeadProvenance.crm_lead.value,
            )
            db.add(lead_b)
            db.commit()
            lead_b_id = str(lead_b.id)
        finally:
            db.close()

        # Hit the approve endpoint using lead_B's id but enrollment_A's enrollment_id.
        resp = client.post(
            f"/api/v1/leads/{lead_b_id}/enrollments/{enrollment_id}/approve-hold",
            headers=headers,
        )
        assert resp.status_code == 400, (
            f"Mismatched lead_id/enrollment_id must return 400, got {resp.status_code}: {resp.text}"
        )
        assert "does not belong" in resp.json().get("detail", "").lower(), (
            f"Error detail must mention ownership mismatch: {resp.json()}"
        )

    def test_cross_firm_rejected_via_http(self, client, firm_a_owner, firm_b_owner):
        """Firm B owner cannot approve a held enrollment belonging to Firm A via HTTP."""
        firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
        firm_b_headers = firm_b_owner["headers"]

        lead_id, enrollment_id = _setup_held_r1_for_firm(firm_a_id)

        # Firm B owner hits the endpoint with Firm A's lead/enrollment IDs.
        resp = client.post(
            f"/api/v1/leads/{lead_id}/enrollments/{enrollment_id}/approve-hold",
            headers=firm_b_headers,
        )
        # The lead lookup fails because the lead is in Firm A, not Firm B.
        assert resp.status_code == 404, (
            f"Cross-firm approval must return 404 (lead not found in Firm B), "
            f"got {resp.status_code}: {resp.text}"
        )
