# app/schemas/client.py
from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, EmailStr, field_validator
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

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v):
        return _normalize_tags(v)

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

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, v):
        return _normalize_tags(v)

class ClientOut(ClientBase):
    id: UUID
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

from app.schemas.project import ProjectOut
from app.schemas.task import TaskSummary

class ClientOverview(BaseModel):
    client: ClientOut
    projects: List[ProjectOut]
    tasks: List[TaskSummary]


