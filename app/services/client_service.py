# app/services/client_service.py

from datetime import datetime, timezone
from uuid import UUID
from sqlalchemy import select, func
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from fastapi import HTTPException, status

from app.crud import client as crud_client
from app.models.client import Client
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event, build_changed_fields


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
            "referral_source": client.referral_source.value if client.referral_source else None,
            "referring_client_id": str(client.referring_client_id) if client.referring_client_id else None,
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


def import_clients_csv(
    *,
    db: Session,
    rows: list,
    firm_id: UUID,
):
    VALID_ENTITY_TYPES = {"individual", "business", "trust", "estate", "non_profit"}

    existing_emails = set(
        row[0]
        for row in db.execute(
            select(Client.email).where(
                Client.firm_id == firm_id,
                Client.email.isnot(None),
            )
        ).all()
        if row[0]
    )

    existing_names = set(
        row[0].lower().strip()
        for row in db.execute(
            select(Client.name).where(
                Client.firm_id == firm_id,
            )
        ).all()
        if row[0]
    )

    created = 0
    skipped = 0
    errors = []

    for i, row in enumerate(rows, start=2):  # start=2 because row 1 is the header
        name = row.get("name", "").strip()
        if not name:
            errors.append({"row": i, "reason": "Missing required field: name"})
            continue

        # Deduplicate on name
        if name.lower().strip() in existing_names:
            skipped += 1
            errors.append({"row": i, "reason": "Client with this name already exists"})
            continue

        email = row.get("email", "").strip() or None
        entity_type = row.get("entity_type", "").strip().lower() or None
        entity_subtype = row.get("entity_subtype", "").strip().lower() or None
        phone = row.get("phone", "").strip() or None
        company_name = row.get("company_name", "").strip() or None
        address_line1 = row.get("address_line1", "").strip() or None
        address_line2 = row.get("address_line2", "").strip() or None
        city = row.get("city", "").strip() or None
        state = row.get("state", "").strip() or None
        postal_code = row.get("postal_code", "").strip() or None
        country = row.get("country", "").strip() or None
        tags = row.get("tags", "").strip() or None
        notes = row.get("notes", "").strip() or None

        # Validate entity_type if provided
        if entity_type and entity_type not in VALID_ENTITY_TYPES:
            errors.append({
                "row": i,
                "reason": f"Invalid entity_type '{entity_type}'. "
                          f"Must be one of: {', '.join(sorted(VALID_ENTITY_TYPES))}",
            })
            continue

        # Deduplicate on email
        if email and email.lower() in existing_emails:
            skipped += 1
            continue

        try:
            new_client = Client(
                firm_id=firm_id,
                name=name,
                email=email,
                entity_type=entity_type,
                entity_subtype=entity_subtype,
                phone=phone,
                company_name=company_name,
                address_line1=address_line1,
                address_line2=address_line2,
                city=city,
                state=state,
                postal_code=postal_code,
                country=country,
                tags=tags,
                notes=notes,
                is_active=True,
            )
            db.add(new_client)
            db.flush()  # get the ID without committing yet

            if email:
                existing_emails.add(email.lower())
            existing_names.add(name.lower().strip())

            created += 1

        except Exception as e:
            db.rollback()
            errors.append({"row": i, "reason": f"Database error: {str(e)}"})
            continue

    db.commit()

    log_event(
        firm_id=firm_id,
        event_type="client.csv_import_completed",
        entity_type="firm",
        entity_id=firm_id,
        actor_type="staff",
        metadata={
            "created": created,
            "skipped": skipped,
            "errors": len(errors),
            "total_rows": len(rows),
        },
    )

    return created, skipped, errors


def update_client(
    *,
    db: Session,
    client: Client,
    payload,  # ClientUpdate
    firm_id: UUID,
    current_user_id: UUID,
):
    old_entity_type = client.entity_type
    old_entity_subtype = client.entity_subtype
    old_is_active = client.is_active
    old_portal_access = client.portal_access_enabled

    # Fields already covered by a dedicated event below -- excluded from the
    # generic no-silent-changes delta so they are not double-logged.
    _EVENTED_FIELDS = {"entity_type", "entity_subtype", "is_active"}
    _tracked_fields = [
        f for f in payload.model_dump(exclude_unset=True).keys()
        if f not in _EVENTED_FIELDS
    ]
    _old_values = {f: getattr(client, f) for f in _tracked_fields}

    updated = crud_client.update_client(db, client, payload)
    write_audit_log(
        db=db,
        firm_id=firm_id,
        action='client.updated',
        actor_id=current_user_id,
        actor_type='staff',
        entity_type='client',
        entity_id=client.id,
    )

    if updated.entity_type != old_entity_type or updated.entity_subtype != old_entity_subtype:
        log_event(
            firm_id=firm_id,
            event_type="client.entity_changed",
            entity_type="client",
            entity_id=client.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_entity_type": str(old_entity_type) if old_entity_type else None,
                "to_entity_type": str(updated.entity_type) if updated.entity_type else None,
                "from_entity_subtype": str(old_entity_subtype) if old_entity_subtype else None,
                "to_entity_subtype": str(updated.entity_subtype) if updated.entity_subtype else None,
            }
        )

    if updated.is_active != old_is_active:
        log_event(
            firm_id=firm_id,
            event_type="client.active_changed",
            entity_type="client",
            entity_id=client.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_active": old_is_active,
                "to_active": updated.is_active,
            }
        )

    if updated.portal_access_enabled != old_portal_access:
        log_event(
            firm_id=firm_id,
            event_type="client.portal_access_changed",
            entity_type="client",
            entity_id=client.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={
                "from_enabled": old_portal_access,
                "to_enabled": updated.portal_access_enabled,
            }
        )

    _new_values = {f: getattr(updated, f) for f in _tracked_fields}
    _changed_fields = build_changed_fields(_old_values, _new_values)
    if _changed_fields:
        log_event(
            firm_id=firm_id,
            event_type="client.updated",
            entity_type="client",
            entity_id=client.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={"changed_fields": _changed_fields},
        )

    return updated


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
