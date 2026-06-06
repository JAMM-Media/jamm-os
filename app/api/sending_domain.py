# app/api/sending_domain.py

import logging
import requests
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.roles import require_firm_owner
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/sending-domain", tags=["sending_domain"])

_POSTMARK_API_BASE = "https://api.postmarkapp.com"


def _account_headers(token: str) -> dict:
    return {
        "X-Postmark-Account-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


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
    from app.services.behavioral_log import log_event

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

    try:
        resp = requests.post(
            f"{_POSTMARK_API_BASE}/domains",
            json={"Name": domain},
            headers=_account_headers(token),
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.error("Postmark domain register failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to reach Postmark API.")

    if not resp.ok:
        try:
            detail = resp.json().get("Message", resp.text)
        except Exception:
            detail = resp.text
        raise HTTPException(status_code=400, detail=detail)

    data = resp.json()
    firm.sending_domain = domain
    firm.sending_domain_postmark_id = data["ID"]
    firm.sending_domain_verified = False
    firm.sending_domain_dkim_host = data.get("DKIMPendingHost", "")
    firm.sending_domain_dkim_value = data.get("DKIMPendingTextValue", "")
    firm.sending_domain_return_path_host = data.get("ReturnPathDomain", "")
    firm.sending_domain_return_path_value = data.get("ReturnPathDomainCNAMEValue", "")
    db.commit()

    log_event(
        firm_id=firm.id,
        event_type="sending_domain.registered",
        entity_type="firm",
        entity_id=firm.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={"domain": domain},
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
    from app.services.behavioral_log import log_event

    settings = get_settings()
    token = settings.POSTMARK_ACCOUNT_TOKEN
    if not token:
        raise HTTPException(status_code=503, detail="Postmark account token not configured.")

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    if not firm.sending_domain or not firm.sending_domain_postmark_id:
        raise HTTPException(status_code=400, detail="No domain registered. Register a domain first.")

    pid = firm.sending_domain_postmark_id

    try:
        requests.post(
            f"{_POSTMARK_API_BASE}/domains/{pid}/verifyDkim",
            headers=_account_headers(token),
            timeout=15,
        )
        requests.post(
            f"{_POSTMARK_API_BASE}/domains/{pid}/verifyReturnPath",
            headers=_account_headers(token),
            timeout=15,
        )
        status_resp = requests.get(
            f"{_POSTMARK_API_BASE}/domains/{pid}",
            headers=_account_headers(token),
            timeout=15,
        )
    except requests.RequestException as exc:
        logger.error("Postmark domain verify failed: %s", exc)
        raise HTTPException(status_code=502, detail="Failed to reach Postmark API.")

    if not status_resp.ok:
        try:
            detail = status_resp.json().get("Message", status_resp.text)
        except Exception:
            detail = status_resp.text
        raise HTTPException(status_code=400, detail=detail)

    data = status_resp.json()
    dkim_verified = bool(data.get("DKIMVerified"))
    return_path_verified = bool(data.get("ReturnPathDomainVerified"))
    newly_verified = dkim_verified and return_path_verified and not firm.sending_domain_verified

    if dkim_verified and return_path_verified:
        firm.sending_domain_verified = True
        db.commit()

    if newly_verified:
        log_event(
            firm_id=firm.id,
            event_type="sending_domain.verified",
            entity_type="firm",
            entity_id=firm.id,
            actor_type="staff",
            actor_id=current_user.id,
            metadata={"domain": firm.sending_domain},
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
    from app.services.behavioral_log import log_event

    settings = get_settings()
    token = settings.POSTMARK_ACCOUNT_TOKEN

    firm = crud_firm.get_firm(db, current_user.firm_id)
    if not firm:
        raise HTTPException(status_code=404, detail="Firm not found.")

    if firm.sending_domain_postmark_id and token:
        try:
            requests.delete(
                f"{_POSTMARK_API_BASE}/domains/{firm.sending_domain_postmark_id}",
                headers=_account_headers(token),
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.warning("Postmark domain delete failed: %s", exc)

    old_domain = firm.sending_domain
    firm.sending_domain = None
    firm.sending_domain_postmark_id = None
    firm.sending_domain_verified = False
    firm.sending_domain_dkim_host = None
    firm.sending_domain_dkim_value = None
    firm.sending_domain_return_path_host = None
    firm.sending_domain_return_path_value = None
    db.commit()

    log_event(
        firm_id=firm.id,
        event_type="sending_domain.removed",
        entity_type="firm",
        entity_id=firm.id,
        actor_type="staff",
        actor_id=current_user.id,
        metadata={"domain": old_domain},
    )

    return RemoveResponse(message="Sending domain removed.")
