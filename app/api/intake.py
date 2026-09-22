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
from app.schemas.intake_pricing_config import IntakePricingConfigOut
from app.schemas.lead import LeadCreate
from app.services.behavioral_log import log_event
from app.services.lead_attribution import (
    derive_referral_source,
    derive_source_placement,
    derive_source_platform,
)
from app.services.pricing_config_service import get_public_intake_config

# _derive_source_platform moved to app/services/lead_attribution.py on
# Sep 17, 2026 (R6), so all three attribution derivations live together as
# pure functions. The alias keeps the old private name importable from here.
_derive_source_platform = derive_source_platform


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


# ---------------------------------------------------------------------------
# Public pricing-config endpoint -- the question tree the intake form renders.
# ---------------------------------------------------------------------------
@router.get("/{slug}/pricing-config", response_model=IntakePricingConfigOut)
@limiter.limit("30/minute")
def intake_pricing_config(
    slug: str,
    request: Request,
    db: Session = Depends(get_db),
):
    """Which services this firm offers, and the questions it has configured.

    NO AUTH DEPENDENCY, ON PURPOSE. This is a public lead-facing surface by
    design (CRM Build Contract Addendum 1 section 9): the intake form is
    rendered to anonymous visitors who have no account and never will, so there
    is nobody to authenticate. It is safe to be public ONLY because
    get_public_intake_config strips every commercial fact before the response
    leaves the service layer. No price, no base_fee, no pricing_mode, no role,
    no guard_threshold, no tier ranges, no chain structure, no firm_id, no row
    ids beyond the opaque system vocabulary option ids, no timestamps. What
    survives is the set of facts a lead needs in order to answer a question.
    tests/test_intake_pricing_config.py enforces that promise by walking a
    serialized response recursively and failing on any forbidden key at any
    depth. If that guard is ever deleted, this endpoint stops being safe to
    serve without auth.

    NOT PAGINATED, ON PURPOSE. Same reasoning as GET /api/pricing/config: this
    is a single configuration object for one firm, not a list resource, so
    PaginatedResponse[T] has nothing to apply to. The services collection
    inside it is bounded by how many engagement types the firm offers.

    Rate limited more generously than the 5/minute on submit below, because
    that limit guards a write that creates a lead and this one guards a read
    that creates nothing. A visitor legitimately loads this once per form view.

    No behavioral event is logged here. Form-view and form-interaction events
    belong to Ben's intake form phase and are captured there with the lead
    context this anonymous read does not have.
    """
    firm = get_firm_by_slug(db, slug)
    if not firm:
        # Same message and status as the config endpoint above, so the error
        # shape cannot be used to enumerate which slugs exist.
        raise HTTPException(status_code=404, detail="Intake form not found")
    return get_public_intake_config(db, firm_id=firm.id)


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
    #
    # All three attribution derivations run HERE and only here (R7,
    # Sep 17, 2026): derivation is a property of how the lead arrived, so
    # it happens once, at public intake creation. A later staff edit to
    # any UTM field does NOT re-derive any of the three -- the firm's own
    # correction must not be overwritten by a machine reading of a tag.
    derived_platform = derive_source_platform(body.utm_source)
    derived_placement = derive_source_placement(
        body.utm_content, body.utm_term, body.utm_medium
    )
    # Layer 1 from the derived platform plus utm_medium (R5). None means
    # not knowable, and the null stands; the all-five-empty case is the
    # one that answers website. This replaces the former comment claiming
    # the CRM contract does not specify the mapping, which R5 now does.
    derived_referral_source = derive_referral_source(
        derived_platform,
        body.utm_source,
        body.utm_medium,
        body.utm_campaign,
        body.utm_content,
        body.utm_term,
    )
    lead_in = LeadCreate(
        name=body.name,
        email=body.email,
        phone=body.phone,
        service_interest=body.service_interest,
        source_platform=derived_platform,
        utm_campaign=body.utm_campaign,
        utm_source=body.utm_source,
        utm_medium=body.utm_medium,
        utm_content=body.utm_content,
        utm_term=body.utm_term,
        provenance=LeadProvenance.crm_lead,
    )
    # Fills an empty value only (R5). A new lead's referral_source is
    # always empty here, so the guard is about intent rather than need:
    # a derivation that answers None must leave the field alone.
    if derived_referral_source is not None:
        lead_in.referral_source = derived_referral_source
    lead = create_lead(
        db=db,
        lead_in=lead_in,
        firm_id=firm.id,
        provenance=LeadProvenance.crm_lead,
        source_placement=derived_placement,
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
