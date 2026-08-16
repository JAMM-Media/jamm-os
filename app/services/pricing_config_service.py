# app/services/pricing_config_service.py

"""Save-time validation for the firm-scoped pricing tables, plus the merged
fee schedule read.

Every write to service_catalog_entries, firm_dimension_configs, firm_tiers and
firm_option_prices goes through this module. The database enforces shape
(single parent, branch uniqueness, referential integrity); this module enforces
the rules that need to read more than one row.

get_fee_schedule_config is the read side, added August 14, 2026 to back
GET /api/pricing/config. It is kept in this module rather than a new one
because the merge it performs is the read-shaped twin of the write rules
above: same six tables, same carve-out, same tenant scoping.

get_public_intake_config sits directly beneath it, added August 16, 2026 to
back the unauthenticated GET /intake/{slug}/pricing-config. It is the
price-stripped public twin of that same read: the question tree a lead sees,
with every commercial fact removed. It and get_fee_schedule_config are the
only two functions in this module that validate nothing.

Service-raise pattern: these functions raise HTTPException, the house domain
exception used by every other service in this codebase. They never return a
tuple signal, and routers stay thin because there is nothing left for them to
decide.

Tenant isolation: firm_id is a required keyword argument on every public
function and always comes from the authenticated context, never from a
payload. The system complexity catalog is read unscoped, by the August 13,
2026 carve-out; every firm-scoped query filters on firm_id without exception.

The rules, in the order the task specifies them:

1. Tier contiguity and completeness      -> _validate_tier_sequence
2. Downhill-only linking                 -> _validate_downhill_link
3. Leaf-only pricing, no double counting -> _assert_tier_can_be_priced,
                                            _assert_parent_is_unpriced,
                                            _assert_option_can_be_priced
4. Direction change is explicit          -> change_dimension_direction
5. Role and kind coherence               -> _validate_role_coherence
6. Activation law                        -> upsert_service_catalog_entry
7. Tenant isolation                      -> every query below
8. Categorical branch ambiguity          -> _validate_categorical_branch_ambiguity

RULE 8, and why it exists.

The branch-uniqueness constraint allows the same dimension to be configured on
more than one branch, which is intended: a firm may want transaction volume
priced differently under two different parents. Option-parented children are
the exception that breaks under it. A child hanging under a vocabulary option
references the OPTION alone, not the parent config, and vocabulary options
belong to the system-owned dimension rather than to any one firm's config of
it. So when a categorical dimension is configured on two branches, an
option-parented child underneath it cannot say which branch it belongs to.

_descendant_config_ids resolves that ambiguity the only way it can, by
claiming the child for every config of that dimension. The consequence is
real data loss: change_dimension_direction on either config deletes tiers and
prices the firm attached under the other one.

Rule 8 forbids the ambiguous shape from being created, in both directions.
It is a save-time guard, not a fix.

THE DURABLE FIX IS DEFERRED AND LEDGERED. firm_dimension_configs.parent_option_id
should be accompanied by a parent_config_id so a child names its branch
outright, at which point _descendant_config_ids becomes exact and rule 8 can
be dropped. That is a schema change with a migration and a backfill, out of
scope for this session.

Rule 8 is enforced in configure_dimension, which is where ambiguous shapes get
created. change_dimension_direction is NOT covered: it can still move a config
into an ambiguous arrangement. That gap is deliberate for now, is recorded in
the session summary, and closes with the durable fix above.
"""

import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    ENGAGEMENT_TYPE_LABELS,
    DimensionKind,
    DimensionRole,
    EngagementType,
)
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_dimension_unit import ComplexityDimensionUnit
from app.models.complexity_flag import ComplexityFlag
from app.models.complexity_flag_engagement_type import ComplexityFlagEngagementType
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption
from app.models.firm import Firm
from app.models.firm_dimension_config import FirmDimensionConfig
from app.models.firm_option_price import FirmOptionPrice
from app.models.firm_tier import FirmTier
from app.models.service_catalog_entry import ServiceCatalogEntry
from app.schemas.complexity_catalog import (
    ComplexityDimensionOut,
    ComplexityDimensionUnitOut,
    ComplexityFlagEngagementTypeOut,
    ComplexityFlagOut,
    ComplexityVocabularyOptionOut,
)
from app.schemas.fee_schedule_config import (
    FeeScheduleCatalogOut,
    FeeScheduleConfigOut,
    FirmPricingOut,
)
from app.schemas.firm_dimension_config import (
    FirmDimensionConfigCreate,
    FirmDimensionConfigOut,
)
from app.schemas.firm_option_price import FirmOptionPriceCreate, FirmOptionPriceOut
from app.schemas.firm_tier import FirmTierBase, FirmTierOut
from app.schemas.intake_pricing_config import (
    IntakePricingConfigOut,
    IntakeQuestionOptionOut,
    IntakeQuestionOut,
    IntakeServiceOut,
)
from app.schemas.service_catalog_entry import (
    ServiceCatalogEntryCreate,
    ServiceCatalogEntryOut,
)
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event


# ---------------------------------------------------------------------------
# Lookups. Firm-scoped ones take firm_id; system catalog ones do not, per the
# carve-out.
# ---------------------------------------------------------------------------

