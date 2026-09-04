# tests/test_nurture_execution.py
"""
Tests for the nurture engine tick loop (app/services/nurture_execution_service.py).

GUARD TEST: test_enrollment_advances_even_when_send_raises
Proves the write-then-send guarantee: advance_enrollment() is called before
EmailService.send_nurture_email(), so a send failure never un-advances an
enrollment. See the watched-fail cycle documentation in the class docstring.
"""

import uuid
from datetime import datetime, timezone, timedelta

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.lead_message import LeadMessage
from app.models.sequence import Sequence, SequenceVersion, Step, StepEdge, SequenceGoal
from app.models.enrollment import Enrollment
from app.models.suppressed_email import SuppressedEmail
from app.models.behavioral_event import BehavioralEvent
from app.core.enums import LeadProvenance, EnrollmentStatus, StepType
from app.crud.enrollment import get_due_enrollments
from app.services.nurture_execution_service import run_nurture_tick


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> Firm:
    db = TestingSessionLocal()
    try:
        # business_hours_start=0 / end=24 so sends are never held by time-of-day
        # in these tests, which test other behaviors and don't need a time window.
        firm = Firm(name=f"Nurture Test Firm {slug}", slug=slug,
                    business_hours_start=0, business_hours_end=24,
                    nurture_enabled=True)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.name
        return firm
    finally:
        db.close()


def _make_lead(firm_id, email: str = None) -> Lead:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Nurture Test Lead",
            email=email or f"nurture-{uuid.uuid4()}@example.com",
            provenance=LeadProvenance.firm_entered.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.firm_id, lead.email
        return lead
    finally:
        db.close()


def _make_sequence_and_version(firm_id):
    """Create a Sequence and one SequenceVersion. Returns (sequence, version)."""
    db = TestingSessionLocal()
    try:
        sequence = Sequence(firm_id=firm_id, name="Nurture Test Sequence")
        db.add(sequence)
        db.flush()
        version = SequenceVersion(sequence_id=sequence.id, version_number=1)
        db.add(version)
        db.commit()
        db.refresh(sequence)
        db.refresh(version)
        _ = sequence.id, version.id
        return sequence, version
    finally:
        db.close()


def _make_step(version_id, step_key: str, config: dict = None) -> Step:
    """Create an email-type Step."""
    db = TestingSessionLocal()
    try:
        step = Step(
            sequence_version_id=version_id,
            step_key=step_key,
            step_type=StepType.email.value,
            channel="email",
            config=config or {"subject": "Test Subject", "body": "<p>Test body</p>"},
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        _ = step.id, step.step_key
        return step
    finally:
        db.close()


def _make_edge(from_step_id, to_step_id) -> StepEdge:
    db = TestingSessionLocal()
    try:
        edge = StepEdge(from_step_id=from_step_id, to_step_id=to_step_id)
        db.add(edge)
        db.commit()
        db.refresh(edge)
        _ = edge.id
        return edge
    finally:
        db.close()


def _make_enrollment(
    firm_id,
    lead_id,
    sequence_id,
    sequence_version_id,
    current_step_id=None,
    next_action_time=None,
    enrolled_at: datetime = None,
) -> Enrollment:
    db = TestingSessionLocal()
    try:
        kwargs = dict(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=sequence_id,
            sequence_version_id=sequence_version_id,
            current_step_id=current_step_id,
            next_action_time=next_action_time,
        )
        if enrolled_at is not None:
            kwargs["enrolled_at"] = enrolled_at
        enrollment = Enrollment(**kwargs)
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        _ = enrollment.id, enrollment.status, enrollment.enrolled_at
        return enrollment
    finally:
        db.close()


def _fetch_enrollment(enrollment_id):
    """Re-fetch enrollment from DB to get current committed state."""
    db = TestingSessionLocal()
    try:
        row = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if row is None:
            return None
        _ = row.current_step_id, row.next_action_time, row.status
        return row
    finally:
        db.close()


def _add_suppression(firm_id, email: str):
    db = TestingSessionLocal()
    try:
        row = SuppressedEmail(
            firm_id=firm_id,
            email=email.lower().strip(),
            reason="test",
            suppressed_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# GUARD TEST: write-then-send guarantee
#
# This test proves advance_enrollment() is called BEFORE send_nurture_email().
# The watched-fail cycle for this test:
#
#   BREAK: In run_nurture_tick(), swap step 8 and step 9 so send_nurture_email
#          is called BEFORE advance_enrollment().
#   RUN:   pytest tests/test_nurture_execution.py::TestWriteThenSendGuarantee::test_enrollment_advances_even_when_send_raises -v
#   EXPECT RED: AssertionError -- enrollment.current_step_id is still step1.id
#               (the send raised before advance could run, so nothing advanced)
#   RESTORE: git checkout app/services/nurture_execution_service.py
#   RERUN:  confirm GREEN -- enrollment.current_step_id == step2.id even though
#           send raised, because advance happened first.
# ---------------------------------------------------------------------------

class TestWriteThenSendGuarantee:
    def test_enrollment_advances_even_when_send_raises(self, monkeypatch):
        """Enrollment advances to the next step even when send_nurture_email raises.

        The send is wrapped in try/except inside run_nurture_tick, so a Postmark
        failure never blocks the advance. The advance must have already committed
        before the send is attempted (write-then-send order).
        """
        firm = _make_firm(f"guard-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        _make_edge(step1.id, step2.id)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=past,
        )

        from app.services import email_service as email_mod

        def _raise(*args, **kwargs):
            raise RuntimeError("simulated Postmark failure")

        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_raise))

        result = run_nurture_tick()

        assert result["checked"] == 1
        assert result["failed_sends"] == 1
        assert result["sent"] == 0

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id, (
            f"Write-then-send guarantee violated: enrollment was NOT advanced despite "
            f"send raising. current_step_id={fetched.current_step_id}, expected {step2.id}. "
            f"This means advance_enrollment() ran AFTER send_nurture_email(), which is wrong."
        )
        assert fetched.next_action_time is None


