# app/services/contact_service.py

"""
Contact writes, moved out of app/api/contacts.py (Phase 7). The router keeps
RBAC, the firm-scoped lookup and its 404; the write and its behavioral event
live here.
"""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import contact as crud_contact
from app.models.client import Client
from app.models.contact import Contact
from app.schemas.contact import ContactCreate, ContactUpdate
from app.services.behavioral_log import build_changed_fields, log_event


def create_contact(
    db: Session,
    *,
    contact_in: ContactCreate,
    firm_id: UUID,
    current_user_id: UUID,
) -> Contact:
    # Tenant guard (ruled Oct 12, 2026): a contact may only attach to a client
    # of the caller's own firm. Runs before the write. 404 because a client of
    # another firm is indistinguishable from an absent one to this caller.
    if contact_in.client_id is not None:
        owned = db.execute(
            select(Client.id).where(
                Client.id == contact_in.client_id,
                Client.firm_id == firm_id,
            )
        ).scalar_one_or_none()
        if owned is None:
            raise HTTPException(status_code=404, detail="Client not found")

    contact = crud_contact.create_contact(db, contact_in, firm_id=firm_id)

    log_event(
        firm_id=firm_id,
        event_type="contact.created",
        entity_type="contact",
        entity_id=contact.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "client_id": str(contact.client_id) if contact.client_id else None,
            "is_active": contact.is_active,
        },
    )
    return contact


def update_contact(
    db: Session,
    *,
    contact: Contact,
    contact_in: ContactUpdate,
    firm_id: UUID,
    current_user_id: UUID,
) -> Contact:
    tracked_fields = list(contact_in.model_dump(exclude_unset=True).keys())
    old_values = {f: getattr(contact, f) for f in tracked_fields}

    updated = crud_contact.update_contact(db, contact, contact_in)

    new_values = {f: getattr(updated, f) for f in tracked_fields}
    changed_fields = build_changed_fields(old_values, new_values)
    if changed_fields:
        log_event(
            firm_id=firm_id,
            event_type="contact.updated",
            entity_type="contact",
            entity_id=updated.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={"changed_fields": changed_fields},
        )
    return updated


def delete_contact(
    db: Session,
    *,
    contact: Contact,
    firm_id: UUID,
    current_user_id: UUID,
) -> None:
    contact_id = contact.id
    client_id = contact.client_id

    crud_contact.delete_contact(db, contact)

    log_event(
        firm_id=firm_id,
        event_type="contact.deleted",
        entity_type="contact",
        entity_id=contact_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"client_id": str(client_id) if client_id else None},
    )
