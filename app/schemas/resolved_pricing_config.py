# app/schemas/resolved_pricing_config.py

"""Read-only response schema for the pricing resolver.

One firm's pricing configuration AFTER per-engagement-type precedence has been
applied: the configs, tiers and option prices that actually govern pricing for
one engagement type, with everything the override displaced already removed.

THERE IS NO Base, Create OR Update HERE, DELIBERATELY, for the same reason
fee_schedule_config.py has none. This is a read projection over tables that
already own their four-schema sets, and writes keep going through those. A
Create here would invent a second write path into firm_dimension_configs.

WHAT MAKES THIS DIFFERENT FROM FeeScheduleConfigOut. That schema is the OWNER'S
view: everything the firm has configured, blanket and scoped alike, so a
settings UI can render and edit both. This one is the RESOLVED view: exactly one
answer per dimension, chosen by precedence, which is what fee resolution and the
next session's public intake endpoint consume. The two must not be confused. A
caller that renders the owner view to a lead would leak every other engagement
type's pricing.

PRECEDENCE IS WHOLESALE REPLACEMENT. If a scoped root config exists for
(dimension, engagement type), that tree entirely supplies the configuration for
that dimension and the blanket tree is absent from this response. There is no
field-level merge and no fallback of any kind, at any depth. See the resolver
docstring in pricing_config_service.py for the full statement of the rule,
including why an option with no scoped price row routes to quote rather than
borrowing the blanket price.

THE NULL-VERSUS-ZERO LAW SURVIVES UNCHANGED. Prices are inherited from
FirmTierOut and FirmOptionPriceOut as Optional[Decimal] defaulting to None.
Nothing here defaults, coerces or fills a price.
"""

import uuid
from typing import Optional

from pydantic import BaseModel

from app.schemas.firm_dimension_config import FirmDimensionConfigOut
from app.schemas.firm_option_price import FirmOptionPriceOut
from app.schemas.firm_tier import FirmTierOut


class ResolvedPricingConfigOut(BaseModel):
    """The configuration governing one engagement type, after precedence."""

    firm_id: uuid.UUID

    # The context this was resolved for. None means no context was supplied and
    # the blanket configuration was returned.
    engagement_type: Optional[str] = None

    # The firm's catalog entry the context resolved to, or None. Note that a
    # context naming an engagement type the firm has no catalog row for also
    # yields None here: absence of a row means not offered, so there is nothing
    # for a scoped config to attach to and the blanket tree governs.
    service_catalog_entry_id: Optional[uuid.UUID] = None

    # Dimensions whose configuration came from a SCOPED tree rather than the
    # blanket one. Present so a caller can see precedence was applied without
    # re-deriving it, and so a test can assert the override actually fired
    # rather than inferring it from row counts.
    overridden_dimension_ids: list[uuid.UUID] = []

    # Every row below is already filtered to the winning trees. A blanket
    # config for an overridden dimension does not appear here at all.
    firm_dimension_configs: list[FirmDimensionConfigOut] = []
    firm_tiers: list[FirmTierOut] = []
    firm_option_prices: list[FirmOptionPriceOut] = []
