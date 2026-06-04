# app/schemas/engagement_letter_template.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EngagementLetterTemplateBase(BaseModel):
    name: str
    engagement_type: Optional[str] = None
    body_html: str
    variable_fields: list[str] = []
    is_active: bool = True


class EngagementLetterTemplateCreate(EngagementLetterTemplateBase):
    # firm_id is intentionally absent — injected from the JWT tenant context
    # in the route handler, never accepted from the request body.
    pass


class EngagementLetterTemplateUpdate(BaseModel):
    name: Optional[str] = None
    engagement_type: Optional[str] = None
    body_html: Optional[str] = None
    variable_fields: Optional[list[str]] = None
    is_active: Optional[bool] = None


class EngagementLetterTemplateOut(EngagementLetterTemplateBase):
    id: UUID
    firm_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