def _get_config(
    db: Session, firm_id: uuid.UUID, config_id: uuid.UUID
) -> FirmDimensionConfig:
    config = db.execute(
        select(FirmDimensionConfig).where(
            FirmDimensionConfig.id == config_id,
            FirmDimensionConfig.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Dimension config not found")
    return config


def _get_dimension(db: Session, dimension_id: uuid.UUID) -> ComplexityDimension:
    dimension = db.get(ComplexityDimension, dimension_id)
    if dimension is None:
        raise HTTPException(status_code=404, detail="Complexity dimension not found")
    return dimension


def _get_option(db: Session, option_id: uuid.UUID) -> ComplexityVocabularyOption:
    option = db.get(ComplexityVocabularyOption, option_id)
    if option is None:
        raise HTTPException(status_code=404, detail="Vocabulary option not found")
    return option


def _get_tier(db: Session, firm_id: uuid.UUID, tier_id: uuid.UUID) -> FirmTier:
    tier = db.execute(
        select(FirmTier).where(FirmTier.id == tier_id, FirmTier.firm_id == firm_id)
    ).scalar_one_or_none()
    if tier is None:
        raise HTTPException(status_code=404, detail="Tier not found")
    return tier


# ---------------------------------------------------------------------------
# Rule 1: tier contiguity and completeness
# ---------------------------------------------------------------------------

def _validate_tier_sequence(tiers: list[FirmTierBase]) -> list[FirmTierBase]:
    """Sorted by sort_order: no gaps, no overlaps, at most one open top and it
    must be last. Errors name the offending boundary.

    Ranges are half-open, [range_min, range_max), so contiguity means each
    tier's range_max equals the next tier's range_min exactly. Anything else is
    a gap or an overlap depending on direction.
    """
    if not tiers:
        return []

    ordered = sorted(tiers, key=lambda t: t.sort_order)

    seen_sort_orders: set[int] = set()
    for tier in ordered:
        if tier.sort_order in seen_sort_orders:
            raise HTTPException(
                status_code=400,
                detail=f"Duplicate sort_order {tier.sort_order} in tier list.",
            )
        seen_sort_orders.add(tier.sort_order)

    for index, tier in enumerate(ordered):
        is_last = index == len(ordered) - 1
        if tier.range_max is None and not is_last:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Only the last tier may have an open top. The tier at "
                    f"sort_order {tier.sort_order} has no range_max but is "
                    f"followed by {len(ordered) - index - 1} more tier(s)."
                ),
            )
        if tier.range_max is not None and tier.range_max <= tier.range_min:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Tier at sort_order {tier.sort_order} has range_max "
                    f"{tier.range_max}, which is not above its range_min "
                    f"{tier.range_min}."
                ),
            )

    for previous, following in zip(ordered, ordered[1:]):
        if previous.range_max != following.range_min:
            if previous.range_max < following.range_min:
                problem = "gap"
            else:
                problem = "overlap"
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Tier {problem} at the boundary between sort_order "
                    f"{previous.sort_order} and sort_order "
                    f"{following.sort_order}: previous range_max is "
                    f"{previous.range_max} but next range_min is "
                    f"{following.range_min}. They must be equal."
                ),
            )

    last = ordered[-1]
    if last.range_max is None and last.price is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The open-top tier at sort_order {last.sort_order} is quote "
                "territory and cannot carry a price."
            ),
        )

    return ordered


# ---------------------------------------------------------------------------
# Rule 2: downhill-only linking
# ---------------------------------------------------------------------------

def _parent_dimension(
    db: Session,
    firm_id: uuid.UUID,
    parent_tier_id: Optional[uuid.UUID],
    parent_option_id: Optional[uuid.UUID],
) -> Optional[ComplexityDimension]:
    """The dimension a prospective parent belongs to, or None for a flat config."""
    if parent_tier_id is not None:
        tier = _get_tier(db, firm_id, parent_tier_id)
        parent_config = _get_config(db, firm_id, tier.config_id)
        return _get_dimension(db, parent_config.dimension_id)
    if parent_option_id is not None:
        option = _get_option(db, parent_option_id)
        return _get_dimension(db, option.dimension_id)
    return None


def _validate_downhill_link(
    child: ComplexityDimension, parent: Optional[ComplexityDimension]
) -> None:
    """A config may only take a parent that is strictly coarser than itself,
    within the same flag. Uphill and same-rank links are rejected, and either
    dimension being unlinkable rejects the link outright."""
    if parent is None:
        return

    if not parent.linkable:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension '{parent.key}' is marked not linkable and cannot be "
                "a parent in a dependency chain."
            ),
        )
    if not child.linkable:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension '{child.key}' is marked not linkable and cannot "
                "hang under another dimension."
            ),
        )
    if parent.flag_id != child.flag_id:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension '{child.key}' cannot hang under '{parent.key}': "
                "they belong to different complexity flags."
            ),
        )
    if child.hierarchy_rank <= parent.hierarchy_rank:
        direction = "the same rank as" if child.hierarchy_rank == parent.hierarchy_rank else "coarser than"
        raise HTTPException(
            status_code=400,
            detail=(
                f"Downhill-only linking: '{child.key}' (hierarchy_rank "
                f"{child.hierarchy_rank}) is {direction} '{parent.key}' "
                f"(hierarchy_rank {parent.hierarchy_rank}), so it cannot hang "
                "under it. A child must be strictly finer than its parent."
            ),
        )


# ---------------------------------------------------------------------------
# Rule 3: leaf-only pricing, no double counting
# ---------------------------------------------------------------------------

def _tier_has_children(db: Session, firm_id: uuid.UUID, tier_id: uuid.UUID) -> bool:
    return db.execute(
        select(FirmDimensionConfig.id).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.parent_tier_id == tier_id,
        ).limit(1)
    ).scalar_one_or_none() is not None


def _option_has_children(db: Session, firm_id: uuid.UUID, option_id: uuid.UUID) -> bool:
    return db.execute(
        select(FirmDimensionConfig.id).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.parent_option_id == option_id,
        ).limit(1)
    ).scalar_one_or_none() is not None


def _assert_parent_is_unpriced(
    db: Session,
    firm_id: uuid.UUID,
    parent_tier_id: Optional[uuid.UUID],
    parent_option_id: Optional[uuid.UUID],
) -> None:
    """Creating a child under a parent that currently carries a price is
    rejected. The price has to be cleared first, and clearing it is the
    explicit direction-change action, not a side effect of this call."""
    if parent_tier_id is not None:
        tier = _get_tier(db, firm_id, parent_tier_id)
        if tier.price is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Tier at sort_order {tier.sort_order} is priced at "
                    f"{tier.price}, so nothing may hang under it. Prices live "
                    "only at the leaf of a chain. Clear the parent price first "
                    "via change_dimension_direction, then add the child."
                ),
            )
    if parent_option_id is not None:
        existing = db.execute(
            select(FirmOptionPrice).where(
                FirmOptionPrice.firm_id == firm_id,
                FirmOptionPrice.option_id == parent_option_id,
            )
        ).scalar_one_or_none()
        if existing is not None and existing.price is not None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Option {parent_option_id} is priced at {existing.price}, "
                    "so nothing may hang under it. Prices live only at the leaf "
                    "of a chain. Clear the parent price first via "
                    "change_dimension_direction, then add the child."
                ),
            )


