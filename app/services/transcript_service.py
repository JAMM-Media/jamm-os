# app/services/transcript_service.py
"""
Transcript request service for JAMM PX.

The actual IRS API integration (IRS e-Services Transcript Delivery System
or a third-party provider like SurePrep / Tax Protection Plus) requires
post-launch credentials and a provider contract.

This phase implements the complete data flow with a stub at the API call
boundary. The stub logs the request and leaves status as 'pending'.

When the live integration is configured, only _submit_to_provider() needs
to be updated — the model, API, tests, and all surrounding logic stay
identical.

Authorization requirement:
  Every transcript request requires an active Form 8821 (Tax Information
  Authorization) for the client. The 8821 authorizes the firm to receive
  IRS transcripts on the client's behalf. Attempting to request a
  transcript without an active 8821 returns a clear 400 error.
"""

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud import irs_authorization as crud_auth
from app.crud import transcript_request as crud_transcript
from app.models.firm import Firm
from app.models.client import Client
from app.schemas.transcript_request import TranscriptRequestCreate
from app.services.audit_service import write_audit_log

logger = logging.getLogger(__name__)


def request_transcript(
    db: Session,
    request_in: TranscriptRequestCreate,
    firm: Firm,
    client: Client,
    requested_by_user_id: UUID,
) -> dict:
    """
    Submit a transcript request for a client.

    Steps:
    1. Verify client has an active Form 8821 on file
    2. Create TranscriptRequest record (status: pending)
    3. Call stub IRS provider (logs request, does nothing else)
    4. Write audit log
    5. Return the TranscriptRequest record

    Returns: {"request": TranscriptRequest, "authorization_required": False}

    If no active 8821 exists, raises ValueError with a clear message.
    The caller (API layer) converts this to a 400 response.
    """
    # Step 1 — Verify active 8821 on file
    active_auth = crud_auth.get_active_authorization_for_client(
        db=db,
        firm_id=firm.id,
        client_id=client.id,
        form_type="8821",
    )

    if not active_auth:
        raise ValueError(
            f"No active Form 8821 (Tax Information Authorization) on file for "
            f"{client.name}. An active 8821 is required before requesting IRS "
            f"transcripts. Please send and obtain a signed 8821 first."
        )

    # Step 2 — Create transcript request record
    transcript = crud_transcript.create_transcript_request(
        db=db,
        firm_id=firm.id,
        client_id=client.id,
        irs_authorization_id=active_auth.id,
        transcript_type=request_in.transcript_type,
        tax_year=request_in.tax_year,
        requested_by=requested_by_user_id,
    )

    # Step 3 — Submit to provider (stub)
    _submit_to_provider_stub(transcript_id=transcript.id, client=client, request_in=request_in)

    # Step 4 — Audit log
    write_audit_log(
        db=db,
        firm_id=firm.id,
        actor_id=requested_by_user_id,
        action="transcript_request.submitted",
        entity_type="transcript_request",
        entity_id=transcript.id,
    )

    return {
        "request": transcript,
        "authorization_required": False,
    }


def _submit_to_provider_stub(transcript_id, client, request_in) -> None:
    """
    Stub for the IRS transcript provider API call.

    In production, this will be replaced with a real call to either:
    - IRS e-Services Transcript Delivery System (TDS) directly
    - A third-party aggregator (SurePrep, Tax Protection Plus, etc.)

    The stub logs the request details so the flow is fully traceable
    in development and during the demo period.

    When a real provider is configured:
    1. Replace this function body with the actual API call
    2. On success: update TranscriptRequest.provider_reference_id
    3. On retrieval: update status to 'retrieved', store PDF in S3,
       create Document record with category='irs_transcript',
       set document_id on the TranscriptRequest
    4. On failure: update status to 'failed', set error_message
    """
    logger.info(
        f"[TRANSCRIPT STUB] Request submitted — "
        f"id={transcript_id}, "
        f"client={client.name}, "
        f"type={request_in.transcript_type}, "
        f"year={request_in.tax_year}. "
        f"Awaiting live IRS provider integration."
    )
