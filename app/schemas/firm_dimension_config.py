# app/schemas/firm_dimension_config.py

"""Schemas for one firm's configuration of one system complexity dimension.

Flat versus dependent is expressed by the two parent fields:

    both None            -> flat, a chain of length one
    exactly one set      -> dependent, hanging under that tier or that option
    both set             -> rejected here and by the database check constraint

Parent references are deliberately NOT settable through FirmDimensionConfigUpdate.
Moving a config between branches is destructive (it invalidates every price
below it), so it goes through pricing_config_service.change_dimension_direction
and its explicit confirm flag instead. No other code path may alter them.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict, model_validator

from app.core.enums import DimensionRole


class FirmDimensionConfigBase(BaseModel):
    role: DimensionRole
    unit_id: Optional[uuid.UUID] = None
    guard_threshold: Optional[Decimal] = None


class FirmDimensionConfigCreate(FirmDimensionConfigBase):
    """firm_id is deliberately absent; it is injected server-side from the JWT."""

    dimension_id: uuid.UUID
    parent_tier_id: Optional[uuid.UUID] = None
    parent_option_id: Optional[uuid.UUID] = None

    @model_validator(mode="after")
    def only_one_parent(self):
        """Mirrors ck_firm_dimension_configs_single_parent so the caller gets a
        readable error instead of an IntegrityError. The database constraint
        remains the real enforcement; this is the friendly front door."""
        if self.parent_tier_id is not None and self.parent_option_id is not None:
            raise ValueError(
                "A config may hang under a tier or under an option, not both. "
                "Set at most one of parent_tier_id and parent_option_id."
            )
        return self


class FirmDimensionConfigUpdate(BaseModel):
    """Role, unit and guard threshold only.

    parent_tier_id and parent_option_id are absent on purpose. See the module
    docstring: direction changes are destructive and belong to
    change_dimension_direction.
    """

    role: Optional[DimensionRole] = None
    unit_id: Optional[uuid.UUID] = None
    guard_threshold: Optional[Decimal] = None


class FirmDimensionConfigOut(FirmDimensionConfigBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    dimension_id: uuid.UUID
    parent_tier_id: Optional[uuid.UUID] = None
    parent_option_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
