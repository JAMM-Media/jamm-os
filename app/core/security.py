# app/core/security.py

from datetime import datetime, timedelta, timezone
from jose import jwt
from passlib.context import CryptContext
import passlib.handlers.bcrypt

from app.core.config import get_settings
from fastapi.security import OAuth2PasswordBearer

# ✅ force stable backend
passlib.handlers.bcrypt.BCRYPT_BACKEND = "bcrypt"

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/token")
settings = get_settings()

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)
