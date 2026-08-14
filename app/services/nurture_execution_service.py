# app/services/nurture_execution_service.py
"""
Nurture engine tick: walks active Enrollments one linear step forward.

SCOPE (TASK 1 OF 2):
- Processes only email-type Steps.
- Advances enrollments with exactly one outgoing StepEdge (linear path only).
- Does not handle branching, wait_fixed timing, wait_until_event, loop caps,
  or SequenceGoal jumps -- those are reserved for Task 2.

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
from app.models.sequence import Step, StepEdge
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


def run_nurture_tick() -> dict:
    """Walk all due active Enrollments forward one linear email step.

    Creates its own DB session in a try/finally block, following the
    deadline_scheduler.py pattern. Never accepts or reuses a request session.

    Returns a summary dict matching deadline_scheduler.py's return convention:
      {
        "checked": N,
        "sent": N,
        "suppressed": N,
        "skipped_branching": N,
        "failed_sends": N,
      }
    """
    db = SessionLocal()
    checked = sent = suppressed = skipped_branching = failed_sends = 0

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

            # 4. Only email-type Steps are processed in Task 1.
            if current_step.step_type != StepType.email.value:
                logger.info(
                    "nurture_tick: enrollment=%s step=%s type=%s is not email (out of scope for task 1), skipping",
                    enrollment.id,
                    current_step.id,
                    current_step.step_type,
                )
                skipped_branching += 1
                continue

            # 5. Determine next step -- must be exactly one outgoing edge.
            edges = (
                db.query(StepEdge)
                .filter(StepEdge.from_step_id == current_step.id)
                .all()
            )
            if len(edges) > 1:
                logger.warning(
                    "nurture_tick: enrollment=%s step=%s has %d outgoing edges (branching out of scope for task 1), skipping",
                    enrollment.id,
                    current_step.id,
                    len(edges),
                )
                skipped_branching += 1
                continue

            next_step_id = edges[0].to_step_id if edges else None

            # 6. Render content from step config.
            # Shape {"subject": str, "body": str} is inferred -- see module docstring.
            config = current_step.config or {}
            subject = config.get("subject", "")
            body = config.get("body", "")

            # 7. Look up firm for sending identity.
            firm = db.query(Firm).filter(Firm.id == enrollment.firm_id).first()
            from_name = firm.name if firm else "JAMM PX"
            sending_domain = (
                firm.sending_domain
                if firm and firm.sending_domain_verified
                else None
            )

            # 8. WRITE FIRST -- advance enrollment before any send attempt.
            # This is the write-then-send guarantee. Do not move this below the
            # send call for any reason, including error-handling convenience.
            crud_enrollment.advance_enrollment(
                db=db,
                enrollment_id=enrollment.id,
                new_current_step_id=next_step_id,
                new_next_action_time=None,
            )

            # 9. Send the email. Failure here is fire-and-forget: the enrollment
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
    }
