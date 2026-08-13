# app/api/intake.py

import requests as http_requests
from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import Optional

from app.core.config import get_settings
from app.core.rate_limit import limiter, check_email_rate_limit
from app.crud.firm import get_firm_by_slug
from app.crud.lead import create_lead
from app.db.session import get_db
from app.core.enums import LeadProvenance
from app.schemas.lead import LeadCreate
from app.services.behavioral_log import log_event

router = APIRouter(prefix="/intake", tags=["Intake"])


# ---------------------------------------------------------------------------
# Public config endpoint -- returns only the safe public subset of firm info.
# The Turnstile site key is safe to expose publicly by design; the secret key
# never leaves the backend.
# ---------------------------------------------------------------------------
@router.get("/{slug}/config")
def intake_config(slug: str, db: Session = Depends(get_db)):
    firm = get_firm_by_slug(db, slug)
    if not firm:
        raise HTTPException(status_code=404, detail="Intake form not found")
    settings = get_settings()
    return {
        "firm_name": firm.name,
        "slug": firm.slug,
        "turnstile_site_key": settings.TURNSTILE_SITE_KEY,
    }


class IntakeSubmitBody(BaseModel):
    name: str
    email: str
    phone: Optional[str] = None
    service_interest: Optional[str] = None
    # Freeform "how did you hear about us". The Lead model has no dedicated
    # text field for attribution notes yet -- referral_source is the structured
    # enum version and no freeform counterpart exists. This value is accepted
    # here for completeness but is not persisted in this task. A future
    # migration should add an attribution_notes: Text column to leads.
    how_did_you_hear: Optional[str] = None
    utm_campaign: Optional[str] = None
    utm_source: Optional[str] = None
    utm_medium: Optional[str] = None
    utm_content: Optional[str] = None
    utm_term: Optional[str] = None
    turnstile_token: str


# ---------------------------------------------------------------------------
# Public submit endpoint -- the ONE place in this codebase that creates a
# lead with provenance=crm_lead. Every other creation path uses firm_entered.
# ---------------------------------------------------------------------------
@router.post("/{slug}/submit", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
def intake_submit(
    slug: str,
    body: IntakeSubmitBody,
    request: Request,
    db: Session = Depends(get_db),
):
    settings = get_settings()

    # a. Look up firm.
    firm = get_firm_by_slug(db, slug)
    if not firm:
        raise HTTPException(status_code=404, detail="Intake form not found")

    # b. Verify Turnstile token server-side.
    remote_ip = request.client.host if request.client else None
    ts_resp = http_requests.post(
        "https://challenges.cloudflare.com/turnstile/v0/siteverify",
        data={
            "secret": settings.TURNSTILE_SECRET_KEY,
            "response": body.turnstile_token,
            **({"remoteip": remote_ip} if remote_ip else {}),
        },
        timeout=5,
    )
    if not ts_resp.ok or not ts_resp.json().get("success"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Security check failed. Please try again.",
        )

    # c. Email-based rate limit -- matches portal's exact call shape and numbers.
    if not check_email_rate_limit(body.email, max_requests=3, window_seconds=900):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many submissions from this email. Please wait a few minutes.",
        )

    # d. Create lead with crm_lead provenance.
    # referral_source is left null -- we do not attempt to map raw UTM strings
    # to ReferralSource enum values in this task. That mapping is a deliberate
    # design decision the CRM contract does not specify yet.
    lead_in = LeadCreate(
        name=body.name,
        email=body.email,
        phone=body.phone,
        service_interest=body.service_interest,
        utm_campaign=body.utm_campaign,
        utm_source=body.utm_source,
        utm_medium=body.utm_medium,
        utm_content=body.utm_content,
        utm_term=body.utm_term,
        provenance=LeadProvenance.crm_lead,
    )
    lead = create_lead(
        db=db,
        lead_in=lead_in,
        firm_id=firm.id,
        provenance=LeadProvenance.crm_lead,
    )

    # e. Behavioral event.
    log_event(
        event_type="lead.created",
        firm_id=firm.id,
        entity_type="lead",
        entity_id=lead.id,
        actor_type="visitor",
    )

    # f. No notification -- NotificationType has no new_lead value and adding
    # one is out of scope for this task.

    return {"status": "ok", "message": "Thank you. We'll be in touch shortly."}
