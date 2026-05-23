# app/schemas/qc_checklist.py

from datetime import datetime
from typing import Optional, List
import uuid
from pydantic import BaseModel, ConfigDict


class QcChecklistTemplateBase(BaseModel):
    name: str
    engagement_type: Optional[str] = None
    items: List[str] = []


class QcChecklistTemplateCreate(QcChecklistTemplateBase):
    pass


class QcChecklistTemplateUpdate(BaseModel):
    name: Optional[str] = None
    engagement_type: Optional[str] = None
    items: Optional[List[str]] = None
    is_active: Optional[bool] = None


class QcChecklistTemplateOut(QcChecklistTemplateBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    is_active: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class QcChecklistItemBase(BaseModel):
    title: str
    order: int = 0


class QcChecklistItemCreate(QcChecklistItemBase):
    engagement_id: uuid.UUID
    is_from_template: bool = False


class QcChecklistItemUpdate(BaseModel):
    title: Optional[str] = None
    is_checked: Optional[bool] = None
    order: Optional[int] = None


class QcChecklistItemOut(QcChecklistItemBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    engagement_id: uuid.UUID
    is_checked: bool
    checked_by_id: Optional[uuid.UUID] = None
    checked_at: Optional[datetime] = None
    is_from_template: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)