# ---------------------------------------------------------------------------
# Suppressed lead is skipped
# ---------------------------------------------------------------------------

class TestSuppressionSkip:
    def test_suppressed_lead_is_not_sent_to(self, monkeypatch):
        """An enrollment whose lead email is suppressed is stopped, not sent to."""
        firm = _make_firm(f"suppressed-{uuid.uuid4().hex[:6]}")
        lead_email = f"suppressed-{uuid.uuid4()}@example.com"
        lead = _make_lead(firm.id, email=lead_email)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        _make_edge(step1.id, step2.id)

        _add_suppression(firm.id, lead_email)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=past,
        )

        send_calls = []

        def _record_send(*args, **kwargs):
            send_calls.append((args, kwargs))

        from app.services import email_service as email_mod
        monkeypatch.setattr(
            email_mod.EmailService, "send_nurture_email", staticmethod(_record_send)
        )

        result = run_nurture_tick()

        assert result["suppressed"] == 1
        assert result["sent"] == 0
        assert send_calls == [], "send_nurture_email must not be called for suppressed leads"

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.status == EnrollmentStatus.unsubscribed.value, (
            f"Expected enrollment status=unsubscribed after suppression, got {fetched.status}"
        )
        assert fetched.current_step_id == step1.id, (
            "Suppressed enrollment must not advance its current_step_id"
        )


# ---------------------------------------------------------------------------
# get_due_enrollments timing precision
# ---------------------------------------------------------------------------

class TestDueEnrollmentsTiming:
    def test_past_enrollment_is_returned_future_is_not(self):
        """get_due_enrollments returns past/present next_action_time, not future."""
        firm = _make_firm(f"timing-{uuid.uuid4().hex[:6]}")
        lead_past = _make_lead(firm.id)
        lead_future = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step = _make_step(version.id, "S1")

        now = datetime.now(timezone.utc)
        past = now - timedelta(minutes=5)
        future = now + timedelta(hours=1)

        enr_past = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead_past.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step.id,
            next_action_time=past,
        )
        enr_future = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead_future.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step.id,
            next_action_time=future,
        )

        db = TestingSessionLocal()
        try:
            due = get_due_enrollments(db=db, firm_id=None, now=now)
            due_ids = {e.id for e in due}
        finally:
            db.close()

        assert enr_past.id in due_ids, (
            f"Past enrollment (next_action_time={past}) was not returned as due"
        )
        assert enr_future.id not in due_ids, (
            f"Future enrollment (next_action_time={future}) should not be due yet"
        )

    def test_null_next_action_time_is_never_due(self):
        """Enrollments with next_action_time=None are never returned as due."""
        firm = _make_firm(f"null-nat-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step = _make_step(version.id, "S1")

        enr = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step.id,
            next_action_time=None,
        )

        db = TestingSessionLocal()
        try:
            due = get_due_enrollments(
                db=db, firm_id=None, now=datetime.now(timezone.utc)
            )
            due_ids = {e.id for e in due}
        finally:
            db.close()

        assert enr.id not in due_ids, (
            "Enrollment with next_action_time=None must never appear as due"
        )


# ---------------------------------------------------------------------------
# Tenant isolation for get_due_enrollments
# ---------------------------------------------------------------------------

