# tests/test_pricing_scope_guards.py

"""Guard tests for per-engagement-type pricing overrides (scope).

Companion to tests/test_pricing_config_guards.py, which covers rules 1 through
9. This file covers what the August 17, 2026 scope ruling added:

    rule 10  scope belongs to the calling firm     (tenant isolation)
    rule 11  scope is uniform within a tree
    rule 8   re-stated to evaluate WITHIN a scope
    the branch-uniqueness constraint, now including the scope column
    the resolver, and its wholesale-replacement precedence

EVERY TEST HERE HAS BEEN WATCHED TO FAIL. Each load-bearing assertion was run
against a deliberately broken copy of the thing it guards, confirmed red for
the right reason, then the break was reverted, the test re-run green, and the
working tree diffed against git. The per-control record is in the session
report. One control per load-bearing rule, not one per file: several tests here
survive defects that only one of them catches, and the controls were chosen to
be the ones that discriminate.

TWO NULLABLE FIELDS, UNRELATED MEANINGS. Read them apart throughout:

    price = None                     -> unpriced, routes to quote
    service_catalog_entry_id = None  -> blanket, says nothing about price

These are service-level tests. There is no write router for pricing config, so
they call pricing_config_service directly with an explicit firm_id, which is
also the shape the tenant isolation tests need.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.enums import (
    DimensionKind,
    DimensionRole,
    EngagementType,
    PricingMode,
    UserRole,
)
from app.core.security import get_password_hash
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_dimension_unit import ComplexityDimensionUnit
from app.models.complexity_flag import ComplexityFlag
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption
from app.models.firm import Firm
from app.models.firm_dimension_config import FirmDimensionConfig
from app.models.firm_option_price import FirmOptionPrice
from app.models.service_catalog_entry import ServiceCatalogEntry
from app.models.user import User
from app.schemas.firm_dimension_config import FirmDimensionConfigCreate
from app.schemas.firm_option_price import FirmOptionPriceCreate
from app.schemas.firm_tier import FirmTierBase
from app.schemas.service_catalog_entry import ServiceCatalogEntryCreate
from app.services import pricing_config_service as svc
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Fixtures. conftest's clean_db truncates between tests, so every test seeds
# the catalog content it needs.
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_firm(db, name: str, slug: str):
    """A firm plus a real owner. The owner is real because audit_logs.actor_id
    is a foreign key to users.id and write_audit_log swallows its own
    failures."""
    firm = Firm(name=name, slug=slug)
    db.add(firm)
    db.commit()
    db.refresh(firm)

    user = User(
        firm_id=firm.id,
        email=f"owner-{slug}-{uuid.uuid4()}@example.com",
        hashed_password=get_password_hash("password123"),
        full_name=f"Owner {name}",
        role=UserRole.firm_owner,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return firm, user


@pytest.fixture
def firm_a(db):
    return _make_firm(db, "Firm A CPA", f"firm-a-{uuid.uuid4().hex[:8]}")


@pytest.fixture
def firm_b(db):
    return _make_firm(db, "Firm B CPA", f"firm-b-{uuid.uuid4().hex[:8]}")


@pytest.fixture
def flag(db):
    row = ComplexityFlag(key="crypto", name="Crypto activity")
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def _entry(db, firm, user, engagement_type: str):
    """One catalog entry, which is what a scope points at."""
    return svc.upsert_service_catalog_entry(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=ServiceCatalogEntryCreate(
            engagement_type=engagement_type,
            is_offered=True,
            pricing_mode=PricingMode.fixed,
        ),
    )


def _numeric_dimension(db, flag, key: str, rank: int):
    dimension = ComplexityDimension(
        flag_id=flag.id,
        key=key,
        kind=DimensionKind.numeric_range,
        hierarchy_rank=rank,
        linkable=True,
    )
    db.add(dimension)
    db.commit()
    db.refresh(dimension)

    unit = ComplexityDimensionUnit(
        dimension_id=dimension.id, key=f"{key}_count", label="transaction count"
    )
    db.add(unit)
    db.commit()
    db.refresh(unit)
    return dimension, unit


def _categorical_dimension(db, flag, key: str, rank: int, option_keys=("a", "b")):
    dimension = ComplexityDimension(
        flag_id=flag.id,
        key=key,
        kind=DimensionKind.categorical,
        hierarchy_rank=rank,
    )
    db.add(dimension)
    db.commit()
    db.refresh(dimension)

    options = []
    for option_key in option_keys:
        option = ComplexityVocabularyOption(
            dimension_id=dimension.id, key=option_key, label=option_key.upper()
        )
        db.add(option)
        options.append(option)
    db.commit()
    for option in options:
        db.refresh(option)
    return dimension, options


def _configure(db, firm, user, dimension, unit=None, scope=None, **kwargs):
    return svc.configure_dimension(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=FirmDimensionConfigCreate(
            dimension_id=dimension.id,
            service_catalog_entry_id=scope,
            role=kwargs.pop("role", DimensionRole.priced),
            unit_id=unit.id if unit is not None else None,
            **kwargs,
        ),
    )


def _tier(lo, hi, price, order):
    return FirmTierBase(
        range_min=Decimal(lo),
        range_max=None if hi is None else Decimal(hi),
        price=None if price is None else Decimal(price),
        sort_order=order,
    )


def _price(db, firm, user, option_id, price, scope=None):
    return svc.set_option_price(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=FirmOptionPriceCreate(
            option_id=option_id,
            service_catalog_entry_id=scope,
            price=None if price is None else Decimal(price),
        ),
    )


# ---------------------------------------------------------------------------
# 1. Branch uniqueness, now including the scope column.
#
# These assert against the DATABASE, not against a service guard. Nothing in
# the service refuses a duplicate flat numeric config; the constraint is the
# only thing standing there, which is exactly why it needs its own tests.
# ---------------------------------------------------------------------------

def test_same_dimension_same_scope_same_branch_is_refused(db, firm_a, flag):
    """Two identical scoped configs collide, as they always did for blanket."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    _configure(db, firm, user, dimension, unit, scope=entry.id)

    with pytest.raises(IntegrityError):
        _configure(db, firm, user, dimension, unit, scope=entry.id)
    db.rollback()


