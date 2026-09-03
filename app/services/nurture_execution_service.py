# app/services/nurture_execution_service.py
"""
Nurture engine tick: walks active Enrollments forward one step.

SCOPE (TASK 3 ADDITIONS):
- wait_fixed: when the enrollment is at a wait_fixed step and the timer has
  elapsed (next_action_time <= now), advance via its single outgoing edge with
  no email send.
- wait_until_event: when due, check whether the awaited event has occurred by
  reading LeadMessage (source=inbound_email) for replies. If a reply exists
  within the step's arrival window, follow the "replied" edge. If the timeout
  deadline has passed with no reply, follow the "timeout" edge.
- next_action_time computed on arrival: whenever advance_enrollment places an
  enrollment into a wait_fixed or wait_until_event step, next_action_time is
  computed and written in that same call.

REPLY CHECK IS FACT-ONLY. LeadMessage (source=inbound_email) is the signal.
The behavioral event log is fire-and-forget and is never used for control flow.
Reply TEXT is never read or interpreted.

TIMING NOTE: per Andrew's ruling 6 (built in a separate task), an inbound reply
immediately pauses the enrollment before the tick ever sees it. The reply check
here only runs on re-activated enrollments (firm owner has cleared the pause)
where the reply LeadMessage already existed at time of re-activation.

STEP CONFIG SHAPES:
  email:             {"subject": str, "body": str}
  wait_fixed:        {"duration_seconds": int}
  wait_until_event:  {"event": str, "timeout_seconds": int}
    event example:   "lead.email_replied"

Config shapes are by convention -- no schema enforcement at the DB layer.

WRITE-THEN-SEND GUARANTEE:
advance_enrollment() is always called BEFORE EmailService.send_nurture_email().
A process crash after the write produces a missed email, never a duplicate.
Do not reverse this ordering.
"""

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from sqlalchemy import exists

from app.db.session import SessionLocal
from app.models.lead import Lead
from app.models.lead_message import LeadMessage
from app.models.firm import Firm
from app.models.user import User
from app.models.sequence import Step, StepEdge, SequenceGoal
from app.models.behavioral_event import BehavioralEvent
from app.core.enums import StepType, UserRole, RecipientType, NotificationType
from app.crud import enrollment as crud_enrollment
from app.crud import lead_message as crud_lead_message
from app.crud.suppressed_email import is_suppressed
from app.core.config import get_settings
from app.services.email_service import EmailService, build_lead_reply_to
from app.services.notification_service import NotificationService

logger = logging.getLogger(__name__)


def _find_entry_step(db, sequence_version_id) -> Optional[Step]:
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


def _check_goal_jump(db, enrollment, current_step) -> Optional[uuid.UUID]:
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


def _compute_next_action_time(db, step_id: Optional[uuid.UUID], now: datetime) -> Optional[datetime]:
    """Compute the next_action_time to write when advancing into a new step.

    wait_fixed:        now + config["duration_seconds"]
    wait_until_event:  now + config["timeout_seconds"]   (the timeout deadline)
    all other types:   None

    Returns None when step_id is None (enrollment finished its path) or when
    the target step cannot be resolved.
    """
    if step_id is None:
        return None
    step = db.query(Step).filter(Step.id == step_id).first()
    if step is None:
        return None
    config = step.config or {}
    if step.step_type == StepType.wait_fixed.value:
        duration = config.get("duration_seconds")
        if duration is not None:
            return now + timedelta(seconds=int(duration))
    elif step.step_type == StepType.wait_until_event.value:
        timeout = config.get("timeout_seconds")
        if timeout is not None:
            return now + timedelta(seconds=int(timeout))
    return None


def _is_within_business_hours(now: datetime, firm_timezone: str, start_hour: int, end_hour: int) -> bool:
    """Return True if now falls within [start_hour, end_hour) in the firm's local timezone.

    Uses the same ZoneInfo(firm_timezone) pattern as slot_computation_service.py
    and booking_service.py. start_hour is inclusive, end_hour is exclusive.
    """
    tz = ZoneInfo(firm_timezone)
    local_now = now.astimezone(tz)
    return start_hour <= local_now.hour < end_hour


