# app/crud/message.py

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.message import ClientMessage, ClientMessageRead


def create_message(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    sender_id: Optional[uuid.UUID],
    sender_role: str,
    body: str,
) -> ClientMessage:
    message = ClientMessage(
        firm_id=firm_id,
        client_id=client_id,
        sender_id=sender_id,
        sender_role=sender_role,
        body=body,
    )
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_messages_for_client(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[ClientMessage]:
    """Returns non-deleted messages ordered by created_at ascending (oldest first)."""
    stmt = (
        select(ClientMessage)
        .where(
            ClientMessage.firm_id == firm_id,
            ClientMessage.client_id == client_id,
            ClientMessage.is_deleted.is_(False),
        )
        .order_by(ClientMessage.created_at.asc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.execute(stmt).scalars().all())


def get_message_by_id(
    db: Session,
    message_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> Optional[ClientMessage]:
    stmt = select(ClientMessage).where(
        ClientMessage.id == message_id,
        ClientMessage.firm_id == firm_id,
        ClientMessage.is_deleted.is_(False),
    )
    return db.execute(stmt).scalar_one_or_none()


def mark_messages_read(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    reader_id: Optional[uuid.UUID],
    reader_role: str,
) -> int:
    """
    Marks all unread messages for this client as read by this reader.
    A message is unread if there is no ClientMessageRead record for
    (message_id, reader_id, reader_role).
    Returns count of messages marked read.
    """
    # Fetch all non-deleted messages for this client
    messages = get_messages_for_client(db, firm_id=firm_id, client_id=client_id, limit=1000)

    count = 0
    for message in messages:
        # Check if already read
        stmt = select(ClientMessageRead).where(
            ClientMessageRead.message_id == message.id,
            ClientMessageRead.reader_id == reader_id,
            ClientMessageRead.reader_role == reader_role,
        )
        existing = db.execute(stmt).scalar_one_or_none()
        if existing is None:
            read_record = ClientMessageRead(
                message_id=message.id,
                reader_id=reader_id,
                reader_role=reader_role,
            )
            db.add(read_record)
            count += 1

    if count > 0:
        db.commit()

    return count


def get_unread_count_for_staff(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    staff_user_id: uuid.UUID,
) -> int:
    """
    Count of messages where sender_role="client" and no read receipt exists
    for (staff_user_id, "staff").
    """
    # Get all client-sent messages
    stmt = select(ClientMessage).where(
        ClientMessage.firm_id == firm_id,
        ClientMessage.client_id == client_id,
        ClientMessage.sender_role == "client",
        ClientMessage.is_deleted.is_(False),
    )
    messages = list(db.execute(stmt).scalars().all())

    count = 0
    for message in messages:
        read_stmt = select(ClientMessageRead).where(
            ClientMessageRead.message_id == message.id,
            ClientMessageRead.reader_id == staff_user_id,
            ClientMessageRead.reader_role == "staff",
        )
        existing = db.execute(read_stmt).scalar_one_or_none()
        if existing is None:
            count += 1

    return count


def get_unread_count_for_client(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
) -> int:
    """
    Count of messages where sender_role="staff" and no read receipt exists
    with reader_role="client".
    """
    stmt = select(ClientMessage).where(
        ClientMessage.firm_id == firm_id,
        ClientMessage.client_id == client_id,
        ClientMessage.sender_role == "staff",
        ClientMessage.is_deleted.is_(False),
    )
    messages = list(db.execute(stmt).scalars().all())

    count = 0
    for message in messages:
        read_stmt = select(ClientMessageRead).where(
            ClientMessageRead.message_id == message.id,
            ClientMessageRead.reader_role == "client",
        )
        existing = db.execute(read_stmt).scalar_one_or_none()
        if existing is None:
            count += 1

    return count
