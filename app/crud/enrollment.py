# app/crud/enrollment.py

from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from sqlalchemy.orm import Session

from app.models.enrollment import Enrollment
from app.core.enums import EnrollmentStatus


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
    """Return active enrollments whose next_action_time is at or before now.

    If firm_id is None, queries across all firms (background job usage,
    matching the pattern in deadline_scheduler.py). If firm_id is provided,
    scopes to that firm only (tenant-isolation usage).
    """
    query = db.query(Enrollment).filter(
        Enrollment.status == EnrollmentStatus.active.value,
        Enrollment.next_action_time.isnot(None),
        Enrollment.next_action_time <= now,
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