def _assert_tier_can_be_priced(
    db: Session, firm_id: uuid.UUID, tier: FirmTier, incoming_price: Optional[Decimal]
) -> None:
    """The mirror of _assert_parent_is_unpriced: a tier that already has
    children cannot gain a price."""
    if incoming_price is None:
        return
    if _tier_has_children(db, firm_id, tier.id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Tier at sort_order {tier.sort_order} has dimension configs "
                "hanging under it, so it cannot carry a price. Pricing it as "
                "well as its children would double count. Price the leaf "
                "instead."
            ),
        )


def _assert_option_can_be_priced(
    db: Session, firm_id: uuid.UUID, option_id: uuid.UUID, incoming_price: Optional[Decimal]
) -> None:
    if incoming_price is None:
        return
    if _option_has_children(db, firm_id, option_id):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Option {option_id} has dimension configs hanging under it, so "
                "it cannot carry a price. Pricing it as well as its children "
                "would double count. Price the leaf instead."
            ),
        )


# ---------------------------------------------------------------------------
# Rule 8: categorical branch ambiguity. See the module docstring for why.
# ---------------------------------------------------------------------------

def _config_count_for_dimension(
    db: Session, firm_id: uuid.UUID, dimension_id: uuid.UUID
) -> int:
    """How many times this firm has configured this dimension, across all branches."""
    return db.execute(
        select(func.count(FirmDimensionConfig.id)).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.dimension_id == dimension_id,
        )
    ).scalar_one()


def _option_parented_child_exists(
    db: Session, firm_id: uuid.UUID, dimension_id: uuid.UUID
) -> bool:
    """Whether any config hangs under any vocabulary option of this dimension."""
    option_ids = db.execute(
        select(ComplexityVocabularyOption.id).where(
            ComplexityVocabularyOption.dimension_id == dimension_id
        )
    ).scalars().all()
    if not option_ids:
        return False

    return db.execute(
        select(FirmDimensionConfig.id).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.parent_option_id.in_(option_ids),
        ).limit(1)
    ).scalar_one_or_none() is not None


def _validate_categorical_branch_ambiguity(
    db: Session,
    firm_id: uuid.UUID,
    dimension: ComplexityDimension,
    parent: Optional[ComplexityDimension],
    parent_option_id: Optional[uuid.UUID],
) -> None:
    """Refuse both ways of creating a branch an option-parented child cannot name.

    Direction one: configuring a categorical dimension again when it already
    has option-parented children. The existing children would become ambiguous
    the moment the second config exists.

    Direction two: hanging a new child under an option whose dimension already
    lives on more than one branch. The new child would be born ambiguous.

    These are separate checks, not two views of one check. Either can fire
    while the other does not, depending on which side of the arrangement is
    created first.
    """
    if dimension.kind == DimensionKind.categorical:
        already_configured = _config_count_for_dimension(db, firm_id, dimension.id)
        if already_configured >= 1 and _option_parented_child_exists(
            db, firm_id, dimension.id
        ):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Dimension '{dimension.key}' is categorical, is already "
                    "configured, and has dependent configs hanging under its "
                    "options. It cannot be configured on a second branch: a "
                    "child hanging under an option would have no way to say "
                    "which branch it belongs to, and a later direction change "
                    "would delete prices from both. Remove the dependent "
                    "configs first, or price this dimension on its existing "
                    "branch."
                ),
            )

    if parent_option_id is not None and parent is not None:
        if _config_count_for_dimension(db, firm_id, parent.id) > 1:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Dimension '{dimension.key}' cannot hang under an option "
                    f"of '{parent.key}', because '{parent.key}' is configured "
                    "on more than one branch. A child references the option "
                    "alone, so it could not say which branch of "
                    f"'{parent.key}' it belongs to. Consolidate "
                    f"'{parent.key}' onto one branch first."
                ),
            )


# ---------------------------------------------------------------------------
# Rule 5: role and kind coherence
# ---------------------------------------------------------------------------

def _validate_role_coherence(
    db: Session,
    dimension: ComplexityDimension,
    role: DimensionRole,
    unit_id: Optional[uuid.UUID],
    guard_threshold: Optional[Decimal],
) -> None:
    if role == DimensionRole.guard and guard_threshold is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension '{dimension.key}' is configured with role guard, "
                "which requires a guard_threshold."
            ),
        )

    if dimension.kind == DimensionKind.numeric_range:
        if unit_id is None:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Dimension '{dimension.key}' is numeric_range, which "
                    "requires a unit_id naming what is being counted."
                ),
            )
        unit = db.get(ComplexityDimensionUnit, unit_id)
        if unit is None:
            raise HTTPException(status_code=404, detail="Dimension unit not found")
        if unit.dimension_id != dimension.id:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Unit '{unit.key}' belongs to a different dimension and "
                    f"cannot be used with '{dimension.key}'."
                ),
            )
    elif unit_id is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension '{dimension.key}' is {dimension.kind.value}, not "
                "numeric_range, so it cannot take a unit_id."
            ),
        )


# ---------------------------------------------------------------------------
# Rule 6: the activation law
# ---------------------------------------------------------------------------

def upsert_service_catalog_entry(
    db: Session,
    *,
    firm_id: uuid.UUID,
    actor_id: uuid.UUID,
    data: ServiceCatalogEntryCreate,
) -> ServiceCatalogEntryOut:
    """Create or update one firm's catalog entry for one engagement type.

    Rows are created lazily: absence of a row means not offered, identical in
    meaning to a row with is_offered false.

    The activation law is the whole point of this function. Turning a service
    on requires a pricing_mode in the same operation. A service cannot be
    half-on.
    """
    if data.is_offered and data.pricing_mode is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot offer '{data.engagement_type}' without a pricing_mode. "
                "Activation requires pricing_mode in the same operation; a "
                "service cannot be half-on."
            ),
        )

    entry = db.execute(
        select(ServiceCatalogEntry).where(
            ServiceCatalogEntry.firm_id == firm_id,
            ServiceCatalogEntry.engagement_type == data.engagement_type,
        )
    ).scalar_one_or_none()

    was_offered = entry.is_offered if entry is not None else False
    previous_mode = entry.pricing_mode if entry is not None else None

    if entry is None:
        entry = ServiceCatalogEntry(
            firm_id=firm_id,
            engagement_type=data.engagement_type,
            is_offered=data.is_offered,
            pricing_mode=data.pricing_mode,
            base_fee=data.base_fee,
        )
        db.add(entry)
    else:
        entry.is_offered = data.is_offered
        entry.pricing_mode = data.pricing_mode
        entry.base_fee = data.base_fee

    db.commit()
    db.refresh(entry)

    if data.is_offered and not was_offered:
        log_event(
            event_type="catalog.service_activated",
            firm_id=firm_id,
            entity_type="service_catalog_entry",
            entity_id=entry.id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={
                "engagement_type": entry.engagement_type,
                "pricing_mode": entry.pricing_mode.value if entry.pricing_mode else None,
            },
        )
    elif was_offered and not data.is_offered:
        log_event(
            event_type="catalog.service_deactivated",
            firm_id=firm_id,
            entity_type="service_catalog_entry",
            entity_id=entry.id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={"engagement_type": entry.engagement_type},
        )

    if entry.pricing_mode != previous_mode:
        log_event(
            event_type="catalog.pricing_mode_set",
            firm_id=firm_id,
            entity_type="service_catalog_entry",
            entity_id=entry.id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={
                "engagement_type": entry.engagement_type,
                "from_mode": previous_mode.value if previous_mode else None,
                "to_mode": entry.pricing_mode.value if entry.pricing_mode else None,
            },
        )

    return ServiceCatalogEntryOut.model_validate(entry)


