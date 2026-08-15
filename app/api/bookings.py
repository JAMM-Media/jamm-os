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
from app.schemas.booking import BookingOut
from app.services.booking_service import create_booking

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
