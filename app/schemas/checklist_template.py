# app/schemas/checklist_template.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.schemas.document_request import ChecklistItem


class ChecklistTemplateBase(BaseModel):
    name: str
    # Stored as a plain string so this schema stays decoupled from the
    # EngagementType enum. Validation against allowed values is enforced
    # at the route layer when needed. Use model_dump() to serialise.
    engagement_type: Optional[str] = None
    items: list[ChecklistItem] = []


class ChecklistTemplateCreate(ChecklistTemplateBase):
    # firm_id is intentionally absent — it is injected from the JWT tenant
    # context in the route handler, never accepted from the request body.
    pass


class ChecklistTemplateUpdate(BaseModel):
    name: Optional[str] = None
    engagement_type: Optional[str] = None
    items: Optional[list[ChecklistItem]] = None


class ChecklistTemplateOut(ChecklistTemplateBase):
    id: UUID
    firm_id: UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
