# app/schemas/complexity_catalog.py

"""Read-only schemas for the system-owned complexity catalog.

These five tables are the documented exception to the firm_id rule (the
August 13, 2026 carve-out, written up in app/models/complexity_flag.py).
They are system-owned shared content and no firm ever writes to them, so
there is deliberately no firm-facing Create or Update path in this build and
therefore no full XBase/XCreate/XUpdate/XOut set. Out schemas only.

The one exception is ComplexityFlagEngagementTypeBase, which exists purely to
carry the EngagementType validator. engagement_type is stored as a plain
String(50) at the database layer, matching Engagement.engagement_type, so the
schema layer is the only thing standing between the catalog and an engagement
type that is not a real enum member.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, field_validator

from app.core.enums import DimensionKind, DimensionRole, EngagementType


class ComplexityFlagOut(BaseModel):
    id: uuid.UUID
    key: str
    name: str
    description: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplexityFlagEngagementTypeBase(BaseModel):
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


class ComplexityFlagEngagementTypeOut(ComplexityFlagEngagementTypeBase):
    id: uuid.UUID
    flag_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplexityDimensionOut(BaseModel):
    id: uuid.UUID
    flag_id: uuid.UUID
    key: str
    kind: DimensionKind
    question_text: Optional[str] = None
    hierarchy_rank: int
    linkable: bool
    default_role: Optional[DimensionRole] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplexityDimensionUnitOut(BaseModel):
    id: uuid.UUID
    dimension_id: uuid.UUID
    key: str
    label: str
    question_text: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ComplexityVocabularyOptionOut(BaseModel):
    id: uuid.UUID
    dimension_id: uuid.UUID
    key: str
    label: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
