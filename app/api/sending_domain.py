# app/api/sending_domain.py

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.models.user import User
from app.services import domain_service

router = APIRouter(prefix="/sending-domain", tags=["sending_domain"])


class RegisterDomainRequest(BaseModel):
    domain: str


class DnsRecordsResponse(BaseModel):
    domain: str
    dkim_host: str
    dkim_value: str
    return_path_host: str
    return_path_value: str
    verified: bool


class VerifyResponse(BaseModel):
    domain: str
    verified: bool
    dkim_verified: bool
    return_path_verified: bool
    message: str


class RemoveResponse(BaseModel):
    message: str


@router.post("/register", response_model=DnsRecordsResponse)
def register_domain(
    body: RegisterDomainRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    from app.core.config import get_settings
    from app.crud import firm as crud_firm

    settings = get_settings()
    token = settings.POSTMARK_ACCOUNT_TOKEN
    if not token:
        raise HTTPException(status_code=503, detail="Postmark account token not configured.")

    domain = body.domain.strip().lower()
    for prefix in ("https://", "http://"):
        if domain.startswith(prefix):
            domain = domain[len(prefix):]
    if not domain:
        raise HTTPException(status_code=400, detail="Domain is required.")
    if " " in domain:
        raise HTTPException(status_code=400, detail="Domain must not contain spaces.")
    if "/" in domain:
        raise HTTPException(status_code=400, detail="Domain must not contain a path. Provide only the domain name (e.g. smithcpa.com).")

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    domain_service.register_sending_domain(
        db=db, firm=firm, domain=domain, token=token, current_user_id=current_user.id,
    )

    return DnsRecordsResponse(
        domain=domain,
        dkim_host=firm.sending_domain_dkim_host or "",
        dkim_value=firm.sending_domain_dkim_value or "",
        return_path_host=firm.sending_domain_return_path_host or "",
        return_path_value=firm.sending_domain_return_path_value or "",
        verified=False,
    )


@router.post("/verify", response_model=VerifyResponse)
def verify_domain(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    from app.core.config import get_settings
    from app.crud import firm as crud_firm

    settings = get_settings()
    token = settings.POSTMARK_ACCOUNT_TOKEN
    if not token:
        raise HTTPException(status_code=503, detail="Postmark account token not configured.")

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    if not firm.sending_domain or not firm.sending_domain_postmark_id:
        raise HTTPException(status_code=400, detail="No domain registered. Register a domain first.")

    dkim_verified, return_path_verified = domain_service.verify_sending_domain(
        db=db, firm=firm, token=token, current_user_id=current_user.id,
    )

    fully_verified = dkim_verified and return_path_verified
    return VerifyResponse(
        domain=firm.sending_domain,
        verified=fully_verified,
        dkim_verified=dkim_verified,
        return_path_verified=return_path_verified,
        message=(
            "Domain verified successfully."
            if fully_verified
            else "DNS records not yet detected. Make sure the records are added and try again in a few minutes."
        ),
    )


@router.delete("", response_model=RemoveResponse)
def remove_domain(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_firm_owner),
):
    from app.core.config import get_settings
    from app.crud import firm as crud_firm

    settings = get_settings()
    token = settings.POSTMARK_ACCOUNT_TOKEN

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    domain_service.remove_sending_domain(db=db, firm=firm, token=token, current_user_id=current_user.id)

    return RemoveResponse(message="Sending domain removed.")