def test_two_blanket_configs_same_branch_still_refused(db, firm_a, flag):
    """THE NULLS NOT DISTINCT CASE, and the reason the property exists.

    Both rows read (firm, dimension, NULL, NULL, NULL). Under Postgres default
    NULLS DISTINCT they would BOTH insert, because NULL never equals NULL,
    which would silently un-enforce this constraint for the flat blanket case:
    the common case. Adding service_catalog_entry_id to the constraint in
    1ed5f6118514 added a THIRD nullable member, so this test is load-bearing
    for the migration as well as for the original design.
    """
    firm, user = firm_a
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    _configure(db, firm, user, dimension, unit)

    with pytest.raises(IntegrityError):
        _configure(db, firm, user, dimension, unit)
    db.rollback()


def test_same_dimension_in_two_scopes_both_insert(db, firm_a, flag):
    """THE POINT OF THE WHOLE SESSION, at the constraint level.

    Same dimension, same branch position (flat), two different scopes. Before
    1ed5f6118514 the second insert collided with the first and the override
    feature was impossible to express. This is the test that a constraint
    missing the scope column fails.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    blanket = _configure(db, firm, user, dimension, unit)
    scoped = _configure(db, firm, user, dimension, unit, scope=entry.id)

    assert blanket.service_catalog_entry_id is None
    assert scoped.service_catalog_entry_id == entry.id
    assert blanket.id != scoped.id

    # Both are really on the table, read directly rather than through a
    # service read whose own filtering could hide one.
    db.expire_all()
    rows = db.execute(
        select(FirmDimensionConfig).where(
            FirmDimensionConfig.firm_id == firm.id,
            FirmDimensionConfig.dimension_id == dimension.id,
        )
    ).scalars().all()
    assert len(rows) == 2


def test_two_scoped_configs_for_different_engagement_types_both_insert(db, firm_a, flag):
    """Three coexisting rows: blanket, plus one per engagement type."""
    firm, user = firm_a
    entry_1040 = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    entry_1120 = _entry(db, firm, user, EngagementType.tax_return_1120.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    _configure(db, firm, user, dimension, unit)
    _configure(db, firm, user, dimension, unit, scope=entry_1040.id)
    _configure(db, firm, user, dimension, unit, scope=entry_1120.id)

    db.expire_all()
    rows = db.execute(
        select(FirmDimensionConfig).where(
            FirmDimensionConfig.firm_id == firm.id,
            FirmDimensionConfig.dimension_id == dimension.id,
        )
    ).scalars().all()
    assert len(rows) == 3
    assert {row.service_catalog_entry_id for row in rows} == {
        None, entry_1040.id, entry_1120.id
    }


# ---------------------------------------------------------------------------
# 1b. The same, for firm_option_prices (Phase 2.5).
# ---------------------------------------------------------------------------

def test_two_blanket_option_prices_refused(db, firm_a, flag):
    """NULLS NOT DISTINCT on firm_option_prices, new in 62e44a7fd8f1.

    Written against the table rather than through set_option_price, because
    set_option_price finds the existing row and updates it instead of
    inserting a second one. The service is the friendly door; this asserts the
    lock behind it.
    """
    firm, user = firm_a
    _dimension, options = _categorical_dimension(db, flag, "choice_dim", rank=1)

    db.add(
        FirmOptionPrice(
            firm_id=firm.id, option_id=options[0].id, price=Decimal("100.00")
        )
    )
    db.commit()

    db.add(
        FirmOptionPrice(
            firm_id=firm.id, option_id=options[0].id, price=Decimal("200.00")
        )
    )
    with pytest.raises(IntegrityError):
        db.commit()
    db.rollback()


def test_blanket_and_scoped_option_prices_coexist(db, firm_a, flag):
    """The categorical half of the override feature, added in Phase 2.5.

    Before 62e44a7fd8f1 an option had exactly one price per firm, so a scoped
    tree and the blanket tree read the same number and per-engagement-type
    pricing of a categorical answer could not be expressed at all.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _dimension, options = _categorical_dimension(db, flag, "choice_dim", rank=1)

    blanket = _price(db, firm, user, options[0].id, "300.00")
    scoped = _price(db, firm, user, options[0].id, "500.00", scope=entry.id)

    assert blanket.service_catalog_entry_id is None
    assert scoped.service_catalog_entry_id == entry.id
    assert blanket.id != scoped.id

    db.expire_all()
    rows = db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.option_id == options[0].id)
    ).scalars().all()
    assert {row.service_catalog_entry_id: row.price for row in rows} == {
        None: Decimal("300.00"),
        entry.id: Decimal("500.00"),
    }


