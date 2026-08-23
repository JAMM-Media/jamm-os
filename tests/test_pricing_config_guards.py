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

STATUS CODES: every law refusal asserted in this file is 422, per the August
2026 ruling recorded above the guard section of pricing_config_service.py.
These assertions pinned 400 until that ruling; the behavior changed on purpose
and the expectations were updated with it. 404 still means absent or another
firm's row, and is asserted as 404 where it appears.
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
    assert "guard_threshold" in exc.value.detail


def test_numeric_dimension_requires_unit(db, firm_a, flag):
    firm, user = firm_a
    dimension, _unit = _numeric_dimension(db, flag, "tx_volume", rank=1)

    with pytest.raises(HTTPException) as exc:
        _configure(db, firm, user, dimension, None)

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
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

    assert exc.value.status_code == 422
    assert "cannot carry option prices" in exc.value.detail


# ---------------------------------------------------------------------------
# Tier edits must not destroy the subtree hanging off them
# ---------------------------------------------------------------------------

def _parent_with_child_chain(db, firm, user, flag):
    """A parent numeric config with two tiers, a child config hanging under the
    first tier, and priced tiers under the child.

    The parent's tier 0 is left unpriced deliberately: it has a child, so the
    leaf-only law forbids it carrying a price at all.
    """
    top, top_unit = _numeric_dimension(db, flag, "top_dim", rank=1)
    leaf, leaf_unit = _numeric_dimension(db, flag, "leaf_dim", rank=3)

    top_config = _configure(db, firm, user, top, top_unit)
    top_tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=top_config.id,
        tiers=[_tier(0, 10, None, 0), _tier(10, 20, "150.00", 1)],
    )

    child_config = _configure(
        db, firm, user, leaf, leaf_unit, parent_tier_id=top_tiers[0].id
    )
    child_tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=child_config.id,
        tiers=[_tier(0, 5, "60.00", 0)],
    )
    return top_config, top_tiers, child_config, child_tiers


def test_tier_edit_preserves_child_configs(db, firm_a, flag):
    """Editing a parent's tiers must not disturb what hangs under them.

    This is the test that pins the in-place update in save_tiers. The obvious
    simplification, delete every existing tier and insert the incoming set,
    passes every other test in this file while corrupting the subtree.

    Note what that corruption actually is, because it is not what you would
    guess from reading the schema. parent_tier_id is ON DELETE CASCADE, but
    save_tiers goes through the ORM, and SQLAlchemy nulls the foreign key
    itself before the database ever applies its own rule. So the child is not
    deleted, it SURVIVES as an orphan with parent_tier_id NULL: silently
    demoted from a dependent price to a flat additive one. That is why the
    assertion below checks parent_tier_id specifically and not merely that the
    row still exists. A test asserting only survival passes against the bug.
    """
    from app.models.firm_dimension_config import FirmDimensionConfig

    firm, user = firm_a
    top_config, top_tiers, child_config, child_tiers = _parent_with_child_chain(
        db, firm, user, flag
    )
    parented_tier_id = top_tiers[0].id

    # Edit the parent: same sort_orders, different boundaries, and a changed
    # price on the tier that has no child.
    svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=top_config.id,
        tiers=[_tier(0, 12, None, 0), _tier(12, 25, "175.00", 1)],
    )

    db.expire_all()

    # The child config survived, still attached to the same tier.
    surviving = db.get(FirmDimensionConfig, child_config.id)
    assert surviving is not None, (
        "the child config was destroyed by an edit to its parent's tiers"
    )
    assert surviving.parent_tier_id == parented_tier_id

    # The tier it hangs under is the same row, not a recreated one.
    reused = db.get(FirmTier, parented_tier_id)
    assert reused is not None, "the parented tier row was replaced, not updated"
    assert reused.range_max == Decimal("12.00"), "the edit did not apply"

    # The child's own tiers and prices are untouched.
    child_after = db.execute(
        select(FirmTier)
        .where(FirmTier.config_id == child_config.id)
        .order_by(FirmTier.sort_order)
    ).scalars().all()
    assert len(child_after) == 1
    assert child_after[0].id == child_tiers[0].id
    assert child_after[0].price == Decimal("60.00")