class TestDueEnrollmentsTenantIsolation:
    def test_firm_id_filter_scopes_to_correct_firm(self):
        """get_due_enrollments with a firm_id never returns another firm's enrollments."""
        firm_a = _make_firm(f"iso-a-{uuid.uuid4().hex[:6]}")
        firm_b = _make_firm(f"iso-b-{uuid.uuid4().hex[:6]}")

        lead_a = _make_lead(firm_a.id)
        lead_b = _make_lead(firm_b.id)

        seq_a, ver_a = _make_sequence_and_version(firm_a.id)
        seq_b, ver_b = _make_sequence_and_version(firm_b.id)

        step_a = _make_step(ver_a.id, "S1")
        step_b = _make_step(ver_b.id, "S1")

        past = datetime.now(timezone.utc) - timedelta(hours=1)

        enr_a = _make_enrollment(
            firm_id=firm_a.id,
            lead_id=lead_a.id,
            sequence_id=seq_a.id,
            sequence_version_id=ver_a.id,
            current_step_id=step_a.id,
            next_action_time=past,
        )
        enr_b = _make_enrollment(
            firm_id=firm_b.id,
            lead_id=lead_b.id,
            sequence_id=seq_b.id,
            sequence_version_id=ver_b.id,
            current_step_id=step_b.id,
            next_action_time=past,
        )

        db = TestingSessionLocal()
        try:
            due_a = get_due_enrollments(
                db=db, firm_id=firm_a.id, now=datetime.now(timezone.utc)
            )
            due_a_ids = {e.id for e in due_a}

            due_b = get_due_enrollments(
                db=db, firm_id=firm_b.id, now=datetime.now(timezone.utc)
            )
            due_b_ids = {e.id for e in due_b}
        finally:
            db.close()

        assert enr_a.id in due_a_ids, "Firm A enrollment must appear in Firm A's due list"
        assert enr_b.id not in due_a_ids, (
            "Tenant isolation breach: Firm B enrollment appeared in Firm A's due list"
        )

        assert enr_b.id in due_b_ids, "Firm B enrollment must appear in Firm B's due list"
        assert enr_a.id not in due_b_ids, (
            "Tenant isolation breach: Firm A enrollment appeared in Firm B's due list"
        )


# ---------------------------------------------------------------------------
# Task 2 helpers
# ---------------------------------------------------------------------------

def _make_edge_with_loop_cap(from_step_id, to_step_id, loop_cap: int) -> StepEdge:
    db = TestingSessionLocal()
    try:
        edge = StepEdge(
            from_step_id=from_step_id,
            to_step_id=to_step_id,
            loop_cap=loop_cap,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
        _ = edge.id, edge.loop_cap
        return edge
    finally:
        db.close()


def _make_step_with_phase(version_id, step_key: str, phase: str, config: dict = None) -> Step:
    db = TestingSessionLocal()
    try:
        step = Step(
            sequence_version_id=version_id,
            step_key=step_key,
            step_type=StepType.email.value,
            channel="email",
            phase=phase,
            config=config or {"subject": "Test Subject", "body": "<p>Test body</p>"},
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        _ = step.id, step.phase
        return step
    finally:
        db.close()


def _make_goal(
    sequence_version_id,
    goal_event: str,
    target_step_id,
    applies_to_phase: str = None,
) -> SequenceGoal:
    db = TestingSessionLocal()
    try:
        goal = SequenceGoal(
            sequence_version_id=sequence_version_id,
            goal_event=goal_event,
            target_step_id=target_step_id,
            applies_to_phase=applies_to_phase,
        )
        db.add(goal)
        db.commit()
        db.refresh(goal)
        _ = goal.id, goal.goal_event
        return goal
    finally:
        db.close()


def _make_behavioral_event(
    firm_id,
    lead_id,
    event_type: str,
    occurred_at: datetime,
) -> BehavioralEvent:
    db = TestingSessionLocal()
    try:
        event = BehavioralEvent(
            firm_id=firm_id,
            event_type=event_type,
            entity_type="lead",
            entity_id=lead_id,
            occurred_at=occurred_at,
        )
        db.add(event)
        db.commit()
        db.refresh(event)
        _ = event.event_id, event.event_type
        return event
    finally:
        db.close()


def _set_next_action_time(enrollment_id, new_time: datetime):
    """Reset an enrollment's next_action_time so it is picked up on the next tick."""
    db = TestingSessionLocal()
    try:
        row = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if row is not None:
            row.next_action_time = new_time
            db.commit()
    finally:
        db.close()


def _fetch_loop_counts(enrollment_id) -> dict:
    db = TestingSessionLocal()
    try:
        row = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        if row is None:
            return {}
        counts = dict(row.loop_counts) if row.loop_counts else {}
        return counts
    finally:
        db.close()


def _noop_send(*args, **kwargs):
    pass


# ---------------------------------------------------------------------------
# GUARD TEST: loop_counts enforcement
#
# This test proves the loop_cap check refuses to advance an enrollment past
# its cap. The watched-fail cycle:
#
#   BREAK: In run_nurture_tick(), comment out the block:
#            if current_count >= edge.loop_cap:
#                logger.warning(...)
#                loop_capped += 1
#                continue
#          so that a capped edge is always followed regardless of count.
#   RUN:   pytest tests/test_nurture_execution.py::TestLoopCapEnforcement::test_loop_cap_is_enforced -v
#   EXPECT RED: AssertionError -- enrollment.current_step_id == step1.id
#               (it advanced from step2 to step1 past the cap, should have stayed at step2)
#   RESTORE: un-comment the cap block
#   RERUN:  confirm GREEN -- enrollment stays at step2, loop_capped == 1
# ---------------------------------------------------------------------------

class TestLoopCapEnforcement:
    def test_loop_cap_is_enforced(self, monkeypatch):
        """Enrollment does not follow a loop-back edge once loop_cap is reached.

        Graph: step1 --edge_fwd--> step2 --edge_loop(cap=1)--> step1

        Tick 1: at step1, follows edge_fwd (no cap) to step2.
        Tick 2: at step2, edge_loop count=0 < cap=1, follows, count becomes 1.
        Tick 3: at step1, follows edge_fwd to step2.
        Tick 4: at step2, edge_loop count=1 >= cap=1, refuses. loop_capped=1.
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"loop-cap-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        edge_fwd = _make_edge(step1.id, step2.id)
        edge_loop = _make_edge_with_loop_cap(step2.id, step1.id, loop_cap=1)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=past,
        )

        # Tick 1: step1 -> step2 via edge_fwd (no cap)
        result1 = run_nurture_tick()
        assert result1["checked"] == 1
        assert result1["loop_capped"] == 0
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id

        # Tick 2: step2 -> step1 via edge_loop, count=0 < 1, follows. count becomes 1.
        _set_next_action_time(enrollment.id, past)
        result2 = run_nurture_tick()
        assert result2["checked"] == 1
        assert result2["loop_capped"] == 0
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step1.id
        counts_after_tick2 = _fetch_loop_counts(enrollment.id)
        assert counts_after_tick2.get(str(edge_loop.id), 0) == 1, (
            f"Expected loop_counts[str(edge_loop.id)]=1 after tick 2, got {counts_after_tick2}"
        )

        # Tick 3: step1 -> step2 via edge_fwd (no cap)
        _set_next_action_time(enrollment.id, past)
        run_nurture_tick()
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id

        # Tick 4: step2 tries edge_loop, count=1 >= cap=1, REFUSES.
        _set_next_action_time(enrollment.id, past)
        result4 = run_nurture_tick()
        assert result4["checked"] == 1
        assert result4["loop_capped"] == 1, (
            f"Expected loop_capped=1 at cap, got {result4['loop_capped']}"
        )
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id, (
            f"Enrollment should stay at step2 when cap reached. Got {fetched.current_step_id!r}"
        )

    def test_loop_counts_increments_across_multiple_ticks(self, monkeypatch):
        """loop_counts for an edge increments with each allowed loop traversal.

        With cap=3, three traversals are allowed. After three, the fourth is refused.
        This test confirms the count accumulates correctly across real tick calls,
        not just within one.
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"loop-count-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        edge_fwd = _make_edge(step1.id, step2.id)
        edge_loop = _make_edge_with_loop_cap(step2.id, step1.id, loop_cap=3)

        past = datetime.now(timezone.utc) - timedelta(hours=1)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=past,
        )

        # Run 3 full loops (each loop = tick from step1 + tick from step2)
        for expected_count in range(1, 4):
            # From step1: advance to step2
            _set_next_action_time(enrollment.id, past)
            run_nurture_tick()
            fetched = _fetch_enrollment(enrollment.id)
            assert fetched.current_step_id == step2.id

            # From step2: loop back to step1 (count goes up by 1)
            _set_next_action_time(enrollment.id, past)
            result = run_nurture_tick()
            assert result["loop_capped"] == 0, (
                f"Loop should not be capped yet (expected_count={expected_count})"
            )
            fetched = _fetch_enrollment(enrollment.id)
            assert fetched.current_step_id == step1.id
            counts = _fetch_loop_counts(enrollment.id)
            assert counts.get(str(edge_loop.id), 0) == expected_count, (
                f"Expected count={expected_count}, got {counts}"
            )

        # 4th attempt from step2: should be capped
        _set_next_action_time(enrollment.id, past)
        run_nurture_tick()
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id

        _set_next_action_time(enrollment.id, past)
        result_capped = run_nurture_tick()
        assert result_capped["loop_capped"] == 1
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id, (
            "Enrollment must stay at step2 when loop cap is reached"
        )


# ---------------------------------------------------------------------------
# SequenceGoal jumps
# ---------------------------------------------------------------------------

class TestSequenceGoalJumps:
    def test_goal_event_fires_jump_to_target_step(self, monkeypatch):
        """A matching BehavioralEvent triggers a direct jump to the goal's target_step.

        The jump replaces the normal linear advance. No email is sent on the
        goal-jump tick; the enrollment is simply repositioned.
        """
        from app.services import email_service as email_mod
        send_calls = []
        monkeypatch.setattr(
            email_mod.EmailService, "send_nurture_email",
            staticmethod(lambda *a, **kw: send_calls.append((a, kw)))
        )

        firm = _make_firm(f"goal-jump-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        step_target = _make_step(version.id, "TARGET")
        _make_edge(step1.id, step2.id)
        _make_goal(version.id, "lead.call_booked", step_target.id)

        now = datetime.now(timezone.utc)
        enrolled_at = now - timedelta(hours=2)
        event_time = now - timedelta(hours=1)  # after enrolled_at

        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=now - timedelta(minutes=5),
            enrolled_at=enrolled_at,
        )

        _make_behavioral_event(
            firm_id=firm.id,
            lead_id=lead.id,
            event_type="lead.call_booked",
            occurred_at=event_time,
        )

        result = run_nurture_tick()

        assert result["goal_jumps"] == 1, (
            f"Expected goal_jumps=1, got {result['goal_jumps']}"
        )
        assert result["sent"] == 0, "No email should be sent on a goal-jump tick"
        assert send_calls == [], "send_nurture_email must not be called on a goal-jump tick"

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step_target.id, (
            f"Enrollment must jump to target step. Got {fetched.current_step_id!r}, "
            f"expected {step_target.id!r}"
        )

    def test_goal_event_before_enrolled_at_does_not_trigger(self, monkeypatch):
        """A BehavioralEvent that fired before enrolled_at is ignored by goal detection.

        The timing anchor is enrollment.enrolled_at: only events at or after that
        time count. A pre-enrollment event must not redirect the sequence.
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"goal-pre-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)
        step1 = _make_step(version.id, "S1")
        step2 = _make_step(version.id, "S2")
        step_target = _make_step(version.id, "TARGET")
        _make_edge(step1.id, step2.id)
        _make_goal(version.id, "lead.call_booked", step_target.id)

        now = datetime.now(timezone.utc)
        enrolled_at = now - timedelta(hours=2)
        past = now - timedelta(minutes=5)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step1.id,
            next_action_time=past,
            enrolled_at=enrolled_at,
        )

        # Event fired BEFORE enrolled_at -- must not trigger the goal.
        pre_enrollment_time = now - timedelta(hours=10)
        _make_behavioral_event(
            firm_id=firm.id,
            lead_id=lead.id,
            event_type="lead.call_booked",
            occurred_at=pre_enrollment_time,
        )

        result = run_nurture_tick()

        assert result["goal_jumps"] == 0, (
            f"Expected goal_jumps=0 for pre-enrollment event, got {result['goal_jumps']}"
        )
        # Should have followed the normal linear advance to step2
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step2.id, (
            f"Enrollment should advance normally when goal event is pre-enrollment. "
            f"Got {fetched.current_step_id!r}"
        )

    def test_goal_with_applies_to_phase_only_triggers_on_matching_phase(self, monkeypatch):
        """A SequenceGoal with applies_to_phase only fires when the current step's phase matches.

        If the current step is in a different phase, the goal is ignored and
        the enrollment advances normally.
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"goal-phase-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)

        # Step in "intro" phase, followed by a step in "followup" phase
        step_intro = _make_step_with_phase(version.id, "INTRO", phase="intro")
        step_followup = _make_step_with_phase(version.id, "FOLLOWUP", phase="followup")
        step_target = _make_step(version.id, "TARGET")
        _make_edge(step_intro.id, step_followup.id)
        # Goal only applies in "followup" phase
        _make_goal(version.id, "lead.call_booked", step_target.id, applies_to_phase="followup")

        now = datetime.now(timezone.utc)
        enrolled_at = now - timedelta(hours=2)
        past = now - timedelta(minutes=5)
        event_time = now - timedelta(hours=1)  # after enrolled_at

        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=step_intro.id,
            next_action_time=past,
            enrolled_at=enrolled_at,
        )

        _make_behavioral_event(
            firm_id=firm.id,
            lead_id=lead.id,
            event_type="lead.call_booked",
            occurred_at=event_time,
        )

        # Tick 1: current step is "intro" phase. Goal applies_to_phase="followup" -- no match.
        result1 = run_nurture_tick()
        assert result1["goal_jumps"] == 0, (
            f"Goal must not fire when step phase does not match applies_to_phase. "
            f"Got goal_jumps={result1['goal_jumps']}"
        )
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step_followup.id, (
            "Enrollment must advance normally when goal phase does not match"
        )

        # Tick 2: current step is now "followup" phase. Goal applies_to_phase="followup" -- match.
        _set_next_action_time(enrollment.id, past)
        result2 = run_nurture_tick()
        assert result2["goal_jumps"] == 1, (
            f"Goal must fire when step phase matches applies_to_phase. "
            f"Got goal_jumps={result2['goal_jumps']}"
        )
        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == step_target.id, (
            f"Enrollment must jump to target step when phase matches. Got {fetched.current_step_id!r}"
        )