def test_setting_a_scoped_price_does_not_disturb_the_blanket_price(db, firm_a, flag):
    """Counterweight. A scoped write must ADD a row, never repoint the blanket
    one, or the override would silently rewrite every other engagement type."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _dimension, options = _categorical_dimension(db, flag, "choice_dim", rank=1)

    _price(db, firm, user, options[0].id, "300.00")
    _price(db, firm, user, options[0].id, "500.00", scope=entry.id)
    _price(db, firm, user, options[0].id, "650.00", scope=entry.id)

    db.expire_all()
    rows = db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.option_id == options[0].id)
    ).scalars().all()
    by_scope = {row.service_catalog_entry_id: row.price for row in rows}
    assert by_scope[None] == Decimal("300.00"), "the blanket price was overwritten"
    assert by_scope[entry.id] == Decimal("650.00")


# ---------------------------------------------------------------------------
# 2. Rule 10: tenant isolation on the scope reference.
#
# Both use a REAL second firm with a REAL catalog entry, so the refusal is
# about ownership rather than about the id not existing.
# ---------------------------------------------------------------------------

def test_firm_a_cannot_scope_a_config_to_firm_b_catalog_entry(db, firm_a, firm_b, flag):
    a_firm, a_user = firm_a
    b_firm, b_user = firm_b

    b_entry = _entry(db, b_firm, b_user, EngagementType.tax_return_1040.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    with pytest.raises(HTTPException) as exc:
        _configure(db, a_firm, a_user, dimension, unit, scope=b_entry.id)

    # 404 rather than 403, deliberately: Firm A must not be able to learn that
    # Firm B's catalog entry exists.
    assert exc.value.status_code == 404
    assert "Service catalog entry not found" in exc.value.detail

    # Nothing was written. Read the table directly, not a service read.
    db.expire_all()
    assert db.execute(
        select(FirmDimensionConfig).where(FirmDimensionConfig.firm_id == a_firm.id)
    ).scalars().all() == []

    # And Firm B's catalog entry is still there, still Firm B's. The refusal
    # must not have reached across and done anything on its way out.
    surviving = db.get(ServiceCatalogEntry, b_entry.id)
    assert surviving is not None
    assert surviving.firm_id == b_firm.id


def test_firm_a_cannot_scope_an_option_price_to_firm_b_catalog_entry(
    db, firm_a, firm_b, flag
):
    a_firm, a_user = firm_a
    b_firm, b_user = firm_b

    b_entry = _entry(db, b_firm, b_user, EngagementType.tax_return_1040.value)
    _dimension, options = _categorical_dimension(db, flag, "choice_dim", rank=1)

    with pytest.raises(HTTPException) as exc:
        _price(db, a_firm, a_user, options[0].id, "10.00", scope=b_entry.id)

    assert exc.value.status_code == 404

    db.expire_all()
    assert db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.firm_id == a_firm.id)
    ).scalars().all() == []


def test_scoping_to_own_catalog_entry_is_accepted(db, firm_a, flag):
    """Positive control for rule 10. Without this, a guard that refused every
    scope reference would pass both tests above while breaking the feature."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    config = _configure(db, firm, user, dimension, unit, scope=entry.id)
    assert config.service_catalog_entry_id == entry.id


