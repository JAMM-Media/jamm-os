# app/api/archive.py

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.archive_star import ArchiveStar
from app.models.behavioral_event import BehavioralEvent
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.task import Task
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.core.enums import UserRole

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /archive/{user_id}
# ---------------------------------------------------------------------------

@router.get("/{user_id}")
def get_archive(
    user_id: uuid.UUID,
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    client_id: Optional[uuid.UUID] = Query(None),
    engagement_id: Optional[uuid.UUID] = Query(None),
    role: Optional[str] = Query(None),
    starred: Optional[bool] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    firm: Firm = Depends(get_current_firm),
):
    # Role-scoped access: staff can only view their own archive.
    if current_user.role == UserRole.staff and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff may only view their own archive.")

    # "reviewed" role has no rows yet -- return an empty result immediately.
    if role == "reviewed":
        return {
            "items": [],
            "total": 0,
            "aggregates": {
                "tasks_completed": 0,
                "hours_logged": 0.0,
                "engagements_touched": 0,
            },
        }

    # Subquery: most recent task.completed event per task entity_id.
    completed_sq = (
        select(
            BehavioralEvent.entity_id.label("task_id"),
            func.max(BehavioralEvent.occurred_at).label("completed_at"),
        )
        .where(
            BehavioralEvent.firm_id == firm.id,
            BehavioralEvent.event_type == "task.completed",
        )
        .group_by(BehavioralEvent.entity_id)
        .subquery()
    )

    # Subquery: total hours per task from TimeEntry.task_id.
    hours_sq = (
        select(
            TimeEntry.task_id.label("task_id"),
            func.sum(TimeEntry.hours).label("total_hours"),
        )
        .where(TimeEntry.firm_id == firm.id)
        .group_by(TimeEntry.task_id)
        .subquery()
    )

    # Subquery: starred task ids for the target user.
    star_sq = (
        select(ArchiveStar.task_id)
        .where(ArchiveStar.user_id == user_id)
        .subquery()
    )

    # Base query: completed tasks assigned to target user in this firm.
    stmt = (
        select(
            Task.id.label("task_id"),
            Task.title.label("task_title"),
            Task.client_id,
            Client.name.label("client_name"),
            Task.engagement_id,
            Engagement.name.label("engagement_name"),
            completed_sq.c.completed_at,
            hours_sq.c.total_hours,
            star_sq.c.task_id.isnot(None).label("starred"),
        )
        .join(Client, Task.client_id == Client.id)
        .join(Engagement, Task.engagement_id == Engagement.id)
        .outerjoin(completed_sq, completed_sq.c.task_id == Task.id)
        .outerjoin(hours_sq, hours_sq.c.task_id == Task.id)
        .outerjoin(star_sq, star_sq.c.task_id == Task.id)
        .where(
            Task.firm_id == firm.id,
            Task.assigned_to == user_id,
            Task.is_completed == True,  # noqa: E712
        )
    )

    # Date filters applied against behavioral event's completed_at.
    if from_date is not None:
        from_dt = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(completed_sq.c.completed_at >= from_dt)
    if to_date is not None:
        to_dt = datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(completed_sq.c.completed_at <= to_dt)

    # Optional filters.
    if client_id is not None:
        stmt = stmt.where(Task.client_id == client_id)
    if engagement_id is not None:
        stmt = stmt.where(Task.engagement_id == engagement_id)
    if starred is True:
        stmt = stmt.where(star_sq.c.task_id.isnot(None))
    elif starred is False:
        stmt = stmt.where(star_sq.c.task_id.is_(None))

    # Fetch the full unfiltered result set first for aggregate computation.
    all_rows = db.execute(stmt).all()

    tasks_completed = len(all_rows)
    hours_logged = float(sum((r.total_hours if r.total_hours is not None else Decimal(0)) for r in all_rows))
    engagements_touched = len({r.engagement_id for r in all_rows})

    # Pagination.
    total = tasks_completed
    offset = (page - 1) * page_size
    paginated = all_rows[offset: offset + page_size]

    items = [
        {
            "task_id": str(r.task_id),
            "task_title": r.task_title,
            "client": {"id": str(r.client_id), "name": r.client_name},
            "engagement": {"id": str(r.engagement_id), "name": r.engagement_name},
            "role": "performed",
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
            "revision_count": None,
            "reviewer": None,
            "hours": float(r.total_hours) if r.total_hours is not None else 0.0,
            "starred": bool(r.starred),
        }
        for r in paginated
    ]

    return {
        "items": items,
        "total": total,
        "aggregates": {
            "tasks_completed": tasks_completed,
            "hours_logged": hours_logged,
            "engagements_touched": engagements_touched,
        },
    }


# ---------------------------------------------------------------------------
# POST /archive/entries/{task_id}/star
# ---------------------------------------------------------------------------

@router.post("/entries/{task_id}/star", status_code=status.HTTP_200_OK)
def star_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    firm: Firm = Depends(get_current_firm),
):
    # Verify the task exists in this firm and is assigned to the current user.
    task = db.execute(
        select(Task).where(Task.id == task_id, Task.firm_id == firm.id)
    ).scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.assigned_to != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You may only star tasks assigned to you.")

    # Idempotent: skip if already starred.
    existing = db.execute(
        select(ArchiveStar).where(
            ArchiveStar.user_id == current_user.id,
            ArchiveStar.task_id == task_id,
        )
    ).scalar_one_or_none()

    if existing is None:
        star = ArchiveStar(user_id=current_user.id, task_id=task_id)
        db.add(star)
        db.commit()

    return {"starred": True}


# ---------------------------------------------------------------------------
# DELETE /archive/entries/{task_id}/star
# ---------------------------------------------------------------------------

@router.delete("/entries/{task_id}/star", status_code=status.HTTP_200_OK)
def unstar_task(
    task_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    firm: Firm = Depends(get_current_firm),
):
    # Verify the task exists in this firm and is assigned to the current user.
    task = db.execute(
        select(Task).where(Task.id == task_id, Task.firm_id == firm.id)
    ).scalar_one_or_none()

    if task is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found.")
    if task.assigned_to != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You may only unstar tasks assigned to you.")

    # Idempotent: skip if not starred.
    existing = db.execute(
        select(ArchiveStar).where(
            ArchiveStar.user_id == current_user.id,
            ArchiveStar.task_id == task_id,
        )
    ).scalar_one_or_none()

    if existing is not None:
        db.delete(existing)
        db.commit()

    return {"starred": False}
