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
 7. Tenant isolation                      -> every query below, and
                                             _resolve_scope for the scope FK
 8. Categorical branch ambiguity          -> _validate_categorical_branch_ambiguity
 9. The Other option is never priceable   -> _assert_option_is_not_other
10. Scope belongs to the calling firm     -> _resolve_scope
11. Scope is uniform within a tree        -> _validate_scope_uniformity

SCOPE, added August 17, 2026 (rules 10 and 11).

firm_dimension_configs.service_catalog_entry_id names the engagement type a
config tree prices, or is NULL for a blanket tree that applies to every
engagement type the system catalog maps the flag to. Precedence is WHOLESALE
replacement: if any scoped root exists for (dimension, engagement type), that
tree entirely supplies the config and the blanket tree is not consulted. There
is no field-level merge anywhere.

Rule 10 is tenant isolation wearing a different hat. service_catalog_entry_id
is a firm-owned foreign key arriving in a payload, so it is the one field on
FirmDimensionConfigCreate that could point at another firm's row. _resolve_scope
refuses that with a 404 rather than a 403, matching _get_config and _get_tier:
the caller must not be able to learn whether another firm's catalog entry
exists.

Rule 11 exists because the database cannot enforce it. A child config
references its parent TIER or parent OPTION, never its parent CONFIG, so there
is no single row Postgres could compare scopes against. The service is the only
thing holding scope uniformity, and if it stops, nothing goes red on its own.

RULE 8 NOW EVALUATES WITHIN A SCOPE. A blanket config and a scoped config for
the same dimension are NOT ambiguous with each other; that coexistence is the
designed precedence and refusing it would refuse the feature. Two configs in
the SAME scope remain subject to rule 8 exactly as before. _descendant_config_ids
was made scope-aware in the same change, and that is load-bearing rather than
tidiness: see the note on that function.

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

RULE 9, and why it exists.

Every categorical dimension in the system catalog carries an Other option,
seeded by scripts/seed_complexity_catalog.py (Open Ruling A in
docs/complexity_catalog_content_v1.md). It exists so a lead whose situation the
vocabulary does not describe still has a real, stable option ID to answer with
instead of falling off the form.

Other means precisely "the system does not know what this is". Attaching a
price to it would take a lead the catalog could not classify and hand them a
computed number anyway, which is a mispricing hole rather than an edge case.
Left unpriced, the answer routes to quote under the universal quote law, and a
human decides. That is the correct and only safe outcome, so rule 9 makes it
the only reachable one.

