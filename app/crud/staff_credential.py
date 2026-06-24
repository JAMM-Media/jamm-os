# app/crud/staff_credential.py

from datetime import date, timedelta
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.staff_credential import StaffCredential
from app.schemas.staff_credential import StaffCredentialCreate, StaffCredentialUpdate


def get(db: Session, credential_id: uuid.UUID, firm_id: uuid.UUID) -> StaffCredential | None:
    return db.execute(
        select(StaffCredential).where(
            StaffCredential.id == credential_id,
            StaffCredential.firm_id == firm_id,
        )
    ).scalars().first()


def list_by_firm(
    db: Session,
    firm_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[StaffCredential]:
    return db.execute(
        select(StaffCredential)
        .where(StaffCredential.firm_id == firm_id)
        .order_by(StaffCredential.created_at.desc())
        .offset(skip)
        .limit(limit)
    ).scalars().all()


def count_by_firm(db: Session, firm_id: uuid.UUID) -> int:
    from sqlalchemy import func
    return db.execute(
        select(func.count(StaffCredential.id)).where(StaffCredential.firm_id == firm_id)
    ).scalar()


def list_by_user(
    db: Session,
    firm_id: uuid.UUID,
    user_id: uuid.UUID,
) -> list[StaffCredential]:
    return db.execute(
        select(StaffCredential)
        .where(
            StaffCredential.firm_id == firm_id,
            StaffCredential.user_id == user_id,
        )
        .order_by(StaffCredential.created_at.desc())
    ).scalars().all()


def create(
    db: Session,
    firm_id: uuid.UUID,
    data: StaffCredentialCreate,
) -> StaffCredential:
    obj = StaffCredential(firm_id=firm_id, **data.model_dump())
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def update(
    db: Session,
    credential: StaffCredential,
    data: StaffCredentialUpdate,
) -> StaffCredential:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(credential, field, value)
    db.commit()
    db.refresh(credential)
    return credential


def delete(db: Session, credential: StaffCredential) -> None:
    db.delete(credential)
    db.commit()


def get_expiring_soon(db: Session, days_ahead: int = 60) -> list[StaffCredential]:
    cutoff = date.today() + timedelta(days=days_ahead)
    return db.execute(
        select(StaffCredential).where(
            StaffCredential.expires_at.isnot(None),
            StaffCredential.expires_at >= date.today(),
            StaffCredential.expires_at <= cutoff,
        )
    ).scalars().all()