# ---------------------------------------------------------------------------
# Configuring a dimension
# ---------------------------------------------------------------------------

def configure_dimension(
    db: Session,
    *,
    firm_id: uuid.UUID,
    actor_id: uuid.UUID,
    data: FirmDimensionConfigCreate,
) -> FirmDimensionConfigOut:
    """Attach one system dimension to one firm, flat or under a parent.

    Runs rules 2, 3, 5 and 8. The single-parent rule is already guaranteed by
    the Create schema and by the database check constraint, so it is not
    re-checked here.
    """
    dimension = _get_dimension(db, data.dimension_id)

    _validate_role_coherence(
        db, dimension, data.role, data.unit_id, data.guard_threshold
    )

    parent = _parent_dimension(db, firm_id, data.parent_tier_id, data.parent_option_id)
    _validate_downhill_link(dimension, parent)
    _assert_parent_is_unpriced(db, firm_id, data.parent_tier_id, data.parent_option_id)
    _validate_categorical_branch_ambiguity(
        db, firm_id, dimension, parent, data.parent_option_id
    )

    config = FirmDimensionConfig(
        firm_id=firm_id,
        dimension_id=data.dimension_id,
        role=data.role,
        unit_id=data.unit_id,
        guard_threshold=data.guard_threshold,
        parent_tier_id=data.parent_tier_id,
        parent_option_id=data.parent_option_id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)

    is_dependent = (
        data.parent_tier_id is not None or data.parent_option_id is not None
    )
    log_event(
        event_type="pricing.dimension_configured",
        firm_id=firm_id,
        entity_type="firm_dimension_config",
        entity_id=config.id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "dimension_key": dimension.key,
            "role": config.role.value,
            "direction": "dependent" if is_dependent else "flat",
            "parent_dimension_key": parent.key if parent is not None else None,
        },
    )

    if config.role == DimensionRole.guard:
        log_event(
            event_type="pricing.guard_set",
            firm_id=firm_id,
            entity_type="firm_dimension_config",
            entity_id=config.id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={
                "dimension_key": dimension.key,
                "guard_threshold": str(config.guard_threshold),
            },
        )

    return FirmDimensionConfigOut.model_validate(config)


# ---------------------------------------------------------------------------
# Reading the merged fee schedule
# ---------------------------------------------------------------------------

def get_fee_schedule_config(
    db: Session, *, firm_id: uuid.UUID
) -> FeeScheduleConfigOut:
    """The whole fee schedule for one firm: system catalog plus that firm's own
    pricing attachments, in one object.

    Backs GET /api/pricing/config. The router does nothing but authenticate,
    check the role and call this.

    TENANT SCOPING, TABLE BY TABLE, BECAUSE THE TWO GROUPS DO NOT MATCH THE
    RESPONSE SHAPE EXACTLY.

    Read unscoped, by the August 13, 2026 carve-out. These five tables carry no
    firm_id column at all, so there is nothing to filter on and no firm owns
    them:

        complexity_flags
        complexity_flag_engagement_types
        complexity_dimensions
        complexity_dimension_units
        complexity_vocabulary_options

    Scoped to firm_id, without exception:

        service_catalog_entries      <- see below
        firm_dimension_configs
        firm_tiers
        firm_option_prices

    service_catalog_entries is reported under `catalog` in the response
    because that is where the session spec put it and because it reads as
    catalog content by name. It is NOT carve-out content. It has a firm_id
    foreign key and holds each firm's own is_offered, pricing_mode and
    base_fee, so it is queried firm-scoped like everything else a firm owns.
    The spec's phrase "no firm_id filtering on any of these" is correct for the
    five carve-out tables and would be a cross-tenant leak if applied to this
    one. Raised with Andrew rather than resolved silently.

    THE NULL-VERSUS-ZERO LAW. Nothing here touches a price. Rows are handed
    straight to the Out schemas, which type every price as Optional[Decimal].
    NULL stays null (unpriced, routes to quote) and 0.00 stays 0.00
    (explicitly free). There is no `or 0`, no fill, no default anywhere in this
    function, and there must never be one.

    NO AUDIT LOG. A firm owner reading their own pricing configuration is not
    one of the audited categories (document access, role changes, logins,
    signature events, payment events, deletions). Nothing in this read touches
    those, so no audit row is written. Deliberate, not an omission.

    Ordering is stable rather than incidental so the response does not reshuffle
    between identical calls.
    """
    flags = db.execute(
        select(ComplexityFlag).order_by(ComplexityFlag.key)
    ).scalars().all()

    flag_engagement_types = db.execute(
        select(ComplexityFlagEngagementType).order_by(
            ComplexityFlagEngagementType.flag_id,
            ComplexityFlagEngagementType.engagement_type,
        )
    ).scalars().all()

    dimensions = db.execute(
        select(ComplexityDimension).order_by(
            ComplexityDimension.flag_id,
            ComplexityDimension.hierarchy_rank,
            ComplexityDimension.key,
        )
    ).scalars().all()

    dimension_units = db.execute(
        select(ComplexityDimensionUnit).order_by(
            ComplexityDimensionUnit.dimension_id,
            ComplexityDimensionUnit.key,
        )
    ).scalars().all()

    vocabulary_options = db.execute(
        select(ComplexityVocabularyOption).order_by(
            ComplexityVocabularyOption.dimension_id,
            ComplexityVocabularyOption.key,
        )
    ).scalars().all()

    catalog_entries = db.execute(
        select(ServiceCatalogEntry)
        .where(ServiceCatalogEntry.firm_id == firm_id)
        .order_by(ServiceCatalogEntry.engagement_type)
    ).scalars().all()

    configs = db.execute(
        select(FirmDimensionConfig)
        .where(FirmDimensionConfig.firm_id == firm_id)
        .order_by(FirmDimensionConfig.created_at, FirmDimensionConfig.id)
    ).scalars().all()

    tiers = db.execute(
        select(FirmTier)
        .where(FirmTier.firm_id == firm_id)
        .order_by(FirmTier.config_id, FirmTier.sort_order)
    ).scalars().all()

    option_prices = db.execute(
        select(FirmOptionPrice)
        .where(FirmOptionPrice.firm_id == firm_id)
        .order_by(FirmOptionPrice.option_id)
    ).scalars().all()

    return FeeScheduleConfigOut(
        firm_id=firm_id,
        catalog=FeeScheduleCatalogOut(
            complexity_flags=[ComplexityFlagOut.model_validate(row) for row in flags],
            complexity_flag_engagement_types=[
                ComplexityFlagEngagementTypeOut.model_validate(row)
                for row in flag_engagement_types
            ],
            complexity_dimensions=[
                ComplexityDimensionOut.model_validate(row) for row in dimensions
            ],
            complexity_dimension_units=[
                ComplexityDimensionUnitOut.model_validate(row)
                for row in dimension_units
            ],
            complexity_vocabulary_options=[
                ComplexityVocabularyOptionOut.model_validate(row)
                for row in vocabulary_options
            ],
            service_catalog_entries=[
                ServiceCatalogEntryOut.model_validate(row) for row in catalog_entries
            ],
        ),
        firm_pricing=FirmPricingOut(
            firm_dimension_configs=[
                FirmDimensionConfigOut.model_validate(row) for row in configs
            ],
            firm_tiers=[FirmTierOut.model_validate(row) for row in tiers],
            firm_option_prices=[
                FirmOptionPriceOut.model_validate(row) for row in option_prices
            ],
        ),
    )


