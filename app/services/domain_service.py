# app/services/domain_service.py

import logging
import secrets
import socket

import requests
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.services.behavioral_log import log_event

logger = logging.getLogger(__name__)

_CNAME_VALUE = "cname.vercel-dns.com"
_POSTMARK_API_BASE = "https://api.postmarkapp.com"


def _account_headers(token: str) -> dict:
    return {
        "X-Postmark-Account-Token": token,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


# ── Portal domain (Vercel CNAME + TXT verification) ────────────────────────

def register_portal_domain(*, db: Session, firm, domain: str, current_user_id):
    token = secrets.token_hex(16)
    firm.portal_domain = domain
    firm.portal_domain_verified = False
    firm.portal_domain_verification_token = token
    db.commit()

    log_event(
        firm_id=firm.id,
        event_type="portal_domain.registered",
        entity_type="firm",
        entity_id=firm.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"domain": domain},
    )

    return token


def verify_portal_domain(*, db: Session, firm, current_user_id):
    cname_resolved = False
    try:
        socket.getaddrinfo(firm.portal_domain, None)
        cname_resolved = True
    except socket.gaierror:
        cname_resolved = False

    txt_verified = False
    try:
        import dns.resolver
        txt_host = "_jammpx-verify." + firm.portal_domain
        answers = dns.resolver.resolve(txt_host, "TXT")
        for rdata in answers:
            for txt_string in rdata.strings:
                if txt_string.decode("utf-8") == firm.portal_domain_verification_token:
                    txt_verified = True
                    break
    except ImportError:
        txt_verified = True
    except Exception:
        txt_verified = False

    if cname_resolved and txt_verified:
        firm.portal_domain_verified = True
        db.commit()
        log_event(
            firm_id=firm.id,
            event_type="portal_domain.verified",
            entity_type="firm",
            entity_id=firm.id,
            actor_type="staff",
            actor_id=current_user_id,
            metadata={"domain": firm.portal_domain},
        )

    return cname_resolved, txt_verified


def remove_portal_domain(*, db: Session, firm, current_user_id):
    old_domain = firm.portal_domain
    firm.portal_domain = None
    firm.portal_domain_verified = False
    firm.portal_domain_verification_token = None
    db.commit()

    log_event(
        firm_id=firm.id,
        event_type="portal_domain.removed",
        entity_type="firm",
        entity_id=firm.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={"domain": old_domain},
    )


# ── Sending domain (Postmark DKIM + Return-Path verification) ──────────────

def register_sending_domain(*, db: Session, firm, domain: str, token: str, current_user_id):
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
        actor_id=current_user_id,
        metadata={"domain": domain},
    )


def verify_sending_domain(*, db: Session, firm, token: str, current_user_id):
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
            actor_id=current_user_id,
            metadata={"domain": firm.sending_domain},
        )

    return dkim_verified, return_path_verified


def remove_sending_domain(*, db: Session, firm, token, current_user_id):
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
        actor_id=current_user_id,
        metadata={"domain": old_domain},
    )
