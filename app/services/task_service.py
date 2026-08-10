# app/services/task_service.py

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException, status as http_status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import task as crud_task
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.user import User
from app.services.behavioral_log import log_event


# ---------------------------------------------------------------------------
# Assignment scoping
#
# Task assignment offers only current members of that engagement. A dropdown
# of members, not a free choice of firm users.
#
# Assignment never grants access beyond what the assigner could already have
# granted by hand. If the assigner holds membership-management authority on
# that engagement, assigning to a non-member adds them automatically, because
# refusing would only send that person to the member list to press one more
# button and come back. The auto-add collapses two steps into one for someone
# who already held the authority to take both. It invents no new permission:
# the check is can_manage_membership(), the same one the manual add makes.
#
# If the assigner does not hold that authority, the assignment is refused and
# the engagement administrators are notified so somebody who can act, does.
# Automation never carries add-member authority at all, because an automation
# rule has no actor whose authority could be checked.
#
# Internal tasks have no engagement, so their assignee pool is every internal
# user of the firm.
# ---------------------------------------------------------------------------

def _resolve_engagement(db: Session, engagement_id: UUID, firm_id: UUID) -> Engagement:
    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == engagement_id,
            Engagement.firm_id == firm_id,
        )
    ).scalars().first()
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return engagement


def _require_firm_user(db: Session, user_id: UUID, firm_id: UUID) -> User:
    from app.services.engagement_member_service import ASSIGNABLE_ROLES

    user = db.execute(
        select(User).where(User.id == user_id, User.firm_id == firm_id)
    ).scalars().first()
    if not user or user.role not in ASSIGNABLE_ROLES:
        raise HTTPException(
            status_code=422,
            detail="Cannot assign a task to a user outside this firm.",
        )
    return user


_REFUSED_DETAIL = (
    "That user is not a member of this engagement, and you do not have "
    "permission to add them. An administrator of this engagement has been "
    "notified and can either add them or make the assignment for you."
)

_REFUSED_AUTOMATION_DETAIL = (
    "Automation cannot assign a task to a user who is not a member of the "
    "engagement. An administrator of this engagement has been notified."
)


def _notify_assignment_refused(
    db: Session,
    *,
    firm_id: UUID,
    engagement_id: UUID,
    assigned_to: UUID,
    by_automation: bool,
) -> None:
    """Tell the engagement administrators that an assignment was refused, so
    the refusal reaches somebody who can actually resolve it."""
    from app.services import engagement_member_service

    target = db.execute(
        select(User).where(User.id == assigned_to, User.firm_id == firm_id)
    ).scalars().first()
    target_name = target.full_name if target else str(assigned_to)

    engagement = db.execute(
        select(Engagement).where(
            Engagement.id == engagement_id,
            Engagement.firm_id == firm_id,
        )
    ).scalars().first()
    engagement_name = engagement.name if engagement else str(engagement_id)

    if by_automation:
        body = (
            f"An automation rule tried to assign a task on {engagement_name} "
            f"to {target_name}, who is not a member of that engagement. The "
            "assignment was refused. Add them to the engagement if they "
            "should be doing this work."
        )
    else:
        body = (
            f"Somebody tried to assign a task on {engagement_name} to "
            f"{target_name}, who is not a member of that engagement, and did "
            "not have permission to add them. The assignment was refused. Add "
            "them to the engagement if they should be doing this work."
        )

    engagement_member_service.notify_engagement_administrators(
        db,
        firm_id=firm_id,
        engagement_id=engagement_id,
        title="Task assignment refused",
        body=body,
    )