# ---------------------------------------------------------------------------
# Reading the public intake config. The stripped public twin of the read above.
# ---------------------------------------------------------------------------

def _engagement_type_label(engagement_type: str) -> Optional[str]:
    """The lead-facing display string for a stored engagement_type value.

    Read from ENGAGEMENT_TYPE_LABELS in app/core/enums.py, which is the single
    backend source of truth for these strings and is kept complete by
    tests/test_engagement_type_canon.py. NOT hand-copied here: a second list
    would drift from the first, which is exactly what happened to the letter
    templates settings tab.

    Returns None rather than raising if the stored value is not an
    EngagementType member. That should be impossible (the schema layer
    validates it on the way in) but this is an unauthenticated read and it will
    not be the thing that 500s over one bad catalog row.
    """
    try:
        return ENGAGEMENT_TYPE_LABELS[EngagementType(engagement_type)]
    except (ValueError, KeyError):
        return None


def get_public_intake_config(
    db: Session, *, firm_id: uuid.UUID
) -> IntakePricingConfigOut:
    """The question tree one firm's public intake form renders.

    Backs GET /intake/{slug}/pricing-config, per CRM Build Contract Addendum 1
    section 9, flattened per Addendum 2. It is the stripped public twin of
    get_fee_schedule_config above and lives beside it deliberately: same
    tables, same carve-out, same tenant scoping, opposite audience.

    Signature mirrors get_fee_schedule_config. firm_id is a required keyword
    argument and is resolved from the slug by the router, never from a payload.

    THE STRIPPING CONTRACT IS THIS FUNCTION'S REASON TO EXIST. The endpoint is
    unauthenticated, so every commercial fact has to be gone before the
    response leaves here: no price, no base_fee, no pricing_mode, no role, no
    guard_threshold, no tier ranges or sort orders, no parent ids, no firm_id,
    no config or tier ids, no timestamps. The schemas in
    app/schemas/intake_pricing_config.py have no field capable of carrying any
    of it, and tests/test_intake_pricing_config.py walks a serialized response
    recursively to prove it. Note what this function never reads: firm_tiers
    and firm_option_prices are not queried here at all.

    THE APPLICABILITY RULE (ruled by Andrew, August 16, 2026). Configured means
    asked; priced means automated. Two separate gates:

    1. A question exists only if the firm has a firm_dimension_config row for
       that dimension. The system catalog decides which engagement types a flag
       is relevant to; the firm's own configs decide which of those questions
       get asked at all. No config, no question.
    2. Whether the configured thing carries a price is INVISIBLE here. A
       configured-but-unpriced dimension is still served as a question. An
       unpriced answer routes to quote at resolution time, which is downstream
       behavior and none of this endpoint's business.

    TENANT SCOPING. service_catalog_entries and firm_dimension_configs are
    filtered on firm_id without exception. The five system catalog tables carry
    no firm_id at all (the August 13, 2026 carve-out) and are read unscoped;
    they are identical for every firm and contain nothing a firm owns.

    Ordering is stable rather than incidental, so the same configuration
    renders the same form on every call: flag key, then dimension
    hierarchy_rank, then dimension key, then unit key where a dimension
    produces more than one question.
    """
    # Re-read the firm rather than taking it from the caller so the signature
    # can mirror get_fee_schedule_config. The router has already resolved the
    # slug, so a miss here is not reachable through the endpoint; the 404 text
    # matches the router's exactly anyway, so no caller can ever learn which of
    # the two lookups failed.
    firm = db.get(Firm, firm_id)
    if firm is None:
        raise HTTPException(status_code=404, detail="Intake form not found")

    # 1. Offered services. Absence of a row means not offered, identical in
    # meaning to a row with is_offered false, so the filter covers both.
    entries = db.execute(
        select(ServiceCatalogEntry)
        .where(
            ServiceCatalogEntry.firm_id == firm_id,
            ServiceCatalogEntry.is_offered.is_(True),
        )
        .order_by(ServiceCatalogEntry.engagement_type)
    ).scalars().all()

    if not entries:
        # A firm offering nothing is a real state, not an error. Empty list,
        # HTTP 200.
        return IntakePricingConfigOut(
            slug=firm.slug, firm_name=firm.name, services=[]
        )

    offered_types = [entry.engagement_type for entry in entries]

    # 2. Which flags apply to those services. Inactive flags are dropped here,
    # which is what keeps their dimensions out of every service below.
    flag_rows = db.execute(
        select(ComplexityFlagEngagementType.engagement_type, ComplexityFlag)
        .join(
            ComplexityFlag,
            ComplexityFlag.id == ComplexityFlagEngagementType.flag_id,
        )
        .where(
            ComplexityFlag.is_active.is_(True),
            ComplexityFlagEngagementType.engagement_type.in_(offered_types),
        )
    ).all()

    flags_by_id: dict[uuid.UUID, ComplexityFlag] = {}
    flag_ids_by_engagement_type: dict[str, set[uuid.UUID]] = defaultdict(set)
    for engagement_type, flag in flag_rows:
        flags_by_id[flag.id] = flag
        flag_ids_by_engagement_type[engagement_type].add(flag.id)

    # 3. What this firm has configured. Firm-scoped, joined to the system
    # dimension so kind, key, question text and hierarchy_rank come along.
    config_rows = db.execute(
        select(FirmDimensionConfig, ComplexityDimension)
        .join(
            ComplexityDimension,
            ComplexityDimension.id == FirmDimensionConfig.dimension_id,
        )
        .where(FirmDimensionConfig.firm_id == firm_id)
    ).all()

    # 4. DEDUPLICATION happens right here, and it is the only place it needs to.
    # Collapsing the config rows into a dict keyed by dimension_id means a
    # dimension configured on five branches is indistinguishable from one
    # configured flat by the time anything below reads it. Chains shape
    # pricing, not question visibility (Addendum 2), and the response carries
    # no trace of how many configs exist or how they are wired.
    dimensions_by_id: dict[uuid.UUID, ComplexityDimension] = {}
    unit_ids_by_dimension: dict[uuid.UUID, set[uuid.UUID]] = defaultdict(set)
    for config, dimension in config_rows:
        if dimension.flag_id not in flags_by_id:
            # The dimension's flag is inactive, or applies to no service this
            # firm offers. Either way the question is not asked.
            continue
        dimensions_by_id[dimension.id] = dimension
        if config.unit_id is not None:
            unit_ids_by_dimension[dimension.id].add(config.unit_id)

    # Units named by those configs. Unit selection is part of the configured
    # gate: a firm that configured the accounts unit and not the transaction
    # count unit is asked about accounts only.
    unit_ids = {
        unit_id for ids in unit_ids_by_dimension.values() for unit_id in ids
    }
    units_by_id: dict[uuid.UUID, ComplexityDimensionUnit] = {}
    if unit_ids:
        units_by_id = {
            unit.id: unit
            for unit in db.execute(
                select(ComplexityDimensionUnit).where(
                    ComplexityDimensionUnit.id.in_(unit_ids)
                )
            ).scalars().all()
        }

    # Active vocabulary for the configured categorical dimensions, ordered by
    # key. Inactive options are excluded: a lead must not be offered an answer
    # the system has retired.
    categorical_ids = [
        dimension.id
        for dimension in dimensions_by_id.values()
        if dimension.kind == DimensionKind.categorical
    ]
    options_by_dimension: dict[uuid.UUID, list[IntakeQuestionOptionOut]] = (
        defaultdict(list)
    )
    if categorical_ids:
        option_rows = db.execute(
            select(ComplexityVocabularyOption)
            .where(
                ComplexityVocabularyOption.dimension_id.in_(categorical_ids),
                ComplexityVocabularyOption.is_active.is_(True),
            )
            .order_by(
                ComplexityVocabularyOption.dimension_id,
                ComplexityVocabularyOption.key,
            )
        ).scalars().all()
        for option in option_rows:
            options_by_dimension[option.dimension_id].append(
                IntakeQuestionOptionOut(id=option.id, label=option.label)
            )

    # 5. Build the questions once per dimension, then hand the same objects to
    # every service whose flag they belong to. Each entry is paired with its
    # sort key so ordering is applied per service without recomputing it.
    questions_by_flag: dict[uuid.UUID, list[tuple[tuple, IntakeQuestionOut]]] = (
        defaultdict(list)
    )
    for dimension_id, dimension in dimensions_by_id.items():
        flag = flags_by_id[dimension.flag_id]

        # 6. Stable ordering: flag key, hierarchy_rank, dimension key, then unit
        # key to separate the several questions one numeric dimension can
        # produce. Same input, same output, every call.
        base_key = (flag.key, dimension.hierarchy_rank, dimension.key)

        if dimension.kind == DimensionKind.numeric_range:
            # One question per DISTINCT unit the firm's configs name. Configs
            # whose unit_id is NULL contribute nothing and are not represented
            # here at all.
            #
            # WHY A NULL unit_id OMITS THE QUESTION ENTIRELY. unit_id is
            # ON DELETE SET NULL, so a config keeps existing after the system
            # unit it counted in is removed from the catalog. A numeric
            # question with no unit cannot be phrased to a lead: "how many?" of
            # nothing is not a question. The alternative, guessing a unit,
            # would ask the lead to answer in units the firm never configured
            # and price the answer against tiers that mean something else.
            # Omitting it means the answer is never collected, so the service
            # routes to quote downstream, which is the designed worst case.
            for unit_id in unit_ids_by_dimension.get(dimension_id, set()):
                unit = units_by_id.get(unit_id)
                if unit is None:
                    continue
                questions_by_flag[flag.id].append(
                    (
                        base_key + (unit.key,),
                        IntakeQuestionOut(
                            flag_key=flag.key,
                            flag_name=flag.name,
                            dimension_key=dimension.key,
                            kind=dimension.kind.value,
                            # The unit-specific phrasing, from the config's
                            # chosen unit row rather than the dimension.
                            question_text=unit.question_text,
                            options=[],
                        ),
                    )
                )
        elif dimension.kind == DimensionKind.categorical:
            questions_by_flag[flag.id].append(
                (
                    base_key + ("",),
                    IntakeQuestionOut(
                        flag_key=flag.key,
                        flag_name=flag.name,
                        dimension_key=dimension.key,
                        kind=dimension.kind.value,
                        question_text=dimension.question_text,
                        options=options_by_dimension.get(dimension_id, []),
                    ),
                )
            )
        else:
            # boolean. The dimension's own question text, no options.
            questions_by_flag[flag.id].append(
                (
                    base_key + ("",),
                    IntakeQuestionOut(
                        flag_key=flag.key,
                        flag_name=flag.name,
                        dimension_key=dimension.key,
                        kind=dimension.kind.value,
                        question_text=dimension.question_text,
                        options=[],
                    ),
                )
            )

    # 7. Assemble. An offered service with zero applicable configured questions
    # still appears, with an empty questions list.
    services: list[IntakeServiceOut] = []
    for entry in entries:
        collected: list[tuple[tuple, IntakeQuestionOut]] = []
        for flag_id in flag_ids_by_engagement_type.get(entry.engagement_type, set()):
            collected.extend(questions_by_flag.get(flag_id, []))
        collected.sort(key=lambda pair: pair[0])

        services.append(
            IntakeServiceOut(
                engagement_type=entry.engagement_type,
                label=_engagement_type_label(entry.engagement_type),
                questions=[question for _, question in collected],
            )
        )

    return IntakePricingConfigOut(
        slug=firm.slug, firm_name=firm.name, services=services
    )


