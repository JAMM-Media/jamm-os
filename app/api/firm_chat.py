# app/api/firm_chat.py

import json
import uuid
from typing import Optional

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    UploadFile,
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
    ChannelOut,
    ChannelUpdate,
    FirmChatUnreadOut,
    FirmMessageCreate,
    FirmMessageOut,
)
from app.services import firm_chat_service
from app.services.s3 import upload_fileobj

router = APIRouter(prefix="/firm-chat", tags=["Firm Chat"])

# Allowed attachment extensions and max size
ALLOWED_EXTENSIONS = {"pdf", "jpg", "jpeg", "png", "xlsx", "csv", "docx"}
MAX_ATTACHMENT_BYTES = 25 * 1024 * 1024  # 25 MB


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
async def send_message(
    channel_id: uuid.UUID,
    body: str = Form(...),
    mentions: str = Form("[]"),
    attachment: Optional[UploadFile] = File(None),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_staff_or_above),
):
    # Parse mentions from JSON string
    try:
        raw_mentions = json.loads(mentions)
        mentions_list = [uuid.UUID(str(m)) for m in raw_mentions]
    except (json.JSONDecodeError, ValueError):
        mentions_list = []

    data = FirmMessageCreate(body=body, mentions=mentions_list)

    # Handle optional file attachment
    attachment_key: Optional[str] = None
    if attachment is not None and attachment.filename:
        ext = attachment.filename.rsplit(".", 1)[-1].lower() if "." in attachment.filename else ""
        if ext not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"File type '.{ext}' not allowed. Allowed: {sorted(ALLOWED_EXTENSIONS)}",
            )

        content = await attachment.read()
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Attachment exceeds 25 MB limit",
            )

        # Generate a deterministic S3 key with message UUID pre-allocated
        message_id = uuid.uuid4()
        attachment_key = (
            f"firm-chat/{current_firm.id}/{channel_id}/{message_id}/{attachment.filename}"
        )

        import io
        upload_fileobj(
            io.BytesIO(content),
            s3_key=attachment_key,
            content_type=attachment.content_type or "application/octet-stream",
        )

    return firm_chat_service.send_message(
        db,
        firm_id=current_firm.id,
        channel_id=channel_id,
        sender_user=current_user,
        data=data,
        attachment_key=attachment_key,
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
