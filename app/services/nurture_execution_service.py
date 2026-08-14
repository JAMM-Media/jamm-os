# app/services/nurture_execution_service.py
"""
Nurture engine tick: walks active Enrollments forward one step.

SCOPE (TASK 2 OF 2 ADDITIONS):
- SequenceGoal jumps: if a behavioral event matching a goal has fired for the
  enrollment's lead since enrollment, advance directly to the goal's target_step
  instead of the normal next step.
- loop_counts enforcement: edges with loop_cap set are only followed if the
  enrollment's count for that specific edge (keyed by str(edge.id)) is below
  the cap. At cap, the enrollment is logged and not advanced.
- Branch evaluation on condition_label and wait/timeout mechanisms remain
  deferred pending a design decision.

STEP CONFIG SHAPE:
Step.config is expected to contain {"subject": str, "body": str}. This shape
is INFERRED from the contract and not yet confirmed from a real sequence-builder
output -- no code in the codebase currently constructs a Step row with a config
dict. Verify against whatever the sequence-builder UI produces before sending
real mail.

WRITE-THEN-SEND GUARANTEE:
advance_enrollment() is always called BEFORE EmailService.send_nurture_email().
A process crash after the write produces a missed email, never a duplicate.
This ordering is deliberate: a duplicate email to a real prospect is more
damaging than one silently skipped message. Do not reverse it.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import exists

from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.firm import Firm
from app.models.sequence import Step, StepEdge, SequenceGoal
from app.models.behavioral_event import BehavioralEvent
from app.core.enums import StepType
from app.crud import enrollment as crud_enrollment
from app.crud import lead_message as crud_lead_message
from app.crud.suppressed_email import is_suppressed
from app.services.email_service import EmailService, build_lead_reply_to

logger = logging.getLogger(__name__)


def _find_entry_step(db, sequence_version_id) -> Step | None:
    """Return the Step in this version that has no incoming StepEdge.

    If zero or multiple such steps exist the graph is malformed; returns None
    and the caller skips the enrollment.
    """
    candidates = (
        db.query(Step)
        .filter(
            Step.sequence_version_id == sequence_version_id,
            ~exists().where(StepEdge.to_step_id == Step.id),
        )
        .all()
    )
    if len(candidates) == 1:
        return candidates[0]
    logger.warning(
        "nurture_tick: sequence_version_id=%s has %d entry-step candidates (expected 1), skipping",
        sequence_version_id,
        len(candidates),
    )
    return None


def _check_goal_jump(db, enrollment, current_step) -> "uuid.UUID | None":
    """Return a target_step_id if a SequenceGoal fires for this enrollment, else None.

    A goal fires when a matching BehavioralEvent exists with occurred_at at or
    after enrollment.enrolled_at. If applies_to_phase is set on the goal, the
    current step's phase must match.
    """
    goals = (
        db.query(SequenceGoal)
        .filter(SequenceGoal.sequence_version_id == enrollment.sequence_version_id)
        .all()
    )
    for goal in goals:
        if goal.applies_to_phase is not None and current_step.phase != goal.applies_to_phase:
            continue
        matching = (
            db.query(BehavioralEvent)
            .filter(
                BehavioralEvent.event_type == goal.goal_event,
                BehavioralEvent.entity_type == "lead",
                BehavioralEvent.entity_id == enrollment.lead_id,
                BehavioralEvent.occurred_at >= enrollment.enrolled_at,
            )
            .first()
        )
        if matching is not None:
            return goal.target_step_id
    return None


def run_nurture_tick() -> dict:
    """Walk all due active Enrollments forward one email step.

    Creates its own DB session in a try/finally block, following the
    deadline_scheduler.py pattern. Never accepts or reuses a request session.

    Returns a summary dict:
      {
        "checked": N,
        "sent": N,
        "suppressed": N,
        "skipped_branching": N,
        "failed_sends": N,
        "goal_jumps": N,
        "loop_capped": N,
      }
    """
    import uuid as _uuid_mod

    db = SessionLocal()
    checked = sent = suppressed = skipped_branching = failed_sends = 0
    goal_jumps = loop_capped = 0

    try:
        now = datetime.now(timezone.utc)
        enrollments = crud_enrollment.get_due_enrollments(db=db, firm_id=None, now=now)

        for enrollment in enrollments:
            checked += 1

            # 1. Load lead; verify it has an email address.
            lead = db.query(Lead).filter(Lead.id == enrollment.lead_id).first()
            if lead is None or not lead.email:
                logger.warning(
                    "nurture_tick: enrollment=%s -- lead missing or has no email, skipping",
                    enrollment.id,
                )
                skipped_branching += 1
                continue

            # 2. Suppression check before doing any work.
            if is_suppressed(db=db, firm_id=enrollment.firm_id, email=lead.email):
                logger.info(
                    "nurture_tick: enrollment=%s lead=%s email suppressed, stopping enrollment",
                    enrollment.id,
                    lead.id,
                )
                crud_enrollment.mark_enrollment_suppressed(
                    db=db, enrollment_id=enrollment.id
                )
                suppressed += 1
                continue

            # 3. Resolve the current Step.
            if enrollment.current_step_id is None:
                current_step = _find_entry_step(db, enrollment.sequence_version_id)
            else:
                current_step = (
                    db.query(Step)
                    .filter(Step.id == enrollment.current_step_id)
                    .first()
                )

            if current_step is None:
                logger.warning(
                    "nurture_tick: enrollment=%s -- cannot resolve current step, skipping",
                    enrollment.id,
                )
                skipped_branching += 1
                continue

            # 4. SequenceGoal check -- before normal advance, see if a goal event
            # has fired for this lead. If so, jump directly to the goal target.
            # Write-then-send ordering: advance first, no email send on goal ticks.
            goal_target_step_id = _check_goal_jump(db, enrollment, current_step)
            if goal_target_step_id is not None:
                crud_enrollment.advance_enrollment(
                    db=db,
                    enrollment_id=enrollment.id,
                    new_current_step_id=goal_target_step_id,
                    new_next_action_time=None,
                )
                goal_jumps += 1
                logger.info(
                    "nurture_tick: goal jump -- enrollment=%s lead=%s target_step=%s",
                    enrollment.id,
                    lead.id,
                    goal_target_step_id,
                )
                continue

            # 5. Only email-type Steps are processed.
            if current_step.step_type != StepType.email.value:
                logger.info(
                    "nurture_tick: enrollment=%s step=%s type=%s is not email, skipping",
                    enrollment.id,
                    current_step.id,
                    current_step.step_type,
                )
                skipped_branching += 1
                continue

            # 6. Determine next step -- must be exactly one outgoing edge.
            edges = (
                db.query(StepEdge)
                .filter(StepEdge.from_step_id == current_step.id)
                .all()
            )
            if len(edges) > 1:
                logger.warning(
                    "nurture_tick: enrollment=%s step=%s has %d outgoing edges (branching deferred), skipping",
                    enrollment.id,
                    current_step.id,
                    len(edges),
                )
                skipped_branching += 1
                continue

            next_step_id = None
            updated_loop_counts = None

            if edges:
                edge = edges[0]
                # 6a. loop_cap enforcement: only apply when edge.loop_cap is not null.
                # Key is str(edge.id) -- uniquely identifies this back-edge.
                if edge.loop_cap is not None:
                    current_count = enrollment.loop_counts.get(str(edge.id), 0)
                    if current_count >= edge.loop_cap:
                        logger.warning(
                            "nurture_tick: loop cap reached -- enrollment=%s edge=%s cap=%d count=%d",
                            enrollment.id,
                            edge.id,
                            edge.loop_cap,
                            current_count,
                        )
                        loop_capped += 1
                        continue
                    # Within cap: record the incremented count for the advance write.
                    updated_loop_counts = {**enrollment.loop_counts, str(edge.id): current_count + 1}
                next_step_id = edge.to_step_id

            # 7. Render content from step config.
            # Shape {"subject": str, "body": str} is inferred -- see module docstring.
            config = current_step.config or {}
            subject = config.get("subject", "")
            body = config.get("body", "")

            # 8. Look up firm for sending identity.
            firm = db.query(Firm).filter(Firm.id == enrollment.firm_id).first()
            from_name = firm.name if firm else "JAMM PX"
            sending_domain = (
                firm.sending_domain
                if firm and firm.sending_domain_verified
                else None
            )

            # 9. WRITE FIRST -- advance enrollment before any send attempt.
            # This is the write-then-send guarantee. Do not move this below the
            # send call for any reason, including error-handling convenience.
            crud_enrollment.advance_enrollment(
                db=db,
                enrollment_id=enrollment.id,
                new_current_step_id=next_step_id,
                new_next_action_time=None,
                new_loop_counts=updated_loop_counts,
            )

            # 10. Send the email. Failure here is fire-and-forget: the enrollment
            # is already advanced regardless of send outcome.
            reply_to = build_lead_reply_to(str(lead.id))
            try:
                EmailService.send_nurture_email(
                    to_email=lead.email,
                    subject=subject,
                    html_body=body,
                    from_name=from_name,
                    reply_to=reply_to,
                    sending_domain=sending_domain,
                )
                crud_lead_message.create_lead_message(
                    db=db,
                    firm_id=enrollment.firm_id,
                    lead_id=enrollment.lead_id,
                    body=body,
                    source="nurture_email",
                )
                sent += 1
                logger.info(
                    "nurture_tick: sent -- enrollment=%s lead=%s step=%s",
                    enrollment.id,
                    lead.id,
                    current_step.id,
                )
            except Exception as exc:
                failed_sends += 1
                logger.error(
                    "nurture_tick: send failed -- enrollment=%s lead=%s step=%s error=%s",
                    enrollment.id,
                    lead.id,
                    current_step.id,
                    exc,
                )

    finally:
        db.close()

    return {
        "checked": checked,
        "sent": sent,
        "suppressed": suppressed,
        "skipped_branching": skipped_branching,
        "failed_sends": failed_sends,
        "goal_jumps": goal_jumps,
        "loop_capped": loop_capped,
    }
