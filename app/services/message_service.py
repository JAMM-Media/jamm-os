# app/services/message_service.py

import uuid
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import message as crud_message
from app.models.client import Client
from app.models.user import User
from app.schemas.message import ClientMessageCreate, ClientMessageOut, UnreadCountOut


def _enrich_message(msg_out: ClientMessageOut, db: Session) -> ClientMessageOut:
    """Populate sender_name based on sender_role."""
    if msg_out.sender_role == "staff" and msg_out.sender_id is not None:
        user = db.execute(
            select(User).where(User.id == msg_out.sender_id)
        ).scalar_one_or_none()
        if user and user.full_name:
            msg_out.sender_name = user.full_name
    elif msg_out.sender_role == "client":
        # Look up client record for the client_id — use name as sender_name
        client = db.execute(
            select(Client).where(Client.id == msg_out.client_id)
        ).scalar_one_or_none()
        if client:
            msg_out.sender_name = client.name
    return msg_out


def get_messages(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    requesting_user: User,
) -> list[ClientMessageOut]:
    """
    Fetches messages for a client, enriches each with sender_name,
    and marks all messages as read by the requesting staff member.
    """
    messages = crud_message.get_messages_for_client(db, firm_id=firm_id, client_id=client_id)
    result = []
    for msg in messages:
        msg_out = ClientMessageOut.model_validate(msg)
        _enrich_message(msg_out, db)
        result.append(msg_out)

    # Mark all messages as read by this staff member
    crud_message.mark_messages_read(
        db,
        firm_id=firm_id,
        client_id=client_id,
        reader_id=requesting_user.id,
        reader_role="staff",
    )

    return result


def send_message_staff(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    sender_user: User,
    data: ClientMessageCreate,
) -> ClientMessageOut:
    """
    Send a message from a staff member to a client.
    Validates the client exists and belongs to this firm.
    """
    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    message = crud_message.create_message(
        db,
        firm_id=firm_id,
        client_id=client_id,
        sender_id=sender_user.id,
        sender_role="staff",
        body=data.body,
    )
    msg_out = ClientMessageOut.model_validate(message)
    _enrich_message(msg_out, db)
    return msg_out


def send_message_client(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    data: ClientMessageCreate,
) -> ClientMessageOut:
    """
    Called from portal endpoints — sender is the client.
    Creates message with sender_role="client", sender_id=None.
    """
    message = crud_message.create_message(
        db,
        firm_id=firm_id,
        client_id=client_id,
        sender_id=None,
        sender_role="client",
        body=data.body,
    )
    msg_out = ClientMessageOut.model_validate(message)
    _enrich_message(msg_out, db)
    return msg_out


def get_staff_unread_count(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
    staff_user_id: uuid.UUID,
) -> UnreadCountOut:
    count = crud_message.get_unread_count_for_staff(
        db, firm_id=firm_id, client_id=client_id, staff_user_id=staff_user_id
    )
    return UnreadCountOut(client_id=client_id, unread_count=count)


def get_portal_unread_count(
    db: Session,
    firm_id: uuid.UUID,
    client_id: uuid.UUID,
) -> UnreadCountOut:
    count = crud_message.get_unread_count_for_client(
        db, firm_id=firm_id, client_id=client_id
    )
    return UnreadCountOut(client_id=client_id, unread_count=count)