def test_removing_parented_tier_is_refused(db, firm_a, flag):
    """A tier with configs hanging under it cannot be dropped by a tier edit.

    Allowing it would delete the subtree through CASCADE, which is a
    destructive operation and therefore belongs to change_dimension_direction
    and its explicit confirm flag.
    """
    from app.models.firm_dimension_config import FirmDimensionConfig

    firm, user = firm_a
    top_config, top_tiers, child_config, child_tiers = _parent_with_child_chain(
        db, firm, user, flag
    )
    parented_tier_id = top_tiers[0].id

    # Omit sort_order 0, the tier the child hangs under.
    with pytest.raises(HTTPException) as exc:
        svc.save_tiers(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=top_config.id,
            tiers=[_tier(0, 20, "150.00", 1)],
        )

    assert exc.value.status_code == 422
    assert "change_dimension_direction" in exc.value.detail

    db.expire_all()

    # Nothing was destroyed by the refused edit.
    assert db.get(FirmTier, parented_tier_id) is not None
    assert db.get(FirmDimensionConfig, child_config.id) is not None
    assert db.get(FirmTier, child_tiers[0].id) is not None
    assert db.get(FirmTier, child_tiers[0].id).price == Decimal("60.00")


# ---------------------------------------------------------------------------
# Rule 8: categorical branch ambiguity, both directions
# ---------------------------------------------------------------------------

def _categorical_ambiguity_fixture(db, firm, user, flag):
    """A categorical dimension plus a numeric dimension to hang it under, plus
    a finer numeric dimension to act as an option-parented child."""
    top, top_unit = _numeric_dimension(db, flag, "top_dim", rank=1)
    choice, options = _categorical_dimension(db, flag, "choice_dim", rank=2)
    leaf, leaf_unit = _numeric_dimension(db, flag, "leaf_dim", rank=3)

    top_config = _configure(db, firm, user, top, top_unit)
    top_tiers = svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=top_config.id,
        tiers=[_tier(0, 10, None, 0), _tier(10, 20, None, 1)],
    )
    return choice, options, leaf, leaf_unit, top_tiers


def test_second_categorical_config_with_option_children_refused(db, firm_a, flag):
    """Direction one of rule 8.

    A categorical dimension that already has children hanging under its options
    cannot be configured on a second branch, because those existing children
    would immediately become unable to say which branch they belong to.
    """
    firm, user = firm_a
    choice, options, leaf, leaf_unit, top_tiers = _categorical_ambiguity_fixture(
        db, firm, user, flag
    )

    # Configure the categorical dimension flat, then hang a child under one of
    # its options. This much is legal.
    _configure(db, firm, user, choice, None)
    _configure(db, firm, user, leaf, leaf_unit, parent_option_id=options[0].id)

    # Now try to put the same categorical dimension on a second branch.
    with pytest.raises(HTTPException) as exc:
        _configure(db, firm, user, choice, None, parent_tier_id=top_tiers[0].id)

    assert exc.value.status_code == 422
    assert "second branch" in exc.value.detail
    assert "choice_dim" in exc.value.detail


def test_option_child_refused_when_dimension_on_multiple_branches(db, firm_a, flag):
    """Direction two of rule 8, the mirror.

    Configuring a categorical dimension twice is legal while nothing hangs
    under its options. What is refused is the child that would be born
    ambiguous underneath that arrangement.
    """
    firm, user = firm_a
    choice, options, leaf, leaf_unit, top_tiers = _categorical_ambiguity_fixture(
        db, firm, user, flag
    )

    # Two branches for the same categorical dimension, legal because no option
    # has children yet. This also proves direction one is not over-firing.
    _configure(db, firm, user, choice, None)
    _configure(db, firm, user, choice, None, parent_tier_id=top_tiers[0].id)

    # Now the child would have no way to name its branch.
    with pytest.raises(HTTPException) as exc:
        _configure(db, firm, user, leaf, leaf_unit, parent_option_id=options[0].id)

    assert exc.value.status_code == 422
    assert "more than one branch" in exc.value.detail
    assert "choice_dim" in exc.value.detail
    assert "leaf_dim" in exc.value.detail


