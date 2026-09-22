# app/api/engagement_pins.py
import uuid

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.services import engagement_pins_service

router = APIRouter(prefix="/engagements", tags=["engagement-pins"])


class PinCreate(BaseModel):
    item_type: str
    item_id: uuid.UUID


@router.post("/{engagement_id}/pins", status_code=status.HTTP_201_CREATED)
def add_pin(
    engagement_id: uuid.UUID,
    payload: PinCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Pin a document or folder to this engagement. Restricted to administrators, managers, and owners."""
    pin = engagement_pins_service.add_pin(
        db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        item_type=payload.item_type,
        item_id=payload.item_id,
        user=current_user,
    )
    return {"id": str(pin.id), "item_type": pin.item_type, "item_id": str(pin.item_id)}


@router.delete("/{engagement_id}/pins/{item_type}/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_pin(
    engagement_id: uuid.UUID,
    item_type: str,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Remove a pin. No error if not currently pinned (idempotent)."""
    engagement_pins_service.remove_pin(
        db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        item_type=item_type,
        item_id=item_id,
        user=current_user,
    )


@router.get("/{engagement_id}/pins")
def list_pins(
    engagement_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """Return pins for this engagement. Readable by all engagement members."""
    return engagement_pins_service.list_pins(
        db,
        firm_id=current_firm.id,
        engagement_id=engagement_id,
        user=current_user,
    )
