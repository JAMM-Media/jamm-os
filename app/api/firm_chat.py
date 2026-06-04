# app/api/firm_chat.py

import uuid

from fastapi import (
    APIRouter,
    Body,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_staff_or_above
from app.models.firm import Firm
from app.models.firm_chat import FirmMessage
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
from app.services.s3 import generate_presigned_put_url, generate_presigned_url

ALLOWED_FILE_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "text/csv",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
}
MAX_FILE_SIZE = 26_214_400  # 25 MB


class UploadUrlRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int


class UploadUrlResponse(BaseModel):
    upload_url: str
    key: str


class DownloadUrlResponse(BaseModel):
    download_url: str
    file_name: str
    file_size: int
    file_type: str

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
        attachment_key=data.attachment_key,
    )


@router.post(
    "/channels/{channel_id}/upload-url",
    response_model=UploadUrlResponse,
    status_code=status.HTTP_200_OK,
)
def get_upload_url(
    channel_id: uuid.UUID,
    body: UploadUrlRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    from app.crud import firm_chat as crud
    channel = crud.get_channel_by_id(db, channel_id=channel_id, firm_id=current_firm.id)
    if channel is None or channel.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Channel not found")

    if body.file_size > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be 25 MB or smaller",
        )
    if body.file_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File type not allowed",
        )

    key = f"firm-chat/{current_firm.id}/{channel_id}/{uuid.uuid4()}/{body.file_name}"
    upload_url = generate_presigned_put_url(key, body.file_type)
    return UploadUrlResponse(upload_url=upload_url, key=key)


@router.get("/messages/{message_id}/attachment-url", response_model=DownloadUrlResponse)
def get_attachment_url(
    message_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    from app.crud import firm_chat as crud
    message = crud.get_message_by_id(db, message_id=message_id, firm_id=current_firm.id)
    if message is None or message.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")
    if not message.attachment_key:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message has no attachment")

    download_url = generate_presigned_url(message.attachment_key)
    return DownloadUrlResponse(
        download_url=download_url,
        file_name=message.attachment_name or "",
        file_size=message.attachment_size or 0,
        file_type=message.attachment_type or "",
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
