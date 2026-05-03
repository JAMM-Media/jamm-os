# app/schemas/retention.py

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class RetentionPolicyBase(BaseModel):
    document_retention_years: int = Field(ge=1, le=100)
    auto_flag_enabled: bool


class RetentionPolicyCreate(RetentionPolicyBase):
    pass


class RetentionPolicyUpdate(BaseModel):
    document_retention_years: Optional[int] = Field(default=None, ge=1, le=100)
    auto_flag_enabled: Optional[bool] = None


class RetentionPolicyOut(RetentionPolicyBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    last_ran_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FlaggedDocumentOut(BaseModel):
    id: uuid.UUID
    filename: str
    created_at: datetime
    client_id: uuid.UUID
    engagement_id: Optional[uuid.UUID] = None
    retention_flag_reason: str

    model_config = ConfigDict(from_attributes=True)