# ---------------------------------------------------------------------------
# Task 3 helpers -- wait_fixed / wait_until_event
# ---------------------------------------------------------------------------

def _make_wait_step(version_id, step_key: str, step_type: str, config: dict) -> Step:
    """Create a wait_fixed or wait_until_event Step."""
    db = TestingSessionLocal()
    try:
        step = Step(
            sequence_version_id=version_id,
            step_key=step_key,
            step_type=step_type,
            channel="email",
            config=config,
        )
        db.add(step)
        db.commit()
        db.refresh(step)
        _ = step.id, step.step_type, step.config
        return step
    finally:
        db.close()


def _make_labeled_edge(from_step_id, to_step_id, condition_label: str) -> StepEdge:
    """Create a StepEdge with a condition_label."""
    db = TestingSessionLocal()
    try:
        edge = StepEdge(
            from_step_id=from_step_id,
            to_step_id=to_step_id,
            condition_label=condition_label,
        )
        db.add(edge)
        db.commit()
        db.refresh(edge)
        _ = edge.id, edge.condition_label
        return edge
    finally:
        db.close()


def _make_lead_message(
    firm_id,
    lead_id,
    source: str,
    created_at: datetime,
) -> LeadMessage:
    """Create a LeadMessage record with a specific source and timestamp.

    sender_role is always "lead" here -- inbound messages originate from the lead.
    """
    db = TestingSessionLocal()
    try:
        msg = LeadMessage(
            firm_id=firm_id,
            lead_id=lead_id,
            sender_role="lead",
            body="Test reply body",
            source=source,
            created_at=created_at,
        )
        db.add(msg)
        db.commit()
        db.refresh(msg)
        _ = msg.id, msg.source, msg.created_at
        return msg
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TestWaitFixed
# ---------------------------------------------------------------------------

