# app/crud/firm_chat.py

import uuid
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.firm_chat import Channel, FirmMessage, FirmMessageRead


# ---------------------------------------------------------------------------
# Channel functions
# ---------------------------------------------------------------------------

def create_channel(
    db: Session,
    firm_id: uuid.UUID,
    name: str,
    created_by_id: uuid.UUID,
) -> Channel:
    channel = Channel(
        firm_id=firm_id,
        name=name,
        created_by=created_by_id,
    )
    db.add(channel)
    db.commit()
    db.refresh(channel)
    return channel


def get_channels(
    db: Session,
    firm_id: uuid.UUID,
    include_deleted: bool = False,
) -> list[Channel]:
    stmt = select(Channel).where(Channel.firm_id == firm_id)
    if not include_deleted:
        stmt = stmt.where(Channel.is_deleted == False)
    stmt = stmt.order_by(Channel.name.asc())
    return list(db.execute(stmt).scalars().all())


def get_channel_by_id(
    db: Session,
    channel_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[Channel]:
    stmt = select(Channel).where(
        Channel.id == channel_id,
        Channel.firm_id == firm_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def get_channel_by_name(
    db: Session,
    firm_id: uuid.UUID,
    name: str,
) -> Optional[Channel]:
    stmt = select(Channel).where(
        Channel.firm_id == firm_id,
        Channel.name == name,
        Channel.is_deleted == False,
    )
    return db.execute(stmt).scalar_one_or_none()


def update_channel(db: Session, channel: Channel, name: str) -> Channel:
    channel.name = name
    db.commit()
    db.refresh(channel)
    return channel


def soft_delete_channel(db: Session, channel: Channel) -> Channel:
    channel.is_deleted = True
    db.commit()
    db.refresh(channel)
    return channel


# ---------------------------------------------------------------------------
# Message functions
# ---------------------------------------------------------------------------

def create_message(
    db: Session,
    firm_id: uuid.UUID,
    channel_id: uuid.UUID,
    sender_id: uuid.UUID,
    body: str,
    attachment_key: Optional[str] = None,
    attachment_name: Optional[str] = None,
    attachment_size: Optional[int] = None,
    attachment_type: Optional[str] = None,
    mentions: Optional[list] = None,
) -> FirmMessage:
    # Store mentions as list of str for JSON serialization
    mentions_data = [str(m) for m in mentions] if mentions else None
    message = FirmMessage(
        firm_id=firm_id,
        channel_id=channel_id,
        sender_id=sender_id,
        body=body,
        attachment_key=attachment_key,
        attachment_name=attachment_name,
        attachment_size=attachment_size,
        attachment_type=attachment_type,
        mentions=mentions_data,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages_for_channel(
    db: Session,
    firm_id: uuid.UUID,
    channel_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[FirmMessage]:
    stmt = (
        select(FirmMessage)
        .where(
            FirmMessage.firm_id == firm_id,
            FirmMessage.channel_id == channel_id,
            FirmMessage.is_deleted == False,
        )
        .order_by(FirmMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_message_by_id(
    db: Session,
    message_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[FirmMessage]:
    stmt = select(FirmMessage).where(
        FirmMessage.id == message_id,
        FirmMessage.firm_id == firm_id,
    )
    return db.execute(stmt).scalar_one_or_none()


def soft_delete_message(db: Session, message: FirmMessage) -> FirmMessage:
    message.is_deleted = True
    db.commit()
    db.refresh(message)
    return message


# ---------------------------------------------------------------------------
# Read receipt functions
# ---------------------------------------------------------------------------

def mark_channel_read(
    db: Session,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """
    Insert FirmMessageRead for all unread messages in the channel for this user.
    Returns count of messages newly marked read.
    """
    # Find message IDs already read by this user
    already_read_stmt = select(FirmMessageRead.message_id).where(
        FirmMessageRead.user_id == user_id
    )
    already_read_ids = set(db.execute(already_read_stmt).scalars().all())

    # Get all non-deleted messages in channel
    messages_stmt = select(FirmMessage).where(
        FirmMessage.channel_id == channel_id,
        FirmMessage.is_deleted == False,
    )
    messages = list(db.execute(messages_stmt).scalars().all())

    count = 0
    for msg in messages:
        if msg.id not in already_read_ids:
            receipt = FirmMessageRead(
                id=uuid.uuid4(),
                message_id=msg.id,
                user_id=user_id,
            )
            db.add(receipt)
            count += 1

    if count > 0:
        db.commit()

    return count


def get_unread_count_for_channel(
    db: Session,
    channel_id: uuid.UUID,
    user_id: uuid.UUID,
) -> int:
    """
    Count messages in this channel that the user has not yet read.
    """
    read_ids_stmt = select(FirmMessageRead.message_id).where(
        FirmMessageRead.user_id == user_id
    )
    stmt = (
        select(func.count())
        .select_from(FirmMessage)
        .where(
            FirmMessage.channel_id == channel_id,
            FirmMessage.is_deleted == False,
            FirmMessage.id.not_in(read_ids_stmt),
        )
    )
    result = db.execute(stmt).scalar_one()
    return result or 0


def get_unread_counts_for_firm(
    db: Session,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, int]:
    """
    Returns {channel_id_str: unread_count} for all non-deleted channels in the firm.
    """
    channels = get_channels(db, firm_id=firm_id, include_deleted=False)
    result = {}
    for channel in channels:
        count = get_unread_count_for_channel(db, channel_id=channel.id, user_id=user_id)
        result[str(channel.id)] = count
    return result