# ---------------------------------------------------------------------------
# Rule 9: the Other option is never priceable
#
# Every categorical dimension in the system catalog carries an Other option
# (scripts/seed_complexity_catalog.py, Open Ruling A). Pricing it would hand a
# lead the catalog could not classify a computed number instead of routing them
# to quote. These four tests cover the rule's whole surface: it fires on a real
# price, it fires on an explicit zero, it does not fire on a clear, and it does
# not fire on ordinary options.
# ---------------------------------------------------------------------------

def _dimension_with_other(db, flag):
    """A categorical dimension carrying one tabled option plus the universal
    Other, which is the shape the seed script produces for all 40 categoricals.
    """
    dimension, options = _categorical_dimension(
        db, flag, "activity_type", rank=10, option_keys=("staking", "other")
    )
    tabled, other = options
    return dimension, tabled, other


def _option_price_rows(db, firm_id, option_id):
    """Read firm_option_prices straight from the database.

    Deliberately not through any service read. A read path's own filtering can
    hide the row an assertion like this exists to catch, so the check that
    nothing was written has to look at the table itself (How We Work, section
    3).
    """
    return db.execute(
        select(FirmOptionPrice).where(
            FirmOptionPrice.firm_id == firm_id,
            FirmOptionPrice.option_id == option_id,
        )
    ).scalars().all()


def test_other_option_cannot_be_priced(db, firm_a, flag):
    """Pricing the catch-all Other answer is refused, and nothing is written.

    The no-row half is not decoration. Rejection guards have to run before side
    effects, so a refusal that still left a firm_option_prices row behind would
    be the mispricing hole this rule exists to close, merely with an error
    message on top of it.
    """
    firm, user = firm_a
    _dimension, _tabled, other = _dimension_with_other(db, flag)

    with pytest.raises(HTTPException) as exc:
        svc.set_option_price(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            data=FirmOptionPriceCreate(option_id=other.id, price=Decimal("250.00")),
        )

    assert exc.value.status_code == 422
    assert "cannot carry a price" in exc.value.detail
    assert "routes to quote" in exc.value.detail

    assert _option_price_rows(db, firm.id, other.id) == []


def test_other_option_cannot_be_priced_at_zero(db, firm_a, flag):
    """The null-versus-zero law applied to rule 9.

    0.00 is a real price meaning "priced at zero", not an absent one, so an
    Other priced at 0.00 still resolves to a computed total for a lead nobody
    classified. This is the assertion that a truthiness check (`if price:`)
    would silently fail while the test above kept passing, which is why it is a
    separate test rather than a second assert.
    """
    firm, user = firm_a
    _dimension, _tabled, other = _dimension_with_other(db, flag)

    with pytest.raises(HTTPException) as exc:
        svc.set_option_price(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            data=FirmOptionPriceCreate(option_id=other.id, price=Decimal("0.00")),
        )

    assert exc.value.status_code == 422
    assert _option_price_rows(db, firm.id, other.id) == []


def test_other_option_price_can_still_be_cleared(db, firm_a, flag):
    """Rule 9 refuses attaching a price, not clearing one.

    price=None means unpriced, which is the state Other is supposed to be in.
    Refusing this too would strand any Other price seeded before the rule
    existed, with no supported way to remove it.
    """
    firm, user = firm_a
    _dimension, _tabled, other = _dimension_with_other(db, flag)

    result = svc.set_option_price(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=FirmOptionPriceCreate(option_id=other.id, price=None),
    )

    assert result.price is None


def test_ordinary_option_is_still_priceable(db, firm_a, flag):
    """Counterweight. Rule 9 must refuse the Other option and nothing else.

    Without this, a rule that rejected every option price would pass all three
    tests above while breaking the entire pricing feature. It also pins that
    only the exact key "other" is caught, so a tabled answer that merely reads
    as a catch-all stays priceable.
    """
    firm, user = firm_a
    _dimension, tabled, _other = _dimension_with_other(db, flag)

    result = svc.set_option_price(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=FirmOptionPriceCreate(option_id=tabled.id, price=Decimal("125.00")),
    )

    assert result.price == Decimal("125.00")
    assert len(_option_price_rows(db, firm.id, tabled.id)) == 1
