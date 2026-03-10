# app/core/security.py

"""
JWT tokens in JAMM OS now include three pieces of information:
  - "sub": the user's UUID (who are you?)
  - "firm_id": the firm's UUID (which firm do you belong to?)
  - "token_version": an integer (has your role changed since this was issued?)

Why does firm_id go in the JWT?
Because every single API request needs to know which firm's data to query.
If we only stored user ID in the token, every request would need an extra
DB query just to find the firm. By including firm_id in the token, the
tenant guard can scope queries to the correct firm without extra lookups.

Why token_version?
When a user's role changes (e.g., staff → firm_owner), any existing JWT
they hold still says "staff". Without version checking, they'd retain
the old permissions until their token expires (up to 30 minutes).
With version checking, the role change takes effect immediately —
old tokens are rejected the next time they make a request.
"""

from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer

from app.core.config import get_settings

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

# Argon2 — the recommended password hashing algorithm.
# More secure than bcrypt: no 72-byte password limit, resistant to GPU attacks.
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Creates a signed JWT.

    Expected data dict:
    {
        "sub": str(user.id),
        "firm_id": str(user.firm_id),
        "token_version": user.token_version,
    }
    """
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    return jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )