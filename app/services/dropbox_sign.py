# app/services/dropbox_sign.py

import hashlib
import hmac
from datetime import datetime

import requests
from requests.auth import HTTPBasicAuth
from fastapi import HTTPException

from app.core.config import get_settings

_BASE_URL = "https://api.hellosign.com/v3"


def _get_auth() -> HTTPBasicAuth:
    settings = get_settings()
    return HTTPBasicAuth(settings.DROPBOX_SIGN_API_KEY, "")


def send_envelope(
    client_name: str,
    client_email: str,
    subject: str,
    message: str,
    pdf_bytes: bytes,
    expires_at: datetime | None = None,
) -> dict:
    """
    Sends a signature request via the Dropbox Sign API.

    Returns the full JSON response from Dropbox Sign on success.
    Raises HTTPException(502) if the upstream API call fails.
    """
    data: dict = {
        "title": subject,
        "subject": subject,
        "message": message,
        "signers[0][name]": client_name,
        "signers[0][email_address]": client_email,
    }
    if expires_at is not None:
        data["expires_at"] = int(expires_at.timestamp())

    files = {
        "file[0]": ("document.pdf", pdf_bytes, "application/pdf"),
    }

    r = requests.post(
        f"{_BASE_URL}/signature_request/send",
        auth=_get_auth(),
        data=data,
        files=files,
        timeout=30,
    )

    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Dropbox Sign API error: {r.status_code}",
        )

    return r.json()


def validate_webhook_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """
    Validates the HMAC-SHA256 signature Dropbox Sign attaches to every webhook POST.

    Uses hmac.compare_digest for timing-safe comparison to prevent timing attacks.
    Returns True if the signature is valid, False otherwise.
    """
    settings = get_settings()
    secret = settings.DROPBOX_SIGN_WEBHOOK_SECRET.encode()
    computed = hmac.new(secret, payload_bytes, hashlib.sha256).hexdigest()
    return hmac.compare_digest(computed, signature_header)


def download_signed_document(signature_request_id: str) -> bytes:
    """
    Downloads the completed signed PDF from Dropbox Sign.

    Returns raw PDF bytes on success.
    Raises HTTPException(502) if the upstream API call fails.
    """
    r = requests.get(
        f"{_BASE_URL}/signature_request/files/{signature_request_id}",
        auth=_get_auth(),
        params={"file_type": "pdf"},
        timeout=60,
    )

    if not r.ok:
        raise HTTPException(
            status_code=502,
            detail=f"Dropbox Sign API error: {r.status_code}",
        )

    return r.content


def send_reminder(signature_request_id: str, signer_email: str | None = None) -> dict:
    """
    Sends a reminder for an existing Dropbox Sign signature request.
    Raises HTTPException(502) if the upstream call fails.
    """
    data = {}
    if signer_email:
        data["email_address"] = signer_email

    r = requests.post(
        f"{_BASE_URL}/signature_request/remind/{signature_request_id}",
        auth=_get_auth(),
        data=data,
        timeout=30,
    )

    if not r.ok:
        import logging
        logging.getLogger(__name__).error(
            "Dropbox Sign remind failed: status=%s body=%s",
            r.status_code,
            r.text,
        )
        raise HTTPException(
            status_code=502,
            detail=f"Dropbox Sign reminder failed: {r.status_code} — {r.text}",
        )

    return r.json()
