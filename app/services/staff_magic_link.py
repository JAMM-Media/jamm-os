# app/services/staff_magic_link.py

import hashlib
import logging
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.enums import StaffAuthPolicy
from app.core.security import create_access_token
from app.models.firm import Firm
from app.models.user import User
from app.services.email_service import EmailService

settings = get_settings()
logger = logging.getLogger(__name__)

_MAGIC_LINK_EXPIRY_MINUTES = 30


def request_staff_magic_link(email: str, db: Session) -> None:
    """
    Generate a magic link for a staff user if policy allows it.
    Always returns None — never reveals whether the email exists or what the policy is.
    Sends the link via email if appropriate.
    """
    user = db.execute(
        select(User).where(User.email == email, User.is_active.is_(True))
    ).scalar_one_or_none()

    if user is None:
        return

    firm = db.execute(select(Firm).where(Firm.id == user.firm_id)).scalar_one_or_none()
    if firm is None:
        return

    policy = firm.staff_auth_policy or StaffAuthPolicy.EITHER.value
    if policy == StaffAuthPolicy.PASSWORD_ONLY.value:
        return

    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    user.magic_link_token_hash = token_hash
    user.magic_link_expires_at = datetime.now(timezone.utc) + timedelta(minutes=_MAGIC_LINK_EXPIRY_MINUTES)
    db.commit()

    if user.email:
        try:
            magic_url = f"{settings.FRONTEND_URL}/login/magic?token={raw_token}"
            html_body = (
                f"<p>Click the link below to sign in to JAMM PX. "
                f"This link expires in {_MAGIC_LINK_EXPIRY_MINUTES} minutes and can only be used once.</p>"
                f"<p><a href='{magic_url}'>{magic_url}</a></p>"
                f"<p>If you did not request this link, you can safely ignore this email.</p>"
            )
            EmailService._send_raw(
                user.email,
                "Your JAMM PX sign-in link",
                html_body,
                "JAMM PX",
            )
        except Exception as e:
            logger.error("Staff magic link email failed: user_id=%s error=%s", user.id, str(e))


def verify_staff_magic_link(token: str, db: Session) -> Tuple[Optional[dict], Optional[str]]:
    """
    Verify a staff magic link token.
    Returns (jwt_dict, None) on success or (None, error_message) on failure.
    Clears the token after successful use (one-time use).
    """
    token_hash = hashlib.sha256(token.encode()).hexdigest()

    user = db.execute(
        select(User).where(
            User.magic_link_token_hash == token_hash,
            User.magic_link_expires_at > datetime.now(timezone.utc),
        )
    ).scalar_one_or_none()

    if user is None:
        return None, "This link is invalid or has expired. Please request a new one."

    session_jti = str(uuid.uuid4())
    user.magic_link_token_hash = None
    user.magic_link_expires_at = None
    user.current_session_jti = session_jti
    db.commit()

    access_token = create_access_token(data={
        "sub": str(user.id),
        "firm_id": str(user.firm_id),
        "token_version": user.token_version,
        "jti": session_jti,
    })

    return {"access_token": access_token, "token_type": "bearer"}, None
