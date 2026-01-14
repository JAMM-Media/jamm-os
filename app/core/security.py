# app/core/security.py

from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
from fastapi.security import OAuth2PasswordBearer
import passlib.handlers.bcrypt

from app.core.config import get_settings

# ✅ Force stable bcrypt backend for CI
passlib.handlers.bcrypt.BCRYPT_BACKEND = "bcrypt"

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")

pwd_context = CryptContext(
    schemes=["bcrypt_sha256"],
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
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta
        if expires_delta
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(
        to_encode,
        settings.SECRET_KEY,
        algorithm=settings.ALGORITHM,
    )
    return encoded_jwt