# ---------------------------------------------------------------------------
# Saving tiers
# ---------------------------------------------------------------------------

def save_tiers(
    db: Session,
    *,
    firm_id: uuid.UUID,
    actor_id: uuid.UUID,
    config_id: uuid.UUID,
    tiers: list[FirmTierBase],
) -> list[FirmTierOut]:
    """Replace the tier set for one config, in place.

    Existing tiers are matched to incoming ones by sort_order and updated
    rather than deleted and recreated. That is deliberate and load-bearing,
    and the reason was measured rather than assumed. Deleting a tier row that
    has configs hanging under it corrupts data two different ways depending on
    how the delete is issued:

      ORM, db.delete(tier)   -> SQLAlchemy sees the child_configs relationship
                                and issues UPDATE ... SET parent_tier_id=NULL
                                first. The child SURVIVES, silently demoted
                                from dependent to flat. Its prices stop being
                                nested and start stacking additively, so the
                                firm quietly begins quoting different numbers.
      Raw SQL, DELETE ...    -> the database applies ON DELETE CASCADE
                                unmediated and the child and its whole subtree
                                are DELETED.

    This function goes through the ORM, so the realistic failure here is the
    silent demotion, which is the worse of the two because nothing disappears
    and nothing errors. Either way a tier edit must never be able to restructure
    a subtree by accident, so removing a tier that still has children is refused
    outright and directed at change_dimension_direction.

    tests/test_pricing_config_guards.py::test_tier_edit_preserves_child_configs
    pins this, and its negative control is the delete-and-recreate rewrite.
    """
    config = _get_config(db, firm_id, config_id)
    dimension = _get_dimension(db, config.dimension_id)

    if dimension.kind != DimensionKind.numeric_range:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension '{dimension.key}' is {dimension.kind.value}, not "
                "numeric_range, so it cannot have tiers."
            ),
        )

    ordered = _validate_tier_sequence(tiers)

    existing = db.execute(
        select(FirmTier).where(
            FirmTier.firm_id == firm_id, FirmTier.config_id == config_id
        )
    ).scalars().all()
    existing_by_sort = {tier.sort_order: tier for tier in existing}
    incoming_sort_orders = {tier.sort_order for tier in ordered}

    for tier in existing:
        if tier.sort_order not in incoming_sort_orders:
            if _tier_has_children(db, firm_id, tier.id):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"Tier at sort_order {tier.sort_order} still has "
                        "dimension configs hanging under it and cannot be "
                        "removed by a tier edit. Move or remove the child "
                        "configs first via change_dimension_direction."
                    ),
                )

    # Validate every price against the leaf-only law before writing anything,
    # so a rejected save leaves the tier set exactly as it was.
    for incoming in ordered:
        current = existing_by_sort.get(incoming.sort_order)
        if current is not None:
            _assert_tier_can_be_priced(db, firm_id, current, incoming.price)

    for tier in existing:
        if tier.sort_order not in incoming_sort_orders:
            db.delete(tier)

    saved: list[FirmTier] = []
    for incoming in ordered:
        current = existing_by_sort.get(incoming.sort_order)
        if current is None:
            current = FirmTier(
                firm_id=firm_id,
                config_id=config_id,
                range_min=incoming.range_min,
                range_max=incoming.range_max,
                price=incoming.price,
                sort_order=incoming.sort_order,
            )
            db.add(current)
        else:
            current.range_min = incoming.range_min
            current.range_max = incoming.range_max
            current.price = incoming.price
        saved.append(current)

    db.commit()
    for tier in saved:
        db.refresh(tier)

    priced_count = sum(1 for tier in saved if tier.price is not None)
    log_event(
        event_type="pricing.tiers_saved",
        firm_id=firm_id,
        entity_type="firm_dimension_config",
        entity_id=config_id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "dimension_key": dimension.key,
            "tier_count": len(saved),
            "priced_count": priced_count,
            "blank_count": len(saved) - priced_count,
        },
    )

    return [FirmTierOut.model_validate(tier) for tier in saved]


