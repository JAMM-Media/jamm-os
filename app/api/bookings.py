# app/api/bookings.py

"""
Staff-facing booking endpoint.

Public unauthenticated lead self-booking is deferred -- it depends on the
public intake config endpoint (Andrew's work) and is a separate future task.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from typing import Literal

from app.schemas.booking import BookingOut
from app.services.booking_service import create_booking
from app.services.booking_outcome_service import mark_booking_outcome

router = APIRouter(prefix="/api/v1/bookings", tags=["Bookings"])


class BookingCreateRequest(BaseModel):
    lead_id: UUID
    staff_user_id: UUID
    start_time: datetime
    end_time: datetime


@router.post("/", response_model=BookingOut, status_code=status.HTTP_201_CREATED)
def create_booking_endpoint(
    payload: BookingCreateRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Claim a slot and create a booking for a lead.

    Re-validates that the slot is still free at the moment of booking using a
    database-level row lock. Returns the created Booking on success.
    Returns 400 if the slot is no longer available, the daily cap is reached,
    or the lead is not in a bookable stage.
    """
    try:
        booking = create_booking(
            db=db,
            firm_id=current_firm.id,
            lead_id=payload.lead_id,
            staff_user_id=payload.staff_user_id,
            start_time=payload.start_time,
            end_time=payload.end_time,
            actor_user_id=current_user.id,
        )
        return booking
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


class BookingOutcomeRequest(BaseModel):
    outcome: Literal["call_held", "not_a_fit", "no_show"]


@router.post("/{booking_id}/outcome", response_model=BookingOut)
def mark_outcome_endpoint(
    booking_id: UUID,
    payload: BookingOutcomeRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Record the call outcome for a past-end booking.

    The outcome drives three mutually exclusive branches:
      call_held  -- marks booking completed; reactivates any paused_reply enrollment.
      not_a_fit  -- marks booking completed; transitions lead to lost (lost_reason=other).
      no_show    -- marks booking no_show; fires call_no_show event with cap metadata.

    Returns 400 if the booking is not found, is already resolved, or the outcome
    task has already been marked.
    """
    try:
        booking = mark_booking_outcome(
            db=db,
            booking_id=booking_id,
            firm_id=current_firm.id,
            outcome=payload.outcome,
            actor_user_id=current_user.id,
        )
        return booking
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
