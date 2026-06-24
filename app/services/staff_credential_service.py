# app/services/staff_credential_service.py

import uuid

from sqlalchemy.orm import Session

from app.crud import staff_credential as crud
from app.schemas.staff_credential import StaffCredentialCreate, StaffCredentialOut, StaffCredentialUpdate
from app.services.behavioral_log import log_event


def create_credential(
    db: Session,
    firm_id: uuid.UUID,
    data: StaffCredentialCreate,
    actor_id: uuid.UUID,
) -> StaffCredentialOut:
    credential = crud.create(db, firm_id, data)
    log_event(
        event_type="staff.credential_created",
        firm_id=firm_id,
        entity_type="staff_credential",
        entity_id=credential.id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "credential_type": credential.credential_type.value,
            "user_id": str(credential.user_id),
            "expires_at": credential.expires_at.isoformat() if credential.expires_at else None,
        },
    )
    return StaffCredentialOut.model_validate(credential)


def update_credential(
    db: Session,
    firm_id: uuid.UUID,
    credential_id: uuid.UUID,
    data: StaffCredentialUpdate,
    actor_id: uuid.UUID,
) -> StaffCredentialOut:
    from fastapi import HTTPException
    credential = crud.get(db, credential_id, firm_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    credential = crud.update(db, credential, data)
    return StaffCredentialOut.model_validate(credential)


def delete_credential(
    db: Session,
    firm_id: uuid.UUID,
    credential_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    from fastapi import HTTPException
    credential = crud.get(db, credential_id, firm_id)
    if not credential:
        raise HTTPException(status_code=404, detail="Credential not found")
    log_event(
        event_type="staff.credential_deleted",
        firm_id=firm_id,
        entity_type="staff_credential",
        entity_id=credential.id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "credential_type": credential.credential_type.value,
            "user_id": str(credential.user_id),
        },
    )
    crud.delete(db, credential)
