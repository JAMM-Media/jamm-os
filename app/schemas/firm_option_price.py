# app/schemas/firm_option_price.py

"""Schemas for a firm's price on one system categorical option.

Same null-versus-zero law as firm_tier: None is unpriced and routes to quote,
0.00 is priced at zero, and nothing here may collapse one into the other.

TWO DIFFERENT NULLABLE FIELDS LIVE HERE AND THEY MEAN UNRELATED THINGS. Read
them apart before changing anything:

    price = None                     -> unpriced. Routes to quote.
    service_catalog_entry_id = None  -> blanket. Applies to every engagement
                                        type, and says nothing about price.

A blanket row priced at 0.00 and a scoped row with no price are both ordinary
and mean opposite things.
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
    # None means blanket. A non-None value must name a catalog entry belonging
    # to the SAME firm; that is a tenant isolation check and lives in the
    # service, because this schema has no idea which firm is calling.
    service_catalog_entry_id: Optional[uuid.UUID] = None


class FirmOptionPriceUpdate(BaseModel):
    """`price=None` means "set to unpriced", not "leave alone". The service
    reads model_dump(exclude_unset=True) to tell those apart. See the same note
    on FirmTierUpdate."""

    price: Optional[Decimal] = None


class FirmOptionPriceOut(FirmOptionPriceBase):
    id: uuid.UUID
    firm_id: uuid.UUID
    option_id: uuid.UUID
    # Carried on the way out so the owner-facing merged read can tell a blanket
    # price from a per-engagement-type one. None means blanket.
    service_catalog_entry_id: Optional[uuid.UUID] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
