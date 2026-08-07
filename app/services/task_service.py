# app/services/task_service.py

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import task as crud_task
from app.models.task import Task
from app.services.behavioral_log import log_event


def create_task(
    *,
    db: Session,
    payload,
    firm_id: UUID,
    current_user_id: UUID,
    created_by_automation: bool = False,
):
    task = crud_task.create_task(db, payload, firm_id=firm_id)

    log_event(
        firm_id=task.firm_id,
        event_type="task.created",
        entity_type="task",
        entity_id=task.id,
        actor_type="automation" if created_by_automation else "staff",
        actor_id=None if created_by_automation else current_user_id,
        metadata={
            "created_by_automation": created_by_automation,
            "engagement_id": str(task.engagement_id) if task.engagement_id else None,
            "client_id": str(task.client_id) if hasattr(task, 'client_id') and task.client_id else None,
            "due_date_set": task.due_date is not None,
            "assigned": task.assigned_to is not None,
            "assigned_to": str(task.assigned_to) if task.assigned_to else None,
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
):
    stmt = select(Task).where(
        Task.id.in_(ids),
        Task.firm_id == firm_id,
    )
    tasks = db.execute(stmt).scalars().all()
    update_data = update.model_dump(exclude_none=True)

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
                actor_id=None,
                metadata={"from_status": str(old_status), "to_status": str(task.status), "via": "bulk"}
            )
        if task.assigned_to != old_assigned_to:
            log_event(
                firm_id=firm_id,
                event_type="task.assigned",
                entity_type="task",
                entity_id=task.id,
                actor_type="staff",
                actor_id=None,
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
                actor_id=None,
                metadata={
                    "from_due_date": old_due_date.isoformat() if old_due_date else None,
                    "to_due_date": task.due_date.isoformat() if task.due_date else None,
                    "via": "bulk",
                }
            )

    return {"updated": len(tasks)}


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
