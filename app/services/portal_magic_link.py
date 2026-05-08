# app/services/portal_magic_link.py

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.client import Client
from app.models.firm import Firm
from app.models.portal_session import PortalSession
from app.schemas.portal import MagicLinkResponse
from app.services.email_service import EmailService
from app.services.behavioral_log import log_event

settings = get_settings()
logger = logging.getLogger(__name__)


def generate_magic_link(
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
    expiry_hours: int,
    db: Session,
) -> tuple[MagicLinkResponse, str]:
    client = db.execute(
        select(Client).where(
            Client.id == client_id,
            Client.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Client not found")

    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    session = db.execute(
        select(PortalSession).where(
            PortalSession.client_id == client_id,
            PortalSession.firm_id == firm_id,
            PortalSession.is_revoked.is_(False),
        )
    ).scalar_one_or_none()

    if session is None:
        session = PortalSession(
            firm_id=firm_id,
            client_id=client_id,
            refresh_token_hash=hashlib.sha256(secrets.token_hex(32).encode()).hexdigest(),
            access_jti=str(uuid.uuid4()),
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.PORTAL_SESSION_HARD_EXPIRE_DAYS),
        )
        db.add(session)
        db.flush()

    expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    session.magic_link_token_hash = token_hash
    session.magic_link_expires_at = expires_at
    db.commit()

    if client.email:
        try:
            firm = db.execute(select(Firm).where(Firm.id == firm_id)).scalar_one_or_none()
            firm_name = firm.name if firm else "Your Accounting Firm"
            magic_url = f"{settings.FRONTEND_URL}/portal/auth?token={raw_token}"
            html_body = (
                f"<p>Click the link below to access your client portal. "
                f"This link expires in {expiry_hours} hours and can only be used once.</p>"
                f"<p><a href='{magic_url}'>{magic_url}</a></p>"
            )
            EmailService._send_raw(client.email, "Your secure portal link", html_body, firm_name)
        except Exception as e:
            logger.error("Magic link email failed: client_id=%s error=%s", client_id, str(e))

    log_event(
        firm_id=firm_id,
        event_type="client.portal_invited",
        entity_type="client",
        entity_id=client_id,
        actor_type="staff",
        actor_id=None,
        metadata={
            "invitation_method": "magic_link",
            "days_since_client_created": None,
        }
    )
    return MagicLinkResponse(sent=True, expires_at=expires_at), raw_token


def exchange_magic_link(token: str, db: Session) -> str:
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    session = db.execute(
        select(PortalSession).where(
            PortalSession.magic_link_token_hash == token_hash,
            PortalSession.magic_link_expires_at > datetime.now(timezone.utc),
        )
    ).scalar_one_or_none()

    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired magic link",
        )

    session.magic_link_token_hash = None
    session.magic_link_expires_at = None

    new_jti = str(uuid.uuid4())
    session.access_jti = new_jti
    session.last_active_at = datetime.now(timezone.utc)
    db.commit()

    from app.services.portal_auth import create_portal_access_token
    return create_portal_access_token(session.client_id, session.firm_id, new_jti)
