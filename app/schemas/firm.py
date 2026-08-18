# app/schemas/firm.py

from typing import Optional
from uuid import UUID
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator
import re


def _slugify(value: str) -> str:
    """
    Convert a firm name to a URL-safe slug.
    "Smith & Associates CPA" → "smith-associates-cpa"
    """
    # Lowercase everything
    value = value.lower()
    # Replace any character that isn't a letter or number with a hyphen
    value = re.sub(r"[^a-z0-9]+", "-", value)
    # Strip leading/trailing hyphens
    value = value.strip("-")
    return value


class FirmBase(BaseModel):
    name: str
    slug: Optional[str] = None
    subscription_tier: str = "trial"
    is_active: bool = True
    settings: Optional[dict] = None
    feature_flags: Optional[dict] = None
    sending_domain: Optional[str] = None
    sending_domain_verified: bool = False
    sending_domain_dkim_host: Optional[str] = None
    sending_domain_dkim_value: Optional[str] = None
    sending_domain_return_path_host: Optional[str] = None
    sending_domain_return_path_value: Optional[str] = None
    portal_domain: Optional[str] = None
    portal_domain_verified: bool = False
    signup_source: Optional[str] = None

    @field_validator("slug", mode="before")
    @classmethod
    def auto_slug(cls, v, info):
        # If no slug provided, we'll generate it from name in FirmCreate.
        # If a slug is provided, clean it up.
        if v:
            return _slugify(str(v))
        return v


class FirmCreate(FirmBase):
    name: str

    @field_validator("slug", mode="before")
    @classmethod
    def auto_slug(cls, v, info):
        # If slug not provided, generate it from the name field.
        # Note: info.data contains fields already validated before this one.
        if not v:
            name = info.data.get("name", "")
            return _slugify(name)
        return _slugify(str(v))


class FirmUpdate(BaseModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    subscription_tier: Optional[str] = None
    is_active: Optional[bool] = None
    settings: Optional[dict] = None
    feature_flags: Optional[dict] = None
    timesheet_approval_required: Optional[bool] = None
    signup_source: Optional[str] = None
    timezone: Optional[str] = None


class FirmOut(FirmBase):
    id: UUID
    staff_auth_policy: Optional[str] = "either"
    plan_override: bool = False
    timesheet_approval_required: bool = False
    concierge_active: bool = True
    firm_type: Optional[str] = None
    timezone: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)