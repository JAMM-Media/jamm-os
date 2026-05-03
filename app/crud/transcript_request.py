# app/crud/transcript_request.py

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transcript_request import TranscriptRequest
from app.schemas.transcript_request import TranscriptRequestUpdate


def create_transcript_request(
    db: Session,
    firm_id: UUID,
    client_id: UUID,
    irs_authorization_id: UUID,
    transcript_type: str,
    tax_year: int,
    requested_by: UUID,
) -> TranscriptRequest:
    request = TranscriptRequest(
        firm_id=firm_id,
        client_id=client_id,
        irs_authorization_id=irs_authorization_id,
        transcript_type=transcript_type,
        tax_year=tax_year,
        requested_by=requested_by,
        status="pending",
    )
    db.add(request)
    db.commit()
    db.refresh(request)
    return request


def get_transcript_request(
    db: Session,
    request_id: UUID,
    firm_id: UUID,
) -> TranscriptRequest | None:
    return db.execute(
        select(TranscriptRequest).where(
            TranscriptRequest.id == request_id,
            TranscriptRequest.firm_id == firm_id,
        )
    ).scalars().first()


def list_transcript_requests(
    db: Session,
    firm_id: UUID,
    client_id: Optional[UUID] = None,
    status: Optional[str] = None,
    transcript_type: Optional[str] = None,
) -> list[TranscriptRequest]:
    stmt = select(TranscriptRequest).where(
        TranscriptRequest.firm_id == firm_id
    )
    if client_id:
        stmt = stmt.where(TranscriptRequest.client_id == client_id)
    if status:
        stmt = stmt.where(TranscriptRequest.status == status)
    if transcript_type:
        stmt = stmt.where(TranscriptRequest.transcript_type == transcript_type)
    stmt = stmt.order_by(TranscriptRequest.created_at.desc())
    return db.execute(stmt).scalars().all()


def update_transcript_request(
    db: Session,
    request: TranscriptRequest,
    update_in: TranscriptRequestUpdate,
) -> TranscriptRequest:
    for key, value in update_in.model_dump(exclude_unset=True).items():
        setattr(request, key, value)
    db.commit()
    db.refresh(request)
    return request
