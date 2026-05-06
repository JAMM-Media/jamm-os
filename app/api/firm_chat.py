# app/api/firm_chat.py

import uuid

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.models.firm import Firm
from app.models.user import User
from app.schemas.firm_chat import (
    ChannelCreate,
    ChannelMemberOut,
    ChannelOut,
    ChannelUpdate,
    FirmChatUnreadOut,
    FirmMessageCreate,
    FirmMessageOut,
)
from app.services import firm_chat_service

router = APIRouter(prefix="/firm-chat", tags=["Firm Chat"])


@router.get("/channels", response_model=list[ChannelOut])
def list_channels(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return firm_chat_service.get_channels(
        db,
        firm_id=current_firm.id,
        requesting_user_id=current_user.id,
    )


@router.post("/channels", response_model=ChannelOut, status_code=status.HTTP_201_CREATED)
def create_channel(
    data: ChannelCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return firm_chat_service.create_channel(
        db,
        firm_id=current_firm.id,
        requesting_user=current_user,
        data=data,
    )


@router.patch("/channels/{channel_id}", response_model=ChannelOut)
def rename_channel(
    channel_id: uuid.UUID,
    data: ChannelUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return firm_chat_service.update_channel(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        requesting_user=current_user,
        data=data,
    )


@router.delete("/channels/{channel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_channel(
    channel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    firm_chat_service.delete_channel(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        requesting_user=current_user,
    )


@router.get("/channels/{channel_id}/members", response_model=list[ChannelMemberOut])
def list_channel_members(
    channel_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    members = firm_chat_service.get_channel_members(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        requesting_user_id=current_user.id,
    )
    return [
        ChannelMemberOut(
            id=m.id,
            channel_id=m.channel_id,
            user_id=m.user_id,
            user_full_name=m.user.full_name if m.user else "Unknown",
            user_email=m.user.email if m.user else "",
            added_at=m.added_at,
        )
        for m in members
    ]


@router.post("/channels/{channel_id}/members", response_model=ChannelMemberOut, status_code=status.HTTP_201_CREATED)
def add_channel_member(
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    m = firm_chat_service.add_channel_member(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        user_id=user_id,
        requesting_user=current_user,
    )
    return ChannelMemberOut(
        id=m.id,
        channel_id=m.channel_id,
        user_id=m.user_id,
        user_full_name=m.user.full_name if m.user else "Unknown",
        user_email=m.user.email if m.user else "",
        added_at=m.added_at,
    )


@router.delete("/channels/{channel_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_channel_member(
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    firm_chat_service.remove_channel_member(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        user_id=user_id,
        requesting_user=current_user,
    )


@router.get("/channels/{channel_id}/messages", response_model=list[FirmMessageOut])
def get_messages(
    channel_id: uuid.UUID,
    skip: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return firm_chat_service.get_messages(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        requesting_user_id=current_user.id,
        skip=skip,
        limit=limit,
    )


@router.post(
    "/channels/{channel_id}/messages",
    response_model=FirmMessageOut,
    status_code=status.HTTP_201_CREATED,
)
def send_message(
    channel_id: uuid.UUID,
    data: FirmMessageCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return firm_chat_service.send_message(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        sender_user=current_user,
        data=data,
        attachment_key=None,
    )


@router.get("/unread", response_model=FirmChatUnreadOut)
def get_unread_summary(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    return firm_chat_service.get_unread_summary(
        db,
        firm_id=current_firm.id,
        user_id=current_user.id,
    )