def test_scope_may_name_a_dormant_service(db, firm_a, flag):
    """Overrides may be configured on is_offered=false engagement types.

    Locked decision, August 17: intake applicability is a separate question.
    A guard that required is_offered would pass every other test here.
    """
    firm, user = firm_a
    dormant = svc.upsert_service_catalog_entry(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=ServiceCatalogEntryCreate(
            engagement_type=EngagementType.tax_return_1120.value,
            is_offered=False,
            pricing_mode=None,
        ),
    )
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    config = _configure(db, firm, user, dimension, unit, scope=dormant.id)
    assert config.service_catalog_entry_id == dormant.id


# ---------------------------------------------------------------------------
# 3. Rule 11: scope is uniform within a tree.
# ---------------------------------------------------------------------------

def _scoped_root_with_tier(db, firm, user, flag, scope):
    """A coarse numeric root in `scope`, with one unpriced tier to hang under."""
    coarse, coarse_unit = _numeric_dimension(db, flag, "coarse_dim", rank=1)
    fine, fine_unit = _numeric_dimension(db, flag, "fine_dim", rank=5)

    root = _configure(db, firm, user, coarse, coarse_unit, scope=scope)
    tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=root.id,
        tiers=[_tier(0, 10, None, 0)],
    )
    return root, tiers[0], fine, fine_unit


def test_scoped_root_with_blanket_child_is_refused(db, firm_a, flag):
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _root, tier, fine, fine_unit = _scoped_root_with_tier(
        db, firm, user, flag, scope=entry.id
    )

    with pytest.raises(HTTPException) as exc:
        _configure(
            db, firm, user, fine, fine_unit, scope=None, parent_tier_id=tier.id
        )

    assert exc.value.status_code == 400
    assert "Scope must be uniform" in exc.value.detail
    # The message names BOTH scopes, or the caller cannot tell which end to fix.
    assert "tax_return_1040" in exc.value.detail
    assert "blanket" in exc.value.detail

    # Rejection before side effects: no child row survived the refusal.
    db.expire_all()
    assert db.execute(
        select(FirmDimensionConfig).where(
            FirmDimensionConfig.firm_id == firm.id,
            FirmDimensionConfig.dimension_id == fine.id,
        )
    ).scalars().all() == []


def test_blanket_root_with_scoped_child_is_refused(db, firm_a, flag):
    """The mirror. Either direction of mismatch is a mismatch."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _root, tier, fine, fine_unit = _scoped_root_with_tier(
        db, firm, user, flag, scope=None
    )

    with pytest.raises(HTTPException) as exc:
        _configure(
            db, firm, user, fine, fine_unit, scope=entry.id, parent_tier_id=tier.id
        )

    assert exc.value.status_code == 400
    assert "Scope must be uniform" in exc.value.detail
    assert "tax_return_1040" in exc.value.detail
    assert "blanket" in exc.value.detail


def test_matching_scopes_are_accepted(db, firm_a, flag):
    """Positive control for rule 11, both flavours."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)

    # Scoped root, scoped child.
    _root, tier, fine, fine_unit = _scoped_root_with_tier(
        db, firm, user, flag, scope=entry.id
    )
    child = _configure(
        db, firm, user, fine, fine_unit, scope=entry.id, parent_tier_id=tier.id
    )
    assert child.service_catalog_entry_id == entry.id
    assert child.parent_tier_id == tier.id


def test_blanket_root_with_blanket_child_is_accepted(db, firm_a, flag):
    """Both NULL counts as equal. The ordinary pre-scope case must still work."""
    firm, user = firm_a
    _root, tier, fine, fine_unit = _scoped_root_with_tier(
        db, firm, user, flag, scope=None
    )
    child = _configure(
        db, firm, user, fine, fine_unit, scope=None, parent_tier_id=tier.id
    )
    assert child.service_catalog_entry_id is None


def test_option_parented_child_in_the_wrong_scope_is_refused(db, firm_a, flag):
    """The option branch of rule 11.

    An option-parented child names only a system vocabulary option, so its
    parent is taken to be the config of that option's dimension IN THE CHILD'S
    OWN SCOPE. Here the categorical dimension is configured blanket only, so a
    scoped child under one of its options has no parent in its scope.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    choice, options = _categorical_dimension(db, flag, "choice_dim", rank=2)
    leaf, leaf_unit = _numeric_dimension(db, flag, "leaf_dim", rank=5)

    _configure(db, firm, user, choice, None, scope=None)

    with pytest.raises(HTTPException) as exc:
        _configure(
            db, firm, user, leaf, leaf_unit,
            scope=entry.id, parent_option_id=options[0].id,
        )

    assert exc.value.status_code == 400
    assert "Scope must be uniform" in exc.value.detail
    assert "same scope as the config of that option's dimension" in exc.value.detail


def test_option_parented_child_in_the_matching_scope_is_accepted(db, firm_a, flag):
    """Positive control for the option branch."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    choice, options = _categorical_dimension(db, flag, "choice_dim", rank=2)
    leaf, leaf_unit = _numeric_dimension(db, flag, "leaf_dim", rank=5)

    _configure(db, firm, user, choice, None, scope=entry.id)
    child = _configure(
        db, firm, user, leaf, leaf_unit,
        scope=entry.id, parent_option_id=options[0].id,
    )
    assert child.service_catalog_entry_id == entry.id


# ---------------------------------------------------------------------------
# 4. Rule 8, re-stated to evaluate within a scope.
# ---------------------------------------------------------------------------

def test_same_scope_categorical_ambiguity_is_still_refused(db, firm_a, flag):
    """Rule 8 unchanged inside one scope. Scoping it must not have weakened it.

    This is the counterweight to the coexistence test below: a scope filter
    applied too eagerly would let this through.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)

    top, top_unit = _numeric_dimension(db, flag, "top_dim", rank=1)
    choice, options = _categorical_dimension(db, flag, "choice_dim", rank=2)
    leaf, leaf_unit = _numeric_dimension(db, flag, "leaf_dim", rank=5)

    top_config = _configure(db, firm, user, top, top_unit, scope=entry.id)
    top_tiers = svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=top_config.id,
        tiers=[_tier(0, 10, None, 0)],
    )

    # Configure the categorical flat in this scope, then hang a child under one
    # of its options. Legal so far.
    _configure(db, firm, user, choice, None, scope=entry.id)
    _configure(
        db, firm, user, leaf, leaf_unit,
        scope=entry.id, parent_option_id=options[0].id,
    )

    # A second branch for the same dimension IN THE SAME SCOPE is the ambiguity.
    with pytest.raises(HTTPException) as exc:
        _configure(
            db, firm, user, choice, None,
            scope=entry.id, parent_tier_id=top_tiers[0].id,
        )

    assert exc.value.status_code == 400
    assert "second branch" in exc.value.detail
    assert "choice_dim" in exc.value.detail


def test_blanket_and_scoped_configs_are_not_ambiguous_with_each_other(db, firm_a, flag):
    """Cross-scope coexistence is the DESIGNED PRECEDENCE, not an ambiguity.

    A blanket categorical config with option-parented children, plus a scoped
    config of the same dimension, is exactly the arrangement the override
    feature is made of. Before rule 8 was scoped it counted configs across all
    scopes and refused this, which would have refused the feature itself.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)

    choice, options = _categorical_dimension(db, flag, "choice_dim", rank=2)
    leaf, leaf_unit = _numeric_dimension(db, flag, "leaf_dim", rank=5)

    # Blanket tree, with an option-parented child.
    _configure(db, firm, user, choice, None, scope=None)
    _configure(
        db, firm, user, leaf, leaf_unit, scope=None, parent_option_id=options[0].id
    )

    # The scoped config of the same dimension must be allowed.
    scoped = _configure(db, firm, user, choice, None, scope=entry.id)
    assert scoped.service_catalog_entry_id == entry.id

    db.expire_all()
    rows = db.execute(
        select(FirmDimensionConfig).where(
            FirmDimensionConfig.firm_id == firm.id,
            FirmDimensionConfig.dimension_id == choice.id,
        )
    ).scalars().all()
    assert len(rows) == 2


