# app/schemas/totp.py

from typing import Optional
from pydantic import BaseModel


class TOTPSetupResponse(BaseModel):
    secret: str
    qr_code_base64: str
    backup_codes: list[str]


class TOTPVerifyRequest(BaseModel):
    code: str


class TOTPStatusResponse(BaseModel):
    totp_enabled: bool
    is_required: bool


class LoginRequest(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None
    backup_code: Optional[str] = None
