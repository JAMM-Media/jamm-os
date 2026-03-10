# app/api/engagements.py

from datetime import date
from typing import Optional
from uuid import UUID
from sqlalchemy import select, func

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.schemas.engagement import (
    EngagementCreate,
    EngagementUpdate,
    EngagementOut,
    EngagementOverview,
)
from app.models.task import Task
from app.models.client import Client
from app.schemas.task import TaskSummary
from app.schemas.pagination import PaginatedResponse
from app.crud import engagement as crud_engagement
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above

router = APIRouter(prefix="/engagements", tags=["engagements"])


# ---------------------------------------------------------
# CREATE
# firm_id comes from the JWT via current_firm — never from the request body.
# ---------------------------------------------------------
@router.post("/", response_model=EngagementOut, status_code=status.HTTP_201_CREATED)
def create_engagement(
    payload: EngagementCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    return crud_engagement.create_engagement(db, payload, firm_id=current_firm.id)


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
    client = db.query(Client).filter(
        Client.id == engagement.client_id,
        Client.firm_id == current_firm.id,
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
def update_engagement(
    engagement_id: UUID,
    payload: EngagementUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    engagement = crud_engagement.get_engagement_for_firm(db, engagement_id, current_firm.id)
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return crud_engagement.update_engagement(db, engagement, payload)


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------
@router.delete("/{engagement_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_engagement(
    engagement_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_staff_or_above),
):
    engagement = crud_engagement.get_engagement_for_firm(db, engagement_id, current_firm.id)
    if not engagement:
        raise HTTPException(status_code=404, detail="Engagement not found")
    crud_engagement.delete_engagement(db, engagement)