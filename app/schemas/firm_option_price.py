# app/schemas/firm_option_price.py

"""Schemas for a firm's price on one system categorical option.

Same null-versus-zero law as firm_tier: None is unpriced and routes to quote,
0.00 is priced at zero, and nothing here may collapse one into the other.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class FirmOptionPriceBase(BaseModel):
    # None means unpriced. See the module docstring.
    price: Optional[Decimal] = None


class FirmOptionPriceCreate(FirmOptionPriceBase):
    """firm_id is deliberately absent; it is injected server-side from the JWT."""

    option_id: uuid.UUID


class FirmOptionPriceUpdate(BaseModel):
    """`price=None` means "set to unpriced", not "leave alone". The service
    reads model_dump(exclude_unset=True) to tell those apart. See the same note
    on FirmTierUpdate."""

    price: Optional[Decimal] = None


class FirmOptionPriceOut(FirmOptionPriceBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    option_id: uuid.UUID
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
