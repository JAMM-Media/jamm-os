# app/services/cpe_record_service.py

import uuid

from sqlalchemy.orm import Session

from app.crud import cpe_record as crud
from app.schemas.cpe_record import CPERecordCreate, CPERecordOut, CPERecordUpdate
from app.services.behavioral_log import log_event


def create_cpe_record(
    db: Session,
    firm_id: uuid.UUID,
    data: CPERecordCreate,
    actor_id: uuid.UUID,
) -> CPERecordOut:
    record = crud.create(db, firm_id, data)
    log_event(
        event_type="staff.cpe_record_created",
        firm_id=firm_id,
        entity_type="cpe_record",
        entity_id=record.id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "user_id": str(record.user_id),
            "hours_required": float(record.hours_required),
            "reporting_period_start": record.reporting_period_start.isoformat(),
            "reporting_period_end": record.reporting_period_end.isoformat(),
        },
    )
    return CPERecordOut.model_validate(record)


def update_cpe_record(
    db: Session,
    firm_id: uuid.UUID,
    record_id: uuid.UUID,
    data: CPERecordUpdate,
    actor_id: uuid.UUID,
) -> CPERecordOut:
    from fastapi import HTTPException
    record = crud.get(db, record_id, firm_id)
    if not record:
        raise HTTPException(status_code=404, detail="CPE record not found")

    if data.hours_completed is not None:
        old_hours = float(record.hours_completed)
        new_hours = data.hours_completed
        hours_remaining_after = max(0.0, float(record.hours_required) - new_hours)
        log_event(
            event_type="staff.cpe_hours_updated",
            firm_id=firm_id,
            entity_type="cpe_record",
            entity_id=record.id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={
                "old_hours": old_hours,
                "new_hours": new_hours,
                "hours_remaining": hours_remaining_after,
            },
        )

    record = crud.update(db, record, data)
    return CPERecordOut.model_validate(record)


def delete_cpe_record(
    db: Session,
    firm_id: uuid.UUID,
    record_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> None:
    from fastapi import HTTPException
    record = crud.get(db, record_id, firm_id)
    if not record:
        raise HTTPException(status_code=404, detail="CPE record not found")
    crud.delete(db, record)
