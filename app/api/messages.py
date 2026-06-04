# app/api/messages.py

from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_staff_or_above
from app.dependencies.tenant import get_current_firm
from app.models.firm import Firm
from app.models.user import User
from app.schemas.message import ClientMessageCreate, ClientMessageOut, UnreadCountOut
from app.services import message_service

router = APIRouter(prefix="/clients/{client_id}/messages", tags=["Messages"])


@router.get("", response_model=list[ClientMessageOut])
def get_messages(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """
    Return message thread for a client.
    Also marks messages as read for the requesting staff member.
    Auth: firm_owner, manager, staff
    """
    return message_service.get_messages(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        requesting_user=current_user,
    )


@router.post("", response_model=ClientMessageOut, status_code=status.HTTP_201_CREATED)
def send_message(
    client_id: UUID,
    data: ClientMessageCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """
    Send a message to a client.
    Auth: firm_owner, manager, staff
    """
    return message_service.send_message_staff(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        sender_user=current_user,
        data=data,
    )


@router.get("/unread-count", response_model=UnreadCountOut)
def get_unread_count(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    """
    Return unread message count for a client (staff perspective).
    Auth: firm_owner, manager, staff
    """
    return message_service.get_staff_unread_count(
        db,
        firm_id=current_firm.id,
        client_id=client_id,
        staff_user_id=current_user.id,
    )
