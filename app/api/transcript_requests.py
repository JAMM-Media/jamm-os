# app/api/transcript_requests.py

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crud import transcript_request as crud_transcript
from app.db.session import get_db
from app.dependencies.auth import get_current_user
from app.dependencies.roles import require_manager_or_above
from app.dependencies.tenant import get_current_firm
from app.models.client import Client
from app.models.firm import Firm
from app.models.user import User
from app.schemas.transcript_request import (
    TranscriptRequestCreate,
    TranscriptRequestOut,
    TranscriptRequestUpdate,
)
from app.services.transcript_service import request_transcript

router = APIRouter(prefix="/transcript-requests", tags=["Transcript Requests"])


@router.post("/", response_model=TranscriptRequestOut, status_code=status.HTTP_201_CREATED)
def submit_transcript_request(
    payload: TranscriptRequestCreate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """
    Submit a transcript request for a client.

    Requires an active Form 8821 on file for the client.
    Returns 400 with a clear message if no active 8821 exists.

    The actual IRS API call is stubbed — the request is logged
    and status set to 'pending' until live integration is configured.

    Manager and firm_owner only. firm_id injected from JWT.
    """
    # Verify client belongs to this firm
    client = db.execute(
        select(Client).where(
            Client.id == payload.client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    try:
        result = request_transcript(
            db=db,
            request_in=payload,
            firm=current_firm,
            client=client,
            requested_by_user_id=current_user.id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result["request"]


@router.get("/", response_model=list[TranscriptRequestOut])
def list_transcript_requests(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
    client_id: Optional[UUID] = None,
    status: Optional[str] = None,
    transcript_type: Optional[str] = None,
):
    """
    List transcript requests for this firm.
    Filter by client_id, status, or transcript_type.
    Manager and firm_owner only.
    """
    return crud_transcript.list_transcript_requests(
        db=db,
        firm_id=current_firm.id,
        client_id=client_id,
        status=status,
        transcript_type=transcript_type,
    )


@router.get("/check/{client_id}", response_model=dict)
def check_transcript_authorization(
    client_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """
    Check whether a client has an active 8821 on file,
    and return their existing transcript requests.

    Used by the frontend to decide whether to show the
    'Request Transcript' button or an authorization warning.
    """
    from app.crud import irs_authorization as crud_auth

    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == current_firm.id,
        )
    ).scalars().first()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    active_auth = crud_auth.get_active_authorization_for_client(
        db, current_firm.id, client_id, "8821"
    )

    requests = crud_transcript.list_transcript_requests(
        db=db,
        firm_id=current_firm.id,
        client_id=client_id,
    )

    return {
        "client_id": str(client_id),
        "can_request": active_auth is not None,
        "authorization_status": "active" if active_auth else "not_on_file",
        "irs_authorization_id": str(active_auth.id) if active_auth else None,
        "existing_requests": [
            TranscriptRequestOut.model_validate(r).model_dump() for r in requests
        ],
    }


@router.get("/{request_id}", response_model=TranscriptRequestOut)
def get_transcript_request(
    request_id: UUID,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    request = crud_transcript.get_transcript_request(db, request_id, current_firm.id)
    if not request:
        raise HTTPException(status_code=404, detail="Transcript request not found")
    return request


@router.patch("/{request_id}", response_model=TranscriptRequestOut)
def update_transcript_request(
    request_id: UUID,
    payload: TranscriptRequestUpdate,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: User = Depends(require_manager_or_above),
):
    """
    Update a transcript request.
    Used to mark as retrieved or failed when the provider responds,
    and to attach the document_id when the PDF is stored.
    """
    request = crud_transcript.get_transcript_request(db, request_id, current_firm.id)
    if not request:
        raise HTTPException(status_code=404, detail="Transcript request not found")
    return crud_transcript.update_transcript_request(db, request, payload)
