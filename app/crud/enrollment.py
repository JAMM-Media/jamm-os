# app/crud/enrollment.py

from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.core.enums import EnrollmentStatus
from app.services.audit_service import write_audit_log


def get_enrollment_for_firm(
    db: Session, enrollment_id: UUID, firm_id: UUID
) -> Enrollment | None:
    return db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.firm_id == firm_id,
    ).first()


def get_due_enrollments(
    db: Session,
    firm_id: Optional[UUID],
    now: datetime,
) -> list[Enrollment]:
    """Return active enrollments whose next_action_time is at or before now,
    restricted to firms with nurture_enabled=True.

    If firm_id is None, queries across all firms (background job usage,
    matching the pattern in deadline_scheduler.py). If firm_id is provided,
    scopes to that firm only (tenant-isolation usage). In both cases the
    Firm join ensures toggle-off firms are excluded at the query level.
    """
    query = (
        db.query(Enrollment)
        .join(Firm, Firm.id == Enrollment.firm_id)
        .filter(
            Enrollment.status == EnrollmentStatus.active.value,
            Enrollment.next_action_time.isnot(None),
            Enrollment.next_action_time <= now,
            Firm.nurture_enabled == True,
        )
    )
    if firm_id is not None:
        query = query.filter(Enrollment.firm_id == firm_id)
    return query.all()


def advance_enrollment(
    db: Session,
    enrollment_id: UUID,
    new_current_step_id: Optional[UUID],
    new_next_action_time: Optional[datetime],
    new_loop_counts: Optional[dict] = None,
    new_unsubscribe_token_hash: Optional[str] = None,
    new_unsubscribe_token_expires_at: Optional[datetime] = None,
) -> None:
    """Write the new step, scheduled time, and optionally updated loop counts.

    Must be called BEFORE any email send. A crash between this write and the
    send produces a missed email, never a duplicate. This ordering is
    deliberate and must not be reversed.

    new_loop_counts: if provided, replaces enrollment.loop_counts in the same
    commit. Used when following a loop-back edge to record the incremented count.

    new_unsubscribe_token_hash / new_unsubscribe_token_expires_at: if provided,
    written in the same commit as the step advance so the unsubscribe token is
    durable before the email is sent.
    """
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if enrollment is None:
        return
    enrollment.current_step_id = new_current_step_id
    enrollment.next_action_time = new_next_action_time
    if new_loop_counts is not None:
        enrollment.loop_counts = new_loop_counts
    if new_unsubscribe_token_hash is not None:
        enrollment.unsubscribe_token_hash = new_unsubscribe_token_hash
    if new_unsubscribe_token_expires_at is not None:
        enrollment.unsubscribe_token_expires_at = new_unsubscribe_token_expires_at
    db.commit()


def mark_enrollment_suppressed(
    db: Session,
    enrollment_id: UUID,
) -> None:
    """Stop an enrollment because the lead's email is on the suppression list."""
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if enrollment is None:
        return
    enrollment.status = EnrollmentStatus.unsubscribed.value
    enrollment.stopped_at = datetime.now(timezone.utc)
    db.commit()


def mark_enrollment_dead_end(db: Session, enrollment_id: UUID) -> None:
    """Terminate an enrollment that has reached a dead_end step.

    Sets status to completed_dead_end, clears next_action_time so the engine
    never re-selects this enrollment, and records stopped_at. Per Contract
    section 6.7: every dead end notifies the owner; the caller in
    nurture_execution_service.py fires the notification after this write.
    """
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if enrollment is None:
        return
    enrollment.status = EnrollmentStatus.completed_dead_end.value
    enrollment.next_action_time = None
    enrollment.stopped_at = datetime.now(timezone.utc)
    db.commit()
    write_audit_log(
        db=db,
        firm_id=enrollment.firm_id,
        action="enrollment.dead_end_reached",
        actor_id=None,
        actor_type="system",
        entity_type="enrollment",
        entity_id=enrollment_id,
        metadata={"lead_id": str(enrollment.lead_id)},
    )


def acknowledge_dead_end_takeover(
    db: Session,
    enrollment_id: UUID,
    firm_id: UUID,
    lead_id: UUID,
    user_id: Optional[UUID] = None,
) -> Enrollment:
    """Record the firm owner's explicit take-over of a dead-ended lead.

    "Manual mode" in this codebase means the lead has no active enrollment
    (already true once completed_dead_end is set by the tick) and the firm
    owner has explicitly acknowledged that they are handling the lead directly,
    recorded here as an audit log entry. No new model field is needed because
    the completed_dead_end status already tells the system the lead is out of
    automation. No new columns are added.

    This is structurally identical to release_enrollment_hold for R1: a firm-
    owner action that resolves a pending state and writes an audit log.

    Raises ValueError if:
    - enrollment not found in this firm
    - enrollment does not belong to the given lead_id
    - enrollment is not in completed_dead_end state
    """
    enrollment = db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.firm_id == firm_id,
    ).first()
    if enrollment is None:
        raise ValueError("Enrollment not found in this firm")
    if enrollment.lead_id != lead_id:
        raise ValueError("Enrollment does not belong to the given lead")
    if enrollment.status != EnrollmentStatus.completed_dead_end.value:
        raise ValueError(
            f"Cannot take over enrollment with status '{enrollment.status}': "
            f"only completed_dead_end enrollments can be taken over"
        )
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action="enrollment.dead_end_takeover",
        actor_id=user_id,
        actor_type="staff" if user_id else "system",
        entity_type="enrollment",
        entity_id=enrollment_id,
        metadata={"lead_id": str(lead_id)},
    )
    return enrollment


