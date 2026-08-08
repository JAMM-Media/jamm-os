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
from app.dependencies.roles import require_staff_or_above, require_manager_or_above
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
# Shared query helper
# ---------------------------------------------------------------------------

def _fetch_archive_rows(
    db: Session,
    firm_id: uuid.UUID,
    star_user_id: uuid.UUID,
    assignee_id: Optional[uuid.UUID],
    from_date: Optional[date],
    to_date: Optional[date],
    client_id: Optional[uuid.UUID],
    engagement_id: Optional[uuid.UUID],
    role: Optional[str],
    starred: Optional[bool],
    search: Optional[str],
) -> list:
    """Build and execute the archive query. Returns all matching rows before pagination.

    star_user_id: whose star records to use for the starred column.
    assignee_id: if provided, scope to this person only; if None, return all staff in the firm.
    """
    # Subquery: most recent task.completed event per task entity_id.
    completed_sq = (
        select(
            BehavioralEvent.entity_id.label("task_id"),
            func.max(BehavioralEvent.occurred_at).label("completed_at"),
        )
        .where(
            BehavioralEvent.firm_id == firm_id,
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
        .where(TimeEntry.firm_id == firm_id)
        .group_by(TimeEntry.task_id)
        .subquery()
    )

    # Subquery: starred task ids for the viewer (personal marking, not task owner's).
    star_sq = (
        select(ArchiveStar.task_id)
        .where(ArchiveStar.user_id == star_user_id)
        .subquery()
    )

    stmt = (
        select(
            Task.id.label("task_id"),
            Task.title.label("task_title"),
            Task.assigned_to.label("assignee_user_id"),
            User.full_name.label("assignee_name"),
            Task.client_id,
            Client.name.label("client_name"),
            Task.engagement_id,
            Engagement.name.label("engagement_name"),
            func.coalesce(completed_sq.c.completed_at, Task.updated_at).label("effective_completed_at"),
            completed_sq.c.completed_at.is_(None).label("completed_at_is_approximate"),
            hours_sq.c.total_hours,
            star_sq.c.task_id.isnot(None).label("starred"),
        )
        .join(Client, Task.client_id == Client.id)
        .join(Engagement, Task.engagement_id == Engagement.id)
        .outerjoin(User, Task.assigned_to == User.id)
        .outerjoin(completed_sq, completed_sq.c.task_id == Task.id)
        .outerjoin(hours_sq, hours_sq.c.task_id == Task.id)
        .outerjoin(star_sq, star_sq.c.task_id == Task.id)
        .where(
            Task.firm_id == firm_id,
            Task.is_completed == True,  # noqa: E712
        )
    )

    if assignee_id is not None:
        stmt = stmt.where(Task.assigned_to == assignee_id)

    # Date filters use the effective date (real event or Task.updated_at fallback).
    if from_date is not None:
        from_dt = datetime.combine(from_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(func.coalesce(completed_sq.c.completed_at, Task.updated_at) >= from_dt)
    if to_date is not None:
        to_dt = datetime.combine(to_date, datetime.max.time()).replace(tzinfo=timezone.utc)
        stmt = stmt.where(func.coalesce(completed_sq.c.completed_at, Task.updated_at) <= to_dt)

    # Optional filters.
    if search is not None:
        stmt = stmt.where(Task.title.ilike(f"%{search}%"))
    if client_id is not None:
        stmt = stmt.where(Task.client_id == client_id)
    if engagement_id is not None:
        stmt = stmt.where(Task.engagement_id == engagement_id)
    if starred is True:
        stmt = stmt.where(star_sq.c.task_id.isnot(None))
    elif starred is False:
        stmt = stmt.where(star_sq.c.task_id.is_(None))

    return db.execute(stmt).all()


def _build_response(all_rows: list, page: int, page_size: int, include_assignee: bool) -> dict:
    """Paginate rows, compute aggregates, and serialize to the response envelope."""
    tasks_completed = len(all_rows)
    hours_logged = float(sum((r.total_hours if r.total_hours is not None else Decimal(0)) for r in all_rows))
    engagements_touched = len({r.engagement_id for r in all_rows})

    offset = (page - 1) * page_size
    paginated = all_rows[offset: offset + page_size]

    items = []
    for r in paginated:
        row: dict = {
            "task_id": str(r.task_id),
            "task_title": r.task_title,
            "client": {"id": str(r.client_id), "name": r.client_name},
            "engagement": {"id": str(r.engagement_id), "name": r.engagement_name},
            "role": "performed",
            "completed_at": r.effective_completed_at.isoformat() if r.effective_completed_at else None,
            "completed_at_is_approximate": bool(r.completed_at_is_approximate),
            "revision_count": None,
            "reviewer": None,
            "hours": float(r.total_hours) if r.total_hours is not None else 0.0,
            "starred": bool(r.starred),
        }
        if include_assignee:
            row["assignee"] = {
                "id": str(r.assignee_user_id) if r.assignee_user_id else None,
                "name": r.assignee_name,
            }
        items.append(row)

    return {
        "items": items,
        "total": tasks_completed,
        "aggregates": {
            "tasks_completed": tasks_completed,
            "hours_logged": hours_logged,
            "engagements_touched": engagements_touched,
        },
    }


# ---------------------------------------------------------------------------
# GET /archive/ -- combined all-staff view, manager/owner only
# ---------------------------------------------------------------------------

@router.get("/")
def get_all_archive(
    from_date: Optional[date] = Query(None, alias="from"),
    to_date: Optional[date] = Query(None, alias="to"),
    client_id: Optional[uuid.UUID] = Query(None),
    engagement_id: Optional[uuid.UUID] = Query(None),
    role: Optional[str] = Query(None),
    starred: Optional[bool] = Query(None),
    search: Optional[str] = Query(None),
    assignee_id: Optional[uuid.UUID] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
    firm: Firm = Depends(get_current_firm),
):
    if role == "reviewed":
        return {"items": [], "total": 0, "aggregates": {"tasks_completed": 0, "hours_logged": 0.0, "engagements_touched": 0}}

    all_rows = _fetch_archive_rows(
        db=db,
        firm_id=firm.id,
        star_user_id=current_user.id,
        assignee_id=assignee_id,
        from_date=from_date,
        to_date=to_date,
        client_id=client_id,
        engagement_id=engagement_id,
        role=role,
        starred=starred,
        search=search,
    )
    return _build_response(all_rows, page, page_size, include_assignee=True)


# ---------------------------------------------------------------------------
# GET /archive/{user_id} -- single-person view, staff see only their own
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
    search: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    firm: Firm = Depends(get_current_firm),
):
    # Role-scoped access: staff can only view their own archive.
    if current_user.role == UserRole.staff and current_user.id != user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Staff may only view their own archive.")

    if role == "reviewed":
        return {"items": [], "total": 0, "aggregates": {"tasks_completed": 0, "hours_logged": 0.0, "engagements_touched": 0}}

    all_rows = _fetch_archive_rows(
        db=db,
        firm_id=firm.id,
        star_user_id=user_id,
        assignee_id=user_id,
        from_date=from_date,
        to_date=to_date,
        client_id=client_id,
        engagement_id=engagement_id,
        role=role,
        starred=starred,
        search=search,
    )
    return _build_response(all_rows, page, page_size, include_assignee=False)


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
