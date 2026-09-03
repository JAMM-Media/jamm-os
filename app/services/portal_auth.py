# app/services/portal_auth.py

"""
Portal authentication service.

Security notes:
- Portal JWTs carry scope="client_portal" — this claim is the enforcement wall
  that prevents staff tokens from being used on portal endpoints and vice versa.
- Refresh tokens are high-entropy random strings; SHA-256 hash storage is
  appropriate (Argon2 is reserved for low-entropy user passwords).
- verify_portal_password never raises — VerifyMismatchError is caught and
  returns False so timing/error-message side channels are minimised.
"""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

import bcrypt as _bcrypt
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.core.config import get_settings
from app.crud import portal_session as crud_portal_session
from app.models.client import Client
from app.models.portal_session import PortalSession
from app.services.behavioral_log import log_event

settings = get_settings()

_pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


# ---------------------------------------------------------------------------
# Password helpers
# ---------------------------------------------------------------------------

def hash_portal_password(password: str) -> str:
    """Hash a client's portal password using Argon2 (legacy invite-accept flow)."""
    return _pwd_context.hash(password)


def hash_portal_password_bcrypt(password: str) -> str:
    """Hash a portal password using bcrypt (new set-password flow)."""
    return _bcrypt.hashpw(password.encode(), _bcrypt.gensalt()).decode()


def verify_portal_password(plain: str, hashed: str) -> bool:
    """
    Verify a portal password. Handles both bcrypt (new) and argon2 (legacy).
    Never raises — returns False on any failure.
    """
    try:
        if hashed.startswith("$2"):
            return _bcrypt.checkpw(plain.encode(), hashed.encode())
        return _pwd_context.verify(plain, hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Token helpers
# ---------------------------------------------------------------------------

def generate_invite_token() -> str:
    return secrets.token_urlsafe(32)


def generate_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """
    SHA-256 hash of the refresh token.
    Refresh tokens are already high-entropy random strings — Argon2 is
    unnecessary and would add latency on every token rotation.
    """
    return hashlib.sha256(token.encode()).hexdigest()


def create_portal_access_token(
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
    jti: str,
) -> str:
    """
    Creates a signed JWT for portal access.

    The scope="client_portal" claim is the enforcement wall — portal endpoints
    MUST verify this claim so staff tokens can never be used on portal routes.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.PORTAL_ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": str(client_id),
        "firm_id": str(firm_id),
        "scope": "client_portal",
        "jti": jti,
        "type": "access",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_preview_access_token(
    client_id: uuid.UUID,
    firm_id: uuid.UUID,
) -> str:
    """
    Creates a short-lived JWT for staff-initiated portal previews.

    Uses scope='portal_staff_preview' (distinct from 'client_portal') so this
    token is accepted only by preview-specific endpoints. All regular portal
    write endpoints check for scope='client_portal' and reject this token,
    preventing any accidental write operations via the preview session.

    Expiry: 10 minutes. Sufficient for a branding review; short enough to limit
    risk if the URL is shared or accidentally logged.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=10)
    payload = {
        "sub": str(client_id),
        "firm_id": str(firm_id),
        "scope": "portal_staff_preview",
        "exp": expire,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_preview_access_token(token: str) -> dict:
    """
    Decode and validate a portal staff preview token.

    Raises HTTP 401 if invalid, expired, or wrong scope.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate preview credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise credentials_exception
    if payload.get("scope") != "portal_staff_preview":
        raise credentials_exception
    return payload


def decode_portal_access_token(token: str) -> dict:
    """
    Decode and validate a portal access token.

    Raises HTTP 401 if:
    - Token is invalid/expired (JWTError)
    - scope is not "client_portal" (prevents staff tokens from being used here)
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate portal credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError:
        raise credentials_exception

    if payload.get("scope") != "client_portal":
        raise credentials_exception

    return payload


# ---------------------------------------------------------------------------
# Authentication helpers
# ---------------------------------------------------------------------------

def login_portal_with_password(
    db: Session,
    email: str,
    password: str,
    firm_id: Optional[uuid.UUID] = None,
) -> Tuple[Optional[Client], Optional[str]]:
    """
    Returns (client, None) on success or (None, error_code) on failure.
    error_code values: "not_found", "no_password", "wrong_password"
    Distinguishes 'no_password' so the caller can return a helpful hint.
    """
    stmt = select(Client).where(
        Client.email == email,
        Client.portal_access_enabled.is_(True),
    )
    if firm_id is not None:
        stmt = stmt.where(Client.firm_id == firm_id)

    client = db.execute(stmt).scalar_one_or_none()
    if client is None:
        return None, "not_found"
    if not client.portal_password_hash:
        return None, "no_password"
    if not verify_portal_password(password, client.portal_password_hash):
        return None, "wrong_password"

    if client.portal_last_login_at is None:
        log_event(
            firm_id=client.firm_id,
            event_type="portal.first_login",
            entity_type="client",
            entity_id=client.id,
            actor_type="client",
            actor_id=None,
            metadata={
                "time_since_invitation_days": (
                    (datetime.now(timezone.utc) - client.portal_invited_at).days
                    if hasattr(client, 'portal_invited_at') and client.portal_invited_at
                    else None
                ),
                "login_method": "password",
            }
        )
    log_event(
        firm_id=client.firm_id,
        event_type="portal.login",
        entity_type="client",
        entity_id=client.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "time_of_day": datetime.now(timezone.utc).hour,
            "day_of_week": datetime.now(timezone.utc).weekday(),
        },
    )
    return client, None


