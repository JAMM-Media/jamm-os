# app/schemas/fee_schedule_config.py

"""Read-only response schema for GET /api/pricing/config.

One firm's whole fee schedule in one object: the system-owned complexity
catalog, plus that firm's own pricing attachments to it.

THERE IS NO Base, Create OR Update HERE, DELIBERATELY. This is a read
projection assembled from six tables, not a persisted entity, so the standing
four-schema rule has nothing to apply to. Every table it reads already owns its
own XBase/XCreate/XUpdate/XOut set (or, for the system catalog, its read-only
Out schemas), and writes continue to go through those. Adding a Create or
Update here would invent a second write path into tables that already have
one.

THE NULL-VERSUS-ZERO LAW SURVIVES THIS SCHEMA UNCHANGED. Every price field
below is inherited from FirmTierOut, FirmOptionPriceOut and
ServiceCatalogEntryOut as Optional[Decimal] with a default of None. Nothing
here defaults, coerces or fills a price. null stays null (unpriced, routes to
quote) and 0.00 stays 0.00 (priced, at zero), and those two must never become
each other on the way out any more than on the way in.
"""

import uuid
from typing import Optional

from pydantic import BaseModel

from app.schemas.complexity_catalog import (
    ComplexityDimensionOut,
    ComplexityDimensionUnitOut,
    ComplexityFlagEngagementTypeOut,
    ComplexityFlagOut,
    ComplexityVocabularyOptionOut,
)
from app.schemas.firm_dimension_config import FirmDimensionConfigOut
from app.schemas.firm_option_price import FirmOptionPriceOut
from app.schemas.firm_tier import FirmTierOut
from app.schemas.service_catalog_entry import ServiceCatalogEntryOut


class EngagementTypeOptionOut(BaseModel):
    """One engagement type as the settings screen needs to render it.

    ADDED FOR THE PRICING SETTINGS UI. The owner-facing screen lists EVERY
    engagement type, dormant ones included, because activating a dormant
    service is the whole point of the top section. service_catalog_entries
    cannot supply that list: its rows are created lazily, so a firm that has
    never touched a service has no row for it and it would simply be missing
    from the screen.

    label, lead_facing_label and category are served rather than computed by
    the caller, and that is load-bearing rather than a convenience. The
    frontend already carries five separate hand-copied engagement type lists
    that have drifted from each other and from the backend ("1040" versus
    "1040 - Individual" versus "Tax Return - 1040"), which is the same drift
    that hit the letter templates tab. The retired FeeScheduleTab names its own
    16-item hand-copied list as the thing its replacement exists to remove, so
    the replacement does not get to add a sixth.

    lead_facing_label always carries a renderable string. The "use the override
    if present, else the formal label" rule lives in the service and nowhere
    else, deliberately: if the frontend implemented it, every consumer would
    own a copy of the rule and they could disagree.

    category may be None, and that is a real and permanent state rather than a
    gap. An uncategorized type renders ungrouped. See _engagement_category.
    """

    value: str
    label: str
    lead_facing_label: str
    category: Optional[str] = None


class FeeScheduleCatalogOut(BaseModel):
    """The shared vocabulary every firm prices against.

    The first five collections are the August 13, 2026 carve-out tables. They
    carry no firm_id, no firm ever writes to them, and they are read unscoped.

    service_catalog_entries is the exception inside this block and is NOT
    unscoped. See the note on the field itself.
    """

    # Every engagement type the system knows about, dormant or not, with the
    # strings the owner screen renders. System-shared content derived from
    # app/core/enums.py, not firm data: it is identical for every firm and
    # carries no firm_id, exactly like the five carve-out collections.
    engagement_types: list[EngagementTypeOptionOut]

    complexity_flags: list[ComplexityFlagOut]
    complexity_flag_engagement_types: list[ComplexityFlagEngagementTypeOut]
    complexity_dimensions: list[ComplexityDimensionOut]
    complexity_dimension_units: list[ComplexityDimensionUnitOut]
    complexity_vocabulary_options: list[ComplexityVocabularyOptionOut]

    # FIRM SCOPED, despite living under `catalog`.
    #
    # service_catalog_entries is not a carve-out table. It has a firm_id
    # foreign key, a uq_service_catalog_entries_firm_engagement_type unique
    # constraint per firm, and it holds each firm's own is_offered,
    # pricing_mode and base_fee. Returning it unscoped would hand the caller
    # every other firm's offering list and base fees.
    #
    # It sits here because it is named and read as catalog content and the
    # session spec placed it here, not because it is unscoped. The query
    # behind it filters on firm_id like every other firm-owned table. Raised
    # with Andrew in the session report.
    service_catalog_entries: list[ServiceCatalogEntryOut]


class FirmPricingOut(BaseModel):
    """This firm's own attachments to the catalog above.

    Every collection here is scoped to the authenticated firm without
    exception.
    """

    firm_dimension_configs: list[FirmDimensionConfigOut]
    firm_tiers: list[FirmTierOut]
    firm_option_prices: list[FirmOptionPriceOut]


class FeeScheduleConfigOut(BaseModel):
    """The merged response.

    firm_id is echoed back so a caller (and a tenant isolation test) can see
    which firm the firm_pricing block belongs to without inferring it from the
    rows.
    """

    firm_id: uuid.UUID
    catalog: FeeScheduleCatalogOut
    firm_pricing: FirmPricingOut