Note what rule 9 does NOT refuse: clearing a price. set_option_price with
price=None is how an Other price seeded before this rule existed would be
removed, so it stays available.
"""

import uuid
from collections import defaultdict
from decimal import Decimal
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.enums import (
    ENGAGEMENT_TYPE_CATEGORIES,
    ENGAGEMENT_TYPE_LABELS,
    LEAD_FACING_LABELS,
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
from app.schemas.resolved_pricing_config import ResolvedPricingConfigOut
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
# THE STATUS CODE RULING FOR EVERY GUARD BELOW. Ruled August 2026.
#
# Pricing law refusals are 422. The request was understood, was well formed,
# and names real rows; it is refused because the pricing rules do not permit
# what it asks for. Every guard in this section raises 422, without exception.
#
# 400 is reserved for a malformed request: something the service could not
# make sense of at all. No guard in this file raises one.
#
# 404 is unchanged and means the row is absent or belongs to another firm.
# _get_config, _get_dimension, _get_option, _get_tier and _resolve_scope keep
# it. The cross-firm case deliberately answers 404 rather than 403 so a caller
# cannot enumerate another firm's rows; see _resolve_scope.
#
# WHAT THIS RULING RESOLVED. Rule 9 (the Other option is never priceable)
# raised 422 while every neighbouring law refusal raised 400, so two guards a
# caller hits in the same request answered the same kind of refusal with two
# different codes. The UI has to branch on the code to decide whether to show
# the detail message verbatim, and a split like that makes that branch wrong
# half the time. Rule 9 was the correct one and the rest were moved to it.
#
# Refusal MESSAGE text was deliberately not touched in the same change. The
# messages are the UI contract and surface verbatim from response detail.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Scope. Rules 10 and 11. See the module docstring for the design.
# ---------------------------------------------------------------------------

def _scope_predicate(column, scope: Optional[uuid.UUID]):
    """A SQL predicate meaning "this row is in this scope".

    Takes the column explicitly because two tables carry a scope now:
    FirmDimensionConfig.service_catalog_entry_id and
    FirmOptionPrice.service_catalog_entry_id.

    NOT a plain `column == scope`. Comparing a column to None in SQLAlchemy
    renders `IS NULL`, but only because SQLAlchemy special-cases the Python
    literal; passing a variable that happens to hold None through `==` is the
    kind of thing that reads as correct and silently matches nothing if it ever
    stops being special-cased. Writing the branch out means the blanket case is
    visibly `IS NULL` rather than incidentally so.

    This is the same present-but-null trap as instance sixteen, one layer over:
    blanket is a real, matchable state, not an absent one.
    """
    if scope is None:
        return column.is_(None)
    return column == scope


def _describe_scope(
    db: Session, scope: Optional[uuid.UUID]
) -> str:
    """Human-readable scope for refusal messages.

    Refusal messages have to name both scopes or the caller cannot tell which
    end of the mismatch to fix, and a bare UUID is not something a firm owner
    can act on, so the engagement type is resolved where it is known.
    """
    if scope is None:
        return "blanket (every engagement type)"
    entry = db.get(ServiceCatalogEntry, scope)
    if entry is None:
        return f"scoped to catalog entry {scope}"
    return f"scoped to '{entry.engagement_type}'"


def _resolve_scope(
    db: Session,
    firm_id: uuid.UUID,
    service_catalog_entry_id: Optional[uuid.UUID],
) -> Optional[ServiceCatalogEntry]:
    """Rule 10. Resolve a scope reference, refusing anything not this firm's.

    None is the blanket case and resolves to None without a query.

    A non-None value is looked up FILTERED ON firm_id, so a reference to
    another firm's catalog entry is indistinguishable from a reference to a row
    that does not exist. That is deliberate: 404 rather than 403, matching
    _get_config and _get_tier, so the caller cannot use this endpoint to
    enumerate another firm's offered services.

    Dormant entries (is_offered false) resolve normally. A firm may configure
    overrides on a service it has not switched on yet; intake applicability is a
    separate question and is decided elsewhere.
    """
    if service_catalog_entry_id is None:
        return None

    entry = db.execute(
        select(ServiceCatalogEntry).where(
            ServiceCatalogEntry.id == service_catalog_entry_id,
            ServiceCatalogEntry.firm_id == firm_id,
        )
    ).scalar_one_or_none()
    if entry is None:
        raise HTTPException(
            status_code=404, detail="Service catalog entry not found"
        )
    return entry


def _validate_scope_uniformity(
    db: Session,
    firm_id: uuid.UUID,
    scope: Optional[uuid.UUID],
    parent_tier_id: Optional[uuid.UUID],
    parent_option_id: Optional[uuid.UUID],
) -> None:
    """Rule 11. A child config carries the same scope as its parent config.

    Both NULL counts as equal: a blanket child under a blanket parent is the
    ordinary case, not a mismatch.

    THE TWO PARENT KINDS ARE CHECKED DIFFERENTLY, because they name their
    parent with different precision.

    A parent TIER names its config exactly (firm_tiers.config_id), so the
    parent's scope is read straight off that row and compared.

    A parent OPTION names only a system vocabulary option, which belongs to the
    system dimension rather than to any one firm config of it. That is the same
    imprecision rule 8 exists to contain. So the parent config is taken to be
    the config of that option's dimension IN THE CHILD'S OWN SCOPE, and the
    check is that such a config exists. If configs of that dimension exist only
    in OTHER scopes, the child is claiming a parent from a different scope and
    is refused.

    WHAT THIS DELIBERATELY DOES NOT REFUSE: hanging a child under an option of
    a dimension the firm has not configured at all, in any scope. That shape
    was reachable before scopes existed and this session is not the place to
    start refusing it; with no parent config anywhere there is no scope to be
    uniform with, so rule 11 has nothing to say about it.
    """
    if parent_tier_id is not None:
        tier = _get_tier(db, firm_id, parent_tier_id)
        parent_config = _get_config(db, firm_id, tier.config_id)
        if parent_config.service_catalog_entry_id != scope:
            raise HTTPException(
                status_code=422,
                detail=(
                    "Scope must be uniform within a config tree. The parent "
                    f"config is {_describe_scope(db, parent_config.service_catalog_entry_id)}, "
                    f"but this config was offered as {_describe_scope(db, scope)}. "
                    "A child must carry the same scope as the config it hangs "
                    "under."
                ),
            )
        return

    if parent_option_id is not None:
        option = _get_option(db, parent_option_id)

        in_scope = db.execute(
            select(FirmDimensionConfig.id).where(
                FirmDimensionConfig.firm_id == firm_id,
                FirmDimensionConfig.dimension_id == option.dimension_id,
                _scope_predicate(FirmDimensionConfig.service_catalog_entry_id, scope),
            ).limit(1)
        ).scalar_one_or_none()
        if in_scope is not None:
            return

        # Selecting the ROW rather than the scope column, deliberately. A query
        # for service_catalog_entry_id alone returns None both when there is no
        # row at all and when the one row found is a blanket config, and those
        # are opposite answers here. Present-but-null is not absent (instance
        # sixteen); fetching the row keeps the two distinguishable.
        elsewhere = db.execute(
            select(FirmDimensionConfig).where(
                FirmDimensionConfig.firm_id == firm_id,
                FirmDimensionConfig.dimension_id == option.dimension_id,
            ).limit(1)
        ).scalar_one_or_none()

        if elsewhere is None:
            # Nothing configured for that dimension anywhere, so there is no
            # parent config to be uniform with. See the docstring.
            return

        raise HTTPException(
            status_code=422,
            detail=(
                "Scope must be uniform within a config tree. The parent "
                f"config is {_describe_scope(db, elsewhere.service_catalog_entry_id)}, "
                f"but this config was offered as {_describe_scope(db, scope)}. "
                "A child hanging under a vocabulary option must be in the same "
                "scope as the config of that option's dimension."
            ),
        )


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
                status_code=422,
                detail=f"Duplicate sort_order {tier.sort_order} in tier list.",
            )
        seen_sort_orders.add(tier.sort_order)

    for index, tier in enumerate(ordered):
        is_last = index == len(ordered) - 1
        if tier.range_max is None and not is_last:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Only the last tier may have an open top. The tier at "
                    f"sort_order {tier.sort_order} has no range_max but is "
                    f"followed by {len(ordered) - index - 1} more tier(s)."
                ),
            )
        if tier.range_max is not None and tier.range_max <= tier.range_min:
            raise HTTPException(
                status_code=422,
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
                status_code=422,
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
            status_code=422,
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
            status_code=422,
            detail=(
                f"Dimension '{parent.key}' is marked not linkable and cannot be "
                "a parent in a dependency chain."
            ),
        )
    if not child.linkable:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Dimension '{child.key}' is marked not linkable and cannot "
                "hang under another dimension."
            ),
        )
    if parent.flag_id != child.flag_id:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Dimension '{child.key}' cannot hang under '{parent.key}': "
                "they belong to different complexity flags."
            ),
        )
    if child.hierarchy_rank <= parent.hierarchy_rank:
        direction = "the same rank as" if child.hierarchy_rank == parent.hierarchy_rank else "coarser than"
        raise HTTPException(
            status_code=422,
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
    """DELIBERATELY NOT SCOPE-FILTERED, unlike _option_has_children below.

    A tier belongs to exactly one config (firm_tiers.config_id) and therefore
    sits in exactly one scope, and rule 11 makes every child under it carry that
    same scope. So this query is already confined to one scope by construction
    and an extra filter would be noise. The option version needs one because a
    vocabulary option is system-owned and shared across every config of its
    dimension, in every scope.
    """
    return db.execute(
        select(FirmDimensionConfig.id).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.parent_tier_id == tier_id,
        ).limit(1)
    ).scalar_one_or_none() is not None


def _option_has_children(
    db: Session,
    firm_id: uuid.UUID,
    option_id: uuid.UUID,
    scope: Optional[uuid.UUID],
) -> bool:
    """Whether anything hangs under this option WITHIN ONE SCOPE.

    Scoped as of August 17, 2026. The leaf-only law is a statement about one
    chain, and a chain lives entirely inside one scope (rule 11). A blanket
    child under this option says nothing about whether the SCOPED price for it
    would double count, and vice versa, so counting across scopes would refuse
    prices that are perfectly safe.
    """
    return db.execute(
        select(FirmDimensionConfig.id).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.parent_option_id == option_id,
            _scope_predicate(FirmDimensionConfig.service_catalog_entry_id, scope),
        ).limit(1)
    ).scalar_one_or_none() is not None


def _assert_parent_is_unpriced(
    db: Session,
    firm_id: uuid.UUID,
    parent_tier_id: Optional[uuid.UUID],
    parent_option_id: Optional[uuid.UUID],
    scope: Optional[uuid.UUID],
) -> None:
    """Creating a child under a parent that currently carries a price is
    rejected. The price has to be cleared first, and clearing it is the
    explicit direction-change action, not a side effect of this call.

    scope is the CHILD'S scope, and it selects which option price to look at.
    A blanket price on the parent option does not block a scoped child, and a
    scoped price does not block a blanket child, because those two never
    resolve together: the double counting this guard prevents can only happen
    within one chain, and a chain lives in one scope. The tier branch needs no
    scope argument for the reason given on _tier_has_children.
    """
    if parent_tier_id is not None:
        tier = _get_tier(db, firm_id, parent_tier_id)
        if tier.price is not None:
            raise HTTPException(
                status_code=422,
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
                _scope_predicate(FirmOptionPrice.service_catalog_entry_id, scope),
            )
        ).scalar_one_or_none()
        if existing is not None and existing.price is not None:
            raise HTTPException(
                status_code=422,
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
            status_code=422,
            detail=(
                f"Tier at sort_order {tier.sort_order} has dimension configs "
                "hanging under it, so it cannot carry a price. Pricing it as "
                "well as its children would double count. Price the leaf "
                "instead."
            ),
        )


def _assert_option_can_be_priced(
    db: Session,
    firm_id: uuid.UUID,
    option_id: uuid.UUID,
    incoming_price: Optional[Decimal],
    scope: Optional[uuid.UUID],
) -> None:
    """The mirror of _assert_parent_is_unpriced for options, within one scope.

    scope is the scope of the PRICE being set. Only children in that same scope
    can double count with it.
    """
    if incoming_price is None:
        return
    if _option_has_children(db, firm_id, option_id, scope):
        raise HTTPException(
            status_code=422,
            detail=(
                f"Option {option_id} has dimension configs hanging under it, so "
                "it cannot carry a price. Pricing it as well as its children "
                "would double count. Price the leaf instead."
            ),
        )


# ---------------------------------------------------------------------------
# Rule 9: the Other option is never priceable. See the module docstring for why.
# ---------------------------------------------------------------------------

# The key every categorical dimension's universal Other option is seeded under.
# Kept in step with OTHER_OPTION_KEY in scripts/seed_complexity_catalog.py;
# tests/test_complexity_catalog_seed.py pins that the two agree.
OTHER_OPTION_KEY = "other"


def _assert_option_is_not_other(
    option: ComplexityVocabularyOption, incoming_price: Optional[Decimal]
) -> None:
    """Refuse to attach a price to a vocabulary option keyed "other".

    THE ZERO CASE IS THE POINT, not an afterthought. Under the null-versus-zero
    law an explicit 0.00 is a real price meaning "priced at zero", not an absent
    one, so an Other priced at 0.00 would resolve to a computed total for a lead
    nobody has classified. The test is `incoming_price is not None`, never a
    truthiness test, so 0.00 is refused exactly as firmly as 500.00.

    Clearing (price=None) is allowed through: see the module docstring.

    Only the exact key "other" is refused. A tabled answer that merely reads as
    a catch-all, such as the notice_type option "other_correspondence" on the
    IRS notice flag, is ordinary priceable content and is deliberately not
    caught here.
    """
    if incoming_price is None:
        return
    if option.key != OTHER_OPTION_KEY:
        return
    raise HTTPException(
        status_code=422,
        detail=(
            f"Option '{option.key}' is the catch-all Other answer and cannot "
            "carry a price. Other means the system could not classify the "
            "lead's situation, so pricing it would produce a computed quote "
            "for a case nobody has looked at. Leave it unpriced and it routes "
            "to quote, which is the intended behavior."
        ),
    )


# ---------------------------------------------------------------------------
# Rule 8: categorical branch ambiguity. See the module docstring for why.
# ---------------------------------------------------------------------------

def _config_count_for_dimension(
    db: Session,
    firm_id: uuid.UUID,
    dimension_id: uuid.UUID,
    scope: Optional[uuid.UUID],
) -> int:
    """How many times this firm has configured this dimension WITHIN ONE SCOPE,
    across all branches.

    Scoped as of August 17, 2026. Counting across scopes would make a blanket
    config and a scoped config of the same dimension look like the two-branch
    arrangement rule 8 refuses, which would refuse the override feature itself.
    """
    return db.execute(
        select(func.count(FirmDimensionConfig.id)).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.dimension_id == dimension_id,
            _scope_predicate(FirmDimensionConfig.service_catalog_entry_id, scope),
        )
    ).scalar_one()


def _option_parented_child_exists(
    db: Session,
    firm_id: uuid.UUID,
    dimension_id: uuid.UUID,
    scope: Optional[uuid.UUID],
) -> bool:
    """Whether any config IN THIS SCOPE hangs under any vocabulary option of
    this dimension.

    Scope uniformity (rule 11) is what makes the scope filter here exact: a
    child under an option of this dimension is in the same scope as the config
    of that dimension it belongs to, so filtering on scope selects this
    arrangement's children and nobody else's.
    """
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
            _scope_predicate(FirmDimensionConfig.service_catalog_entry_id, scope),
        ).limit(1)
    ).scalar_one_or_none() is not None


def _validate_categorical_branch_ambiguity(
    db: Session,
    firm_id: uuid.UUID,
    dimension: ComplexityDimension,
    parent: Optional[ComplexityDimension],
    parent_option_id: Optional[uuid.UUID],
    scope: Optional[uuid.UUID],
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

    BOTH CHECKS EVALUATE WITHIN ONE SCOPE, as of August 17, 2026. The ambiguity
    rule 8 protects against is a child that cannot name which BRANCH it belongs
    to. A blanket config and a scoped config of the same dimension are not two
    branches of one arrangement, they are two arrangements, and scope
    uniformity (rule 11) means a child names its scope outright. So a blanket
    config and a scoped config coexisting is the designed precedence rather
    than an ambiguity, and the counts below are filtered accordingly. Two
    configs in the SAME scope are ambiguous exactly as before.
    """
    if dimension.kind == DimensionKind.categorical:
        already_configured = _config_count_for_dimension(
            db, firm_id, dimension.id, scope
        )
        if already_configured >= 1 and _option_parented_child_exists(
            db, firm_id, dimension.id, scope
        ):
            raise HTTPException(
                status_code=422,
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
        if _config_count_for_dimension(db, firm_id, parent.id, scope) > 1:
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Dimension '{dimension.key}' cannot hang under an option "
                    f"of '{parent.key}', because '{parent.key}' is configured "
                    "on more than one branch in this scope. A child references "
                    "the option alone, so it could not say which branch of "
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
            status_code=422,
            detail=(
                f"Dimension '{dimension.key}' is configured with role guard, "
                "which requires a guard_threshold."
            ),
        )

    if dimension.kind == DimensionKind.numeric_range:
        if unit_id is None:
            raise HTTPException(
                status_code=422,
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
                status_code=422,
                detail=(
                    f"Unit '{unit.key}' belongs to a different dimension and "
                    f"cannot be used with '{dimension.key}'."
                ),
            )
    elif unit_id is not None:
        raise HTTPException(
            status_code=422,
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
            status_code=422,
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
    """Attach one system dimension to one firm, flat or under a parent, blanket
    or scoped to one engagement type.

    Runs rules 2, 3, 5, 8, 10 and 11. The single-parent rule is already
    guaranteed by the Create schema and by the database check constraint, so it
    is not re-checked here.

    EVERY GUARD BELOW RUNS BEFORE db.add. A refused call writes nothing, per the
    standing rule that rejection guards precede side effects. Rule 10 runs
    first: a cross-firm scope reference is refused before this function does any
    other work with it.
    """
    dimension = _get_dimension(db, data.dimension_id)

    # Rule 10, first. Tenant isolation on the one firm-owned foreign key that
    # arrives in the payload.
    _resolve_scope(db, firm_id, data.service_catalog_entry_id)
    scope = data.service_catalog_entry_id

    _validate_role_coherence(
        db, dimension, data.role, data.unit_id, data.guard_threshold
    )

    parent = _parent_dimension(db, firm_id, data.parent_tier_id, data.parent_option_id)
    _validate_downhill_link(dimension, parent)
    _validate_scope_uniformity(
        db, firm_id, scope, data.parent_tier_id, data.parent_option_id
    )
    _assert_parent_is_unpriced(
        db, firm_id, data.parent_tier_id, data.parent_option_id, scope
    )
    _validate_categorical_branch_ambiguity(
        db, firm_id, dimension, parent, data.parent_option_id, scope
    )

    config = FirmDimensionConfig(
        firm_id=firm_id,
        dimension_id=data.dimension_id,
        service_catalog_entry_id=scope,
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
            # Recorded as a plain flag alongside the id so the log stays
            # readable without a join. The behavioral log is a recorder only;
            # nothing operational reads this back.
            "scope": "blanket" if scope is None else "engagement_type",
            "service_catalog_entry_id": str(scope) if scope is not None else None,
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
# The resolver. Per-engagement-type precedence, applied.
# ---------------------------------------------------------------------------

def _root_configs(configs: list[FirmDimensionConfig]) -> list[FirmDimensionConfig]:
    """The tops of trees: flat configs, hanging under nothing."""
    return [
        config
        for config in configs
        if config.parent_tier_id is None and config.parent_option_id is None
    ]


def resolve_pricing_config(
    db: Session,
    *,
    firm_id: uuid.UUID,
    engagement_type: Optional[str] = None,
) -> ResolvedPricingConfigOut:
    """The configuration that governs pricing for one engagement type.

    This is the read fee resolution consumes, and the one the next session's
    public intake config endpoint will consume. It is NOT get_fee_schedule_config:
    that one is the owner's view of everything configured, blanket and scoped
    together, for a settings UI to edit. This one returns exactly one answer per
    dimension.

    THE PRECEDENCE RULE, IN FULL.

    With an engagement-type context that resolves to one of this firm's catalog
    entries: for each dimension, if a SCOPED ROOT config exists for that
    (dimension, entry), that tree supplies the dimension's configuration
    entirely and the blanket tree for it is not returned at all. Otherwise the
    blanket tree is returned. The decision is made per dimension, at the root,
    and it is WHOLESALE: there is no field-level merge, at any depth.

    Without a context, or with a context naming an engagement type this firm has
    no catalog row for, the blanket configuration is returned. Absence of a
    catalog row means not offered, so there is nothing for a scoped tree to
    attach to.

    NO FALLBACK EXISTS, IN ANY FORM. Ruled by Andrew, August 17, 2026, and this
    paragraph is the statement of it because the behavior is easy to "fix" into
    a bug later. Inside a winning scoped tree, an option with a cleared price
    (a row with price NULL) and an option with NO ROW AT ALL behave IDENTICALLY:
    both are unpriced, and both route to quote under the universal quote law.
    Neither borrows the blanket price. A scoped tree answers for itself
    completely, because anything else would be the field-level merge the design
    forbids, arriving one row at a time.

    The consequence is deliberate and is mitigated OUTSIDE this function: the
    settings UI prefills a new override from the blanket values at creation
    time, so a firm that overrides one answer does not silently unprice the
    other twelve. That is the UI's job. Do not add a fallback here to make it
    easier. If this function ever starts consulting a blanket row while a scoped
    tree is winning, the wholesale-replacement guarantee is gone and every test
    asserting zero blanket leakage is measuring nothing.

    TENANT SCOPING. Every query below filters on firm_id without exception. The
    only unscoped read is the vocabulary options lookup, which is carve-out
    content carrying no firm_id (August 13, 2026).

    THE NULL-VERSUS-ZERO LAW. Nothing here touches a price. Rows go straight to
    the Out schemas. There is no `or 0`, no fill, no default, and there must
    never be one.
    """
    # 1. Resolve the context to one of this firm's catalog entries. Filtered on
    # firm_id, so another firm's engagement type can never resolve here.
    entry: Optional[ServiceCatalogEntry] = None
    if engagement_type is not None:
        entry = db.execute(
            select(ServiceCatalogEntry).where(
                ServiceCatalogEntry.firm_id == firm_id,
                ServiceCatalogEntry.engagement_type == engagement_type,
            )
        ).scalar_one_or_none()
    scope_id: Optional[uuid.UUID] = entry.id if entry is not None else None

    # 2. Load this firm's pricing rows once. Ordering is stable so identical
    # calls return identical responses.
    configs = db.execute(
        select(FirmDimensionConfig)
        .where(FirmDimensionConfig.firm_id == firm_id)
        .order_by(FirmDimensionConfig.created_at, FirmDimensionConfig.id)
    ).scalars().all()

    if not configs:
        return ResolvedPricingConfigOut(
            firm_id=firm_id,
            engagement_type=engagement_type,
            service_catalog_entry_id=scope_id,
        )

    tiers = db.execute(
        select(FirmTier)
        .where(FirmTier.firm_id == firm_id)
        .order_by(FirmTier.config_id, FirmTier.sort_order)
    ).scalars().all()

    # 3. Decide, per dimension, which scope wins. Only ROOT configs vote: a
    # scoped child cannot exist without a scoped root above it (rule 11), so
    # looking at roots is both sufficient and the thing the rule is stated in
    # terms of.
    roots = _root_configs(configs)

    overridden_dimension_ids: list[uuid.UUID] = []
    if scope_id is not None:
        seen: set[uuid.UUID] = set()
        for root in roots:
            if (
                root.service_catalog_entry_id == scope_id
                and root.dimension_id not in seen
            ):
                seen.add(root.dimension_id)
                overridden_dimension_ids.append(root.dimension_id)
    overridden = set(overridden_dimension_ids)

    def winning_scope(dimension_id: uuid.UUID) -> Optional[uuid.UUID]:
        return scope_id if dimension_id in overridden else None

    selected_roots = [
        root
        for root in roots
        if root.service_catalog_entry_id == winning_scope(root.dimension_id)
    ]

    # 4. Walk down from the winning roots. Built in Python from the rows
    # already loaded rather than by re-querying per node.
    tier_to_config = {tier.id: tier.config_id for tier in tiers}

    dimension_ids = {config.dimension_id for config in configs}
    option_to_dimension: dict[uuid.UUID, uuid.UUID] = {}
    if dimension_ids:
        option_to_dimension = {
            option.id: option.dimension_id
            for option in db.execute(
                select(ComplexityVocabularyOption).where(
                    ComplexityVocabularyOption.dimension_id.in_(dimension_ids)
                )
            ).scalars().all()
        }

    # A config's children, keyed by parent config id. The option-parented case
    # resolves its parent the same way rule 11 defines it: the config of that
    # option's dimension IN THE SAME SCOPE as the child. Matching on scope is
    # what keeps a blanket tree's walk out of a scoped tree.
    configs_by_dimension_and_scope: dict[
        tuple[uuid.UUID, Optional[uuid.UUID]], list[FirmDimensionConfig]
    ] = defaultdict(list)
    for config in configs:
        configs_by_dimension_and_scope[
            (config.dimension_id, config.service_catalog_entry_id)
        ].append(config)

    children_by_parent: dict[uuid.UUID, list[FirmDimensionConfig]] = defaultdict(list)
    for config in configs:
        if config.parent_tier_id is not None:
            parent_config_id = tier_to_config.get(config.parent_tier_id)
            if parent_config_id is not None:
                children_by_parent[parent_config_id].append(config)
        elif config.parent_option_id is not None:
            parent_dimension_id = option_to_dimension.get(config.parent_option_id)
            if parent_dimension_id is None:
                continue
            for candidate in configs_by_dimension_and_scope.get(
                (parent_dimension_id, config.service_catalog_entry_id), []
            ):
                children_by_parent[candidate.id].append(config)

    selected: list[FirmDimensionConfig] = []
    seen_ids: set[uuid.UUID] = set()
    frontier = list(selected_roots)
    while frontier:
        current = frontier.pop()
        if current.id in seen_ids:
            continue
        seen_ids.add(current.id)
        selected.append(current)
        frontier.extend(children_by_parent.get(current.id, []))

    # Restore the stable load order; the walk above visits depth-first.
    selected.sort(key=lambda config: (config.created_at, str(config.id)))
    selected_ids = {config.id for config in selected}

    # 5. Tiers belonging to the winning configs only.
    selected_tiers = [tier for tier in tiers if tier.config_id in selected_ids]

    # 6. Option prices, read AT THE WINNING SCOPE ONLY. This is where the
    # no-fallback ruling is enforced: for a dimension whose scoped tree won,
    # only rows carrying that scope are eligible, so an option the firm never
    # priced in this scope contributes nothing and routes to quote. The blanket
    # row for the same option is deliberately not consulted.
    eligible_pairs = {
        (option_id, config.service_catalog_entry_id)
        for config in selected
        for option_id, dimension_id in option_to_dimension.items()
        if dimension_id == config.dimension_id
    }

    selected_option_prices: list[FirmOptionPrice] = []
    if eligible_pairs:
        option_prices = db.execute(
            select(FirmOptionPrice)
            .where(FirmOptionPrice.firm_id == firm_id)
            .order_by(FirmOptionPrice.option_id, FirmOptionPrice.id)
        ).scalars().all()
        selected_option_prices = [
            row
            for row in option_prices
            if (row.option_id, row.service_catalog_entry_id) in eligible_pairs
        ]

    return ResolvedPricingConfigOut(
        firm_id=firm_id,
        engagement_type=engagement_type,
        service_catalog_entry_id=scope_id,
        overridden_dimension_ids=overridden_dimension_ids,
        firm_dimension_configs=[
            FirmDimensionConfigOut.model_validate(config) for config in selected
        ],
        firm_tiers=[FirmTierOut.model_validate(tier) for tier in selected_tiers],
        firm_option_prices=[
            FirmOptionPriceOut.model_validate(row) for row in selected_option_prices
        ],
    )


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

    THIS IS THE OWNER'S VIEW, NOT THE RESOLVED VIEW. It returns EVERYTHING the
    firm has configured, blanket and scoped together, unfiltered by precedence,
    because a settings UI has to render and edit both. resolve_pricing_config is
    the other one: exactly one answer per dimension, precedence applied, for
    fee resolution and the public intake endpoint. Do not swap them. Serving
    this response to a lead would expose every engagement type's pricing at
    once.

    BLANKET AND SCOPED ARE DISTINGUISHABLE IN THE RESPONSE, which is the whole
    reason the field was added to the Out schemas. Both
    FirmDimensionConfigOut.service_catalog_entry_id and
    FirmOptionPriceOut.service_catalog_entry_id are carried: None means blanket,
    a value means that config or price applies only when pricing that
    engagement type. The catalog block already contains the firm's
    service_catalog_entries, so the UI can resolve those ids to engagement
    types without a second request.

    STILL firm_owner ONLY. The manager-toggle question remains deferred and
    nothing here widens it; see the RBAC note on the router.

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

    # option_id alone stopped being a unique sort key in Phase 2.5: one option
    # can now carry a blanket price and one price per scoped engagement type.
    # Ordering on it alone would leave the tie broken by whatever the database
    # felt like, so identical calls could reshuffle. id is the tiebreaker
    # because service_catalog_entry_id is nullable and NULLS ordering is a
    # second thing to reason about for no benefit here.
    option_prices = db.execute(
        select(FirmOptionPrice)
        .where(FirmOptionPrice.firm_id == firm_id)
        .order_by(FirmOptionPrice.option_id, FirmOptionPrice.id)
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


def _lead_facing_label(engagement_type: str) -> Optional[str]:
    """The plain-English name a lead sees, falling back to the formal one.

    Added August 18, 2026. LEAD_FACING_LABELS is a SPARSE override map and is
    empty today; absence is the designed default, not a gap. A type with no
    entry serves its ENGAGEMENT_TYPE_LABELS value, which every member is
    guaranteed to have.

    THE FALLBACK LIVES HERE AND NOWHERE ELSE. It deliberately does not live in
    the intake form: if the frontend had to implement "use lead_facing_label if
    present, else label", then a firm's form and any other consumer would each
    own a copy of the rule and could disagree about it. The payload therefore
    always carries a renderable string in this field.

    Falls back THROUGH _engagement_type_label rather than reading
    ENGAGEMENT_TYPE_LABELS directly, so there stays exactly one door to the
    canon and the two functions cannot drift apart.

    Returns None only for a stored engagement_type that is not an
    EngagementType member, matching _engagement_type_label: an unauthenticated
    read does not 500 over one bad catalog row.
    """
    try:
        member = EngagementType(engagement_type)
    except ValueError:
        return None
    override = LEAD_FACING_LABELS.get(member)
    if override is not None:
        return override
    return _engagement_type_label(engagement_type)


def _engagement_category(engagement_type: str) -> Optional[str]:
    """The broad bucket the intake form groups this service under, or None.

    Added August 18, 2026. Serialized as the plain string value of a
    ServiceCategory member, matching how `kind` is served from DimensionKind.

    NO FALLBACK, AND NO DEFAULT BUCKET, ON PURPOSE. Unlike the label above,
    None here is a real and permanent state rather than a gap: a type absent
    from ENGAGEMENT_TYPE_CATEGORIES is uncategorized and the form renders it in
    a flat, ungrouped list. Guessing that an unmapped type is "tax" would put a
    service in front of leads under a heading its firm never chose, which is
    worse than no heading at all.
    """
    try:
        member = EngagementType(engagement_type)
    except ValueError:
        return None
    category = ENGAGEMENT_TYPE_CATEGORIES.get(member)
    return category.value if category is not None else None


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

    SCOPE AWARENESS, added August 18, 2026. This function used to load every
    one of the firm's configs in a single query and collapse them into one dict
    keyed by dimension_id, which was correct only while every config was
    blanket. Once per-engagement-type overrides existed (August 17, 2026) that
    shape was wrong in two visible ways: a question authored as an override for
    one engagement type was asked on ALL of them, and a blanket config and its
    scoped override collapsed into a single indistinguishable question. It now
    resolves PER ENGAGEMENT TYPE through resolve_pricing_config, which is the
    same precedence the priced path uses.

    WHY THE RESOLVER IS CALLED IN A LOOP RATHER THAN BATCHED. Precedence is
    decided per (dimension, engagement type) and there is no batch entry point,
    so this costs a handful of queries per active service. That is accepted on
    purpose. The alternative is re-implementing wholesale replacement here in a
    single pass, which would be a SECOND copy of the precedence rule, reachable
    without authentication, drifting from the first the day either changes. A
    public read that silently disagrees with the priced path about which
    questions govern an engagement type is a worse failure than N round trips
    on a rate-limited endpoint a visitor hits once per form view.

    THE STRIPPING CONTRACT IS THIS FUNCTION'S REASON TO EXIST. The endpoint is
    unauthenticated, so every commercial fact has to be gone before the
    response leaves here: no price, no base_fee, no pricing_mode, no role, no
    guard_threshold, no tier ranges or sort orders, no parent ids, no firm_id,
    no config or tier ids, no timestamps. The schemas in
    app/schemas/intake_pricing_config.py have no field capable of carrying any
    of it, and tests/test_intake_pricing_config.py walks a serialized response
    recursively to prove it.

    THE RESOLVER'S RETURN VALUE IS A COMMERCIAL OBJECT AND STOPS HERE.
    ResolvedPricingConfigOut carries firm_id, firm_tiers and firm_option_prices,
    every one of which is forbidden downstream of this function. Exactly two
    fields are ever read off it below, dimension_id and unit_id, and the public
    schemas are built fresh from the system catalog rather than from anything
    the resolver hands back. Nothing from that object is passed through, and
    nothing from it may ever be. This boundary is the price of reusing the
    resolver instead of duplicating it, and it is where a leak would be
    introduced if one ever is.

    THE APPLICABILITY RULE (ruled by Andrew, August 16, 2026). Configured means
    asked; priced means automated. Two separate gates:

    1. A question exists only if the firm has a firm_dimension_config row for
       that dimension THAT WINS AT THIS ENGAGEMENT TYPE. The system catalog
       decides which engagement types a flag is relevant to; the firm's own
       configs decide which of those questions get asked at all. No config, no
       question.
    2. Whether the configured thing carries a price is INVISIBLE here. A
       configured-but-unpriced dimension is still served as a question. An
       unpriced answer routes to quote at resolution time, which is downstream
       behavior and none of this endpoint's business.

    ACTIVE ONLY, AND EXCLUDED BEFORE RESOLUTION. Dormant services (is_offered
    false, which means the same thing as no row at all) are filtered out by the
    query in step 1, so a dormant type is never resolved and never serialized.
    That ordering is deliberate and is guarded: a firm may legitimately author
    scoped overrides on a service it has not switched on yet, and resolving
    first and filtering afterwards would mean a dormant service's configuration
    had already been assembled into public shape before anything dropped it.
    Filtering last is the shape that leaks when someone later moves the filter.

    TENANT SCOPING. service_catalog_entries is filtered on firm_id, and
    resolve_pricing_config filters every row it reads on the firm_id passed to
    it. The five system catalog tables carry no firm_id at all (the August 13,
    2026 carve-out) and are read unscoped; they are identical for every firm
    and contain nothing a firm owns.

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

    # 1. ACTIVE services only. Absence of a row means not offered, identical in
    # meaning to a row with is_offered false, so the filter covers both. This is
    # the dormant exclusion, and it happens here, before any resolution.
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

    # 3. Resolve each ACTIVE service independently, applying the same
    # per-engagement precedence the priced path applies. Only the dimension and
    # unit references are kept; see the boundary note in the docstring.
    #
    # DEDUPLICATION happens right here, per engagement type, and it is the only
    # place it needs to. Collapsing a service's winning configs into a list
    # keyed by dimension_id means a dimension configured on five branches is
    # indistinguishable from one configured flat by the time anything below
    # reads it. Chains shape pricing, not question visibility (Addendum 2), and
    # the response carries no trace of how many configs exist or how they are
    # wired. What it does NOT collapse any more is one engagement type's
    # configuration into another's.
    dimension_ids_by_type: dict[str, list[uuid.UUID]] = {}
    unit_ids_by_type_and_dimension: dict[
        tuple[str, uuid.UUID], set[uuid.UUID]
    ] = defaultdict(set)

    for entry in entries:
        resolved = resolve_pricing_config(
            db, firm_id=firm_id, engagement_type=entry.engagement_type
        )
        seen_dimensions: list[uuid.UUID] = []
        for config in resolved.firm_dimension_configs:
            if config.dimension_id not in seen_dimensions:
                seen_dimensions.append(config.dimension_id)
            if config.unit_id is not None:
                unit_ids_by_type_and_dimension[
                    (entry.engagement_type, config.dimension_id)
                ].add(config.unit_id)
        dimension_ids_by_type[entry.engagement_type] = seen_dimensions

    # 4. Load the system catalog rows those configs name, once for the whole
    # response rather than once per service. Carve-out content, read unscoped.
    all_dimension_ids = {
        dimension_id
        for dimension_ids in dimension_ids_by_type.values()
        for dimension_id in dimension_ids
    }
    dimensions_by_id: dict[uuid.UUID, ComplexityDimension] = {}
    if all_dimension_ids:
        dimensions_by_id = {
            dimension.id: dimension
            for dimension in db.execute(
                select(ComplexityDimension).where(
                    ComplexityDimension.id.in_(all_dimension_ids)
                )
            ).scalars().all()
        }

    # Units named by those configs. Unit selection is part of the configured
    # gate: a firm that configured the accounts unit and not the transaction
    # count unit is asked about accounts only.
    all_unit_ids = {
        unit_id
        for unit_ids in unit_ids_by_type_and_dimension.values()
        for unit_id in unit_ids
    }
    units_by_id: dict[uuid.UUID, ComplexityDimensionUnit] = {}
    if all_unit_ids:
        units_by_id = {
            unit.id: unit
            for unit in db.execute(
                select(ComplexityDimensionUnit).where(
                    ComplexityDimensionUnit.id.in_(all_unit_ids)
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

    # 5. Build each service's questions from ITS OWN resolved dimensions.
    services: list[IntakeServiceOut] = []
    for entry in entries:
        applicable_flag_ids = flag_ids_by_engagement_type.get(
            entry.engagement_type, set()
        )
        collected: list[tuple[tuple, IntakeQuestionOut]] = []

        for dimension_id in dimension_ids_by_type.get(entry.engagement_type, []):
            dimension = dimensions_by_id.get(dimension_id)
            if dimension is None:
                continue
            if dimension.flag_id not in applicable_flag_ids:
                # The dimension's flag is inactive, or the system catalog does
                # not map it to THIS engagement type. Either way the question is
                # not asked here, even though the config resolved. A blanket
                # config applies to every type its flag maps to, not to every
                # type the firm happens to offer.
                continue
            flag = flags_by_id[dimension.flag_id]

            # 6. Stable ordering: flag key, hierarchy_rank, dimension key, then
            # unit key to separate the several questions one numeric dimension
            # can produce. Same input, same output, every call.
            base_key = (flag.key, dimension.hierarchy_rank, dimension.key)

            if dimension.kind == DimensionKind.numeric_range:
                # One question per DISTINCT unit this service's winning configs
                # name. Configs whose unit_id is NULL contribute nothing and are
                # not represented here at all.
                #
                # WHY A NULL unit_id OMITS THE QUESTION ENTIRELY. unit_id is
                # ON DELETE SET NULL, so a config keeps existing after the system
                # unit it counted in is removed from the catalog. A numeric
                # question with no unit cannot be phrased to a lead: "how many?"
                # of nothing is not a question. The alternative, guessing a unit,
                # would ask the lead to answer in units the firm never configured
                # and price the answer against tiers that mean something else.
                # Omitting it means the answer is never collected, so the service
                # routes to quote downstream, which is the designed worst case.
                for unit_id in unit_ids_by_type_and_dimension.get(
                    (entry.engagement_type, dimension_id), set()
                ):
                    unit = units_by_id.get(unit_id)
                    if unit is None:
                        continue
                    collected.append(
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
                collected.append(
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
                collected.append(
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

        collected.sort(key=lambda pair: pair[0])

        # 7. An ACTIVE service with zero applicable configured questions still
        # appears, with an empty questions list. That is a legitimate state (the
        # lead picks it and the engagement routes to quote), not an error, which
        # is why nothing here is conditional on `collected` being non-empty.
        services.append(
            IntakeServiceOut(
                engagement_type=entry.engagement_type,
                label=_engagement_type_label(entry.engagement_type),
                lead_facing_label=_lead_facing_label(entry.engagement_type),
                category=_engagement_category(entry.engagement_type),
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
            status_code=422,
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
                    status_code=422,
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
    """Set or clear one firm's price on one categorical option, in one scope.

    data.price of None means unpriced, which routes to quote. It does not mean
    "leave the existing price alone" -- there is no such operation here.

    data.service_catalog_entry_id is the SCOPE, and it addresses a DIFFERENT
    ROW rather than modifying one. Setting a scoped price never touches the
    blanket price and vice versa; the two coexist and resolution picks between
    them. That is the whole point of Phase 2.5: before it, one option had one
    price per firm and per-engagement-type categorical overrides could not be
    expressed at all.

    Do not read the two None-able fields as related. price=None means unpriced;
    service_catalog_entry_id=None means blanket. Clearing a scoped price
    (price=None with a scope set) leaves a real row that says "this engagement
    type has no price for this answer", which under the universal quote law
    routes to quote rather than falling back to the blanket price. That is
    deliberate: wholesale replacement means a scoped tree answers for itself.

    Every rejection below runs before the row is touched, so a refused call
    leaves firm_option_prices exactly as it found it.
    """
    option = _get_option(db, data.option_id)
    dimension = _get_dimension(db, option.dimension_id)

    if dimension.kind != DimensionKind.categorical:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Dimension '{dimension.key}' is {dimension.kind.value}, not "
                "categorical, so its answers cannot carry option prices."
            ),
        )

    # Rule 10. Tenant isolation on the scope reference, before anything else
    # reads it and well before any write.
    scope = data.service_catalog_entry_id
    _resolve_scope(db, firm_id, scope)

    # Rule 9 is UNCHANGED by scoping and needs no scope argument. It keys on
    # option.key alone, so the catch-all Other answer is refused a price
    # identically inside a scoped tree and inside the blanket tree. Verified by
    # test rather than assumed.
    _assert_option_is_not_other(option, data.price)
    _assert_option_can_be_priced(db, firm_id, data.option_id, data.price, scope)

    row = db.execute(
        select(FirmOptionPrice).where(
            FirmOptionPrice.firm_id == firm_id,
            FirmOptionPrice.option_id == data.option_id,
            _scope_predicate(FirmOptionPrice.service_catalog_entry_id, scope),
        )
    ).scalar_one_or_none()

    if row is None:
        row = FirmOptionPrice(
            firm_id=firm_id,
            option_id=data.option_id,
            service_catalog_entry_id=scope,
            price=data.price,
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

    THE OPTION WALK IS FILTERED ON SCOPE, AND THAT FILTER IS LOAD-BEARING.

    A tier names its config exactly, so the tier walk is precise. The option
    walk is not: it claims every config of this firm hanging under any option
    of this dimension, which before scopes existed was the known imprecision
    rule 8 contains. With scopes, that imprecision would reach ACROSS scopes.
    A blanket config and a scoped config of the same categorical dimension are
    designed to coexist (that is the whole feature), and without this filter a
    direction change on the blanket config would walk into the scoped tree and
    delete the tiers and option prices belonging to the override, and the
    reverse. Rule 8 no longer refuses that arrangement, so nothing else would
    stop it.

    Scope uniformity (rule 11) is what makes the filter exact rather than
    approximate: every config in a tree carries its root's scope, so "same
    scope" and "same tree" agree for the option walk.
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
                        # Same scope only. See the docstring: without this the
                        # walk crosses from a blanket tree into a scoped one.
                        _scope_predicate(
                            FirmDimensionConfig.service_catalog_entry_id,
                            current.service_catalog_entry_id,
                        ),
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

    SCOPE IS NOT CHANGED HERE AND CANNOT BE. The moved config keeps its own
    service_catalog_entry_id, and rule 11 is re-run against the NEW parent, so
    a config cannot be moved out of its scope and under a parent in another
    one. There is deliberately no re-scope operation in this build: re-scoping
    a tree invalidates every price under it for the same reason a direction
    change does, so it needs its own confirmed, audited action rather than a
    quiet extra argument here. Recorded in the session summary as the next
    thing this function will grow.
    """
    if not confirm:
        raise HTTPException(
            status_code=422,
            detail=(
                "Changing a dimension's direction deletes every tier and "
                "option price belonging to it and everything below it. Pass "
                "confirm=True to proceed."
            ),
        )

    if new_parent_tier_id is not None and new_parent_option_id is not None:
        raise HTTPException(
            status_code=422,
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
    # Rule 11 on the update side. The config keeps its scope, so the new parent
    # has to be in that same scope or the move would break tree uniformity.
    # Runs before anything is deleted, per the rejection-before-side-effects
    # rule: a refused move must not destroy the prices it was refused over.
    _validate_scope_uniformity(
        db,
        firm_id,
        config.service_catalog_entry_id,
        new_parent_tier_id,
        new_parent_option_id,
    )
    _assert_parent_is_unpriced(
        db,
        firm_id,
        new_parent_tier_id,
        new_parent_option_id,
        config.service_catalog_entry_id,
    )

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
            # SCOPE-FILTERED, and load-bearing for the same reason the option
            # walk in _descendant_config_ids is. Every affected config carries
            # the moved config's scope (rule 11), so only option prices in that
            # scope belong to this tree. Without the filter, moving a blanket
            # config would delete the per-engagement-type prices a firm set on
            # the same vocabulary options in a scoped tree, and vice versa:
            # silent destruction of an override the caller never mentioned.
            option_prices_to_delete = db.execute(
                select(FirmOptionPrice).where(
                    FirmOptionPrice.firm_id == firm_id,
                    FirmOptionPrice.option_id.in_(option_ids),
                    _scope_predicate(
                        FirmOptionPrice.service_catalog_entry_id,
                        config.service_catalog_entry_id,
                    ),
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


# ---------------------------------------------------------------------------
# Deleting a config. Delete-and-recreate is the path for a scope change or for
# removing a dimension, so this is the only way a config tree leaves the
# database.
# ---------------------------------------------------------------------------

def delete_config(
    db: Session,
    *,
    firm_id: uuid.UUID,
    actor_id: uuid.UUID,
    config_id: uuid.UUID,
    confirm: bool = False,
) -> None:
    """Delete one config, everything below it, and every price they carry.

    There is no re-scope and no un-parent operation in this build. A firm that
    wants a config in a different scope, or wants a dimension gone, deletes and
    recreates. That makes this the destructive twin of configure_dimension, and
    it destroys strictly more than change_dimension_direction does: that one
    clears prices and keeps the configs, this one takes the configs too.

    WHAT IS DELETED, and in what order.

      1. every option price belonging to the affected configs, in this tree's
         scope
      2. every tier belonging to the affected configs
      3. the configs themselves, DEEPEST FIRST, root last

    CHILDREN BEFORE PARENTS, EXPLICITLY. The ordering is not tidiness and the
    reason was measured rather than assumed (see the note on save_tiers).
    firm_tiers.child_configs carries no cascade, so deleting a tier through the
    ORM issues UPDATE ... SET parent_tier_id = NULL on any config hanging under
    it rather than removing it: the child SURVIVES, silently demoted from
    dependent to flat, and its prices stop nesting and start stacking. Nothing
    errors and nothing disappears, which is what makes it dangerous. Here every
    such child is inside the affected set and is deleted in step 3, so the
    demotion is transient rather than a leak, but the order is written out
    explicitly so a later edit cannot reintroduce the silent-survivor shape by
    reordering these blocks.

    _descendant_config_ids appends a child only while processing its parent, so
    a parent always precedes its children in that list. Walking it in reverse
    is therefore deepest-first, and the root is deleted last.

    NO TEST CAN CURRENTLY DISCRIMINATE THAT ORDERING, and the negative control
    that tried says so: deleting the configs shallowest-first leaves every test
    in tests/test_pricing_config_delete.py green. The reason is structural
    rather than a gap in the tests. A config never references another config
    directly (the link runs through a tier or a vocabulary option), so with the
    tiers already gone there is no constraint left for the config order to
    violate. The ordering is defensive against a future parent_config_id
    column, which is the deferred fix recorded in the module docstring, and it
    becomes load-bearing the moment that column lands. Treat it as unguarded
    until then rather than as a rule something is watching.

    SCOPE IS AN ABSOLUTE BOUNDARY HERE. The option-price query filters on this
    tree's own service_catalog_entry_id, exactly as change_dimension_direction
    does and for the same load-bearing reason: a blanket config and a scoped
    override of the same categorical dimension are designed to coexist, and an
    unfiltered delete would walk out of the tree it was asked about and destroy
    the other one's prices. Deleting a scoped override never touches blanket
    rows, and deleting a blanket config never touches a scoped override.

    The tier query needs no scope filter: a tier names its config exactly
    (firm_tiers.config_id) and every affected config is already in this tree.

    CONFIRM, AND WHY THE LOOKUP COMES FIRST. change_dimension_direction checks
    its confirm flag before doing anything else, because its refusal message is
    generic. This refusal names what will actually be destroyed, including
    counts, so the config has to be loaded to write it. _get_config is
    therefore called first, and the ordering is deliberate in both directions:
    a caller naming a config that does not exist, or one belonging to another
    firm, gets 404 from _get_config and never reaches a message that would
    confirm the row exists and tell them how much is hanging off it. Refusing
    on confirm first would have leaked exactly that.

    NOTHING IS WRITTEN ON THE REFUSAL PATH. Every read above happens before the
    first db.delete, per the standing rule that rejection guards precede side
    effects: a refused delete must not destroy anything on its way to the
    refusal.
    """
    config = _get_config(db, firm_id, config_id)
    dimension = _get_dimension(db, config.dimension_id)
    scope = config.service_catalog_entry_id

    descendant_ids = _descendant_config_ids(db, firm_id, config_id)
    affected_ids = [config_id] + descendant_ids

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
                    # See the docstring: this tree's scope only.
                    _scope_predicate(
                        FirmOptionPrice.service_catalog_entry_id, scope
                    ),
                )
            ).scalars().all()

    deleted_tier_count = len(tiers_to_delete)
    deleted_option_price_count = len(option_prices_to_delete)

    if not confirm:
        raise HTTPException(
            status_code=422,
            detail=(
                f"Deleting this configuration of '{dimension.key}' permanently "
                f"removes it, the {len(descendant_ids)} dependent "
                "configuration(s) beneath it, and every price they carry: "
                f"{deleted_tier_count} tier(s) and "
                f"{deleted_option_price_count} option price(s). This cannot be "
                "undone and the prices cannot be recovered. Pass confirm=true "
                "to proceed."
            ),
        )

    # Order is load-bearing. See the docstring.
    for option_price in option_prices_to_delete:
        db.delete(option_price)
    for tier in tiers_to_delete:
        db.delete(tier)

    # Deepest first, root last.
    for descendant_id in reversed(descendant_ids):
        descendant = db.get(FirmDimensionConfig, descendant_id)
        if descendant is not None:
            db.delete(descendant)
    db.delete(config)

    db.commit()

    write_audit_log(
        db,
        firm_id=firm_id,
        action="pricing.config_deleted",
        actor_id=actor_id,
        actor_type="staff",
        entity_type="firm_dimension_config",
        entity_id=config_id,
        metadata={
            "dimension_key": dimension.key,
            "scope": "blanket" if scope is None else "engagement_type",
            "service_catalog_entry_id": str(scope) if scope is not None else None,
            "deleted_config_count": len(affected_ids),
            "deleted_descendant_count": len(descendant_ids),
            "deleted_tier_count": deleted_tier_count,
            "deleted_option_price_count": deleted_option_price_count,
        },
    )

    log_event(
        event_type="pricing.config_deleted",
        firm_id=firm_id,
        entity_type="firm_dimension_config",
        entity_id=config_id,
        actor_type="staff",
        actor_id=actor_id,
        metadata={
            "dimension_key": dimension.key,
            "scope": "blanket" if scope is None else "engagement_type",
            "deleted_config_count": len(affected_ids),
            "deleted_tier_count": deleted_tier_count,
            "deleted_option_price_count": deleted_option_price_count,
        },
    )