def authenticate_portal_client(
    db: Session,
    email: str,
    password: str,
    firm_id: uuid.UUID,
) -> Optional[Client]:
    """
    Verify email + password for a portal-enabled client.

    Queries by email AND firm_id AND portal_access_enabled to ensure the client
    belongs to the correct firm and has been granted portal access.
    Never reveals which check failed — always returns None on any failure.
    """
    stmt = select(Client).where(
        Client.email == email,
        Client.firm_id == firm_id,
        Client.portal_access_enabled.is_(True),
    )
    client = db.execute(stmt).scalar_one_or_none()
    if client is None:
        return None
    if not client.portal_password_hash:
        return None
    if not verify_portal_password(password, client.portal_password_hash):
        return None
    if client.portal_last_login_at is None:
        log_event(
            firm_id=firm_id,
            event_type="portal.first_login",
            entity_type="client",
            entity_id=client.id,
            actor_type="client",
            actor_id=None,
            metadata={
                "time_since_invitation_days": (
                    (datetime.now(timezone.utc) - client.portal_invited_at).days
                    if hasattr(client, 'portal_invited_at') and client.portal_invited_at
                    else None
                ),
                "login_method": "magic_link",
            }
        )
    log_event(
        firm_id=firm_id,
        event_type="portal.login",
        entity_type="client",
        entity_id=client.id,
        actor_type="client",
        actor_id=None,
        metadata={
            "time_of_day": datetime.now(timezone.utc).hour,
            "day_of_week": datetime.now(timezone.utc).weekday(),
        }
    )
    return client


def check_session_active(
    db: Session,
    jti: str,
    firm_id: uuid.UUID,
) -> Optional[PortalSession]:
    """
    Verify a portal session is still valid.

    Returns None if:
    - Session not found
    - Session is revoked
    - last_active_at is more than 30 minutes ago (inactivity timeout)

    If active, updates last_active_at before returning.
    """
    session = crud_portal_session.get_session_by_jti(db, jti, firm_id)
    if session is None or session.is_revoked:
        return None

    inactivity_limit = datetime.now(timezone.utc) - timedelta(
        minutes=settings.PORTAL_ACCESS_TOKEN_EXPIRE_MINUTES
    )
    # last_active_at may be timezone-naive from server_default — normalise
    last_active = session.last_active_at
    if last_active.tzinfo is None:
        last_active = last_active.replace(tzinfo=timezone.utc)

    if last_active < inactivity_limit:
        return None

    return crud_portal_session.update_session_activity(db, session)