def test_option_child_allowed_when_the_other_branch_is_in_another_scope(db, firm_a, flag):
    """Rule 8 DIRECTION TWO, evaluated within a scope.

    Direction two refuses hanging a child under an option whose dimension is
    configured on more than one branch, because the child could not name which
    branch it means. Counted across scopes, a dimension configured once blanket
    and once scoped reads as two branches and this legitimate child would be
    refused, which is the override feature refusing itself.

    ADDED AFTER A NEGATIVE CONTROL FOUND THE GAP. The first control for the
    scope filter on _config_count_for_dimension removed it and every test still
    passed, because direction one's refusal needs BOTH a config count and an
    option-parented child in the same scope, and rule 11 guarantees that
    whenever the child exists in a scope the count in that scope is already at
    least one. So direction one can never observe that filter, and nothing else
    was watching it. This test is the assertion that does.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)

    choice, options = _categorical_dimension(db, flag, "choice_dim", rank=2)
    leaf, leaf_unit = _numeric_dimension(db, flag, "leaf_dim", rank=5)

    # One branch per scope: blanket flat, and scoped flat. Two rows for the
    # dimension in total, but exactly one in each scope.
    _configure(db, firm, user, choice, None, scope=None)
    _configure(db, firm, user, choice, None, scope=entry.id)

    # A child under an option, in the scoped tree. Its branch is unambiguous:
    # there is exactly one config of choice_dim in this scope.
    child = _configure(
        db, firm, user, leaf, leaf_unit,
        scope=entry.id, parent_option_id=options[0].id,
    )
    assert child.service_catalog_entry_id == entry.id
    assert child.parent_option_id == options[0].id


# ---------------------------------------------------------------------------
# 5. Rule 9 inside a scoped tree. No new code was written for this; the test
# exists to prove that scoping did not weaken it.
# ---------------------------------------------------------------------------

def test_other_option_cannot_be_priced_inside_a_scoped_tree(db, firm_a, flag):
    """Rule 9 keys on option.key alone, so it must fire identically in a scoped
    tree. If scoping had routed around it, an Other answer would become
    priceable for one engagement type and a lead nobody could classify would be
    handed a computed number."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _dimension, options = _categorical_dimension(
        db, flag, "activity_type", rank=10, option_keys=("staking", "other")
    )
    _tabled, other = options

    with pytest.raises(HTTPException) as exc:
        _price(db, firm, user, other.id, "250.00", scope=entry.id)

    assert exc.value.status_code == 422
    assert "cannot carry a price" in exc.value.detail
    assert "routes to quote" in exc.value.detail

    db.expire_all()
    assert db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.option_id == other.id)
    ).scalars().all() == []


def test_other_option_cannot_be_priced_at_zero_inside_a_scoped_tree(db, firm_a, flag):
    """The null-versus-zero half, inside a scope. 0.00 is a real price."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _dimension, options = _categorical_dimension(
        db, flag, "activity_type", rank=10, option_keys=("staking", "other")
    )
    _tabled, other = options

    with pytest.raises(HTTPException) as exc:
        _price(db, firm, user, other.id, "0.00", scope=entry.id)

    assert exc.value.status_code == 422
    db.expire_all()
    assert db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.option_id == other.id)
    ).scalars().all() == []


def test_ordinary_option_is_still_priceable_inside_a_scoped_tree(db, firm_a, flag):
    """Counterweight. Rule 9 must refuse Other and nothing else, in any scope."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _dimension, options = _categorical_dimension(
        db, flag, "activity_type", rank=10, option_keys=("staking", "other")
    )
    tabled, _other = options

    result = _price(db, firm, user, tabled.id, "125.00", scope=entry.id)
    assert result.price == Decimal("125.00")
    assert result.service_catalog_entry_id == entry.id