def _check_assignable(
    db: Session,
    *,
    firm_id: UUID,
    engagement_id: UUID | None,
    assigned_to: UUID | None,
    acting_user_id: UUID | None,
    created_by_automation: bool = False,
) -> bool:
    """Decide an assignment without writing anything.

    Returns True when the assignment is allowed but needs the target added to
    the engagement first, False when no membership work is required. Raises
    422 when the assignment must be refused, having notified the engagement
    administrators on the way out.

    Kept separate from _require_assignable so the bulk path can evaluate every
    task in a batch before performing a single auto-add.
    """
    if assigned_to is None:
        return False

    _require_firm_user(db, assigned_to, firm_id)

    if engagement_id is None:
        return False

    from app.services import engagement_member_service

    if engagement_member_service.is_member(
        db, firm_id=firm_id, engagement_id=engagement_id, user_id=assigned_to
    ):
        return False

    # An automation rule has no created_by column, so there is no actor whose
    # authority could be checked. Automation therefore never auto-adds.
    if created_by_automation:
        _notify_assignment_refused(
            db,
            firm_id=firm_id,
            engagement_id=engagement_id,
            assigned_to=assigned_to,
            by_automation=True,
        )
        raise HTTPException(status_code=422, detail=_REFUSED_AUTOMATION_DETAIL)

    acting_user = _require_firm_user(db, acting_user_id, firm_id)

    if not engagement_member_service.can_manage_membership(
        db, firm_id=firm_id, engagement_id=engagement_id, user=acting_user
    ):
        _notify_assignment_refused(
            db,
            firm_id=firm_id,
            engagement_id=engagement_id,
            assigned_to=assigned_to,
            by_automation=False,
        )
        raise HTTPException(status_code=422, detail=_REFUSED_DETAIL)

    return True


def _require_assignable(
    db: Session,
    *,
    firm_id: UUID,
    engagement_id: UUID | None,
    assigned_to: UUID | None,
    acting_user_id: UUID | None,
    created_by_automation: bool = False,
) -> dict | None:
    """Scope one assignment, auto-adding the target when the acting user has
    the authority to add them.

    Returns a record of the auto-add performed, or None when none was needed,
    so callers can report it back rather than leaving the new membership to be
    discovered later on a member list.
    """
    needs_add = _check_assignable(
        db,
        firm_id=firm_id,
        engagement_id=engagement_id,
        assigned_to=assigned_to,
        acting_user_id=acting_user_id,
        created_by_automation=created_by_automation,
    )
    if not needs_add:
        return None

    from app.services import engagement_member_service

    acting_user = _require_firm_user(db, acting_user_id, firm_id)
    membership = engagement_member_service.add_member_for_assignment(
        db,
        firm_id=firm_id,
        engagement_id=engagement_id,
        user_id=assigned_to,
        acting_user=acting_user,
    )
    if membership is None:
        _notify_assignment_refused(
            db,
            firm_id=firm_id,
            engagement_id=engagement_id,
            assigned_to=assigned_to,
            by_automation=False,
        )
        raise HTTPException(status_code=422, detail=_REFUSED_DETAIL)

    return {"user_id": assigned_to, "engagement_id": engagement_id}


def require_can_create_task(
    db: Session,
    *,
    firm_id: UUID,
    engagement_id: UUID | None,
    current_user: User,
) -> None:
    """Anyone ON an engagement can create tasks for it, whatever their firm
    role. firm_owner and manager can create tasks on any engagement in the
    firm without being members. Internal tasks belong to no engagement, so
    any internal firm user can create one."""
    if engagement_id is None:
        return

    from app.services import engagement_member_service

    if current_user.role in engagement_member_service.FIRM_WIDE_MANAGEMENT_ROLES:
        return

    if engagement_member_service.is_member(
        db, firm_id=firm_id, engagement_id=engagement_id, user_id=current_user.id
    ):
        return

    raise HTTPException(
        status_code=http_status.HTTP_403_FORBIDDEN,
        detail="You must be a member of this engagement to create tasks for it.",
    )


def create_task(
    *,
    db: Session,
    payload,
    firm_id: UUID,
    current_user_id: UUID,
    created_by_automation: bool = False,
):
    engagement_id = getattr(payload, "engagement_id", None)
    if engagement_id is not None:
        _resolve_engagement(db, engagement_id, firm_id)

    _require_assignable(
        db,
        firm_id=firm_id,
        engagement_id=engagement_id,
        assigned_to=getattr(payload, "assigned_to", None),
        acting_user_id=current_user_id,
        created_by_automation=created_by_automation,
    )

    # Set once, here, and never recomputed. Deriving it later by comparing a
    # creator to assigned_to would let a reassignment erase the original
    # relationship, and the Employee Archive would silently change its mind
    # about history.
    is_self_created = (
        not created_by_automation
        and getattr(payload, "assigned_to", None) is not None
        and str(payload.assigned_to) == str(current_user_id)
    )

    task = crud_task.create_task(
        db, payload, firm_id=firm_id, is_self_created=is_self_created
    )

    log_event(
        firm_id=task.firm_id,
        event_type="task.created",
        entity_type="task",
        entity_id=task.id,
        actor_type="automation" if created_by_automation else "staff",
        actor_id=None if created_by_automation else current_user_id,
        metadata={
            "created_by_automation": created_by_automation,
            "task_type": str(task.task_type),
            "engagement_id": str(task.engagement_id) if task.engagement_id else None,
            "client_id": str(task.client_id) if hasattr(task, 'client_id') and task.client_id else None,
            "due_date_set": task.due_date is not None,
            "assigned": task.assigned_to is not None,
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
            "is_self_created": bool(task.is_self_created),
        }
    )

    return task


