# app/crud/document_expiry.py

from sqlalchemy.orm import Session
from sqlalchemy import select
from app.models.document_expiry import DocumentExpiry
from app.schemas.document_expiry import DocumentExpiryCreate, DocumentExpiryUpdate
import uuid


def create(db: Session, firm_id: uuid.UUID, data: DocumentExpiryCreate) -> DocumentExpiry:
    obj = DocumentExpiry(
        firm_id=firm_id,
        **data.model_dump()
    )
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj


def list_for_client(db: Session, firm_id: uuid.UUID, client_id: uuid.UUID) -> list[DocumentExpiry]:
    return db.execute(
        select(DocumentExpiry)
        .where(
            DocumentExpiry.firm_id == firm_id,
            DocumentExpiry.client_id == client_id,
        )
        .order_by(DocumentExpiry.expires_on.asc())
    ).scalars().all()


def get(db: Session, firm_id: uuid.UUID, expiry_id: uuid.UUID) -> DocumentExpiry | None:
    return db.execute(
        select(DocumentExpiry)
        .where(
            DocumentExpiry.id == expiry_id,
            DocumentExpiry.firm_id == firm_id,
        )
    ).scalars().first()


def update(db: Session, obj: DocumentExpiry, data: DocumentExpiryUpdate) -> DocumentExpiry:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    db.commit()
    db.refresh(obj)
    return obj


def delete(db: Session, obj: DocumentExpiry) -> None:
    db.delete(obj)
    db.commit()


def get_expiring_soon(db: Session, days_ahead: int = 60) -> list[DocumentExpiry]:
    from datetime import date, timedelta
    cutoff = date.today() + timedelta(days=days_ahead)
    return db.execute(
        select(DocumentExpiry)
        .where(
            DocumentExpiry.expires_on <= cutoff,
            DocumentExpiry.expires_on >= date.today(),
            DocumentExpiry.status == "active",
            DocumentExpiry.expiry_notification_sent == False,
        )
    ).scalars().all()
