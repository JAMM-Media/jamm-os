# app/schemas/firm_tier.py

"""Schemas for one numeric bucket in a firm's configured dimension.

THE NULL-VERSUS-ZERO LAW, at the schema layer:

    price = None   -> unpriced. Routes to quote.
    price = 0.00   -> priced, at zero.

Optional[Decimal] with a default of None is what keeps those apart on the way
in and on the way out. Nothing here may coerce one into the other: no
`or 0`, no `Decimal(price or 0)`, no non-null default. FirmTierUpdate is the
place this is easiest to get wrong, which is why it does not reuse None as
its "field not provided" signal -- see its docstring.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FirmTierBase(BaseModel):
    range_min: Decimal
    # None means open top. An open-top tier is quote territory and carries no
    # price, enforced in pricing_config_service.
    range_max: Optional[Decimal] = None
    # None means unpriced. See the module docstring.
    price: Optional[Decimal] = None
    sort_order: int


class FirmTierCreate(FirmTierBase):
    """firm_id is deliberately absent; it is injected server-side from the JWT.

    config_id is present because a tier is meaningless without the config it
    belongs to. save_tiers takes the config separately and rejects any item
    whose config_id disagrees, so the two can never drift apart.
    """

    config_id: uuid.UUID


class FirmTierUpdate(BaseModel):
    """All fields optional.

    Note carefully: `price=None` here does NOT mean "leave the price alone".
    It means "set this tier to unpriced". Callers distinguish the two through
    Pydantic's model_fields_set, which the service reads via
    model_dump(exclude_unset=True). If this ever changes to treat None as
    "no change", the blank-versus-zero distinction collapses and the universal
    quote law silently stops working for edited tiers.
    """

    range_min: Optional[Decimal] = None
    range_max: Optional[Decimal] = None
    price: Optional[Decimal] = None
    sort_order: Optional[int] = None


class FirmTierOut(FirmTierBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    config_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
