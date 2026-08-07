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
from app.services import transcript_request_service

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

    Requires an active Form 8821 or Form 2848 on file for the client.
    Both permit transcript access. Returns 400 naming the real state of
    each form type when neither is active.

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
    Whether this client's IRS authorizations permit a transcript request,
    and their existing requests.

    Answers from crud_auth.resolve_authorization_state for BOTH form types.
    Two defects are fixed here. The old version asked only about form type
    8821, so a firm holding a valid 2848 was reported as unable to request
    transcripts, and it collapsed pending, lapsed and revoked records into
    "not_on_file", which is false whenever a record exists.

    can_request keeps its name and its meaning: true when a transcript
    request would actually be accepted, which is now either form type
    resolving to active. authorization_status is the best of the two states,
    so it still reads "active" when one is active and still reads
    "not_on_file" only when neither form type has ever existed.

    response_model=dict with an ad hoc literal is left alone deliberately.
    Giving this endpoint a real schema is a separate cleanup.
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

    resolved_8821 = crud_auth.resolve_authorization_state(
        db, current_firm.id, client_id, "8821"
    )
    resolved_2848 = crud_auth.resolve_authorization_state(
        db, current_firm.id, client_id, "2848"
    )

    # Both forms permit transcript access, so either one being active opens
    # the gate. 8821 is preferred when both are active only because it is the
    # form written specifically for information access.
    granting = next(
        (
            resolved
            for resolved in (resolved_8821, resolved_2848)
            if resolved.state == crud_auth.AUTH_STATE_ACTIVE
        ),
        None,
    )

    best_state = min(
        (resolved_8821.state, resolved_2848.state),
        key=crud_auth.AUTH_STATE_PRECEDENCE_BEST_FIRST.index,
    )
    # "not_on_file" is preserved for the one case where it is true. Any other
    # state reports itself, because telling a firm nothing is on file when a
    # lapsed authorization is sitting right there is the bug this replaces.
    authorization_status = (
        "not_on_file" if best_state == crud_auth.AUTH_STATE_NONE else best_state
    )

    requests = crud_transcript.list_transcript_requests(
        db=db,
        firm_id=current_firm.id,
        client_id=client_id,
    )

    return {
        "client_id": str(client_id),
        "can_request": granting is not None,
        "authorization_status": authorization_status,
        "irs_authorization_id": str(granting.record.id) if granting else None,
        "state_8821": resolved_8821.state,
        "state_2848": resolved_2848.state,
        "expires_on_8821": resolved_8821.expires_on,
        "expires_on_2848": resolved_2848.expires_on,
        "authorization_id_8821": (
            str(resolved_8821.record.id) if resolved_8821.record else None
        ),
        "authorization_id_2848": (
            str(resolved_2848.record.id) if resolved_2848.record else None
        ),
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
    return transcript_request_service.update_transcript_request(db, request, payload)
