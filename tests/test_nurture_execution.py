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
        firm = Firm(name=f"Nurture Test Firm {slug}", slug=slug)
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
