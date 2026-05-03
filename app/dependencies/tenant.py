# app/dependencies/tenant.py

"""
Tenant Guard — the most important security dependency in JAMM PX.

Every authenticated endpoint (except system_admin endpoints) MUST use
get_current_firm() as a dependency. This is what enforces that Firm A
can never see Firm B's data.

How it works:
1. The JWT we issue includes both the user's ID and their firm's ID.
2. This dependency decodes the JWT and extracts firm_id.
3. It looks up the Firm in the database and verifies it exists and is active.
4. It returns the Firm object, which every router then uses to scope queries.

Usage in a router:
    @router.get("/clients/")
    def list_clients(
        db: Session = Depends(get_db),
        current_firm: Firm = Depends(get_current_firm),
    ):
        # CORRECT — scoped to firm
        clients = db.query(Client).filter(Client.firm_id == current_firm.id).all()

        # WRONG — never do this — returns all clients from all firms
        # clients = db.query(Client).all()
"""

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.security import oauth2_scheme
from app.core.config import get_settings
from app.db.session import get_db
from app.models.firm import Firm
from app.models.user import User

settings = get_settings()


def get_current_firm(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Firm:
    """
    Decodes the JWT, extracts firm_id, and returns the Firm object.
    Raises 401 if the token is invalid.
    Raises 403 if the firm is inactive (suspended account).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        firm_id_str: str | None = payload.get("firm_id")
        if firm_id_str is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    firm = db.query(Firm).filter(Firm.id == UUID(firm_id_str)).first()
    if firm is None:
        raise credentials_exception

    if not firm.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This firm account is inactive. Please contact support.",
        )

    return firm


def get_current_user_and_firm(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> tuple[User, Firm]:
    """
    Returns both the current user AND their firm in a single dependency call.
    Use this when you need to check the user's role AND scope by firm.

    Most endpoints will use this rather than get_current_firm alone.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        user_id_str: str | None = payload.get("sub")
        firm_id_str: str | None = payload.get("firm_id")
        token_version: int | None = payload.get("token_version")

        if user_id_str is None or firm_id_str is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == UUID(user_id_str)).first()
    if user is None:
        raise credentials_exception

    # Check token_version to enforce session invalidation on role change.
    # If the version in the token doesn't match the current version in the DB,
    # the user's role was changed after this token was issued — reject it.
    if token_version is not None and user.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    firm = db.query(Firm).filter(Firm.id == UUID(firm_id_str)).first()
    if firm is None:
        raise credentials_exception

    if not firm.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This firm account is inactive. Please contact support.",
        )

    return user, firm