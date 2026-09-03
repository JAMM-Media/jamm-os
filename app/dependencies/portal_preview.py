# app/dependencies/portal_preview.py

"""
Preview authentication dependency for staff-initiated portal previews.

get_current_preview_client() accepts only scope="portal_staff_preview" tokens,
which are issued by POST /portal-preview/token. It MUST NOT accept regular
scope="client_portal" tokens (those belong to real client sessions).

Write endpoints in portal.py use get_current_portal_client which requires
scope="client_portal" -- so preview tokens are automatically rejected on all
write endpoints without any per-endpoint changes.
"""

from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.client import Client
from app.services.portal_auth import decode_preview_access_token

_bearer = HTTPBearer()


def get_current_preview_client(
    credentials: HTTPAuthorizationCredentials = Depends(_bearer),
    db: Session = Depends(get_db),
) -> Client:
    """
    FastAPI dependency that authenticates a staff preview session.

    Steps:
    1. Extract Bearer token from Authorization header.
    2. Decode and validate the JWT -- raises 401 if invalid, expired, or wrong scope.
    3. Look up the Client by sub+firm_id claims, enforcing tenant isolation.
    4. Return the Client object for read-only preview use.

    No PortalSession lookup is performed. The JWT exp claim (10 minutes) is
    the sole expiry mechanism for preview tokens.
    """
    token = credentials.credentials
    payload = decode_preview_access_token(token)

    client_id_str = payload.get("sub")
    firm_id_str = payload.get("firm_id")

    if not client_id_str or not firm_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate preview credentials",
        )

    stmt = select(Client).where(
        Client.id == UUID(client_id_str),
        Client.firm_id == UUID(firm_id_str),
    )
    client = db.execute(stmt).scalar_one_or_none()
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate preview credentials",
        )

    return client
