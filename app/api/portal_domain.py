# app/api/portal_domain.py

# NOTE: This wizard handles the firm-side CNAME setup and verification tracking.
# After a firm verifies their domain here, the domain must also be added to the
# Vercel project dashboard (vercel.com) to enable actual routing. This is a
# manual step performed by the JAMM PX team.

import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.models.user import User
from app.services import domain_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/portal-domain", tags=["portal_domain"])

_CNAME_VALUE = "cname.vercel-dns.com"


class RegisterDomainRequest(BaseModel):
    domain: str


class DnsRecordsResponse(BaseModel):
    domain: str
    cname_host: str
    cname_value: str
    txt_host: str
    txt_value: str
    verified: bool


class VerifyResponse(BaseModel):
    domain: str
    verified: bool
    cname_resolved: bool
    txt_verified: bool
    message: str


class RemoveResponse(BaseModel):
    message: str


@router.post("/register", response_model=DnsRecordsResponse)
def register_domain(
    body: RegisterDomainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    from app.crud import firm as crud_firm

    domain = body.domain.strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    if not domain:
        raise HTTPException(status_code=400, detail="Domain is required.")
    if " " in domain:
        raise HTTPException(status_code=400, detail="Domain must not contain spaces.")
    if "/" in domain:
        raise HTTPException(status_code=400, detail="Domain must not contain a path. Provide only the domain name (e.g. portal.smithcpa.com).")
    if "." not in domain:
        raise HTTPException(status_code=400, detail="Domain must contain at least one dot.")

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    token = domain_service.register_portal_domain(
        db=db, firm=firm, domain=domain, current_user_id=current_user.id,
    )

    return DnsRecordsResponse(
        domain=domain,
        cname_host=domain,
        cname_value=_CNAME_VALUE,
        txt_host="_jammpx-verify." + domain,
        txt_value=token,
        verified=False,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify_domain(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    from app.crud import firm as crud_firm

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    if not firm.portal_domain:
        raise HTTPException(status_code=400, detail="No domain registered. Register a domain first.")

    cname_resolved, txt_verified = domain_service.verify_portal_domain(
        db=db, firm=firm, current_user_id=current_user.id,
    )

    fully_verified = cname_resolved and txt_verified
    return VerifyResponse(
        domain=firm.portal_domain,
        verified=fully_verified,
        cname_resolved=cname_resolved,
        txt_verified=txt_verified,
        message=(
            "Domain verified successfully."
            if fully_verified
            else "DNS records not yet detected. Make sure both records are added and try again in a few minutes."
        ),
    )


@router.delete("", response_model=RemoveResponse)
def remove_domain(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    from app.crud import firm as crud_firm

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    domain_service.remove_portal_domain(db=db, firm=firm, current_user_id=current_user.id)

    return RemoveResponse(message="Portal domain removed.")


@router.get("/records", response_model=DnsRecordsResponse)
def get_records(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    from app.crud import firm as crud_firm

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    if not firm.portal_domain:
        raise HTTPException(status_code=404, detail="No portal domain configured.")

    return DnsRecordsResponse(
        domain=firm.portal_domain,
        cname_host=firm.portal_domain,
        cname_value=_CNAME_VALUE,
        txt_host="_jammpx-verify." + firm.portal_domain,
        txt_value=firm.portal_domain_verification_token or "",
        verified=firm.portal_domain_verified,
    )
