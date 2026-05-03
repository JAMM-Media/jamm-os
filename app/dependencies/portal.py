# app/dependencies/portal.py

"""
Portal authentication dependency.

get_current_portal_client() is the ONLY entry point into portal endpoints.
It MUST NOT be mixed with get_current_user() from the staff auth system.

The scope="client_portal" claim in the JWT is the enforcement wall that
prevents staff tokens from being accepted here.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.services.portal_auth import decode_portal_access_token, check_session_active

_bearer = HTTPBearer()


def get_current_portal_client(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Client:
    """
    FastAPI dependency that authenticates a portal client.

    Steps:
    1. Extract Bearer token from Authorization header (HTTPBearer raises 403 if missing).
    2. Decode and validate the JWT — raises 401 if invalid or wrong scope.
    3. Extract jti and firm_id from claims.
    4. Verify the session is still active (not revoked, not inactive for >30 min).
    5. Look up the Client and confirm portal access is still enabled.
    6. Return the Client object.
    """
    token = credentials.credentials

    # decode_portal_access_token raises 401 on any failure including wrong scope
    payload = decode_portal_access_token(token)

    jti: str | None = payload.get("jti")
    firm_id_str: str | None = payload.get("firm_id")
    client_id_str: str | None = payload.get("sub")

    if not jti or not firm_id_str or not client_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate portal credentials",
        )

    firm_id = UUID(firm_id_str)

    session = check_session_active(db, jti, firm_id)
    if session is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired or inactive",
        )

    stmt = select(Client).where(
        Client.id == UUID(client_id_str),
        Client.firm_id == firm_id,
        Client.portal_access_enabled.is_(True),
    )
    client = db.execute(stmt).scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate portal credentials",
        )

    return client
