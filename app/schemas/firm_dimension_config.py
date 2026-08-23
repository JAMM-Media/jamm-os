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

service_catalog_entry_id is the config's SCOPE, added August 17, 2026:

    None      -> blanket, applies to every engagement type the flag maps to
    set        -> scoped, applies only when pricing that engagement type

It is settable at creation and absent from FirmDimensionConfigUpdate for the
same reason the parent fields are: re-scoping a tree invalidates the prices
underneath it exactly as a direction change does. There is no re-scope
operation in this build; a tree is created in its scope or replaced.
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
    # None means blanket. A non-None value must name a catalog entry belonging
    # to the SAME firm; that is a tenant isolation check and lives in the
    # service, because this schema has no idea which firm is calling.
    service_catalog_entry_id: Optional[uuid.UUID] = None
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


class ConfigMoveRequest(BaseModel):
    """Request body for POST /api/pricing/configs/{config_id}/move.

    The config_id being moved arrives in the path, not here, so this carries
    only the destination and the confirmation.

    BOTH PARENT FIELDS MAY BE None, and that is a real request rather than a
    malformed one: it means make this config flat. That is why neither field
    is required and why there is no "at least one" validator.

    only_one_parent is deliberately NOT mirrored here, unlike on
    FirmDimensionConfigCreate. change_dimension_direction already refuses a
    both-set payload with its own 422 and its own message, and the UI contract
    is that guard refusal messages surface verbatim from response detail. A
    schema validator here would intercept the payload first and replace that
    message with Pydantic's generic validation envelope, so the service stays
    the single voice for this rule.

    confirm defaults to False so no caller performs a destructive move by
    accident. The service refuses without it.
    """

    new_parent_tier_id: Optional[uuid.UUID] = None
    new_parent_option_id: Optional[uuid.UUID] = None
    confirm: bool = False


class FirmDimensionConfigOut(FirmDimensionConfigBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    dimension_id: uuid.UUID
    # Carried on the way out so the owner-facing merged config read can tell a
    # blanket config from a scoped one and render both. None means blanket.
    service_catalog_entry_id: Optional[uuid.UUID] = None
    parent_tier_id: Optional[uuid.UUID] = None
    parent_option_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
