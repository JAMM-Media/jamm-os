# app/crud/cpe_record.py

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.cpe_record import CPERecord
from app.schemas.cpe_record import CPERecordCreate, CPERecordUpdate


def get(db: Session, record_id: uuid.UUID, firm_id: uuid.UUID) -> CPERecord | None:
    return db.execute(
        select(CPERecord).where(
            CPERecord.id == record_id,
            CPERecord.firm_id == firm_id,
        )
    ).scalars().first()


def list_by_firm(
    db: Session,
    firm_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[CPERecord]:
    return db.execute(
        select(CPERecord)
        .where(CPERecord.firm_id == firm_id)
        .order_by(CPERecord.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).scalars().all()


def count_by_firm(db: Session, firm_id: uuid.UUID) -> int:
    from sqlalchemy import func
    return db.execute(
        select(func.count(CPERecord.id)).where(CPERecord.firm_id == firm_id)
    ).scalar()


def list_by_user(
    db: Session,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[CPERecord]:
    return db.execute(
        select(CPERecord)
        .where(
            CPERecord.firm_id == firm_id,
            CPERecord.user_id == user_id,
        )
        .order_by(CPERecord.created_at.desc())
    ).scalars().all()


def create(
    db: Session,
    firm_id: uuid.UUID,
    data: CPERecordCreate,
) -> CPERecord:
    obj = CPERecord(firm_id=firm_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(
    db: Session,
    record: CPERecord,
    data: CPERecordUpdate,
) -> CPERecord:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    return record


def delete(db: Session, record: CPERecord) -> None:
    db.delete(record)
    db.commit()