# ---------------------------------------------------------------------------
# Option prices
# ---------------------------------------------------------------------------

def set_option_price(
    db: Session,
    *,
    firm_id: uuid.UUID,
    actor_id: uuid.UUID,
    data: FirmOptionPriceCreate,
) -> FirmOptionPriceOut:
    """Set or clear one firm's price on one categorical option.

    data.price of None means unpriced, which routes to quote. It does not mean
    "leave the existing price alone" -- there is no such operation here.
    """
    option = _get_option(db, data.option_id)
    dimension = _get_dimension(db, option.dimension_id)

    if dimension.kind != DimensionKind.categorical:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Dimension '{dimension.key}' is {dimension.kind.value}, not "
                "categorical, so its answers cannot carry option prices."
            ),
        )

    _assert_option_can_be_priced(db, firm_id, data.option_id, data.price)

    row = db.execute(
        select(FirmOptionPrice).where(
            FirmOptionPrice.firm_id == firm_id,
            FirmOptionPrice.option_id == data.option_id,
        )
    ).scalar_one_or_none()

    if row is None:
        row = FirmOptionPrice(
            firm_id=firm_id, option_id=data.option_id, price=data.price
        )
        db.add(row)
    else:
        row.price = data.price

    db.commit()
    db.refresh(row)

    return FirmOptionPriceOut.model_validate(row)