# ---------------------------------------------------------------------------
# 6. The resolver: wholesale-replacement precedence.
# ---------------------------------------------------------------------------

def test_resolver_returns_the_override_tree_wholesale(db, firm_a, flag):
    """Override present: the scoped tree, and ONLY the scoped tree.

    The blanket config is priced differently on purpose so any leak is visible
    as a value rather than only as a row count.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    blanket = _configure(db, firm, user, dimension, unit)
    svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=blanket.id,
        tiers=[_tier(0, 10, "100.00", 0)],
    )
    scoped = _configure(db, firm, user, dimension, unit, scope=entry.id)
    svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=scoped.id,
        tiers=[_tier(0, 10, "250.00", 0)],
    )

    resolved = svc.resolve_pricing_config(
        db, firm_id=firm.id, engagement_type=EngagementType.tax_return_1040.value
    )

    assert [c.id for c in resolved.firm_dimension_configs] == [scoped.id]
    assert resolved.overridden_dimension_ids == [dimension.id]

    # Zero blanket leakage, asserted on the value, not just the id.
    assert [t.price for t in resolved.firm_tiers] == [Decimal("250.00")]
    assert Decimal("100.00") not in [t.price for t in resolved.firm_tiers]
    assert blanket.id not in {c.id for c in resolved.firm_dimension_configs}


def test_resolver_returns_the_blanket_tree_when_no_override_exists(db, firm_a, flag):
    """Override absent for THIS engagement type: blanket, even though an
    override exists for a different one."""
    firm, user = firm_a
    entry_1040 = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    _entry(db, firm, user, EngagementType.tax_return_1120.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    blanket = _configure(db, firm, user, dimension, unit)
    svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=blanket.id,
        tiers=[_tier(0, 10, "100.00", 0)],
    )
    scoped = _configure(db, firm, user, dimension, unit, scope=entry_1040.id)
    svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=scoped.id,
        tiers=[_tier(0, 10, "250.00", 0)],
    )

    resolved = svc.resolve_pricing_config(
        db, firm_id=firm.id, engagement_type=EngagementType.tax_return_1120.value
    )

    assert [c.id for c in resolved.firm_dimension_configs] == [blanket.id]
    assert resolved.overridden_dimension_ids == []
    assert [t.price for t in resolved.firm_tiers] == [Decimal("100.00")]


def test_resolver_without_context_returns_the_blanket_tree(db, firm_a, flag):
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    blanket = _configure(db, firm, user, dimension, unit)
    svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=blanket.id,
        tiers=[_tier(0, 10, "100.00", 0)],
    )
    _configure(db, firm, user, dimension, unit, scope=entry.id)

    resolved = svc.resolve_pricing_config(db, firm_id=firm.id)

    assert resolved.service_catalog_entry_id is None
    assert resolved.engagement_type is None
    assert [c.id for c in resolved.firm_dimension_configs] == [blanket.id]
    assert resolved.overridden_dimension_ids == []


def test_resolver_context_for_an_unoffered_type_returns_blanket(db, firm_a, flag):
    """A context naming an engagement type the firm has no catalog row for.

    Absence of a row means not offered, so there is nothing a scoped tree could
    be attached to and the blanket tree governs. This must not raise.
    """
    firm, user = firm_a
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    blanket = _configure(db, firm, user, dimension, unit)

    resolved = svc.resolve_pricing_config(
        db, firm_id=firm.id, engagement_type=EngagementType.bookkeeping_monthly.value
    )
    assert resolved.service_catalog_entry_id is None
    assert [c.id for c in resolved.firm_dimension_configs] == [blanket.id]


def test_resolver_descendants_follow_the_winning_tree(db, firm_a, flag):
    """A tree is won or lost whole, including its children."""
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    coarse, coarse_unit = _numeric_dimension(db, flag, "coarse_dim", rank=1)
    fine, fine_unit = _numeric_dimension(db, flag, "fine_dim", rank=5)

    blanket_root = _configure(db, firm, user, coarse, coarse_unit)
    blanket_tiers = svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=blanket_root.id,
        tiers=[_tier(0, 10, None, 0)],
    )
    blanket_child = _configure(
        db, firm, user, fine, fine_unit, parent_tier_id=blanket_tiers[0].id
    )

    scoped_root = _configure(db, firm, user, coarse, coarse_unit, scope=entry.id)
    scoped_tiers = svc.save_tiers(
        db, firm_id=firm.id, actor_id=user.id, config_id=scoped_root.id,
        tiers=[_tier(0, 10, None, 0)],
    )
    scoped_child = _configure(
        db, firm, user, fine, fine_unit,
        scope=entry.id, parent_tier_id=scoped_tiers[0].id,
    )

    resolved = svc.resolve_pricing_config(
        db, firm_id=firm.id, engagement_type=EngagementType.tax_return_1040.value
    )

    ids = {c.id for c in resolved.firm_dimension_configs}
    assert ids == {scoped_root.id, scoped_child.id}
    assert blanket_root.id not in ids
    assert blanket_child.id not in ids, (
        "the blanket tree's child leaked into a scoped resolution"
    )


def test_resolver_distinguishes_three_option_states_in_a_scoped_context(
    db, firm_a, flag
):
    """THE NO-FALLBACK RULING, ruled by Andrew August 17, 2026.

    Inside a winning scoped tree, an option has exactly three states and two of
    them resolve identically:

        scoped price set      -> that price is used
        scoped price cleared  -> row present, price NULL -> quote
        no scoped row at all  -> nothing returned        -> quote

    Neither of the last two borrows the blanket price. All three blanket prices
    are set to the same conspicuous value so ANY fallback shows up as that
    number appearing where it must not.

    The mitigation for the obvious ergonomic problem (a firm overriding one
    answer and silently unpricing the rest) is that the settings UI prefills a
    new override from the blanket values at creation. That is the UI's job. Do
    not add a fallback to the resolver to solve it.
    """
    firm, user = firm_a
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    dimension, options = _categorical_dimension(
        db, flag, "activity_type", rank=1,
        option_keys=("priced", "cleared", "absent"),
    )
    priced, cleared, absent = options

    # Blanket tree prices all three identically, so leakage is unmistakable.
    _configure(db, firm, user, dimension, None)
    for option in options:
        _price(db, firm, user, option.id, "999.00")

    # Scoped tree: one priced, one explicitly cleared, one never touched.
    _configure(db, firm, user, dimension, None, scope=entry.id)
    _price(db, firm, user, priced.id, "500.00", scope=entry.id)
    _price(db, firm, user, cleared.id, None, scope=entry.id)

    resolved = svc.resolve_pricing_config(
        db, firm_id=firm.id, engagement_type=EngagementType.tax_return_1040.value
    )
    by_option = {p.option_id: p for p in resolved.firm_option_prices}

    # Zero blanket leakage, two ways.
    assert all(
        p.service_catalog_entry_id == entry.id for p in resolved.firm_option_prices
    ), "a blanket-scoped price row leaked into a scoped resolution"
    assert Decimal("999.00") not in [
        p.price for p in resolved.firm_option_prices
    ], "the blanket price value leaked into a scoped resolution"

    # State one: the scoped price is used.
    assert by_option[priced.id].price == Decimal("500.00")

    # State two: cleared scoped price. Row present, unpriced, routes to quote.
    assert cleared.id in by_option
    assert by_option[cleared.id].price is None

    # State three: no scoped row at all. Nothing returned, routes to quote.
    assert absent.id not in by_option


def test_resolver_is_tenant_scoped(db, firm_a, firm_b, flag):
    """Firm B's identically-named engagement type must not resolve into Firm A's
    response, and vice versa."""
    a_firm, a_user = firm_a
    b_firm, b_user = firm_b

    _entry(db, a_firm, a_user, EngagementType.tax_return_1040.value)
    b_entry = _entry(db, b_firm, b_user, EngagementType.tax_return_1040.value)

    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    b_scoped = _configure(db, b_firm, b_user, dimension, unit, scope=b_entry.id)
    svc.save_tiers(
        db, firm_id=b_firm.id, actor_id=b_user.id, config_id=b_scoped.id,
        tiers=[_tier(0, 10, "777.00", 0)],
    )

    resolved = svc.resolve_pricing_config(
        db, firm_id=a_firm.id, engagement_type=EngagementType.tax_return_1040.value
    )

    assert resolved.firm_id == a_firm.id
    assert resolved.firm_dimension_configs == []
    assert resolved.firm_tiers == []
    assert b_scoped.id not in {c.id for c in resolved.firm_dimension_configs}
