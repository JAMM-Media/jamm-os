# app/crud/signature_envelope.py

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.models.signature_envelope import SignatureEnvelope
from app.schemas.signature_envelope import SignatureEnvelopeCreate, SignatureEnvelopeUpdate


def create_signature_envelope(
    db: Session,
    schema: SignatureEnvelopeCreate,
    firm_id: UUID,
) -> SignatureEnvelope:
    envelope = SignatureEnvelope(
        firm_id=firm_id,
        client_id=schema.client_id,
        engagement_id=schema.engagement_id,
        document_id=schema.document_id,
        provider=schema.provider,
        status=schema.status,
        subject=schema.subject,
        message=schema.message,
        signers=schema.signers,
        expires_at=schema.expires_at,
    )
    db.add(envelope)
    db.commit()
    db.refresh(envelope)
    return envelope


def get_signature_envelope(
    db: Session,
    envelope_id: UUID,
    firm_id: UUID,
) -> SignatureEnvelope | None:
    stmt = select(SignatureEnvelope).where(
        SignatureEnvelope.id == envelope_id,
        SignatureEnvelope.firm_id == firm_id,
    )
    return db.execute(stmt).scalars().first()


def list_signature_envelopes(
    db: Session,
    firm_id: UUID,
    client_id: UUID | None = None,
    engagement_id: UUID | None = None,
    status: str | None = None,
    skip: int = 0,
    limit: int = 20,
) -> list[SignatureEnvelope]:
    stmt = select(SignatureEnvelope).where(SignatureEnvelope.firm_id == firm_id)
    if client_id is not None:
        stmt = stmt.where(SignatureEnvelope.client_id == client_id)
    if engagement_id is not None:
        stmt = stmt.where(SignatureEnvelope.engagement_id == engagement_id)
    if status is not None:
        stmt = stmt.where(SignatureEnvelope.status == status)
    stmt = stmt.offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def update_signature_envelope(
    db: Session,
    envelope: SignatureEnvelope,
    schema: SignatureEnvelopeUpdate,
) -> SignatureEnvelope:
    updates = schema.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(envelope, key, value)
    if "signers" in updates:
        flag_modified(envelope, "signers")
    db.commit()
    db.refresh(envelope)
    return envelope


def delete_signature_envelope(
    db: Session,
    envelope: SignatureEnvelope,
) -> None:
    db.delete(envelope)
    db.commit()