# ---------------------------------------------------------------------------
# Rule 4: direction change, explicit and destructive
# ---------------------------------------------------------------------------

def _descendant_config_ids(
    db: Session, firm_id: uuid.UUID, config_id: uuid.UUID
) -> list[uuid.UUID]:
    """Every config below this one, breadth first.

    Two ways down: through this config's own tiers (children point at a tier),
    and through the vocabulary options of this config's dimension (children
    point at an option). Both are walked.
    """
    found: list[uuid.UUID] = []
    frontier = [config_id]
    seen = {config_id}

    while frontier:
        current_id = frontier.pop()
        current = db.get(FirmDimensionConfig, current_id)
        if current is None or current.firm_id != firm_id:
            continue

        tier_ids = db.execute(
            select(FirmTier.id).where(
                FirmTier.firm_id == firm_id, FirmTier.config_id == current_id
            )
        ).scalars().all()

        option_ids = db.execute(
            select(ComplexityVocabularyOption.id).where(
                ComplexityVocabularyOption.dimension_id == current.dimension_id
            )
        ).scalars().all()

        children: list[uuid.UUID] = []
        if tier_ids:
            children.extend(
                db.execute(
                    select(FirmDimensionConfig.id).where(
                        FirmDimensionConfig.firm_id == firm_id,
                        FirmDimensionConfig.parent_tier_id.in_(tier_ids),
                    )
                ).scalars().all()
            )
        if option_ids:
            children.extend(
                db.execute(
                    select(FirmDimensionConfig.id).where(
                        FirmDimensionConfig.firm_id == firm_id,
                        FirmDimensionConfig.parent_option_id.in_(option_ids),
                    )
                ).scalars().all()
            )

        for child_id in children:
            if child_id not in seen:
                seen.add(child_id)
                found.append(child_id)
                frontier.append(child_id)

    return found


def change_dimension_direction(
    db: Session,
    *,
    firm_id: uuid.UUID,
    actor_id: uuid.UUID,
    config_id: uuid.UUID,
    new_parent_tier_id: Optional[uuid.UUID] = None,
    new_parent_option_id: Optional[uuid.UUID] = None,
    confirm: bool = False,
) -> FirmDimensionConfigOut:
    """Move a config between branches, or between flat and dependent.

    This is the ONLY code path permitted to alter parent_tier_id or
    parent_option_id. It is destructive by design: every price below the moved
    config stops meaning what it meant, so every tier and every option price
    belonging to the moved config and its descendants is deleted.

    confirm must be passed True explicitly. The default is False so that no
    caller performs this by accident.
    """
    if not confirm:
        raise HTTPException(
            status_code=400,
            detail=(
                "Changing a dimension's direction deletes every tier and "
                "option price belonging to it and everything below it. Pass "
                "confirm=True to proceed."
            ),
        )

    if new_parent_tier_id is not None and new_parent_option_id is not None:
        raise HTTPException(
            status_code=400,
            detail=(
                "A config may hang under a tier or under an option, not both."
            ),
        )

    config = _get_config(db, firm_id, config_id)
    dimension = _get_dimension(db, config.dimension_id)

    before_parent = _parent_dimension(
        db, firm_id, config.parent_tier_id, config.parent_option_id
    )
    before_direction = (
        "dependent"
        if config.parent_tier_id is not None or config.parent_option_id is not None
        else "flat"
    )

    after_parent = _parent_dimension(
        db, firm_id, new_parent_tier_id, new_parent_option_id
    )
    _validate_downhill_link(dimension, after_parent)
    _assert_parent_is_unpriced(db, firm_id, new_parent_tier_id, new_parent_option_id)

    affected_ids = [config_id] + _descendant_config_ids(db, firm_id, config_id)

    affected_dimension_ids = db.execute(
        select(FirmDimensionConfig.dimension_id).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.id.in_(affected_ids),
        )
    ).scalars().all()

    tiers_to_delete = db.execute(
        select(FirmTier).where(
            FirmTier.firm_id == firm_id, FirmTier.config_id.in_(affected_ids)
        )
    ).scalars().all()

    option_prices_to_delete = []
    if affected_dimension_ids:
        option_ids = db.execute(
            select(ComplexityVocabularyOption.id).where(
                ComplexityVocabularyOption.dimension_id.in_(affected_dimension_ids)
            )
        ).scalars().all()
        if option_ids:
            option_prices_to_delete = db.execute(
                select(FirmOptionPrice).where(
                    FirmOptionPrice.firm_id == firm_id,
                    FirmOptionPrice.option_id.in_(option_ids),
                )
            ).scalars().all()

    deleted_tier_count = len(tiers_to_delete)
    deleted_option_price_count = len(option_prices_to_delete)

    for tier in tiers_to_delete:
        db.delete(tier)
    for option_price in option_prices_to_delete:
        db.delete(option_price)

    config.parent_tier_id = new_parent_tier_id
    config.parent_option_id = new_parent_option_id

    after_direction = (
        "dependent"
        if new_parent_tier_id is not None or new_parent_option_id is not None
        else "flat"
    )

    db.commit()
    db.refresh(config)

    write_audit_log(
        db,
        firm_id=firm_id,
        action="pricing.direction_changed",
        actor_id=actor_id,
        actor_type="staff",
        entity_type="firm_dimension_config",
        entity_id=config_id,
        metadata={
            "dimension_key": dimension.key,
            "from_direction": before_direction,
            "to_direction": after_direction,
            "from_parent_dimension_key": (
                before_parent.key if before_parent is not None else None
            ),
            "to_parent_dimension_key": (
                after_parent.key if after_parent is not None else None
            ),
            "affected_config_count": len(affected_ids),
            "deleted_tier_count": deleted_tier_count,
            "deleted_option_price_count": deleted_option_price_count,
        },
    )

    log_event(
        event_type="pricing.direction_changed",
        firm_id=firm_id,
        entity_type="firm_dimension_config",
        entity_id=config_id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "dimension_key": dimension.key,
            "from_direction": before_direction,
            "to_direction": after_direction,
            "from_parent_dimension_key": (
                before_parent.key if before_parent is not None else None
            ),
            "to_parent_dimension_key": (
                after_parent.key if after_parent is not None else None
            ),
            "deleted_tier_count": deleted_tier_count,
            "deleted_option_price_count": deleted_option_price_count,
        },
    )

    return FirmDimensionConfigOut.model_validate(config)