class TestWaitFixed:
    """Tests for wait_fixed step type in the nurture tick loop.

    Covers:
    - When an enrollment advances INTO a wait_fixed step, next_action_time is
      set to now + duration_seconds in the same write (not left null).
    - An enrollment AT a wait_fixed step with a future next_action_time is not
      picked up by the tick until the timer has elapsed.
    """

    def test_next_action_time_set_when_enrollment_arrives_at_wait_fixed(self, monkeypatch):
        """Advancing into a wait_fixed step sets next_action_time to now + duration_seconds.

        Setup: email step -> wait_fixed (60 s). Enroll at entry (no current_step_id),
        run tick. The tick sends the email and advances to the wait_fixed step.
        The resulting next_action_time must be approximately now + 60 seconds.
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"wf-arrival-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)

        email_step = _make_step(version.id, "EMAIL_1")
        wait_step = _make_wait_step(
            version.id, "WAIT_60",
            step_type=StepType.wait_fixed.value,
            config={"duration_seconds": 60},
        )
        _make_edge(email_step.id, wait_step.id)

        now = datetime.now(timezone.utc)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=None,
            next_action_time=now - timedelta(minutes=5),
        )

        before_tick = datetime.now(timezone.utc)
        run_nurture_tick()
        after_tick = datetime.now(timezone.utc)

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == wait_step.id, (
            f"Enrollment must advance to the wait_fixed step after the email tick. "
            f"Got {fetched.current_step_id!r}"
        )
        assert fetched.next_action_time is not None, (
            "next_action_time must be set (not null) when arriving at a wait_fixed step"
        )
        earliest = before_tick + timedelta(seconds=60)
        latest = after_tick + timedelta(seconds=60)
        assert earliest <= fetched.next_action_time <= latest, (
            f"next_action_time must be now + 60 s (expected between {earliest} and {latest}). "
            f"Got {fetched.next_action_time!r}"
        )

    def test_wait_fixed_enrollment_not_advanced_before_timer_elapses(self, monkeypatch):
        """An enrollment at a wait_fixed step with a future next_action_time is not processed.

        The tick must not advance the enrollment until next_action_time <= now.
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"wf-early-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)

        wait_step = _make_wait_step(
            version.id, "WAIT_3600",
            step_type=StepType.wait_fixed.value,
            config={"duration_seconds": 3600},
        )
        next_email = _make_step(version.id, "NEXT_EMAIL")
        _make_edge(wait_step.id, next_email.id)

        now = datetime.now(timezone.utc)
        future_deadline = now + timedelta(seconds=3600)
        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=wait_step.id,
            next_action_time=future_deadline,
        )

        run_nurture_tick()

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == wait_step.id, (
            "Enrollment must remain at the wait_fixed step when the timer has not elapsed"
        )
        assert fetched.next_action_time == future_deadline, (
            "next_action_time must not change when the enrollment is not yet due"
        )


