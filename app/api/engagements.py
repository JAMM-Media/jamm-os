# app/api/engagements.py

from datetime import date, timedelta
from typing import Optional
from uuid import UUID
from sqlalchemy import select, func

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.schemas.engagement import (
    EngagementCreate,
    EngagementUpdate,
    EngagementOut,
    EngagementOverview,
    DeadlineWatchItem,
    BulkEngagementUpdate,
    CalendarEngagementItem,
    CalendarResponse,
)
from app.models.task import Task
from app.models.client import Client as ClientModel
from app.schemas.task import TaskSummary
from app.schemas.pagination import PaginatedResponse
from app.crud import engagement as crud_engagement
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_firm_owner
from app.models.user import User
from app.core.enums import TriggerEvent
from app.services.event_bus import emit_event
from app.services.deadline_scheduler import check_approaching_deadlines
import app.services.engagement_service as engagement_service

router = APIRouter(prefix="/engagements", tags=["engagements"])


# ---------------------------------------------------------
# CREATE
# firm_id comes from the JWT via current_firm — never from the request body.
# ---------------------------------------------------------
@router.post("/", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
async def create_engagement(
    payload: EngagementCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    return await engagement_service.create_engagement(
        db=db, payload=payload, firm_id=current_firm.id,
        current_user_id=current_user.id,
        background_tasks=background_tasks,
    )


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[EngagementOut])
def list_engagements(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
    client_id: Optional[UUID] = None,
    status_filter: Optional[str] = None,
    start_before: Optional[date] = None,
    start_after: Optional[date] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
):
    # firm_id filter is ALWAYS the first WHERE clause.
    stmt = select(Engagement).where(Engagement.firm_id == current_firm.id)

    if client_id:
        stmt = stmt.where(Engagement.client_id == client_id)
    if status_filter:
        stmt = stmt.where(Engagement.status == status_filter)
    if start_before:
        stmt = stmt.where(Engagement.start_date <= start_before)
    if start_after:
        stmt = stmt.where(Engagement.start_date >= start_after)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = db.execute(count_stmt).scalar_one()

    stmt = stmt.order_by(Engagement.start_date.is_(None), Engagement.start_date)
    stmt = stmt.offset(offset).limit(limit)
    items = db.execute(stmt).scalars().all()

    return PaginatedResponse(total=total, limit=limit, offset=offset, items=items)


# ---------------------------------------------------------
# DEADLINE WATCH
# ---------------------------------------------------------
@router.get("/deadline-watch", response_model=list[DeadlineWatchItem])
def deadline_watch(
    days: int = Query(60, ge=1, le=365),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    """
    Returns all active engagements with a filing or extended deadline
    within the next N days (default 60). Used by the dashboard
    Tax Deadline Watch section.

    effective_deadline = extended_deadline if set, else filing_deadline.
    Excludes completed and archived engagements.
    """
    today = date.today()
    window_end = today + timedelta(days=days)

    stmt = (
        select(Engagement)
        .where(
            Engagement.firm_id == current_firm.id,
            Engagement.status.notin_(["completed", "archived"]),
            Engagement.is_active == True,
        )
    )

    engagements = db.execute(stmt).scalars().all()

    results = []
    for eng in engagements:
        effective = eng.extended_deadline or eng.filing_deadline
        if not effective:
            continue
        if not (today <= effective <= window_end):
            continue

        days_remaining = (effective - today).days

        # Fetch client name — always scoped to firm
        client = db.execute(
            select(ClientModel).where(
                ClientModel.id == eng.client_id,
                ClientModel.firm_id == current_firm.id,
            )
        ).scalars().first()

        results.append(DeadlineWatchItem(
            engagement_id=eng.id,
            engagement_name=eng.name,
            client_id=eng.client_id,
            client_name=client.name if client else "Unknown",
            engagement_type=eng.engagement_type,
            filing_deadline=eng.filing_deadline,
            extended_deadline=eng.extended_deadline,
            effective_deadline=effective,
            days_remaining=days_remaining,
            status=eng.status,
        ))

    # Sort by days_remaining ascending (most urgent first)
    results.sort(key=lambda x: x.days_remaining)
    return results


# ---------------------------------------------------------
# RUN DEADLINE CHECK
# ---------------------------------------------------------
@router.post("/run-deadline-check", status_code=200)
def run_deadline_check(
    background_tasks: BackgroundTasks,
    _: object = Depends(require_firm_owner),
    current_firm: Firm = Depends(get_current_firm),
):
    """
    Manually trigger the deadline check job.
    Firm owner only. Runs as a background task.
    """
    background_tasks.add_task(check_approaching_deadlines)
    return {"message": "Deadline check job queued"}


# ---------------------------------------------------------
# BULK UPDATE ENGAGEMENTS
# ---------------------------------------------------------
@router.patch("/bulk")
def bulk_update_engagements(
    payload: BulkEngagementUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    stmt = select(Engagement).where(
        Engagement.id.in_(payload.ids),
        Engagement.firm_id == current_firm.id,
    )
    engagements = db.execute(stmt).scalars().all()
    for eng in engagements:
        if payload.update.status is not None:
            eng.status = payload.update.status
        if payload.update.deadline_push_days is not None:
            delta = timedelta(days=payload.update.deadline_push_days)
            if eng.extended_deadline is not None:
                eng.extended_deadline = eng.extended_deadline + delta
            elif eng.filing_deadline is not None:
                eng.filing_deadline = eng.filing_deadline + delta
    db.commit()
    return {"updated": len(engagements)}


# ---------------------------------------------------------
# 6-MONTH DEADLINE CALENDAR
# ---------------------------------------------------------
@router.get("/calendar", response_model=CalendarResponse)
def get_engagement_calendar(
    days: int = Query(180, ge=1, le=365),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    today = date.today()
    window_end = today + timedelta(days=days)

    stmt = select(Engagement).where(
        Engagement.firm_id == current_firm.id,
        Engagement.status.notin_(["completed", "archived"]),
    )
    engagements = db.execute(stmt).scalars().all()

    results = []
    for eng in engagements:
        if eng.extended_deadline is not None:
            effective = eng.extended_deadline
            deadline_type = "extended"
        elif eng.filing_deadline is not None:
            effective = eng.filing_deadline
            deadline_type = "filing"
        else:
            continue

        if not (effective >= today and effective <= window_end):
            continue

        client = db.execute(
            select(ClientModel).where(
                ClientModel.id == eng.client_id,
                ClientModel.firm_id == current_firm.id,
            )
        ).scalars().first()

        results.append(CalendarEngagementItem(
            engagement_id=eng.id,
            engagement_name=eng.name,
            engagement_type=eng.engagement_type,
            client_id=eng.client_id,
            client_name=client.name if client else "Unknown",
            effective_deadline=effective,
            deadline_type=deadline_type,
            status=eng.status,
        ))

    results.sort(key=lambda x: x.effective_deadline)
    return CalendarResponse(items=results)


# ---------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------
@router.get("/{engagement_id}", response_model=EngagementOut)
def get_engagement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    engagement = crud_engagement.get_engagement_for_firm(db, engagement_id, current_firm.id)
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return engagement


# ---------------------------------------------------------
# OVERVIEW
# ---------------------------------------------------------
@router.get("/{engagement_id}/overview", response_model=EngagementOverview)
def get_engagement_overview(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    engagement = crud_engagement.get_engagement_for_firm(db, engagement_id, current_firm.id)
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")

    # Fetch client — verify it also belongs to this firm
    client = db.query(ClientModel).filter(
        ClientModel.id == engagement.client_id,
        ClientModel.firm_id == current_firm.id,
    ).first()

    tasks = db.execute(
        select(Task).where(
            Task.engagement_id == engagement_id,
            Task.firm_id == current_firm.id,
        )
    ).scalars().all()

    return EngagementOverview(engagement=engagement, client=client, tasks=tasks)


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------
@router.patch("/{engagement_id}", response_model=EngagementOut)
async def update_engagement(
    engagement_id: UUID,
    payload: EngagementUpdate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    result = await engagement_service.update_engagement(
        db=db, engagement_id=engagement_id, payload=payload,
        firm_id=current_firm.id, current_user_id=current_user.id,
        background_tasks=background_tasks,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return result


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------
@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_engagement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    result = engagement_service.delete_engagement(
        db=db, engagement_id=engagement_id,
        firm_id=current_firm.id, current_user_id=current_user.id,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="Engagement not found")