def update_task(
    *,
    db: Session,
    task_id: UUID,
    payload,
    firm_id: UUID,
    current_user_id: UUID,
):
    task = crud_task.get_task_for_firm(db, task_id, firm_id)
    if not task:
        return None

    # Scope the assignment BEFORE anything is written. The engagement checked
    # against is the one the task will have after this patch, not the one it
    # had before, so moving a task and reassigning it in a single request is
    # still validated against the destination engagement.
    _patch = payload.model_dump(exclude_unset=True)
    if "assigned_to" in _patch or "engagement_id" in _patch:
        _target_engagement_id = (
            _patch["engagement_id"] if "engagement_id" in _patch else task.engagement_id
        )
        _target_assignee = (
            _patch["assigned_to"] if "assigned_to" in _patch else task.assigned_to
        )
        if _target_engagement_id is not None:
            _resolve_engagement(db, _target_engagement_id, firm_id)
        _require_assignable(
            db,
            firm_id=firm_id,
            engagement_id=_target_engagement_id,
            assigned_to=_target_assignee,
            acting_user_id=current_user_id,
        )

    old_status = str(task.status) if task.status else None
    old_assigned = str(task.assigned_to) if task.assigned_to else None
    old_due_date = task.due_date

    # Fields already covered by a dedicated event below -- excluded from the
    # generic no-silent-changes delta so they are not double-logged.
    _EVENTED_FIELDS = {"status", "assigned_to", "due_date"}
    _tracked_fields = [
        f for f in payload.model_dump(exclude_unset=True).keys()
        if f not in _EVENTED_FIELDS
    ]
    _old_values = {f: getattr(task, f) for f in _tracked_fields}

    updated = crud_task.update_task(db, task, payload)

    new_status = str(updated.status) if updated.status else None
    new_assigned = str(updated.assigned_to) if updated.assigned_to else None

    if old_status != new_status:
        log_event(
            firm_id=updated.firm_id,
            event_type="task.status_changed",
            entity_type="task",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_status": old_status,
                "to_status": new_status,
                "days_since_creation": (datetime.now(timezone.utc) - updated.created_at).days
                    if updated.created_at else None,
            }
        )

        completed_statuses = {"completed", "done", "complete"}
        if new_status and new_status.lower() in completed_statuses:
            updated.is_completed = True
            db.commit()
            log_event(
                firm_id=updated.firm_id,
                event_type="task.completed",
                entity_type="task",
                entity_id=updated.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={
                    "days_from_creation": (datetime.now(timezone.utc) - updated.created_at).days
                        if updated.created_at else None,
                    "completed_by_assignee": str(current_user_id) == str(updated.assigned_to)
                        if updated.assigned_to and current_user_id else None,
                    "days_relative_to_due": (datetime.now(timezone.utc).date() - updated.due_date).days
                        if updated.due_date else None,
                    "engagement_id": str(updated.engagement_id) if updated.engagement_id else None,
                }
            )
        elif old_status and old_status.lower() in completed_statuses:
            updated.is_completed = False
            db.commit()

    if old_assigned != new_assigned and payload.model_dump(exclude_none=True).get('assigned_to') is not None:
        event_type = "task.reassigned" if old_assigned else "task.assigned"
        log_event(
            firm_id=updated.firm_id,
            event_type=event_type,
            entity_type="task",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_staff_id": old_assigned,
                "to_staff_id": new_assigned,
                "days_since_creation": (datetime.now(timezone.utc) - updated.created_at).days
                    if updated.created_at else None,
                "days_until_due": (updated.due_date - datetime.now(timezone.utc).date()).days
                    if updated.due_date else None,
                "current_status": new_status,
            }
        )

    if old_due_date != updated.due_date and payload.model_dump(exclude_none=True).get('due_date') is not None:
        log_event(
            firm_id=updated.firm_id,
            event_type="task.due_date_changed",
            entity_type="task",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "old_due_date": old_due_date.isoformat() if old_due_date else None,
                "new_due_date": updated.due_date.isoformat() if updated.due_date else None,
                "days_before_original_due": (old_due_date - datetime.now(timezone.utc).date()).days
                    if old_due_date else None,
            }
        )

    from app.services.behavioral_log import build_changed_fields

    _new_values = {f: getattr(updated, f) for f in _tracked_fields}
    _changed_fields = build_changed_fields(_old_values, _new_values)
    if _changed_fields:
        log_event(
            firm_id=updated.firm_id,
            event_type="task.updated",
            entity_type="task",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={"changed_fields": _changed_fields},
        )

    return updated


