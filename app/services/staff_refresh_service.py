# app/services/staff_refresh_service.py

import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import (
    create_access_token,
    generate_staff_refresh_token,
    hash_staff_refresh_token,
)
from app.core.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)

settings = get_settings()

REFRESH_INACTIVITY_HOURS = 8    # Rolling window — resets on each use
REFRESH_ABSOLUTE_HOURS = 72     # Hard cap — no renewal past this point


def issue_staff_refresh_token(user: User, db: Session) -> str:
    """
    Generates a new refresh token, stores the hash on the user record,
    sets the expiry to now + REFRESH_INACTIVITY_HOURS, and commits.
    Returns the raw token (caller must store in HttpOnly cookie).
    """
    raw_token = generate_staff_refresh_token()
    token_hash = hash_staff_refresh_token(raw_token)
    expires_at = datetime.now(timezone.utc) + timedelta(hours=REFRESH_INACTIVITY_HOURS)

    user.staff_refresh_token_hash = token_hash
    user.staff_refresh_expires_at = expires_at
    db.commit()

    return raw_token


def refresh_staff_access_token(raw_token: str, db: Session) -> dict | None:
    """
    Validates the refresh token. If valid and not expired:
    - Issues a new access token
    - Rolls the refresh token expiry forward by REFRESH_INACTIVITY_HOURS
    - Enforces the REFRESH_ABSOLUTE_HOURS hard cap from login time
    - Returns {"access_token": str, "refresh_token": str} on success
    - Returns None if token is invalid, expired, or user is inactive

    The returned refresh_token is a NEW raw token — caller must update
    the cookie. This rotation invalidates the old token immediately.
    """
    token_hash = hash_staff_refresh_token(raw_token)
    now = datetime.now(timezone.utc)

    stmt = select(User).where(
        User.staff_refresh_token_hash == token_hash,
        User.staff_refresh_expires_at > now,
        User.is_active == True,
    )
    user = db.execute(stmt).scalar_one_or_none()

    if user is None:
        return None

    # Carry forward the session jti; heal legacy sessions that lack one
    jti = user.current_session_jti
    if jti is None:
        jti = str(uuid.uuid4())
        user.current_session_jti = jti

    # Issue new access token
    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "firm_id": str(user.firm_id),
            "role": user.role,
            "token_version": user.token_version,
            "jti": jti,
        }
    )

    # Roll the refresh token — new token, new hash, new expiry
    new_raw_token = generate_staff_refresh_token()
    new_hash = hash_staff_refresh_token(new_raw_token)

    # Inactivity window resets on each use
    new_expires = now + timedelta(hours=REFRESH_INACTIVITY_HOURS)

    user.staff_refresh_token_hash = new_hash
    user.staff_refresh_expires_at = new_expires
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": new_raw_token,
    }


def revoke_staff_refresh_token(user: User, db: Session) -> None:
    """
    Clears the refresh token fields on logout. Immediately invalidates
    the session — the old cookie value will never match again.
    """
    user.staff_refresh_token_hash = None
    user.staff_refresh_expires_at = None
    db.commit()