def reactivate_enrollment(
    db: Session,
    enrollment_id: UUID,
    firm_id: UUID,
) -> Enrollment:
    """Move a paused_reply enrollment back to active so the sequence resumes.

    Raises ValueError if the enrollment is not found in this firm, or if its
    current status is not paused_reply. Silently reactivating an already-active
    or terminated enrollment would mask bugs in the caller; the guard is intentional.
    """
    enrollment = db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.firm_id == firm_id,
    ).first()
    if enrollment is None:
        raise ValueError("Enrollment not found in this firm")
    if enrollment.status != EnrollmentStatus.paused_reply.value:
        raise ValueError(
            f"Cannot reactivate enrollment with status '{enrollment.status}': "
            f"only paused_reply enrollments can be reactivated"
        )
    enrollment.status = EnrollmentStatus.active.value
    db.commit()
    return enrollment


def hold_enrollment_for_approval(db: Session, enrollment_id: UUID) -> None:
    """Put an enrollment into held_for_approval state, awaiting firm-owner action.

    Clears next_action_time so the engine never re-picks it up automatically.
    The enrollment stays at its current step until the firm owner approves or
    overrides via release_enrollment_hold(). Per Contract section 6.7.
    """
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if enrollment is None:
        return
    enrollment.status = EnrollmentStatus.held_for_approval.value
    enrollment.next_action_time = None
    db.commit()
    write_audit_log(
        db=db,
        firm_id=enrollment.firm_id,
        action="enrollment.held_for_approval",
        actor_id=None,
        actor_type="system",
        entity_type="enrollment",
        entity_id=enrollment_id,
        metadata={"lead_id": str(enrollment.lead_id)},
    )


def release_enrollment_hold(
    db: Session,
    enrollment_id: UUID,
    firm_id: UUID,
    lead_id: UUID,
    condition_label: str,
    user_id: Optional[UUID] = None,
) -> Enrollment:
    """Advance a held_for_approval enrollment via the named outgoing edge.

    condition_label is the edge label to follow (e.g. "APPROVED" or "OVERRIDE").
    lead_id must match the enrollment's lead_id: the enrollment must belong to the
    lead named in the URL, not just the firm.
    Sets status back to active with next_action_time = now so the engine picks it
    up on the next tick.

    Raises ValueError if:
    - enrollment not found in this firm
    - enrollment does not belong to the given lead_id
    - enrollment is not in held_for_approval state
    - no outgoing edge with the given condition_label exists from the current step
    """
    from app.models.sequence import StepEdge

    enrollment = db.query(Enrollment).filter(
        Enrollment.id == enrollment_id,
        Enrollment.firm_id == firm_id,
    ).first()
    if enrollment is None:
        raise ValueError("Enrollment not found in this firm")
    if enrollment.lead_id != lead_id:
        raise ValueError(
            "Enrollment does not belong to the given lead"
        )
    if enrollment.status != EnrollmentStatus.held_for_approval.value:
        raise ValueError(
            f"Cannot release enrollment with status '{enrollment.status}': "
            f"only held_for_approval enrollments can be released"
        )
    edge = db.query(StepEdge).filter(
        StepEdge.from_step_id == enrollment.current_step_id,
        StepEdge.condition_label == condition_label,
    ).first()
    if edge is None:
        raise ValueError(
            f"No outgoing edge with condition_label='{condition_label}' "
            f"from step {enrollment.current_step_id}"
        )
    from_step_id = enrollment.current_step_id
    enrollment.current_step_id = edge.to_step_id
    enrollment.status = EnrollmentStatus.active.value
    enrollment.next_action_time = datetime.now(timezone.utc)
    db.commit()
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action=f"enrollment.hold_{condition_label.lower()}",
        actor_id=user_id,
        actor_type="staff" if user_id else "system",
        entity_type="enrollment",
        entity_id=enrollment_id,
        metadata={
            "lead_id": str(lead_id),
            "from_step_id": str(from_step_id),
            "to_step_id": str(edge.to_step_id),
            "condition_label": condition_label,
        },
    )
    return enrollment
