# app/schemas/invoice.py

from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import InvoiceStatus, InvoiceDeliveryMethod


class LineItemSchema(BaseModel):
    description: str
    quantity: Decimal
    unit_price: Decimal
    total: Decimal


class InvoiceBase(BaseModel):
    invoice_number: str
    line_items: list[LineItemSchema] = []
    subtotal: Decimal
    tax_rate: Decimal = Decimal("0.0")
    tax_amount: Decimal = Decimal("0.0")
    total_amount: Decimal
    status: InvoiceStatus = InvoiceStatus.draft
    due_date: Optional[date] = None
    notes_client_visible: Optional[str] = None
    delivery_method: InvoiceDeliveryMethod = InvoiceDeliveryMethod.portal

    @field_validator('line_items', mode='before')
    @classmethod
    def coerce_line_items(cls, v):
        if v is None:
            return []
        return v


class InvoiceCreate(InvoiceBase):
    client_id: uuid.UUID
    engagement_id: Optional[uuid.UUID] = None
    notes: Optional[str] = None


class InvoiceUpdate(BaseModel):
    line_items: Optional[list[LineItemSchema]] = None
    subtotal: Optional[Decimal] = None
    tax_rate: Optional[Decimal] = None
    tax_amount: Optional[Decimal] = None
    total_amount: Optional[Decimal] = None
    status: Optional[InvoiceStatus] = None
    due_date: Optional[date] = None
    notes: Optional[str] = None
    notes_client_visible: Optional[str] = None
    delivery_method: Optional[InvoiceDeliveryMethod] = None


class InvoiceOut(InvoiceBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    client_id: uuid.UUID
    engagement_id: Optional[uuid.UUID]
    notes: Optional[str]
    stripe_payment_intent_id: Optional[str]
    stripe_charge_id: Optional[str]
    paid_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_by: Optional[uuid.UUID]
    created_at: datetime
    updated_at: datetime
    is_deleted: bool
    line_items: list[LineItemSchema] = []

    model_config = ConfigDict(from_attributes=True)


class BulkInvoiceUpdate(BaseModel):
    ids: list[uuid.UUID]
    action: str  # "send" or "void"


class PortalInvoiceOut(BaseModel):
    id: uuid.UUID
    invoice_number: str
    line_items: list[LineItemSchema] = []
    subtotal: Decimal
    tax_rate: Decimal
    tax_amount: Decimal
    total_amount: Decimal
    status: InvoiceStatus
    due_date: Optional[date]
    notes_client_visible: Optional[str]
    paid_at: Optional[datetime]
    sent_at: Optional[datetime]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

    @field_validator('line_items', mode='before')
    @classmethod
    def coerce_line_items(cls, v):
        if v is None:
            return []
        return v
