# app/services/pricing_config_service.py

"""Save-time validation for the firm-scoped pricing tables.

Every write to service_catalog_entries, firm_dimension_configs, firm_tiers and
firm_option_prices goes through this module. The database enforces shape
(single parent, branch uniqueness, referential integrity); this module enforces
the rules that need to read more than one row.

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
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import DimensionKind, DimensionRole
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_dimension_unit import ComplexityDimensionUnit
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption
from app.models.firm_dimension_config import FirmDimensionConfig
from app.models.firm_option_price import FirmOptionPrice
from app.models.firm_tier import FirmTier
from app.models.service_catalog_entry import ServiceCatalogEntry
from app.schemas.firm_dimension_config import (
    FirmDimensionConfigCreate,
    FirmDimensionConfigOut,
)
from app.schemas.firm_option_price import FirmOptionPriceCreate, FirmOptionPriceOut
from app.schemas.firm_tier import FirmTierBase, FirmTierOut
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
