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
    BulkEngagementCreate,
    BulkEngagementCreateResult,
    BulkSendLetterRequest,
    BulkSendLetterResult,
    ComplexityFlagsUpdate,
)
from app.models.task import Task
from app.models.client import Client as ClientModel
from app.schemas.task import TaskSummary
from app.schemas.pagination import PaginatedResponse
from app.crud import engagement as crud_engagement
from app.dependencies.auth import get_current_user
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above, require_firm_owner, require_manager_or_above
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
    changed = []
    for eng in engagements:
        old_status = eng.status
        old_filing = eng.filing_deadline
        old_extended = eng.extended_deadline
        if payload.update.status is not None:
            eng.status = payload.update.status
        if payload.update.deadline_push_days is not None:
            delta = timedelta(days=payload.update.deadline_push_days)
            if eng.extended_deadline is not None:
                eng.extended_deadline = eng.extended_deadline + delta
            elif eng.filing_deadline is not None:
                eng.filing_deadline = eng.filing_deadline + delta
        changed.append((eng, old_status, old_filing, old_extended))
    db.commit()

    from app.services.behavioral_log import log_event
    for eng, old_status, old_filing, old_extended in changed:
        if payload.update.status is not None and eng.status != old_status:
            log_event(
                firm_id=current_firm.id,
                event_type="engagement.status_changed",
                entity_type="engagement",
                entity_id=eng.id,
                actor_type="staff",
                actor_id=None,
                metadata={
                    "from_status": str(old_status),
                    "to_status": str(eng.status),
                    "via": "bulk",
                }
            )
        if eng.filing_deadline != old_filing or eng.extended_deadline != old_extended:
            log_event(
                firm_id=current_firm.id,
                event_type="engagement.deadline_changed",
                entity_type="engagement",
                entity_id=eng.id,
                actor_type="staff",
                actor_id=None,
                metadata={
                    "from_filing_deadline": old_filing.isoformat() if old_filing else None,
                    "to_filing_deadline": eng.filing_deadline.isoformat() if eng.filing_deadline else None,
                    "from_extended_deadline": old_extended.isoformat() if old_extended else None,
                    "to_extended_deadline": eng.extended_deadline.isoformat() if eng.extended_deadline else None,
                    "via": "bulk",
                    "push_days": payload.update.deadline_push_days,
                }
            )

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
            assigned_to=eng.assigned_to if hasattr(eng, 'assigned_to') else None,
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


# ---------------------------------------------------------
# UPDATE COMPLEXITY FLAGS
# ---------------------------------------------------------
@router.patch("/{engagement_id}/complexity_flags", response_model=EngagementOut)
def update_complexity_flags(
    engagement_id: UUID,
    payload: ComplexityFlagsUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_manager_or_above),
):
    result = engagement_service.update_complexity_flags(
        db=db,
        engagement_id=engagement_id,
        firm_id=current_firm.id,
        flags=payload.flags,
        current_user_id=current_user.id,
    )
    if not result:
        raise HTTPException(status_code=404, detail="Engagement not found")
    return result


# ---------------------------------------------------------
# BULK CREATE ENGAGEMENTS
# ---------------------------------------------------------
@router.post("/bulk-create", response_model=BulkEngagementCreateResult, status_code=status.HTTP_201_CREATED)
def bulk_create_engagements(
    payload: BulkEngagementCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_staff_or_above),
):
    from app.services.audit_service import write_audit_log
    from sqlalchemy import select as _select

    created_ids = []
    skipped = 0

    for client_id in payload.client_ids:
        client = db.execute(
            _select(ClientModel).where(
                ClientModel.id == client_id,
                ClientModel.firm_id == current_firm.id,
            )
        ).scalars().first()
        if not client:
            skipped += 1
            continue

        eng_create = EngagementCreate(
            client_id=client.id,
            name=payload.name,
            engagement_type=payload.engagement_type,
            status=payload.status,
            start_date=payload.start_date,
            end_date=payload.end_date,
            notes=payload.notes,
            filing_deadline=payload.filing_deadline,
        )
        engagement = crud_engagement.create_engagement(db, eng_create, firm_id=current_firm.id)

        write_audit_log(
            db=db,
            firm_id=current_firm.id,
            action="engagement.bulk_created",
            actor_id=current_user.id,
            actor_type="staff",
            entity_type="engagement",
            entity_id=engagement.id,
        )
        created_ids.append(engagement.id)

    return BulkEngagementCreateResult(
        created=len(created_ids),
        engagement_ids=created_ids,
        skipped=skipped,
    )


# ---------------------------------------------------------
# BULK SEND ENGAGEMENT LETTER
# ---------------------------------------------------------
@router.post("/bulk-send-letter", response_model=BulkSendLetterResult)
def bulk_send_letter(
    payload: BulkSendLetterRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(get_current_user),
    _: object = Depends(require_manager_or_above),
):
    from sqlalchemy import select as _select
    from app.crud import engagement_letter_template as crud_template
    from app.services import esign_service

    template = crud_template.get_template(db, payload.template_id, current_firm.id)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    sent = 0
    failed = 0
    errors = []

    for engagement_id in payload.engagement_ids:
        engagement = db.execute(
            _select(Engagement).where(
                Engagement.id == engagement_id,
                Engagement.firm_id == current_firm.id,
            )
        ).scalars().first()
        if not engagement:
            continue

        client = db.execute(
            _select(ClientModel).where(
                ClientModel.id == engagement.client_id,
                ClientModel.firm_id == current_firm.id,
            )
        ).scalars().first()
        if not client:
            errors.append(f"Engagement {engagement.name}: client not found")
            failed += 1
            continue

        if not client.email:
            errors.append(f"Client {client.name}: no email address")
            failed += 1
            continue

        try:
            envelope = esign_service.prepare_and_create_envelope(
                db=db,
                firm=current_firm,
                engagement=engagement,
                template=template,
                current_user=current_user,
                fee_amount=payload.fee_amount or "",
                extra_context={},
            )
            esign_service.send_envelope_to_dropbox(
                db=db,
                firm=current_firm,
                envelope=envelope,
                current_user=current_user,
            )
            sent += 1
        except Exception as exc:
            errors.append(f"Client {client.name}: {str(exc)}")
            failed += 1
            continue

    return BulkSendLetterResult(sent=sent, failed=failed, errors=errors)