def bulk_update_tasks(
    *,
    db: Session,
    ids,
    update,  # TaskUpdate
    firm_id: UUID,
    current_user_id: UUID,
):
    stmt = select(Task).where(
        Task.id.in_(ids),
        Task.firm_id == firm_id,
    )
    tasks = db.execute(stmt).scalars().all()
    update_data = update.model_dump(exclude_none=True)

    members_added: list[dict] = []

    # A bulk reassignment is still an assignment: it has to respect engagement
    # membership exactly like the single-task path, or it becomes the way
    # around the rule. All or nothing, in two passes. The first pass decides
    # every targeted task and writes nothing, so one refused task anywhere in
    # the batch refuses the whole batch and leaves zero memberships behind. The
    # adds only happen once the entire batch is known to be allowed.
    if update_data.get("assigned_to") is not None:
        assigned_to = update_data["assigned_to"]

        engagement_ids_needing_add = []
        for task in tasks:
            if _check_assignable(
                db,
                firm_id=firm_id,
                engagement_id=task.engagement_id,
                assigned_to=assigned_to,
                acting_user_id=current_user_id,
            ) and task.engagement_id not in engagement_ids_needing_add:
                engagement_ids_needing_add.append(task.engagement_id)

        added_engagement_ids = []
        for engagement_id in engagement_ids_needing_add:
            record = _require_assignable(
                db,
                firm_id=firm_id,
                engagement_id=engagement_id,
                assigned_to=assigned_to,
                acting_user_id=current_user_id,
            )
            if record:
                added_engagement_ids.append(record["engagement_id"])

        # Reported so a firm owner sees that a bulk reassignment also placed
        # somebody on nine engagements, rather than finding out later.
        if added_engagement_ids:
            members_added.append({
                "user_id": assigned_to,
                "engagement_ids": added_engagement_ids,
            })

    changed = []
    for task in tasks:
        old_status = task.status
        old_assigned_to = task.assigned_to
        old_due_date = task.due_date
        for key, value in update_data.items():
            setattr(task, key, value)
        changed.append((task, old_status, old_assigned_to, old_due_date))
    db.commit()

    for task, old_status, old_assigned_to, old_due_date in changed:
        if task.status != old_status:
            log_event(
                firm_id=firm_id,
                event_type="task.status_changed",
                entity_type="task",
                entity_id=task.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={"from_status": str(old_status), "to_status": str(task.status), "via": "bulk"}
            )
        if task.assigned_to != old_assigned_to:
            log_event(
                firm_id=firm_id,
                event_type="task.assigned",
                entity_type="task",
                entity_id=task.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={
                    "from_staff_id": str(old_assigned_to) if old_assigned_to else None,
                    "to_staff_id": str(task.assigned_to) if task.assigned_to else None,
                    "via": "bulk",
                }
            )
        if task.due_date != old_due_date:
            log_event(
                firm_id=firm_id,
                event_type="task.due_date_changed",
                entity_type="task",
                entity_id=task.id,
                actor_type="staff",
                actor_id=current_user_id,
                metadata={
                    "from_due_date": old_due_date.isoformat() if old_due_date else None,
                    "to_due_date": task.due_date.isoformat() if task.due_date else None,
                    "via": "bulk",
                }
            )

    return {"updated": len(tasks), "members_added": members_added}


def delete_task(
    *,
    db: Session,
    task_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
):
    task = crud_task.get_task_for_firm(db, task_id, firm_id)
    if not task:
        return None

    completion_status = str(task.status) if task.status else None
    days_since_creation = (datetime.now(timezone.utc) - task.created_at).days \
        if task.created_at else None
    task_firm_id = task.firm_id

    crud_task.delete_task(db, task)

    log_event(
        firm_id=task_firm_id,
        event_type="task.deleted",
        entity_type="task",
        entity_id=task_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "completion_status": completion_status,
            "days_since_creation": days_since_creation,
        }
    )

    return True
