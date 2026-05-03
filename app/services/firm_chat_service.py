# app/services/firm_chat_service.py

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import firm_chat as crud
from app.models.user import User
from app.schemas.firm_chat import (
    ChannelCreate,
    ChannelOut,
    ChannelUpdate,
    FirmChatUnreadOut,
    FirmMessageCreate,
    FirmMessageOut,
)
from app.core.enums import UserRole
from app.services.s3 import generate_presigned_url
from app.services.behavioral_log import log_event


def _enrich_message(msg_out: FirmMessageOut, db: Session) -> FirmMessageOut:
    """Populate sender_name and attachment_url on a FirmMessageOut."""
    if msg_out.sender_id:
        stmt = select(User).where(User.id == msg_out.sender_id)
        user = db.execute(stmt).scalar_one_or_none()
        if user and user.full_name:
            msg_out.sender_name = user.full_name

    if msg_out.attachment_key:
        try:
            msg_out.attachment_url = generate_presigned_url(msg_out.attachment_key)
        except Exception:
            # S3 not available in all environments — skip silently
            pass

    return msg_out


def get_channels(
    db: Session,
    firm_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
) -> list[ChannelOut]:
    channels = crud.get_channels(db, firm_id=firm_id, include_deleted=False)
    result = []
    for ch in channels:
        ch_out = ChannelOut.model_validate(ch)
        ch_out.unread_count = crud.get_unread_count_for_channel(
            db, channel_id=ch.id, user_id=requesting_user_id
        )
        result.append(ch_out)
    return result


def create_channel(
    db: Session,
    firm_id: uuid.UUID,
    requesting_user: User,
    data: ChannelCreate,
) -> ChannelOut:
    if requesting_user.role not in (UserRole.firm_owner, UserRole.system_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only firm owners can create channels",
        )

    # Normalize: lowercase, spaces → hyphens, strip whitespace
    normalized_name = data.name.strip().lower().replace(" ", "-")

    existing = crud.get_channel_by_name(db, firm_id=firm_id, name=normalized_name)
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A channel named '{normalized_name}' already exists",
        )

    channel = crud.create_channel(
        db,
        firm_id=firm_id,
        name=normalized_name,
        created_by_id=requesting_user.id,
    )
    ch_out = ChannelOut.model_validate(channel)
    ch_out.unread_count = 0
    return ch_out


def update_channel(
    db: Session,
    firm_id: uuid.UUID,
    channel_id: uuid.UUID,
    requesting_user: User,
    data: ChannelUpdate,
) -> ChannelOut:
    if requesting_user.role not in (UserRole.firm_owner, UserRole.system_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only firm owners can rename channels",
        )

    channel = crud.get_channel_by_id(db, channel_id=channel_id, firm_id=firm_id)
    if channel is None or channel.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    normalized_name = data.name.strip().lower().replace(" ", "-")

    # Check for duplicate name, excluding the current channel
    existing = crud.get_channel_by_name(db, firm_id=firm_id, name=normalized_name)
    if existing is not None and existing.id != channel_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A channel named '{normalized_name}' already exists",
        )

    channel = crud.update_channel(db, channel=channel, name=normalized_name)
    ch_out = ChannelOut.model_validate(channel)
    ch_out.unread_count = crud.get_unread_count_for_channel(
        db, channel_id=channel.id, user_id=requesting_user.id
    )
    return ch_out


def delete_channel(
    db: Session,
    firm_id: uuid.UUID,
    channel_id: uuid.UUID,
    requesting_user: User,
) -> None:
    if requesting_user.role not in (UserRole.firm_owner, UserRole.system_admin):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only firm owners can delete channels",
        )

    channel = crud.get_channel_by_id(db, channel_id=channel_id, firm_id=firm_id)
    if channel is None or channel.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    crud.soft_delete_channel(db, channel=channel)


def get_messages(
    db: Session,
    firm_id: uuid.UUID,
    channel_id: uuid.UUID,
    requesting_user_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[FirmMessageOut]:
    channel = crud.get_channel_by_id(db, channel_id=channel_id, firm_id=firm_id)
    if channel is None or channel.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    messages = crud.get_messages_for_channel(
        db, firm_id=firm_id, channel_id=channel_id, skip=skip, limit=limit
    )

    result = []
    for msg in messages:
        msg_out = FirmMessageOut.model_validate(msg)
        _enrich_message(msg_out, db)
        result.append(msg_out)

    # Mark all messages as read for the requesting user
    crud.mark_channel_read(db, channel_id=channel_id, user_id=requesting_user_id)

    return result


def send_message(
    db: Session,
    firm_id: uuid.UUID,
    channel_id: uuid.UUID,
    sender_user: User,
    data: FirmMessageCreate,
    attachment_key: Optional[str] = None,
) -> FirmMessageOut:
    channel = crud.get_channel_by_id(db, channel_id=channel_id, firm_id=firm_id)
    if channel is None or channel.is_deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Channel not found",
        )

    # Validate mentions: keep only UUIDs that are valid users in this firm
    valid_mentions: list[uuid.UUID] = []
    if data.mentions:
        mentioned_ids = list(data.mentions)
        stmt = select(User.id).where(
            User.id.in_(mentioned_ids),
            User.firm_id == firm_id,
        )
        valid_ids = set(db.execute(stmt).scalars().all())
        valid_mentions = [m for m in mentioned_ids if m in valid_ids]

    message = crud.create_message(
        db,
        firm_id=firm_id,
        channel_id=channel_id,
        sender_id=sender_user.id,
        body=data.body,
        attachment_key=attachment_key,
        mentions=valid_mentions if valid_mentions else None,
    )

    msg_out = FirmMessageOut.model_validate(message)
    _enrich_message(msg_out, db)
    log_event(
        firm_id=firm_id,
        event_type="firm_chat.message_sent",
        entity_type="firm_chat_message",
        entity_id=message.id,
        actor_type="staff",
        actor_id=sender_user.id,
        metadata={
            "channel_id": str(message.channel_id) if hasattr(message, 'channel_id') else None,
            "message_length": len(message.body) if hasattr(message, 'body') and message.body else None,
            "has_mentions": len(message.mentions) > 0
                if hasattr(message, 'mentions') and message.mentions else False,
            "mention_count": len(message.mentions)
                if hasattr(message, 'mentions') and message.mentions else 0,
            "time_of_day": datetime.now(timezone.utc).hour,
        }
    )
    return msg_out


def get_unread_summary(
    db: Session,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> FirmChatUnreadOut:
    per_channel = crud.get_unread_counts_for_firm(db, firm_id=firm_id, user_id=user_id)
    total_unread = sum(per_channel.values())
    return FirmChatUnreadOut(total_unread=total_unread, per_channel=per_channel)