# ---------------------------------------------------------------------------
# TestWaitUntilEvent
# ---------------------------------------------------------------------------

class TestWaitUntilEvent:
    """Tests for wait_until_event step type in the nurture tick loop.

    GUARD TEST: test_reply_present_follows_replied_edge_not_timeout
    Watched-fail cycle: temporarily forces the code to always pick the timeout
    edge, confirms the test is red when a real reply exists, then restores
    and confirms green. See class docstring of TestWriteThenSendGuarantee for
    the guard-test pattern used in this file.
    """

    def test_reply_present_follows_replied_edge_not_timeout(self, monkeypatch):
        """A LeadMessage present after arrival but before the deadline resolves the wait
        via the 'replied' edge, not the 'timeout' edge.

        GUARD TEST -- see watched-fail cycle in test run report.

        Timeline:
          arrival_time = now - 120 s
          timeout      = 60 s
          deadline     = arrival_time + 60 s  =  now - 60 s  (past, so enrollment is due)
          reply        = arrival_time + 30 s  =  now - 90 s  (after arrival, before deadline)
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"wue-reply-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)

        timeout_seconds = 60
        now = datetime.now(timezone.utc)
        arrival_time = now - timedelta(seconds=120)
        deadline = arrival_time + timedelta(seconds=timeout_seconds)  # now - 60 s

        wait_step = _make_wait_step(
            version.id, "WAIT_EVENT",
            step_type=StepType.wait_until_event.value,
            config={"event": "lead.email_replied", "timeout_seconds": timeout_seconds},
        )
        replied_step = _make_step(version.id, "REPLIED_BRANCH")
        timeout_step = _make_step(version.id, "TIMEOUT_BRANCH")
        _make_labeled_edge(wait_step.id, replied_step.id, "replied")
        _make_labeled_edge(wait_step.id, timeout_step.id, "timeout")

        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=wait_step.id,
            next_action_time=deadline,
        )

        # Reply arrived 30 s after the enrollment landed at this step (before deadline).
        _make_lead_message(
            firm_id=firm.id,
            lead_id=lead.id,
            source="inbound_email",
            created_at=arrival_time + timedelta(seconds=30),
        )

        result = run_nurture_tick()

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == replied_step.id, (
            f"A reply present after arrival must resolve via the 'replied' edge. "
            f"Got {fetched.current_step_id!r} (timeout_step.id={timeout_step.id!r})"
        )
        assert result["timeouts_fired"] == 0, (
            f"timeouts_fired must be 0 when the reply edge is taken. "
            f"Got {result['timeouts_fired']}"
        )

    def test_no_reply_deadline_passed_follows_timeout_edge(self, monkeypatch):
        """When no reply has arrived and the deadline has passed, the timeout edge is taken.

        Timeline:
          arrival_time = now - 120 s
          timeout      = 60 s
          deadline     = now - 60 s  (past, enrollment is due)
          no LeadMessage
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"wue-timeout-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)

        timeout_seconds = 60
        now = datetime.now(timezone.utc)
        arrival_time = now - timedelta(seconds=120)
        deadline = arrival_time + timedelta(seconds=timeout_seconds)

        wait_step = _make_wait_step(
            version.id, "WAIT_EVENT",
            step_type=StepType.wait_until_event.value,
            config={"event": "lead.email_replied", "timeout_seconds": timeout_seconds},
        )
        replied_step = _make_step(version.id, "REPLIED_BRANCH")
        timeout_step = _make_step(version.id, "TIMEOUT_BRANCH")
        _make_labeled_edge(wait_step.id, replied_step.id, "replied")
        _make_labeled_edge(wait_step.id, timeout_step.id, "timeout")

        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=wait_step.id,
            next_action_time=deadline,
        )

        # No LeadMessage created.

        result = run_nurture_tick()

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == timeout_step.id, (
            f"No reply present must resolve via the 'timeout' edge. "
            f"Got {fetched.current_step_id!r}"
        )
        assert result["timeouts_fired"] >= 1, (
            f"timeouts_fired must be incremented when the timeout edge is taken. "
            f"Got {result['timeouts_fired']}"
        )

    def test_reply_before_deadline_resolves_even_on_late_tick(self, monkeypatch):
        """A reply that arrived before the deadline resolves the wait via 'replied',
        even when the tick runs well after the deadline (early-resolution case).

        Timeline:
          arrival_time = now - 180 s
          timeout      = 60 s
          deadline     = arrival_time + 60 s  =  now - 120 s  (well past)
          reply        = arrival_time + 20 s  =  now - 160 s  (after arrival, before deadline)
          tick runs now (60 s after deadline)
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"wue-early-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)

        timeout_seconds = 60
        now = datetime.now(timezone.utc)
        arrival_time = now - timedelta(seconds=180)
        deadline = arrival_time + timedelta(seconds=timeout_seconds)  # now - 120 s

        wait_step = _make_wait_step(
            version.id, "WAIT_EVENT",
            step_type=StepType.wait_until_event.value,
            config={"event": "lead.email_replied", "timeout_seconds": timeout_seconds},
        )
        replied_step = _make_step(version.id, "REPLIED_BRANCH")
        timeout_step = _make_step(version.id, "TIMEOUT_BRANCH")
        _make_labeled_edge(wait_step.id, replied_step.id, "replied")
        _make_labeled_edge(wait_step.id, timeout_step.id, "timeout")

        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=wait_step.id,
            next_action_time=deadline,
        )

        # Reply arrived 20 s after enrollment landed here -- before the 60 s deadline.
        _make_lead_message(
            firm_id=firm.id,
            lead_id=lead.id,
            source="inbound_email",
            created_at=arrival_time + timedelta(seconds=20),
        )

        result = run_nurture_tick()

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == replied_step.id, (
            f"A reply before the deadline must resolve via 'replied' even when the tick "
            f"runs well after the deadline. Got {fetched.current_step_id!r}"
        )
        assert result["timeouts_fired"] == 0, (
            f"timeouts_fired must be 0 when reply edge is taken. Got {result['timeouts_fired']}"
        )

    def test_stale_reply_before_arrival_does_not_resolve_wait(self, monkeypatch):
        """A LeadMessage created before the enrollment arrived at this step is stale
        and must not count as a reply for this step.

        The enrollment must follow the 'timeout' edge despite a LeadMessage existing.

        Timeline:
          arrival_time = now - 120 s
          timeout      = 60 s
          deadline     = now - 60 s  (past, enrollment is due)
          stale reply  = arrival_time - 30 s  =  now - 150 s  (before arrival -- stale)
        """
        from app.services import email_service as email_mod
        monkeypatch.setattr(email_mod.EmailService, "send_nurture_email", staticmethod(_noop_send))

        firm = _make_firm(f"wue-stale-{uuid.uuid4().hex[:6]}")
        lead = _make_lead(firm.id)
        sequence, version = _make_sequence_and_version(firm.id)

        timeout_seconds = 60
        now = datetime.now(timezone.utc)
        arrival_time = now - timedelta(seconds=120)
        deadline = arrival_time + timedelta(seconds=timeout_seconds)

        wait_step = _make_wait_step(
            version.id, "WAIT_EVENT",
            step_type=StepType.wait_until_event.value,
            config={"event": "lead.email_replied", "timeout_seconds": timeout_seconds},
        )
        replied_step = _make_step(version.id, "REPLIED_BRANCH")
        timeout_step = _make_step(version.id, "TIMEOUT_BRANCH")
        _make_labeled_edge(wait_step.id, replied_step.id, "replied")
        _make_labeled_edge(wait_step.id, timeout_step.id, "timeout")

        enrollment = _make_enrollment(
            firm_id=firm.id,
            lead_id=lead.id,
            sequence_id=sequence.id,
            sequence_version_id=version.id,
            current_step_id=wait_step.id,
            next_action_time=deadline,
        )

        # Reply is from 30 s BEFORE the enrollment arrived at this step -- stale.
        _make_lead_message(
            firm_id=firm.id,
            lead_id=lead.id,
            source="inbound_email",
            created_at=arrival_time - timedelta(seconds=30),
        )

        result = run_nurture_tick()

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.current_step_id == timeout_step.id, (
            f"A LeadMessage created before arrival must not resolve the wait. "
            f"Expected timeout_step ({timeout_step.id!r}), got {fetched.current_step_id!r}"
        )
        assert result["timeouts_fired"] >= 1, (
            f"timeouts_fired must be incremented for a stale-reply timeout. "
            f"Got {result['timeouts_fired']}"
        )
