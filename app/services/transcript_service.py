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
  Authorization) OR an active Form 2848 (Power of Attorney) for the client.
  Both authorize the firm to receive IRS transcripts on the client's behalf.
  The gate used to demand an 8821 specifically, which blocked firms holding a
  perfectly valid 2848. Without an active authorization of either type the
  request returns a 400 naming the real situation of each form type.
"""

import logging
from datetime import date
from uuid import UUID

from sqlalchemy.orm import Session

from app.crud import irs_authorization as crud_auth
from app.crud import transcript_request as crud_transcript
from app.models.firm import Firm
from app.models.client import Client
from app.schemas.transcript_request import TranscriptRequestCreate
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)


# What each resolved state actually means, in the firm's words. "lapsed" is
# absent on purpose: a lapse is described by _describe_form_state, which has
# to decide whether it can name a date.
_STATE_CLAUSES = {
    crud_auth.AUTH_STATE_ACTIVE: "active",
    crud_auth.AUTH_STATE_PENDING: "sent and awaiting signature",
    crud_auth.AUTH_STATE_REVOKED: "revoked",
    crud_auth.AUTH_STATE_NONE: "none on file",
}


def _format_lapse_date(value: date) -> str:
    """
    'March 20, 2025'. Written out rather than using %-d, which is not portable
    to Windows. The year is always shown: a lapse can be years old, and
    "expired March 20" with no year is a worse sentence than a long one.
    """
    return f"{value:%B} {value.day}, {value.year}"


def _describe_form_state(resolved) -> str:
    """
    One clause describing what actually exists for one form type.

    A lapse names its date when the record carries one. Where valid_until is
    null the lapse is stated without a date. Nothing is inferred: a firm
    reading an invented expiry date on a compliance message would have no way
    to tell it was invented.
    """
    if resolved.state == crud_auth.AUTH_STATE_LAPSED:
        if resolved.expires_on is not None:
            return f"expired {_format_lapse_date(resolved.expires_on)}"
        return "expired, with no expiry date on record"
    return _STATE_CLAUSES[resolved.state]


def _build_authorization_error(client, resolved_8821, resolved_2848) -> str:
    """
    The 400 body. It must say which situation actually applies to each form
    type, and it must never say nothing is on file when a record exists in
    any state. A firm that let an 8821 lapse and is told it never had one
    goes looking for a problem that is not there.
    """
    return (
        f"IRS transcripts for {client.name} require an active Form 8821 or "
        f"Form 2848, and neither is active. "
        f"Form 8821: {_describe_form_state(resolved_8821)}. "
        f"Form 2848: {_describe_form_state(resolved_2848)}. "
        f"Send an authorization and collect the signature before requesting "
        f"transcripts."
    )


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
    1. Verify client has an active Form 8821 or Form 2848 on file
    2. Create TranscriptRequest record (status: pending)
    3. Call stub IRS provider (logs request, does nothing else)
    4. Write audit log
    5. Return the TranscriptRequest record

    Returns: {"request": TranscriptRequest, "authorization_required": False}

    If neither form type is active, raises ValueError naming the real state
    of each. The caller (API layer) converts this to a 400 response.
    """
    # Step 1. Verify an active authorization of either form type.
    # Both 8821 and 2848 permit transcript access, so requiring an 8821
    # specifically blocked firms that hold a valid 2848 and nothing else.
    resolved_8821 = crud_auth.resolve_authorization_state(
        db=db,
        firm_id=firm.id,
        client_id=client.id,
        form_type="8821",
    )
    resolved_2848 = crud_auth.resolve_authorization_state(
        db=db,
        firm_id=firm.id,
        client_id=client.id,
        form_type="2848",
    )

    granting = next(
        (
            resolved
            for resolved in (resolved_8821, resolved_2848)
            if resolved.state == crud_auth.AUTH_STATE_ACTIVE
        ),
        None,
    )

    if granting is None:
        raise ValueError(
            _build_authorization_error(client, resolved_8821, resolved_2848)
        )

    active_auth = granting.record

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

    log_event(
        firm_id=firm.id,
        event_type="transcript_request.created",
        entity_type="transcript_request",
        entity_id=transcript.id,
        actor_type="staff",
        actor_id=requested_by_user_id,
        metadata={
            "client_id": str(client.id),
            "transcript_type": str(request_in.transcript_type) if hasattr(request_in, "transcript_type") else None,
            "authorization_required": True,
        }
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
