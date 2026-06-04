# app/schemas/portal_preview.py

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class PortalPreviewDocumentRequestItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str
    status: str
    due_date: Optional[datetime] = None
    items_total: int
    items_completed: int


class PortalPreviewDocumentItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    uploaded_at: datetime
    visibility: str


class PortalPreviewInvoiceItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    invoice_number: str
    amount_due: float
    status: str
    due_date: Optional[datetime] = None


class PortalPreviewMessageSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    unread_count: int
    last_message_at: Optional[datetime] = None


class PortalPreviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    client_id: UUID
    client_name: str
    document_requests: list[PortalPreviewDocumentRequestItem]
    documents: list[PortalPreviewDocumentItem]
    invoices: list[PortalPreviewInvoiceItem]
    messages: PortalPreviewMessageSummary
    generated_at: datetime
