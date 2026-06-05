from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, EmailStr, field_validator, ConfigDict
from uuid import UUID


def _normalize_tags(value: Optional[List[str] | str]) -> Optional[List[str]]:
    if value is None:
        return None
    if isinstance(value, str):
        items = [v.strip() for v in value.split(",") if v.strip()]
        return list(dict.fromkeys(items))
    return value


class ClientBase(BaseModel):
    name: str
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = True
    entity_type: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v):
        return _normalize_tags(v)

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v):
        if v is None:
            return v
        valid = {"individual", "business", "trust", "estate"}
        if v not in valid:
            raise ValueError(f"entity_type must be one of {sorted(valid)}")
        return v


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    company_name: Optional[str] = None
    tax_id: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    tags: Optional[List[str]] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    entity_type: Optional[str] = None

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v):
        return _normalize_tags(v)

    @field_validator("entity_type")
    @classmethod
    def validate_entity_type(cls, v):
        if v is None:
            return v
        valid = {"individual", "business", "trust", "estate"}
        if v not in valid:
            raise ValueError(f"entity_type must be one of {sorted(valid)}")
        return v


class ClientOut(ClientBase):
    id: UUID
    created_at: datetime
    updated_at: datetime
    quickbooks_customer_id: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class ClientImportResult(BaseModel):
    created: int
    skipped: int
    errors: list[dict]  # [{row: int, reason: str}]


class QBOARBalanceOut(BaseModel):
    connected: bool
    outstanding_balance: Optional[float] = None
    current_balance: Optional[float] = None      # not yet due
    days_1_30: Optional[float] = None            # 1-30 days overdue
    days_31_60: Optional[float] = None           # 31-60 days overdue
    days_61_90: Optional[float] = None           # 61-90 days overdue
    days_over_90: Optional[float] = None         # 91+ days overdue
    last_payment_date: Optional[date] = None


class ClientHealthOut(BaseModel):
    status: str  # "healthy", "needs_attention", "at_risk"
    reasons: list[dict]


class QBOHealthSignal(BaseModel):
    status: str  # "green", "amber", "red"
    finding: str  # plain English explanation


class QBOHealthSignals(BaseModel):
    reconciliation: Optional[QBOHealthSignal] = None
    balance_sheet: Optional[QBOHealthSignal] = None
    pl_activity: Optional[QBOHealthSignal] = None
    transaction_recency: Optional[QBOHealthSignal] = None
    gl_recency: Optional[QBOHealthSignal] = None


class QBOHealthOut(BaseModel):
    connected: bool
    status: str
    signals: QBOHealthSignals
    checked_at: Optional[datetime] = None
