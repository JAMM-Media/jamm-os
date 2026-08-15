# app/services/password_reset_service.py

import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import get_password_hash
from app.models.firm import Firm
from app.models.user import User
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

EXPIRY_HOURS = 1


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode()).hexdigest()


def validate_password_policy(password: str, policy: dict) -> str | None:
    if len(password) < policy.get("min_length", 8):
        return f"Password must be at least {policy.get('min_length', 8)} characters."
    if policy.get("require_uppercase") and not any(c.isupper() for c in password):
        return "Password must contain at least one uppercase letter."
    if policy.get("require_number") and not any(c.isdigit() for c in password):
        return "Password must contain at least one number."
    if policy.get("require_special") and not any(not c.isalnum() for c in password):
        return "Password must contain at least one special character."
    return None


def request_password_reset(email: str, db: Session) -> None:
    """
    Looks up the user by email. If found, generates a reset token,
    stores the SHA-256 hash, and sends the reset email.

    IMPORTANT: Always returns None regardless of whether the email
    exists. This prevents user enumeration — the caller always returns
    the same response to the client.

    Never raises. Email send failure is logged and silently ignored.
    """
    settings = get_settings()

    stmt = select(User).where(User.email == email.lower().strip())
    user = db.execute(stmt).scalar_one_or_none()

    if user is None:
        # Do not reveal whether the email exists
        return

    raw_token = secrets.token_hex(32)
    token_hash = _hash_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=EXPIRY_HOURS)

    user.password_reset_token_hash = token_hash
    user.password_reset_expires_at = expires_at
    db.commit()

    reset_url = f"{settings.FRONTEND_URL}/reset-password?token={raw_token}"

    try:
        EmailService.send_password_reset_email(
            to_email=user.email,
            recipient_name=user.full_name or user.email,
            reset_url=reset_url,
            expiry_hours=EXPIRY_HOURS,
        )
    except Exception as e:
        logger.error("Password reset email failed: user_id=%s error=%s", user.id, str(e))


def reset_password(token: str, new_password: str, db: Session) -> tuple[bool, str | None]:
    """
    Validates the token, checks the firm password policy, hashes the new
    password, updates the user record, and clears the reset token fields.

    Returns (True, None) on success.
    Returns (False, None) if the token is invalid or expired.
    Returns (False, error_message) if the password violates the firm policy.

    On success, increments token_version to invalidate all existing
    staff JWTs — forces a fresh login after password reset.
    """
    token_hash = _hash_token(token)
    now = datetime.now(timezone.utc)

    stmt = select(User).where(
        User.password_reset_token_hash == token_hash,
        User.password_reset_expires_at > now,
    )
    user = db.execute(stmt).scalar_one_or_none()

    if user is None:
        return False, None

    firm = db.query(Firm).filter(Firm.id == user.firm_id).first()
    firm_settings = firm.settings or {} if firm else {}
    # `or {}` rather than a .get default: the default only fires when the key is
    # absent, and the blob accepts arbitrary unvalidated values, so
    # password_policy can legitimately be present and null. validate_password_policy
    # calls .get on whatever it receives, so a null here would raise.
    policy = firm_settings.get("password_policy") or {}

    policy_error = validate_password_policy(new_password, policy)
    if policy_error:
        return False, policy_error

    user.hashed_password = get_password_hash(new_password)
    user.password_reset_token_hash = None
    user.password_reset_expires_at = None
    user.token_version = (user.token_version or 0) + 1

    db.commit()
    return True, None
