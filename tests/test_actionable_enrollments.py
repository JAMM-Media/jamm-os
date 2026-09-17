# tests/test_actionable_enrollments.py
"""
Guard test for the actionable_enrollments field on GET /api/v1/leads/{lead_id}.

One guard, watched red then green:
  A lead with a held_for_approval enrollment returns a populated
  actionable_enrollments list; a lead with no such enrollment returns [].

Watch red: temporarily make get_actionable_enrollments_for_lead return []
unconditionally. Confirm the test fails because the held enrollment is absent.
Restore; confirm green. Confirm git diff on the restored file is empty.
"""

import uuid
from datetime import datetime, timezone

from tests.conftest import TestingSessionLocal
from app.models.enrollment import Enrollment
from app.models.sequence import Sequence, SequenceVersion
from app.core.enums import EnrollmentStatus


def _create_lead(client, headers) -> dict:
    r = client.post(
        "/api/v1/leads/",
        json={"name": f"Test Lead {uuid.uuid4()}", "provenance": "firm_entered"},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def _insert_minimal_sequence(firm_id: str) -> tuple:
    """Create the minimal Sequence + SequenceVersion rows needed to satisfy
    Enrollment FKs. Returns (sequence_id, sequence_version_id)."""
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        seq = Sequence(
            firm_id=uuid.UUID(firm_id),
            name=f"Test Seq {uuid.uuid4().hex[:8]}",
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        db.add(seq)
        db.flush()
        ver = SequenceVersion(
            sequence_id=seq.id,
            version_number=1,
            created_at=now,
        )
        db.add(ver)
        db.commit()
        return str(seq.id), str(ver.id)
    finally:
        db.close()


def _insert_enrollment(firm_id: str, lead_id: str, seq_id: str, ver_id: str, status: str) -> str:
    """Insert an Enrollment row directly. Returns enrollment id."""
    db = TestingSessionLocal()
    try:
        enrollment = Enrollment(
            firm_id=uuid.UUID(firm_id),
            lead_id=uuid.UUID(lead_id),
            sequence_id=uuid.UUID(seq_id),
            sequence_version_id=uuid.UUID(ver_id),
            status=status,
            loop_counts={},
            enrolled_at=datetime.now(timezone.utc),
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        return str(enrollment.id)
    finally:
        db.close()


def test_actionable_enrollments_populated_and_empty(client, firm_a_owner):
    """
    Guard: get_actionable_enrollments_for_lead is called and its results are
    returned in the GET /leads/{id} response.

    Lead A has a held_for_approval enrollment -- must appear in actionable_enrollments.
    Lead B has no actionable enrollment -- must return an empty list.
    """
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]

    lead_a = _create_lead(client, headers)
    lead_b = _create_lead(client, headers)

    seq_id, ver_id = _insert_minimal_sequence(firm_id)
    enr_id = _insert_enrollment(
        firm_id, lead_a["id"], seq_id, ver_id,
        EnrollmentStatus.held_for_approval.value,
    )

    # Lead A: should have one actionable enrollment
    r_a = client.get(f"/api/v1/leads/{lead_a['id']}", headers=headers)
    assert r_a.status_code == 200, r_a.text
    data_a = r_a.json()
    assert "actionable_enrollments" in data_a, "actionable_enrollments field missing from response"
    assert len(data_a["actionable_enrollments"]) == 1, (
        f"Expected 1 actionable enrollment, got {len(data_a['actionable_enrollments'])}"
    )
    assert data_a["actionable_enrollments"][0]["id"] == enr_id
    assert data_a["actionable_enrollments"][0]["status"] == EnrollmentStatus.held_for_approval.value

    # Lead B: should have an empty list
    r_b = client.get(f"/api/v1/leads/{lead_b['id']}", headers=headers)
    assert r_b.status_code == 200, r_b.text
    data_b = r_b.json()
    assert data_b["actionable_enrollments"] == [], (
        f"Expected empty list for lead B, got {data_b['actionable_enrollments']}"
    )
