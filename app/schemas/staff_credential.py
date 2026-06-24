# app/schemas/staff_credential.py

from datetime import date, datetime, timedelta
from typing import Optional
import uuid

from pydantic import BaseModel, ConfigDict, computed_field

from app.core.enums import CredentialType


class StaffCredentialBase(BaseModel):
    credential_type: CredentialType
    credential_number: Optional[str] = None
    state: Optional[str] = None
    issued_at: Optional[date] = None
    expires_at: Optional[date] = None
    notes: Optional[str] = None


class StaffCredentialCreate(StaffCredentialBase):
    user_id: uuid.UUID


class StaffCredentialUpdate(BaseModel):
    credential_type: Optional[CredentialType] = None
    credential_number: Optional[str] = None
    state: Optional[str] = None
    issued_at: Optional[date] = None
    expires_at: Optional[date] = None
    notes: Optional[str] = None


class StaffCredentialOut(StaffCredentialBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @computed_field
    @property
    def is_expiring_soon(self) -> bool:
        if self.expires_at is None:
            return False
        return self.expires_at <= date.today() + timedelta(days=60)
