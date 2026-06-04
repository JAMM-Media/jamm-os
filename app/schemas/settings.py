# app/schemas/settings.py

from pydantic import BaseModel, EmailStr, ConfigDict
from app.core.enums import StaffAuthPolicy


class StaffAuthPolicyUpdate(BaseModel):
    staff_auth_policy: StaffAuthPolicy


class StaffAuthPolicyOut(BaseModel):
    staff_auth_policy: str


class EmailSettingsUpdate(BaseModel):
    reply_to: EmailStr | None = None
    display_name: str | None = None
    model_config = ConfigDict(str_strip_whitespace=True)


class ReviewSettingsUpdate(BaseModel):
    google_review_url: str | None = None
    model_config = ConfigDict(str_strip_whitespace=True)
