# tests/test_pricing_config_delete.py

"""Guard tests for pricing_config_service.delete_config.

A NEW FILE rather than an addition to tests/test_pricing_config_guards.py.
That file covers rules 1 through 9 as save-time validation on the write path;
this one covers the only destructive-removal path in the pricing service, and
its fixtures are shaped around what must SURVIVE a delete rather than around
what must be refused at save time. Keeping them apart means the survivor
seeding below does not have to be explained away in every unrelated guard test.

WHAT IS PINNED HERE:

1. Happy path. A config with tiers, an option price, and a dependent child
   config is fully removed, and rows belonging to a DIFFERENT config of the
   same firm are untouched.
2. confirm=False refuses with 422 and destroys nothing. Row counts are read
   before and after and compared, rather than trusting the refusal.
3. Tenant isolation, in both of the two shapes it can fail:
     a. Firm A cannot delete Firm B's config by naming its id.
     b. Firm A deleting its OWN config does not delete Firm B's prices on the
        SAME shared vocabulary options.
   Shape (b) is the one a missing firm_id filter would actually produce, and it
   is only expressible because both firms price the same system-owned option.
   See the note on _seed_two_firms_sharing_an_option.
4. Scope. Deleting a scoped override leaves blanket rows intact, and deleting a
   blanket config leaves a scoped override intact.

STATUS CODES: the confirm refusal is 422, per the August 2026 ruling recorded
above the guard section of pricing_config_service.py. 404 means the config is
absent or belongs to another firm.

TWO NULLABLE FIELDS, UNRELATED MEANINGS, as in the scope guard file:

    price = None                     -> unpriced, routes to quote
    service_catalog_entry_id = None  -> blanket, says nothing about price

NEGATIVE CONTROL: test_confirm_false_refuses_and_destroys_nothing was run
against a copy of delete_config with the confirm check deleted, confirmed red
for the right reason (rows destroyed without confirm, not merely a wrong status
code), then the break was reverted, the test re-run green, and the working tree
diffed against git. Recorded in the session report.
"""

import uuid
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select

