# tests/test_pricing_config_guards.py

"""Guard tests for pricing_config_service.

Every test here has been watched to fail. Each one was run against a
deliberately broken copy of the rule it guards, confirmed red, then the break
was reverted, the test re-run green, and the working tree diffed against git.
The per-test negative control is recorded in the session report; without it a
passing test proves only that it runs, not that it catches anything.

These are service-level tests. There is no router for pricing config in this
build, so they call pricing_config_service directly with an explicit firm_id,
which is also the shape the tenant isolation tests need.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

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
from app.models.firm_option_price import FirmOptionPrice
from app.models.firm_tier import FirmTier
from app.models.user import User
from app.schemas.complexity_catalog import ComplexityFlagEngagementTypeBase
from app.schemas.firm_dimension_config import FirmDimensionConfigCreate
from app.schemas.firm_option_price import FirmOptionPriceCreate
from app.schemas.firm_tier import FirmTierBase, FirmTierOut
from app.schemas.service_catalog_entry import ServiceCatalogEntryCreate
from app.services import pricing_config_service as svc
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Fixtures. The system catalog is truncated between tests by conftest's
# clean_db, so every test seeds the catalog content it needs.
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _make_firm(db, name: str, slug: str):
    """A firm plus an owner. The owner is real because audit_logs.actor_id is a
    foreign key to users.id, and write_audit_log swallows its own failures --
    a fake actor id would make the audit assertions silently vacuous."""
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


def _numeric_dimension(db, flag, key: str, rank: int, linkable: bool = True):
    dimension = ComplexityDimension(
        flag_id=flag.id,
        key=key,
        kind=DimensionKind.numeric_range,
        hierarchy_rank=rank,
        linkable=linkable,
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


def _configure(db, firm, user, dimension, unit=None, **kwargs):
    return svc.configure_dimension(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=FirmDimensionConfigCreate(
            dimension_id=dimension.id,
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


# ---------------------------------------------------------------------------
# 1. Tier contiguity
# ---------------------------------------------------------------------------

def test_tier_contiguity_rejects_gap(db, firm_a, flag):
    firm, user = firm_a
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    config = _configure(db, firm, user, dimension, unit)

    with pytest.raises(HTTPException) as exc:
        svc.save_tiers(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=config.id,
            tiers=[_tier(0, 10, "100", 0), _tier(15, 20, "200", 1)],
        )

    assert exc.value.status_code == 400
    assert "gap" in exc.value.detail
    # The error names the offending boundary, not just the fact of a problem.
    assert "sort_order 0" in exc.value.detail
    assert "sort_order 1" in exc.value.detail

    # Nothing was written.
    remaining = db.execute(
        select(FirmTier).where(FirmTier.config_id == config.id)
    ).scalars().all()
    assert remaining == []


def test_tier_contiguity_rejects_overlap(db, firm_a, flag):
    firm, user = firm_a
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    config = _configure(db, firm, user, dimension, unit)

    with pytest.raises(HTTPException) as exc:
        svc.save_tiers(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=config.id,
            tiers=[_tier(0, 15, "100", 0), _tier(10, 20, "200", 1)],
        )

    assert exc.value.status_code == 400
    assert "overlap" in exc.value.detail

    remaining = db.execute(
        select(FirmTier).where(FirmTier.config_id == config.id)
    ).scalars().all()
    assert remaining == []


def test_tier_contiguity_accepts_a_clean_ladder(db, firm_a, flag):
    """The positive control. Without this, the two rejection tests above would
    still pass if save_tiers rejected absolutely everything."""
    firm, user = firm_a
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    config = _configure(db, firm, user, dimension, unit)

    saved = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=config.id,
        tiers=[_tier(0, 10, "100", 0), _tier(10, 20, "200", 1), _tier(20, None, None, 2)],
    )
    assert len(saved) == 3


# ---------------------------------------------------------------------------
# 2. Downhill-only linking
# ---------------------------------------------------------------------------

def test_uphill_link_rejected(db, firm_a, flag):
    """A child that is COARSER than its prospective parent must be refused.

    coarse has hierarchy_rank 1, fine has 5. Hanging coarse under a tier of
    fine is uphill and is the thing this rejects.
    """
    firm, user = firm_a
    fine, fine_unit = _numeric_dimension(db, flag, "fine_dim", rank=5)
    coarse, coarse_unit = _numeric_dimension(db, flag, "coarse_dim", rank=1)

    fine_config = _configure(db, firm, user, fine, fine_unit)
    tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=fine_config.id,
        tiers=[_tier(0, 10, None, 0)],
    )

    with pytest.raises(HTTPException) as exc:
        _configure(
            db, firm, user, coarse, coarse_unit, parent_tier_id=tiers[0].id
        )

    assert exc.value.status_code == 400
    assert "Downhill-only linking" in exc.value.detail


def test_same_rank_link_rejected(db, firm_a, flag):
    """Same rank is not downhill either. This is the case a `<` instead of a
    `<=` in the comparison would let through, and it is the reason the
    negative control for rule 2 breaks the comparison rather than deleting it."""
    firm, user = firm_a
    first, first_unit = _numeric_dimension(db, flag, "first_dim", rank=3)
    second, second_unit = _numeric_dimension(db, flag, "second_dim", rank=3)

    first_config = _configure(db, firm, user, first, first_unit)
    tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=first_config.id,
        tiers=[_tier(0, 10, None, 0)],
    )

    with pytest.raises(HTTPException) as exc:
        _configure(db, firm, user, second, second_unit, parent_tier_id=tiers[0].id)

    assert exc.value.status_code == 400
    assert "same rank" in exc.value.detail


def test_downhill_link_accepted(db, firm_a, flag):
    """Positive control for rule 2."""
    firm, user = firm_a
    coarse, coarse_unit = _numeric_dimension(db, flag, "coarse_dim", rank=1)
    fine, fine_unit = _numeric_dimension(db, flag, "fine_dim", rank=5)

    coarse_config = _configure(db, firm, user, coarse, coarse_unit)
    tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=coarse_config.id,
        tiers=[_tier(0, 10, None, 0)],
    )

    child = _configure(db, firm, user, fine, fine_unit, parent_tier_id=tiers[0].id)
    assert child.parent_tier_id == tiers[0].id


# ---------------------------------------------------------------------------
# 3. Leaf-only pricing, both directions
# ---------------------------------------------------------------------------

def test_parent_tier_with_price_cannot_gain_child(db, firm_a, flag):
    firm, user = firm_a
    coarse, coarse_unit = _numeric_dimension(db, flag, "coarse_dim", rank=1)
    fine, fine_unit = _numeric_dimension(db, flag, "fine_dim", rank=5)

    coarse_config = _configure(db, firm, user, coarse, coarse_unit)
    tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=coarse_config.id,
        tiers=[_tier(0, 10, "250.00", 0)],
    )
    assert tiers[0].price == Decimal("250.00")

    with pytest.raises(HTTPException) as exc:
        _configure(db, firm, user, fine, fine_unit, parent_tier_id=tiers[0].id)

    assert exc.value.status_code == 400
    assert "Clear the parent price first" in exc.value.detail


def test_tier_with_child_cannot_gain_price(db, firm_a, flag):
    firm, user = firm_a
    coarse, coarse_unit = _numeric_dimension(db, flag, "coarse_dim", rank=1)
    fine, fine_unit = _numeric_dimension(db, flag, "fine_dim", rank=5)

    coarse_config = _configure(db, firm, user, coarse, coarse_unit)
    tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=coarse_config.id,
        tiers=[_tier(0, 10, None, 0)],
    )
    _configure(db, firm, user, fine, fine_unit, parent_tier_id=tiers[0].id)

    with pytest.raises(HTTPException) as exc:
        svc.save_tiers(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=coarse_config.id,
            tiers=[_tier(0, 10, "250.00", 0)],
        )

    assert exc.value.status_code == 400
    assert "double count" in exc.value.detail

    # The rejected save left the tier exactly as it was, still unpriced.
    db.expire_all()
    still = db.execute(
        select(FirmTier).where(FirmTier.config_id == coarse_config.id)
    ).scalar_one()
    assert still.price is None


# ---------------------------------------------------------------------------
# 4. Blank is not zero
# ---------------------------------------------------------------------------

def test_blank_price_is_not_zero(db, firm_a, flag):
    """A tier with no price and a tier priced at zero are different facts and
    must stay distinguishable through the Out schema in both directions."""
    firm, user = firm_a
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    config = _configure(db, firm, user, dimension, unit)

    saved = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=config.id,
        tiers=[_tier(0, 10, None, 0), _tier(10, 20, "0.00", 1)],
    )

    blank, zero = saved[0], saved[1]

    assert blank.price is None
    assert zero.price == Decimal("0.00")
    assert zero.price is not None

    # Neither collapsed into the other in the database itself.
    db.expire_all()
    rows = db.execute(
        select(FirmTier)
        .where(FirmTier.config_id == config.id)
        .order_by(FirmTier.sort_order)
    ).scalars().all()
    assert rows[0].price is None
    assert rows[1].price == Decimal("0.00")

    # And they survive a fresh trip through the Out schema.
    round_tripped = [FirmTierOut.model_validate(row) for row in rows]
    assert round_tripped[0].price is None
    assert round_tripped[1].price == Decimal("0.00")

    # The serialized form keeps them apart too, which is what the config
    # endpoint will eventually depend on.
    assert round_tripped[0].model_dump()["price"] is None
    assert round_tripped[1].model_dump()["price"] == Decimal("0.00")


# ---------------------------------------------------------------------------
# 5. Direction change
# ---------------------------------------------------------------------------

def test_direction_change_requires_confirm(db, firm_a, flag):
    firm, user = firm_a
    coarse, coarse_unit = _numeric_dimension(db, flag, "coarse_dim", rank=1)
    config = _configure(db, firm, user, coarse, coarse_unit)

    with pytest.raises(HTTPException) as exc:
        svc.change_dimension_direction(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=config.id,
            new_parent_tier_id=None,
            new_parent_option_id=None,
        )

    assert exc.value.status_code == 400
    assert "confirm=True" in exc.value.detail


def test_direction_change_clears_descendant_prices(db, firm_a, flag):
    """Three levels deep. Moving the middle config must delete its own tiers
    AND the tiers of the config below it, because every price below a moved
    config stops meaning what it meant."""
    firm, user = firm_a
    top, top_unit = _numeric_dimension(db, flag, "top_dim", rank=1)
    middle, middle_unit = _numeric_dimension(db, flag, "middle_dim", rank=2)
    bottom, bottom_unit = _numeric_dimension(db, flag, "bottom_dim", rank=3)

    top_config = _configure(db, firm, user, top, top_unit)
    top_tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=top_config.id,
        tiers=[_tier(0, 10, None, 0), _tier(10, 20, None, 1)],
    )

    middle_config = _configure(
        db, firm, user, middle, middle_unit, parent_tier_id=top_tiers[0].id
    )
    middle_tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=middle_config.id,
        tiers=[_tier(0, 5, None, 0)],
    )

    bottom_config = _configure(
        db, firm, user, bottom, bottom_unit, parent_tier_id=middle_tiers[0].id
    )
    svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=bottom_config.id,
        tiers=[_tier(0, 3, "75.00", 0)],
    )

    # Precondition: the descendant really does have a priced tier to lose.
    db.expire_all()
    before = db.execute(
        select(FirmTier).where(FirmTier.config_id == bottom_config.id)
    ).scalars().all()
    assert len(before) == 1
    assert before[0].price == Decimal("75.00")

    svc.change_dimension_direction(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=middle_config.id,
        new_parent_tier_id=top_tiers[1].id,
        confirm=True,
    )

    db.expire_all()
    middle_after = db.execute(
        select(FirmTier).where(FirmTier.config_id == middle_config.id)
    ).scalars().all()
    bottom_after = db.execute(
        select(FirmTier).where(FirmTier.config_id == bottom_config.id)
    ).scalars().all()

    assert middle_after == [], "the moved config's own tiers should be gone"
    assert bottom_after == [], "the descendant's tiers should be gone too"

    # The move itself landed, so this is not just "everything got deleted".
    from app.models.firm_dimension_config import FirmDimensionConfig

    moved = db.get(FirmDimensionConfig, middle_config.id)
    assert moved.parent_tier_id == top_tiers[1].id


def test_direction_change_clears_descendant_option_prices(db, firm_a, flag):
    """The option-price half of the same law. Descendants are reachable through
    vocabulary options as well as through tiers, and both paths must be walked
    or a categorical branch keeps stale prices after a move."""
    firm, user = firm_a
    top, top_unit = _numeric_dimension(db, flag, "top_dim", rank=1)
    choice, options = _categorical_dimension(db, flag, "choice_dim", rank=2)

    top_config = _configure(db, firm, user, top, top_unit)
    top_tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=top_config.id,
        tiers=[_tier(0, 10, None, 0), _tier(10, 20, None, 1)],
    )

    choice_config = _configure(
        db, firm, user, choice, None, parent_tier_id=top_tiers[0].id
    )
    svc.set_option_price(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=FirmOptionPriceCreate(option_id=options[0].id, price=Decimal("40.00")),
    )

    db.expire_all()
    assert db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.firm_id == firm.id)
    ).scalars().all(), "precondition: an option price exists to be cleared"

    svc.change_dimension_direction(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=choice_config.id,
        new_parent_tier_id=top_tiers[1].id,
        confirm=True,
    )

    db.expire_all()
    after = db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.firm_id == firm.id)
    ).scalars().all()
    assert after == [], "the moved config's option prices should be gone"


# ---------------------------------------------------------------------------
# 6. The activation law
# ---------------------------------------------------------------------------

def test_activation_requires_pricing_mode(db, firm_a):
    firm, user = firm_a

    with pytest.raises(HTTPException) as exc:
        svc.upsert_service_catalog_entry(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            data=ServiceCatalogEntryCreate(
                engagement_type=EngagementType.tax_return_1040.value,
                is_offered=True,
                pricing_mode=None,
            ),
        )

    assert exc.value.status_code == 400
    assert "half-on" in exc.value.detail

    # A service cannot be half-on: the refusal must leave no row behind.
    from app.models.service_catalog_entry import ServiceCatalogEntry

    db.expire_all()
    rows = db.execute(
        select(ServiceCatalogEntry).where(ServiceCatalogEntry.firm_id == firm.id)
    ).scalars().all()
    assert rows == []


def test_activation_with_pricing_mode_is_accepted(db, firm_a):
    """Positive control for rule 6."""
    firm, user = firm_a

    entry = svc.upsert_service_catalog_entry(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=ServiceCatalogEntryCreate(
            engagement_type=EngagementType.tax_return_1040.value,
            is_offered=True,
            pricing_mode=PricingMode.fixed,
        ),
    )
    assert entry.is_offered is True
    assert entry.pricing_mode == PricingMode.fixed


def test_deactivation_without_pricing_mode_is_allowed(db, firm_a):
    """Turning a service OFF does not require a pricing_mode. The law is about
    activation only, and a test that asserted otherwise would encode a rule
    nobody wrote."""
    firm, user = firm_a

    entry = svc.upsert_service_catalog_entry(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=ServiceCatalogEntryCreate(
            engagement_type=EngagementType.tax_return_1040.value,
            is_offered=False,
            pricing_mode=None,
        ),
    )
    assert entry.is_offered is False


# ---------------------------------------------------------------------------
# 7. Tenant isolation, all three firm-scoped pricing tables
# ---------------------------------------------------------------------------

def test_tenant_isolation_firm_a_cannot_touch_firm_b_pricing(db, firm_a, firm_b, flag):
    a_firm, a_user = firm_a
    b_firm, b_user = firm_b

    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    _, options = _categorical_dimension(db, flag, "choice_dim", rank=2)

    # Firm B builds a config, a tier and an option price.
    b_config = _configure(db, b_firm, b_user, dimension, unit)
    b_tiers = svc.save_tiers(
        db,
        firm_id=b_firm.id,
        actor_id=b_user.id,
        config_id=b_config.id,
        tiers=[_tier(0, 10, "500.00", 0)],
    )
    svc.set_option_price(
        db,
        firm_id=b_firm.id,
        actor_id=b_user.id,
        data=FirmOptionPriceCreate(option_id=options[0].id, price=Decimal("99.00")),
    )

    # (a) config: Firm A cannot read or act on Firm B's config.
    with pytest.raises(HTTPException) as exc:
        svc.change_dimension_direction(
            db,
            firm_id=a_firm.id,
            actor_id=a_user.id,
            config_id=b_config.id,
            confirm=True,
        )
    assert exc.value.status_code == 404

    # (b) tier: Firm A cannot overwrite tiers hanging off Firm B's config.
    with pytest.raises(HTTPException) as exc:
        svc.save_tiers(
            db,
            firm_id=a_firm.id,
            actor_id=a_user.id,
            config_id=b_config.id,
            tiers=[_tier(0, 10, "1.00", 0)],
        )
    assert exc.value.status_code == 404

    # Firm B's tier is untouched.
    db.expire_all()
    b_tier_now = db.get(FirmTier, b_tiers[0].id)
    assert b_tier_now.price == Decimal("500.00")
    assert b_tier_now.firm_id == b_firm.id

    # (c) option price: the option itself is system-owned and shared, so Firm A
    # pricing it must create Firm A's own row and leave Firm B's alone.
    svc.set_option_price(
        db,
        firm_id=a_firm.id,
        actor_id=a_user.id,
        data=FirmOptionPriceCreate(option_id=options[0].id, price=Decimal("1.00")),
    )

    db.expire_all()
    b_price = db.execute(
        select(FirmOptionPrice).where(
            FirmOptionPrice.firm_id == b_firm.id,
            FirmOptionPrice.option_id == options[0].id,
        )
    ).scalar_one()
    a_price = db.execute(
        select(FirmOptionPrice).where(
            FirmOptionPrice.firm_id == a_firm.id,
            FirmOptionPrice.option_id == options[0].id,
        )
    ).scalar_one()

    assert b_price.price == Decimal("99.00"), "Firm B's price was overwritten"
    assert a_price.price == Decimal("1.00")
    assert a_price.id != b_price.id


# ---------------------------------------------------------------------------
# 8 and 9. Schema-layer engagement type validation
# ---------------------------------------------------------------------------

def test_engagement_type_validated_on_catalog_entry():
    with pytest.raises(ValidationError) as exc:
        ServiceCatalogEntryCreate(
            engagement_type="not_a_real_engagement_type",
            is_offered=False,
        )
    assert "Invalid engagement_type" in str(exc.value)

    # A real member passes, so the validator is not simply rejecting everything.
    ok = ServiceCatalogEntryCreate(
        engagement_type=EngagementType.bookkeeping_monthly.value, is_offered=False
    )
    assert ok.engagement_type == "bookkeeping_monthly"


def test_flag_engagement_type_must_be_real_enum_member():
    with pytest.raises(ValidationError) as exc:
        ComplexityFlagEngagementTypeBase(engagement_type="tax_return_9999")
    assert "Invalid engagement_type" in str(exc.value)

    ok = ComplexityFlagEngagementTypeBase(
        engagement_type=EngagementType.tax_return_1040.value
    )
    assert ok.engagement_type == "tax_return_1040"


# ---------------------------------------------------------------------------
# Rule 5 coherence, kept small
# ---------------------------------------------------------------------------

def test_guard_role_requires_threshold(db, firm_a, flag):
    firm, user = firm_a
    dimension, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    with pytest.raises(HTTPException) as exc:
        _configure(db, firm, user, dimension, unit, role=DimensionRole.guard)

    assert exc.value.status_code == 400
    assert "guard_threshold" in exc.value.detail


def test_numeric_dimension_requires_unit(db, firm_a, flag):
    firm, user = firm_a
    dimension, _unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    with pytest.raises(HTTPException) as exc:
        _configure(db, firm, user, dimension, None)

    assert exc.value.status_code == 400
    assert "unit_id" in exc.value.detail


def test_categorical_dimension_cannot_have_tiers(db, firm_a, flag):
    firm, user = firm_a
    dimension, _options = _categorical_dimension(db, flag, "choice_dim", rank=1)
    config = _configure(db, firm, user, dimension, None)

    with pytest.raises(HTTPException) as exc:
        svc.save_tiers(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=config.id,
            tiers=[_tier(0, 10, "100", 0)],
        )

    assert exc.value.status_code == 400
    assert "cannot have tiers" in exc.value.detail


def test_numeric_dimension_cannot_have_option_prices(db, firm_a, flag):
    """The mirror of the test above. The option belongs to a numeric dimension,
    which has no vocabulary, so pricing it is incoherent."""
    firm, user = firm_a
    dimension, _unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    stray_option = ComplexityVocabularyOption(
        dimension_id=dimension.id, key="stray", label="Stray"
    )
    db.add(stray_option)
    db.commit()
    db.refresh(stray_option)

    with pytest.raises(HTTPException) as exc:
        svc.set_option_price(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            data=FirmOptionPriceCreate(
                option_id=stray_option.id, price=Decimal("10.00")
            ),
        )

    assert exc.value.status_code == 400
    assert "cannot carry option prices" in exc.value.detail
