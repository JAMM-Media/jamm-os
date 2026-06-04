# app/api/time_entries.py

from datetime import date as date_type
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above, require_staff_or_above
from app.models.firm import Firm
from app.models.user import User
from app.schemas.time_entry import (
    SubmittedEditPayload,
    TimeEntryCreate,
    TimeEntryOut,
    TimeEntryUpdate,
    TimesheetSummaryRow,
)
from app.schemas.pagination import PaginatedResponse
from app.core.enums import UserRole
from app.crud import time_entry as crud_time_entry
import app.services.time_entry_service as time_entry_service

router = APIRouter()


# ---------------------------------------------------------
# CREATE
# ---------------------------------------------------------
@router.post("/", response_model=TimeEntryOut, status_code=status.HTTP_201_CREATED)
def create_time_entry(
    payload: TimeEntryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    return time_entry_service.create_time_entry(
        db=db, payload=payload, firm_id=current_user.firm_id,
        current_user=current_user,
    )


# ---------------------------------------------------------
# LIST
# ---------------------------------------------------------
@router.get("/", response_model=PaginatedResponse[TimeEntryOut])
def list_time_entries(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    engagement_id: Optional[UUID] = None,
    user_id: Optional[UUID] = None,
    is_billable: Optional[bool] = None,
    is_billed: Optional[bool] = None,
    entry_date: Optional[date_type] = Query(None, alias="date"),
    start_date: Optional[date_type] = None,
    end_date: Optional[date_type] = None,
):
    if current_user.role == UserRole.staff:
        user_id = current_user.id

    items = crud_time_entry.get_time_entries(
        db,
        firm_id=current_user.firm_id,
        skip=skip,
        limit=limit,
        engagement_id=engagement_id,
        user_id=user_id,
        is_billable=is_billable,
        is_billed=is_billed,
        entry_date=entry_date,
        start_date=start_date,
        end_date=end_date,
    )
    total = crud_time_entry.get_time_entries_count(
        db,
        firm_id=current_user.firm_id,
        engagement_id=engagement_id,
        user_id=user_id,
        is_billable=is_billable,
        is_billed=is_billed,
        entry_date=entry_date,
        start_date=start_date,
        end_date=end_date,
    )
    return PaginatedResponse(total=total, limit=limit, offset=skip, items=items)


# ---------------------------------------------------------
# SUBMIT DAY — must be before /{entry_id} routes
# ---------------------------------------------------------
@router.post("/submit-day")
def submit_day(
    payload: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    try:
        entry_date = date_type.fromisoformat(str(payload.get("date", "")))
    except (ValueError, TypeError):
        raise HTTPException(status_code=422, detail="Invalid date format. Use YYYY-MM-DD.")

    count, error = time_entry_service.submit_day(
        db=db, firm_id=current_user.firm_id,
        current_user=current_user, entry_date=entry_date,
    )
    if error == "no_entries":
        raise HTTPException(status_code=400, detail="No unsubmitted entries for this date")

    return {"submitted_count": count, "date": str(entry_date)}


# ---------------------------------------------------------
# SUMMARY — must be before /{entry_id} routes
# ---------------------------------------------------------
@router.get("/summary", response_model=list[TimesheetSummaryRow])
def get_timesheet_summary(
    start_date: date_type = Query(...),
    end_date: date_type = Query(...),
    user_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    if current_user.role == UserRole.staff:
        user_id = current_user.id

    return time_entry_service.get_timesheet_summary(
        db=db,
        firm_id=current_user.firm_id,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        current_user=current_user,
    )


# ---------------------------------------------------------
# EXPORT CSV — must be before /{entry_id} routes
# ---------------------------------------------------------
@router.get("/export")
def export_timesheets(
    start_date: date_type = Query(...),
    end_date: date_type = Query(...),
    user_id: Optional[UUID] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    return time_entry_service.get_csv_export(
        db=db,
        firm_id=current_user.firm_id,
        start_date=start_date,
        end_date=end_date,
        user_id=user_id,
        current_user=current_user,
    )


# ---------------------------------------------------------
# TIMESHEET SETTINGS — must be before /{entry_id} routes
# ---------------------------------------------------------
@router.get("/settings")
def get_timesheet_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    from sqlalchemy import select
    firm = db.execute(
        select(Firm).where(Firm.id == current_user.firm_id)
    ).scalar_one_or_none()
    approval_required = getattr(firm, "timesheet_approval_required", False) if firm else False
    return {"approval_required": bool(approval_required)}


# ---------------------------------------------------------
# GET SINGLE
# ---------------------------------------------------------
@router.get("/{entry_id}", response_model=TimeEntryOut)
def get_time_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    entry = crud_time_entry.get_time_entry(db, entry_id, firm_id=current_user.firm_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Time entry not found")
    if current_user.role == UserRole.staff and entry.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")
    return entry


# ---------------------------------------------------------
# UPDATE
# ---------------------------------------------------------
@router.patch("/{entry_id}", response_model=TimeEntryOut)
def update_time_entry(
    entry_id: UUID,
    payload: TimeEntryUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    result, error = time_entry_service.update_time_entry(
        db=db, entry_id=entry_id, payload=payload,
        firm_id=current_user.firm_id, current_user=current_user,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Time entry not found")
    if error == "access_denied":
        raise HTTPException(status_code=403, detail="Access denied")
    if error == "billed":
        raise HTTPException(status_code=400, detail="Cannot modify a billed time entry")
    return result


# ---------------------------------------------------------
# DELETE
# ---------------------------------------------------------
@router.delete("/{entry_id}")
def delete_time_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    result, error = time_entry_service.delete_time_entry(
        db=db, entry_id=entry_id,
        firm_id=current_user.firm_id, current_user=current_user,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Time entry not found")
    if error == "billed":
        raise HTTPException(status_code=400, detail="Cannot delete a billed time entry")
    return {"message": "Time entry deleted"}


# ---------------------------------------------------------
# EDIT SUBMITTED ENTRY
# ---------------------------------------------------------
@router.patch("/{entry_id}/submitted-edit", response_model=TimeEntryOut)
def edit_submitted_entry(
    entry_id: UUID,
    payload: SubmittedEditPayload,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_staff_or_above),
):
    result, error = time_entry_service.edit_submitted_entry(
        db=db, entry_id=entry_id, payload=payload,
        firm_id=current_user.firm_id, current_user=current_user,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Time entry not found")
    if error == "not_submitted":
        raise HTTPException(
            status_code=400,
            detail="Entry has not been submitted — use the regular edit endpoint",
        )
    if error == "access_denied":
        raise HTTPException(status_code=403, detail="Access denied")
    return result


# ---------------------------------------------------------
# APPROVE SUBMITTED ENTRY
# ---------------------------------------------------------
@router.post("/{entry_id}/approve", response_model=TimeEntryOut)
def approve_time_entry(
    entry_id: UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_manager_or_above),
):
    result, error = time_entry_service.approve_entry(
        db=db, entry_id=entry_id,
        firm_id=current_user.firm_id, current_user=current_user,
    )
    if error == "not_found":
        raise HTTPException(status_code=404, detail="Time entry not found")
    if error == "not_submitted":
        raise HTTPException(status_code=400, detail="Entry has not been submitted")
    return result