from app.core.enums import (
    DimensionKind,
    DimensionRole,
    EngagementType,
    PricingMode,
    UserRole,
)
from app.core.security import get_password_hash
from app.models.audit_log import AuditLog
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_dimension_unit import ComplexityDimensionUnit
from app.models.complexity_flag import ComplexityFlag
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption
from app.models.firm import Firm
from app.models.firm_dimension_config import FirmDimensionConfig
from app.models.firm_option_price import FirmOptionPrice
from app.models.firm_tier import FirmTier
from app.models.user import User
from app.schemas.firm_dimension_config import FirmDimensionConfigCreate
from app.schemas.firm_option_price import FirmOptionPriceCreate
from app.schemas.firm_tier import FirmTierBase
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
    a fake actor id would make the audit assertion silently vacuous."""
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
        linkable=True,
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


def _set_price(db, firm, user, option, price, scope=None):
    return svc.set_option_price(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        data=FirmOptionPriceCreate(
            option_id=option.id,
            price=None if price is None else Decimal(price),
            service_catalog_entry_id=scope,
        ),
    )


# ---------------------------------------------------------------------------
# Counting helpers. Tests assert against the DATABASE rather than against what
# the service returned, because the failure being guarded against is rows
# surviving or disappearing without the service saying so.
# ---------------------------------------------------------------------------

def _count(db, model, firm_id):
    return db.execute(
        select(func.count(model.id)).where(model.firm_id == firm_id)
    ).scalar_one()


def _row_census(db, firm_id):
    """Every firm-scoped pricing row count, as one comparable object."""
    return {
        "configs": _count(db, FirmDimensionConfig, firm_id),
        "tiers": _count(db, FirmTier, firm_id),
        "option_prices": _count(db, FirmOptionPrice, firm_id),
    }


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------

def _seed_tree_and_a_bystander(db, firm, user, flag):
    """A two-level tree to delete, plus an unrelated config that must survive.

    THE TREE (blanket scope):
        tx_volume (numeric, rank 1), two UNPRICED tiers
          -> wallet_type (categorical, rank 2) hanging under tier sort_order 0
             -> an option price on wallet_type option "a"

    The root tiers are unpriced deliberately: the leaf-only pricing law refuses
    a child under a priced parent, so a priced root could not have the child
    this test needs.

    THE BYSTANDER: notice_type (categorical, rank 5), configured flat, with its
    own option price. It shares the firm and the flag with the tree but is not
    in it, so the happy-path test can prove the delete stopped at the tree
    boundary rather than clearing the firm.
    """
    numeric, unit = _numeric_dimension(db, flag, "tx_volume", rank=1)
    root = _configure(db, firm, user, numeric, unit)
    svc.save_tiers(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=root.id,
        tiers=[_tier("0", "100", None, 0), _tier("100", "500", None, 1)],
    )
    root_tiers = db.execute(
        select(FirmTier).where(FirmTier.config_id == root.id)
    ).scalars().all()
    first_tier = next(t for t in root_tiers if t.sort_order == 0)

    categorical, options = _categorical_dimension(db, flag, "wallet_type", rank=2)
    child = _configure(
        db, firm, user, categorical, parent_tier_id=first_tier.id
    )
    _set_price(db, firm, user, options[0], "250.00")

    bystander_dim, bystander_options = _categorical_dimension(
        db, flag, "notice_type", rank=5, option_keys=("x", "y")
    )
    bystander = _configure(db, firm, user, bystander_dim)
    _set_price(db, firm, user, bystander_options[0], "50.00")

    return {
        "root": root,
        "child": child,
        "options": options,
        "bystander": bystander,
        "bystander_option": bystander_options[0],
    }


def _seed_two_firms_sharing_an_option(db, firm_a, firm_b, flag):
    """Both firms configure THE SAME system dimension and price THE SAME option.

    THE SHARING IS LOAD-BEARING, NOT INCIDENTAL SEED DATA. Vocabulary options
    are system-owned carve-out content with no firm_id, so one option row is
    shared by every firm that prices it. That is precisely the record a missing
    firm_id filter in the option-price delete would travel along: it would
    collect every firm's price on that option and delete them all.

    A fixture that gave each firm its own dimension would make that leak
    unexpressible, and the test would pass against the broken code while
    proving nothing (instance eighteen). Do not "simplify" this by seeding a
    second dimension.
    """
    dimension, options = _categorical_dimension(db, flag, "wallet_type", rank=2)

    firm_a_obj, user_a = firm_a
    firm_b_obj, user_b = firm_b

    config_a = _configure(db, firm_a_obj, user_a, dimension)
    config_b = _configure(db, firm_b_obj, user_b, dimension)

    _set_price(db, firm_a_obj, user_a, options[0], "250.00")
    _set_price(db, firm_b_obj, user_b, options[0], "999.00")

    return {
        "dimension": dimension,
        "option": options[0],
        "config_a": config_a,
        "config_b": config_b,
    }


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

def test_delete_removes_the_tree_and_leaves_other_configs_alone(db, firm_a, flag):
    firm, user = firm_a
    seeded = _seed_tree_and_a_bystander(db, firm, user, flag)

    before = _row_census(db, firm.id)
    assert before == {"configs": 3, "tiers": 2, "option_prices": 2}

    svc.delete_config(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=seeded["root"].id,
        confirm=True,
    )

    # The root, its child, its tiers and its option price are gone.
    assert db.get(FirmDimensionConfig, seeded["root"].id) is None
    assert db.get(FirmDimensionConfig, seeded["child"].id) is None
    assert _count(db, FirmTier, firm.id) == 0

    # The bystander config and ITS option price survive untouched.
    bystander = db.get(FirmDimensionConfig, seeded["bystander"].id)
    assert bystander is not None
    surviving_prices = db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.firm_id == firm.id)
    ).scalars().all()
    assert len(surviving_prices) == 1
    assert surviving_prices[0].option_id == seeded["bystander_option"].id
    assert surviving_prices[0].price == Decimal("50.00")

    assert _row_census(db, firm.id) == {
        "configs": 1,
        "tiers": 0,
        "option_prices": 1,
    }


def test_delete_writes_an_audit_log_entry(db, firm_a, flag):
    """The audit entry is the only durable record that the deletion happened,
    since the rows it describes no longer exist to be inspected."""
    firm, user = firm_a
    seeded = _seed_tree_and_a_bystander(db, firm, user, flag)

    svc.delete_config(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=seeded["root"].id,
        confirm=True,
    )

    entry = db.execute(
        select(AuditLog).where(
            AuditLog.firm_id == firm.id,
            AuditLog.action == "pricing.config_deleted",
        )
    ).scalar_one()
    assert entry.actor_id == user.id
    assert entry.entity_id == seeded["root"].id
    assert entry.extra_metadata["dimension_key"] == "tx_volume"
    assert entry.extra_metadata["deleted_config_count"] == 2
    assert entry.extra_metadata["deleted_tier_count"] == 2
    assert entry.extra_metadata["deleted_option_price_count"] == 1


# ---------------------------------------------------------------------------
# 2. confirm=False refuses and destroys nothing
# ---------------------------------------------------------------------------

def test_confirm_false_refuses_and_destroys_nothing(db, firm_a, flag):
    """THE LOAD-BEARING ASSERTION IS THE ROW CENSUS, NOT THE STATUS CODE.

    A delete_config that destroyed everything and THEN raised 422 would satisfy
    a status-code-only test perfectly. The census is read before the call and
    compared after it, so the test fails if anything was removed on the way to
    the refusal.
    """
    firm, user = firm_a
    seeded = _seed_tree_and_a_bystander(db, firm, user, flag)

    before = _row_census(db, firm.id)

    with pytest.raises(HTTPException) as exc:
        svc.delete_config(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=seeded["root"].id,
        )

    assert exc.value.status_code == 422

    db.expire_all()
    after = _row_census(db, firm.id)
    assert after == before, (
        "delete_config destroyed rows on the refusal path: "
        f"before={before} after={after}"
    )

    # Every individual row is still addressable, not merely the counts equal.
    assert db.get(FirmDimensionConfig, seeded["root"].id) is not None
    assert db.get(FirmDimensionConfig, seeded["child"].id) is not None


def test_confirm_false_message_names_what_would_be_destroyed(db, firm_a, flag):
    """The refusal message is the UI contract: the Phase 5 confirmation dialog
    repeats it verbatim, so it has to state the real blast radius rather than a
    generic warning."""
    firm, user = firm_a
    seeded = _seed_tree_and_a_bystander(db, firm, user, flag)

    with pytest.raises(HTTPException) as exc:
        svc.delete_config(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=seeded["root"].id,
        )

    detail = exc.value.detail
    assert "tx_volume" in detail
    assert "1 dependent" in detail
    assert "2 tier(s)" in detail
    assert "1 option price(s)" in detail
    assert "confirm=true" in detail


def test_default_is_refusal(db, firm_a, flag):
    """confirm defaults to False, so an accidental call deletes nothing. This
    is a separate test from the explicit-False one on purpose: a signature
    change to confirm=True would leave that one green."""
    firm, user = firm_a
    seeded = _seed_tree_and_a_bystander(db, firm, user, flag)
    before = _row_census(db, firm.id)

    with pytest.raises(HTTPException) as exc:
        svc.delete_config(
            db, firm_id=firm.id, actor_id=user.id, config_id=seeded["root"].id
        )

    assert exc.value.status_code == 422
    db.expire_all()
    assert _row_census(db, firm.id) == before


# ---------------------------------------------------------------------------
# 3. Tenant isolation, both shapes
# ---------------------------------------------------------------------------

def test_firm_a_cannot_delete_firm_b_config(db, firm_a, firm_b, flag):
    """Naming another firm's config id answers 404, not 403 and not a deletion.

    404 rather than 403 is deliberate and matches _get_config: the caller must
    not be able to learn whether another firm's config exists.
    """
    firm_a_obj, user_a = firm_a
    firm_b_obj, _ = firm_b
    shared = _seed_two_firms_sharing_an_option(db, firm_a, firm_b, flag)

    before_b = _row_census(db, firm_b_obj.id)

    with pytest.raises(HTTPException) as exc:
        svc.delete_config(
            db,
            firm_id=firm_a_obj.id,
            actor_id=user_a.id,
            config_id=shared["config_b"].id,
            confirm=True,
        )

    assert exc.value.status_code == 404

    db.expire_all()
    assert _row_census(db, firm_b_obj.id) == before_b
    assert db.get(FirmDimensionConfig, shared["config_b"].id) is not None


def test_deleting_own_config_leaves_another_firms_price_on_the_shared_option(
    db, firm_a, firm_b, flag
):
    """The leak a missing firm_id filter would actually produce.

    Both firms price the SAME system-owned vocabulary option, so the option row
    is a record they genuinely share and a leak has somewhere to travel. Firm A
    deletes its own config; Firm B's price on that same option must survive.
    """
    firm_a_obj, user_a = firm_a
    firm_b_obj, _ = firm_b
    shared = _seed_two_firms_sharing_an_option(db, firm_a, firm_b, flag)

    svc.delete_config(
        db,
        firm_id=firm_a_obj.id,
        actor_id=user_a.id,
        config_id=shared["config_a"].id,
        confirm=True,
    )

    db.expire_all()

    # Firm A's own rows are gone.
    assert db.get(FirmDimensionConfig, shared["config_a"].id) is None
    assert _count(db, FirmOptionPrice, firm_a_obj.id) == 0

    # Firm B is untouched: the config, the price, and the price's VALUE.
    assert db.get(FirmDimensionConfig, shared["config_b"].id) is not None
    firm_b_prices = db.execute(
        select(FirmOptionPrice).where(FirmOptionPrice.firm_id == firm_b_obj.id)
    ).scalars().all()
    assert len(firm_b_prices) == 1
    assert firm_b_prices[0].option_id == shared["option"].id
    assert firm_b_prices[0].price == Decimal("999.00")


# ---------------------------------------------------------------------------
# 4. Scope. Deleting one side never touches the other.
# ---------------------------------------------------------------------------

def _seed_blanket_and_scoped(db, firm, user, flag):
    """One categorical dimension configured twice: blanket, and scoped to one
    engagement type, each with its own price on the SAME option.

    Coexistence is the designed precedence (wholesale replacement), and rule 8
    permits it because the two live in different scopes. The two prices sit on
    one shared option row, which is what makes a scope-unfiltered delete able
    to cross from one to the other.
    """
    entry = _entry(db, firm, user, EngagementType.tax_return_1040.value)
    dimension, options = _categorical_dimension(db, flag, "wallet_type", rank=2)

    blanket = _configure(db, firm, user, dimension)
    scoped = _configure(
        db, firm, user, dimension, service_catalog_entry_id=entry.id
    )

    _set_price(db, firm, user, options[0], "250.00")
    _set_price(db, firm, user, options[0], "400.00", scope=entry.id)

    return {
        "entry": entry,
        "option": options[0],
        "blanket": blanket,
        "scoped": scoped,
    }


def _prices_by_scope(db, firm_id, option_id):
    rows = db.execute(
        select(FirmOptionPrice).where(
            FirmOptionPrice.firm_id == firm_id,
            FirmOptionPrice.option_id == option_id,
        )
    ).scalars().all()
    return {row.service_catalog_entry_id: row.price for row in rows}


def test_deleting_scoped_override_leaves_blanket_rows_intact(db, firm_a, flag):
    firm, user = firm_a
    seeded = _seed_blanket_and_scoped(db, firm, user, flag)

    svc.delete_config(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=seeded["scoped"].id,
        confirm=True,
    )

    db.expire_all()
    assert db.get(FirmDimensionConfig, seeded["scoped"].id) is None
    assert db.get(FirmDimensionConfig, seeded["blanket"].id) is not None

    prices = _prices_by_scope(db, firm.id, seeded["option"].id)
    assert prices == {None: Decimal("250.00")}


def test_deleting_blanket_config_leaves_scoped_override_intact(db, firm_a, flag):
    firm, user = firm_a
    seeded = _seed_blanket_and_scoped(db, firm, user, flag)

    svc.delete_config(
        db,
        firm_id=firm.id,
        actor_id=user.id,
        config_id=seeded["blanket"].id,
        confirm=True,
    )

    db.expire_all()
    assert db.get(FirmDimensionConfig, seeded["blanket"].id) is None
    assert db.get(FirmDimensionConfig, seeded["scoped"].id) is not None

    prices = _prices_by_scope(db, firm.id, seeded["option"].id)
    assert prices == {seeded["entry"].id: Decimal("400.00")}


# ---------------------------------------------------------------------------
# 5. Missing config
# ---------------------------------------------------------------------------

def test_deleting_a_config_that_does_not_exist_is_404(db, firm_a):
    firm, user = firm_a
    with pytest.raises(HTTPException) as exc:
        svc.delete_config(
            db,
            firm_id=firm.id,
            actor_id=user.id,
            config_id=uuid.uuid4(),
            confirm=True,
        )
    assert exc.value.status_code == 404
