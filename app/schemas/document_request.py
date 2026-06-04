# app/schemas/document_request.py

from datetime import date, datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ChecklistItem(BaseModel):
    """
    A single line item inside a DocumentRequest or ChecklistTemplate.

    This is a pure value-object schema — it has no corresponding DB table.
    Instances live as elements inside the JSON checklist_items / items columns.
    Use model_dump() to serialise before writing to the database.
    """

    id: str
    label: str
    description: str = ""
    is_required: bool = True
    status: Literal["pending", "uploaded", "approved", "rejected"] = "pending"


class DocumentRequestBase(BaseModel):
    title: str
    due_date: Optional[date] = None
    checklist_items: list[ChecklistItem] = []


class DocumentRequestCreate(DocumentRequestBase):
    # firm_id is intentionally absent — it is injected from the JWT tenant
    # context in the route handler, never accepted from the request body.
    client_id: UUID
    engagement_id: UUID


class DocumentRequestUpdate(BaseModel):
    title: Optional[str] = None
    due_date: Optional[date] = None
    checklist_items: Optional[list[ChecklistItem]] = None
    status: Optional[Literal["pending", "partial", "complete"]] = None


class DocumentRequestOut(DocumentRequestBase):
    id: UUID
    firm_id: UUID
    client_id: UUID
    engagement_id: UUID
    status: str
    reminder_count: int
    last_reminder_sent_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
