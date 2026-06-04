# app/services/client_service.py

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.crud import client as crud_client
from app.models.client import Client
from app.services.behavioral_log import log_event


def create_client(
    *,
    db: Session,
    payload,  # ClientCreate
    firm_id: UUID,
    current_user_id: UUID,
):
    try:
        client = crud_client.create_client(db, payload, firm_id=firm_id)
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A client with this email already exists.",
        )

    client_count = db.execute(
        select(func.count()).where(Client.firm_id == firm_id)
    ).scalar()

    log_event(
        firm_id=client.firm_id,
        event_type="client.created",
        entity_type="client",
        entity_id=client.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "entity_type": str(client.entity_type)
                if hasattr(client, 'entity_type') and client.entity_type else None,
            "source": "manual",
            "client_id": str(client.id),
        }
    )

    if client_count == 1:
        log_event(
            firm_id=client.firm_id,
            event_type="firm.first_client_created",
            entity_type="firm",
            entity_id=client.firm_id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={}
        )

    return client


def delete_client(
    *,
    db: Session,
    client_id: UUID,
    firm_id: UUID,
    current_user_id: UUID,
):
    client = crud_client.get_client_for_firm(db, client_id, firm_id)
    if not client:
        return None

    tenure_days = (datetime.now(timezone.utc) - client.created_at).days \
        if client.created_at else None
    entity_type = str(client.entity_type) \
        if hasattr(client, 'entity_type') and client.entity_type else None
    cli_firm_id = client.firm_id

    crud_client.delete_client(db, client)

    log_event(
        firm_id=cli_firm_id,
        event_type="client.archived",
        entity_type="client",
        entity_id=client_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "tenure_days": tenure_days,
            "entity_type": entity_type,
        }
    )

    return True
