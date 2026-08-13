# app/schemas/service_catalog_entry.py

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import EngagementType, PricingMode


class ServiceCatalogEntryBase(BaseModel):
    is_offered: bool = False
    pricing_mode: Optional[PricingMode] = None
    base_fee: Optional[Decimal] = None


class ServiceCatalogEntryCreate(ServiceCatalogEntryBase):
    """firm_id is deliberately absent. It is injected server-side from the JWT,
    never accepted from a request body."""

    engagement_type: str

    @field_validator("engagement_type")
    @classmethod
    def validate_engagement_type(cls, v):
        valid = {e.value for e in EngagementType}
        if v not in valid:
            raise ValueError(
                f"Invalid engagement_type '{v}'. Must be one of: {sorted(valid)}"
            )
        return v


class ServiceCatalogEntryUpdate(BaseModel):
    """Every field optional. The service reads model_dump(exclude_unset=True)
    to tell "not provided" apart from "explicitly set to null", which matters
    for base_fee for the same reason it matters for tier prices."""

    is_offered: Optional[bool] = None
    pricing_mode: Optional[PricingMode] = None
    base_fee: Optional[Decimal] = None


class ServiceCatalogEntryOut(ServiceCatalogEntryBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    engagement_type: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
