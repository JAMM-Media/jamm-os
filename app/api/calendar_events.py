# app/api/calendar_events.py

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import AwareDatetime
from sqlalchemy.orm import Session

from app.core.enums import UserRole
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.calendar_category import (
    CalendarCategoryCreate,
    CalendarCategoryOut,
    CalendarCategoryUpdate,
)
from app.schemas.calendar_event import (
    CalendarEventCreate,
    CalendarEventDeleteRequest,
    CalendarEventOut,
    CalendarEventUpdate,
)
from app.schemas.pagination import PaginatedResponse
import app.services.calendar_category_service as cat_svc
import app.services.calendar_event_service as event_svc

router = APIRouter(prefix="/calendar", tags=["calendar"])


def _enrich_event(ev) -> CalendarEventOut:
    out = CalendarEventOut.model_validate(ev)
    if ev.category:
        out.category_name = ev.category.name
        out.category_color = ev.category.color
    if ev.client:
        out.client_name = ev.client.name
    if ev.owner:
        out.owner_name = ev.owner.full_name
    return out


@router.get("/categories", response_model=PaginatedResponse[CalendarCategoryOut])
def list_categories(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
    include_inactive: bool = False,
    limit: int = Query(100, le=100),
    offset: int = 0,
):
    if include_inactive and current_user.role not in (
        UserRole.firm_owner,
        UserRole.manager,
        UserRole.system_admin,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or firm owner access required",
        )
    return cat_svc.list_categories(db, current_firm.id, include_inactive, limit, offset)


@router.post(
    "/categories",
    response_model=CalendarCategoryOut,
    status_code=status.HTTP_201_CREATED,
)
def create_category(
    payload: CalendarCategoryCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    return cat_svc.create_category(db, payload, current_firm.id, current_user.id)


@router.patch("/categories/{category_id}", response_model=CalendarCategoryOut)
def update_category(
    category_id: UUID,
    payload: CalendarCategoryUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    return cat_svc.update_category(db, category_id, payload, current_firm.id, current_user.id)


@router.get("/events", response_model=PaginatedResponse[CalendarEventOut])
def list_events(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
    from_: AwareDatetime = Query(..., alias="from"),
    to: AwareDatetime = Query(...),
    owner_user_id: Optional[UUID] = None,
    category_id: Optional[UUID] = None,
    deleted: bool = False,
    limit: int = Query(50, le=100),
    offset: int = 0,
):
    if from_ >= to:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="'from' must be before 'to'.",
        )
    if deleted and current_user.role not in (
        UserRole.firm_owner,
        UserRole.manager,
        UserRole.system_admin,
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager or firm owner access required",
        )
    result = event_svc.list_events(
        db, current_firm.id, from_, to,
        owner_user_id, category_id, deleted, current_user, limit, offset,
    )
    return {
        "total": result["total"],
        "limit": result["limit"],
        "offset": result["offset"],
        "items": [_enrich_event(ev) for ev in result["items"]],
    }


@router.get("/events/{event_id}", response_model=CalendarEventOut)
def get_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    ev = event_svc.get_event(db, current_firm.id, event_id, current_user)
    return _enrich_event(ev)


@router.post(
    "/events",
    response_model=CalendarEventOut,
    status_code=status.HTTP_201_CREATED,
)
def create_event(
    payload: CalendarEventCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    ev = event_svc.create_event(
        db, payload, current_firm.id, current_user, current_firm.timezone
    )
    return _enrich_event(ev)


@router.patch("/events/{event_id}", response_model=CalendarEventOut)
def update_event(
    event_id: UUID,
    payload: CalendarEventUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    ev = event_svc.update_event(db, event_id, payload, current_firm.id, current_user)
    return _enrich_event(ev)


@router.delete("/events/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    event_svc.delete_event(db, event_id, current_firm.id, current_user)


@router.post("/events/{event_id}/restore", response_model=CalendarEventOut)
def restore_event(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    ev = event_svc.restore_event(db, event_id, current_firm.id, current_user)
    return _enrich_event(ev)


@router.post("/events/{event_id}/delete-request", response_model=CalendarEventOut)
def request_delete_event(
    event_id: UUID,
    payload: CalendarEventDeleteRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    ev = event_svc.request_delete(db, event_id, current_firm.id, current_user, payload.reason)
    return _enrich_event(ev)


@router.post("/events/{event_id}/delete-request/approve", response_model=CalendarEventOut)
def approve_delete_request(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    ev = event_svc.approve_delete_request(db, event_id, current_firm.id, current_user)
    return _enrich_event(ev)


@router.post("/events/{event_id}/delete-request/deny", response_model=CalendarEventOut)
def deny_delete_request(
    event_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    ev = event_svc.deny_delete_request(db, event_id, current_firm.id, current_user)
    return _enrich_event(ev)