def run_nurture_tick() -> dict:
    """Walk all due active Enrollments forward one step.

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
        "timeouts_fired": N,
        "held_for_business_hours": N,
        "held_for_approval": N,
        "dead_ends_reached": N,
      }
    """
    db = SessionLocal()
    checked = sent = suppressed = skipped_branching = failed_sends = 0
    goal_jumps = loop_capped = timeouts_fired = held_for_business_hours = held_for_approval = 0
    dead_ends_reached = 0

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

            # 4. SequenceGoal check -- fires before all other logic.
            # next_action_time is computed for the jump target (may be a wait step).
            goal_target_step_id = _check_goal_jump(db, enrollment, current_step)
            if goal_target_step_id is not None:
                crud_enrollment.advance_enrollment(
                    db=db,
                    enrollment_id=enrollment.id,
                    new_current_step_id=goal_target_step_id,
                    new_next_action_time=_compute_next_action_time(db, goal_target_step_id, now),
                )
                goal_jumps += 1
                logger.info(
                    "nurture_tick: goal jump -- enrollment=%s lead=%s target_step=%s",
                    enrollment.id,
                    lead.id,
                    goal_target_step_id,
                )
                continue

            # 5. wait_until_event: check for the awaited event or timeout.
            # Reply check reads LeadMessage only -- never the behavioral event log.
            if current_step.step_type == StepType.wait_until_event.value:
                config = current_step.config or {}
                timeout_seconds = config.get("timeout_seconds", 0)
                awaited_event = config.get("event", "")

                # arrival_time is reconstructed as next_action_time minus timeout_seconds,
                # which is only valid because next_action_time is set exactly once, on arrival,
                # and never adjusted before this step resolves. If next_action_time is ever
                # recomputed for a waiting enrollment for any other reason, this derivation
                # breaks silently.
                arrival_time = enrollment.next_action_time - timedelta(seconds=int(timeout_seconds))

                reply_message = None
                if awaited_event == "lead.email_replied":
                    reply_message = (
                        db.query(LeadMessage)
                        .filter(
                            LeadMessage.lead_id == enrollment.lead_id,
                            LeadMessage.source == "inbound_email",
                            LeadMessage.created_at >= arrival_time,
                        )
                        .first()
                    )

                edges = (
                    db.query(StepEdge)
                    .filter(StepEdge.from_step_id == current_step.id)
                    .all()
                )

                if reply_message is not None:
                    target_label = "replied"
                else:
                    target_label = "timeout"

                target_edge = next(
                    (e for e in edges if e.condition_label == target_label), None
                )
                if target_edge is None:
                    logger.warning(
                        "nurture_tick: wait_until_event has no %r edge -- enrollment=%s step=%s, skipping",
                        target_label,
                        enrollment.id,
                        current_step.id,
                    )
                    skipped_branching += 1
                    continue

                next_step_id = target_edge.to_step_id
                crud_enrollment.advance_enrollment(
                    db=db,
                    enrollment_id=enrollment.id,
                    new_current_step_id=next_step_id,
                    new_next_action_time=_compute_next_action_time(db, next_step_id, now),
                )
                if target_label == "timeout":
                    timeouts_fired += 1
                logger.info(
                    "nurture_tick: wait_until_event %s -- enrollment=%s lead=%s next_step=%s",
                    target_label,
                    enrollment.id,
                    lead.id,
                    next_step_id,
                )
                continue  # no email send for wait steps

            # 6. wait_fixed: timer elapsed, advance via single edge. No email send.
            if current_step.step_type == StepType.wait_fixed.value:
                edges = (
                    db.query(StepEdge)
                    .filter(StepEdge.from_step_id == current_step.id)
                    .all()
                )
                if len(edges) > 1:
                    logger.warning(
                        "nurture_tick: wait_fixed step=%s has %d outgoing edges, skipping",
                        current_step.id,
                        len(edges),
                    )
                    skipped_branching += 1
                    continue

                next_step_id = None
                updated_loop_counts = None
                if edges:
                    edge = edges[0]
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
                        updated_loop_counts = {**enrollment.loop_counts, str(edge.id): current_count + 1}
                    next_step_id = edge.to_step_id

                crud_enrollment.advance_enrollment(
                    db=db,
                    enrollment_id=enrollment.id,
                    new_current_step_id=next_step_id,
                    new_next_action_time=_compute_next_action_time(db, next_step_id, now),
                    new_loop_counts=updated_loop_counts,
                )
                logger.info(
                    "nurture_tick: wait_fixed elapsed -- enrollment=%s lead=%s next_step=%s",
                    enrollment.id,
                    lead.id,
                    next_step_id,
                )
                continue  # no email send for wait steps

            # 7. Action steps with hold_for_approval: hold for firm-owner review before any
            # external action fires. Per Contract section 6.7: any automated action with
            # external consequences is held for human approval -- concretely, R1 (the
            # unqualified decline) is HELD; the owner approves or overrides. This is a
            # status change to held_for_approval, NOT the business-hours retry hold:
            # an approval hold requires an explicit human release; a timing hold retries
            # automatically. Conflating them would hide a pending decision behind a counter.
            if (
                current_step.step_type == StepType.action.value
                and (current_step.config or {}).get("hold_for_approval")
            ):
                crud_enrollment.hold_enrollment_for_approval(
                    db=db, enrollment_id=enrollment.id
                )
                held_for_approval += 1
                firm_owner = (
                    db.query(User)
                    .filter(
                        User.firm_id == enrollment.firm_id,
                        User.role == UserRole.firm_owner,
                    )
                    .first()
                )
                if firm_owner is not None:
                    NotificationService.create_notification(
                        db=db,
                        firm_id=enrollment.firm_id,
                        recipient_id=firm_owner.id,
                        recipient_type=RecipientType.staff,
                        title="Lead pending approval -- decline held",
                        body=(
                            f"An automated decline for lead {lead.name} is awaiting"
                            " your approval. Approve to send the decline email, or"
                            " override to return the lead to the sequence."
                        ),
                        notification_type=NotificationType.nurture_hold_for_approval,
                        related_entity_type="lead",
                        related_entity_id=lead.id,
                    )
                logger.info(
                    "nurture_tick: held for approval -- enrollment=%s lead=%s step=%s",
                    enrollment.id,
                    lead.id,
                    current_step.id,
                )
                continue

            # 7.5. Dead_end steps: terminate the enrollment and notify the firm owner.
            # Per Contract section 6.7: every dead end notifies the owner with a one-click
            # take-over. This branch MUST come before the generic "not processable" fallthrough
            # below -- without it, dead_end steps would increment skipped_branching and loop
            # forever because next_action_time is never cleared (real, confirmed bug).
            if current_step.step_type == StepType.dead_end.value:
                crud_enrollment.mark_enrollment_dead_end(
                    db=db, enrollment_id=enrollment.id
                )
                dead_ends_reached += 1
                firm_owner = (
                    db.query(User)
                    .filter(
                        User.firm_id == enrollment.firm_id,
                        User.role == UserRole.firm_owner,
                    )
                    .first()
                )
                if firm_owner is not None:
                    NotificationService.create_notification(
                        db=db,
                        firm_id=enrollment.firm_id,
                        recipient_id=firm_owner.id,
                        recipient_type=RecipientType.staff,
                        title=f"Lead reached a dead end: {lead.name}",
                        body=(
                            f"Lead {lead.name} has reached the end of the nurture sequence"
                            " with no further automated steps. Take over to handle this lead"
                            " directly."
                        ),
                        notification_type=NotificationType.nurture_dead_end_reached,
                        related_entity_type="lead",
                        related_entity_id=lead.id,
                    )
                logger.info(
                    "nurture_tick: dead_end reached -- enrollment=%s lead=%s step=%s",
                    enrollment.id,
                    lead.id,
                    current_step.id,
                )
                continue

            # 8. Only email-type Steps proceed to send.
            if current_step.step_type != StepType.email.value:
                logger.info(
                    "nurture_tick: enrollment=%s step=%s type=%s not processable, skipping",
                    enrollment.id,
                    current_step.id,
                    current_step.step_type,
                )
                skipped_branching += 1
                continue

            # 8. Email step: single outgoing edge required.
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
                    updated_loop_counts = {**enrollment.loop_counts, str(edge.id): current_count + 1}
                next_step_id = edge.to_step_id

            # 9. Look up firm -- needed for business-hours check and sending identity.
            # Moved here from the original step 11 position so the business-hours
            # guard can read firm.timezone / business_hours_start / business_hours_end
            # without a second query.
            firm = db.query(Firm).filter(Firm.id == enrollment.firm_id).first()
            from_name = firm.name if firm else "JAMM PX"
            sending_domain = (
                firm.sending_domain
                if firm and firm.sending_domain_verified
                else None
            )

            # 10. Business-hours check: hold if currently outside the firm's send window.
            # Per contract section 6.1, nurture sends must respect firm business hours
            # (default 8am-6pm firm-local). A step config with "bypass_business_hours": true
            # skips this check -- the flag is built now but not applied to any seeded step.
            bypass = (current_step.config or {}).get("bypass_business_hours", False)
            if not bypass:
                firm_timezone = firm.timezone if firm else 'America/New_York'
                bh_start = firm.business_hours_start if firm else 8
                bh_end = firm.business_hours_end if firm else 18
                if not _is_within_business_hours(now, firm_timezone, bh_start, bh_end):
                    crud_enrollment.advance_enrollment(
                        db=db,
                        enrollment_id=enrollment.id,
                        new_current_step_id=enrollment.current_step_id,
                        new_next_action_time=now + timedelta(minutes=30),
                    )
                    held_for_business_hours += 1
                    logger.info(
                        "nurture_tick: held for business hours -- enrollment=%s lead=%s",
                        enrollment.id,
                        lead.id,
                    )
                    continue

            # 11. Generate a fresh unsubscribe token for this specific send.
            # Raw token is single-use and lives only in the email link; only the
            # hash is written to the database. Long expiry (10 years) because an
            # unsubscribe link that silently expires is a real compliance problem.
            # Per contract section 6.6: every nurture send must carry an unsubscribe link.
            settings = get_settings()
            raw_unsubscribe_token = secrets.token_hex(32)
            unsubscribe_token_hash = hashlib.sha256(raw_unsubscribe_token.encode()).hexdigest()
            unsubscribe_token_expires_at = now + timedelta(days=3650)
            unsubscribe_url = f"{settings.FRONTEND_URL}/unsubscribe/{raw_unsubscribe_token}"

            # 12. Render content from step config and inject the unsubscribe link.
            config = current_step.config or {}
            subject = config.get("subject", "")
            body = config.get("body", "")

            # Inject unsubscribe_url using the same {{key}} convention as letter_renderer.py.
            # If the body contains {{unsubscribe_url}}, substitute it in place.
            # If not (e.g. placeholder body or manually-authored body with no tag),
            # append a plain unsubscribe footer so the link is never silently omitted.
            if "{{unsubscribe_url}}" in body:
                body = body.replace("{{unsubscribe_url}}", unsubscribe_url)
            else:
                body = (
                    body
                    + f'<p style="font-size:11px;color:#888;margin-top:32px;">'
                    + f'<a href="{unsubscribe_url}">Unsubscribe</a> from these emails.</p>'
                )

            # 13. WRITE FIRST -- advance enrollment before any send attempt.
            # Write-then-send guarantee: a crash after write produces a missed email,
            # never a duplicate. Do not move this below the send call.
            crud_enrollment.advance_enrollment(
                db=db,
                enrollment_id=enrollment.id,
                new_current_step_id=next_step_id,
                new_next_action_time=_compute_next_action_time(db, next_step_id, now),
                new_loop_counts=updated_loop_counts,
                new_unsubscribe_token_hash=unsubscribe_token_hash,
                new_unsubscribe_token_expires_at=unsubscribe_token_expires_at,
            )

            # 14. Send the email. Failure is fire-and-forget: enrollment is already advanced.
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
        "timeouts_fired": timeouts_fired,
        "held_for_business_hours": held_for_business_hours,
        "held_for_approval": held_for_approval,
        "dead_ends_reached": dead_ends_reached,
    }
