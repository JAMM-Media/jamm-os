# app/schemas/settings.py

from pydantic import BaseModel
from app.core.enums import StaffAuthPolicy


class StaffAuthPolicyUpdate(BaseModel):
    staff_auth_policy: StaffAuthPolicy


class StaffAuthPolicyOut(BaseModel):
    staff_auth_policy: str
