# app/dependencies/auth.py

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from sqlalchemy.orm import Session
from uuid import UUID

from app.core.security import oauth2_scheme
from app.core.config import get_settings
from app.db.session import get_db
from app.models.user import User

settings = get_settings()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Decodes the JWT and returns the current user.

    Also validates token_version — if the user's role was changed after
    this token was issued, the version numbers won't match and we reject
    the token, forcing a fresh login.
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
        user_id: str | None = payload.get("sub")
        token_version: int | None = payload.get("token_version")

        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = db.query(User).filter(User.id == UUID(user_id)).first()
    if user is None:
        raise credentials_exception

    # Validate token_version for session invalidation.
    if token_version is not None and user.token_version != token_version:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expired. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user