# tests/test_pricing_write_api.py

"""Tests for the six pricing write endpoints, through the HTTP layer.

The service-layer rules these endpoints call are already pinned by
tests/test_pricing_config_guards.py, tests/test_pricing_scope_guards.py and
tests/test_pricing_config_delete.py. This file does NOT re-test them. It tests
the things that only exist once there is an HTTP surface:

1. Each endpoint is reachable, wired to the right service function, and returns
   the right status and body shape.
2. RBAC survives the trip through FastAPI's dependency graph.
3. Tenant isolation survives it too, including the delete probe: Firm A aiming
   at Firm B's config learns nothing, not even that it exists.
4. Refusal detail reaches the client VERBATIM. This is the UI's contract. The
   settings screen renders response detail as its own copy, so a message that
   is reworded, wrapped or swallowed in transit is a broken contract even
   though the status code is still correct.
5. confirm-gated actions refuse without it AND mutate nothing on the way to
   the refusal.

On the verbatim test specifically: it is aimed at the OPTION branch of
_assert_parent_is_unpriced by ruling. One verbatim test pins the contract for
the shared mechanism; the remaining standardized guard sites ride it and are
recorded as a deferred item rather than each getting their own copy of this
assertion.
"""

import uuid
from decimal import Decimal

import pytest

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
from app.models.complexity_flag_engagement_type import ComplexityFlagEngagementType
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption
from app.models.firm_dimension_config import FirmDimensionConfig
from app.models.firm_option_price import FirmOptionPrice
from app.models.firm_tier import FirmTier
from app.models.service_catalog_entry import ServiceCatalogEntry
from app.models.user import User
from tests.conftest import TestingSessionLocal

CATALOG = "/api/pricing/catalog"
CONFIGS = "/api/pricing/configs"
OPTION_PRICES = "/api/pricing/option-prices"


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Seeding. conftest's clean_db truncates the system catalog between tests, so
# every test seeds the catalog it needs.
# ---------------------------------------------------------------------------

def _seed_catalog(db):
    """One flag mapped to one engagement type, and three dimensions of it.

    The three ranks are chosen so the linking tests have somewhere to go:

        coarse_numeric   rank 10, numeric_range, has a unit
        categorical      rank 20, categorical, two options
        fine_numeric     rank 30, numeric_range, has a unit

    fine_numeric is strictly finer than categorical, so it may hang under one
    of categorical's options. That downhill relationship is load-bearing for
    the verbatim test: without it _validate_downhill_link would refuse the call
    one guard earlier and the test would pass on the wrong message.
    """
    flag = ComplexityFlag(key="crypto", name="Crypto activity")
    db.add(flag)
    db.commit()
    db.refresh(flag)

    db.add(
        ComplexityFlagEngagementType(
            flag_id=flag.id, engagement_type=EngagementType.tax_return_1040.value
        )
    )

    coarse_numeric = ComplexityDimension(
        flag_id=flag.id,
        key="transaction_volume",
        kind=DimensionKind.numeric_range,
        hierarchy_rank=10,
        linkable=True,
    )
    categorical = ComplexityDimension(
        flag_id=flag.id,
        key="wallet_type",
        kind=DimensionKind.categorical,
        hierarchy_rank=20,
        linkable=True,
    )
    fine_numeric = ComplexityDimension(
        flag_id=flag.id,
        key="reconciliation_hours",
        kind=DimensionKind.numeric_range,
        hierarchy_rank=30,
        linkable=True,
    )
    db.add_all([coarse_numeric, categorical, fine_numeric])
    db.commit()
    db.refresh(coarse_numeric)
    db.refresh(categorical)
    db.refresh(fine_numeric)

    coarse_unit = ComplexityDimensionUnit(
        dimension_id=coarse_numeric.id, key="transaction_count", label="transactions"
    )
    fine_unit = ComplexityDimensionUnit(
        dimension_id=fine_numeric.id, key="hours", label="hours"
    )
    option_one = ComplexityVocabularyOption(
        dimension_id=categorical.id, key="custodial", label="Custodial"
    )
    option_two = ComplexityVocabularyOption(
        dimension_id=categorical.id, key="self_hosted", label="Self hosted"
    )
    db.add_all([coarse_unit, fine_unit, option_one, option_two])
    db.commit()
    for row in (coarse_unit, fine_unit, option_one, option_two):
        db.refresh(row)

    return {
        "flag": flag,
        "coarse_numeric": coarse_numeric,
        "categorical": categorical,
        "fine_numeric": fine_numeric,
        "coarse_unit": coarse_unit,
        "fine_unit": fine_unit,
        "option_one": option_one,
        "option_two": option_two,
    }


def _make_user(db, client, firm_id, role, password="rolepass123"):
    """A user of the given role inside an existing firm, logged in."""
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@firmwrite.com"
    user = User(
        firm_id=firm_id,
        email=email,
        hashed_password=get_password_hash(password),
        full_name=f"{role.value} user",
        role=role,
    )
    db.add(user)
    db.commit()

    login = client.post("/auth/token", json={"username": email, "password": password})
    assert login.status_code == 200, f"login failed for {role}: {login.text}"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _make_config(db, firm_id, dimension_id, *, unit_id=None, scope=None,
                 parent_option_id=None, parent_tier_id=None):
    """A config row inserted directly.

    Direct insertion is deliberate for SETUP rows: the save-time rules are
    pinned elsewhere, and going through the service here would make these
    tests fail for reasons that have nothing to do with the endpoint under
    test. Rows the endpoint itself is supposed to create are never seeded this
    way.
    """
    config = FirmDimensionConfig(
        firm_id=firm_id,
        dimension_id=dimension_id,
        service_catalog_entry_id=scope,
        role=DimensionRole.priced,
        unit_id=unit_id,
        parent_option_id=parent_option_id,
        parent_tier_id=parent_tier_id,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def _decimal_or_none(value):
    """None stays None. It is never turned into Decimal('0')."""
    if value is None:
        return None
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# 1. Happy path, one per endpoint.
# ---------------------------------------------------------------------------

def test_owner_upserts_catalog_entry(client, firm_a_owner, db):
    """PUT /api/pricing/catalog/{engagement_type}."""
    body = {
        "engagement_type": EngagementType.tax_return_1040.value,
        "is_offered": True,
        "pricing_mode": PricingMode.fixed.value,
        "base_fee": "500.00",
    }
    response = client.put(
        f"{CATALOG}/{EngagementType.tax_return_1040.value}",
        json=body,
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["firm_id"] == firm_a_owner["firm_id"]
    assert out["engagement_type"] == EngagementType.tax_return_1040.value
    assert out["is_offered"] is True
    assert out["pricing_mode"] == PricingMode.fixed.value
    assert _decimal_or_none(out["base_fee"]) == Decimal("500.00")

    # Upsert, not insert: the same call twice leaves one row.
    again = client.put(
        f"{CATALOG}/{EngagementType.tax_return_1040.value}",
        json={**body, "base_fee": "650.00"},
        headers=firm_a_owner["headers"],
    )
    assert again.status_code == 200, again.text
    assert again.json()["id"] == out["id"]
    assert _decimal_or_none(again.json()["base_fee"]) == Decimal("650.00")


def test_owner_creates_dimension_config(client, firm_a_owner, db):
    """POST /api/pricing/configs returns 201 and the created config."""
    catalog = _seed_catalog(db)

    response = client.post(
        CONFIGS,
        json={
            "dimension_id": str(catalog["coarse_numeric"].id),
            "role": DimensionRole.priced.value,
            "unit_id": str(catalog["coarse_unit"].id),
        },
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 201, response.text
    out = response.json()
    assert out["firm_id"] == firm_a_owner["firm_id"]
    assert out["dimension_id"] == str(catalog["coarse_numeric"].id)
    assert out["service_catalog_entry_id"] is None  # blanket
    assert out["parent_tier_id"] is None
    assert out["parent_option_id"] is None

    row = db.get(FirmDimensionConfig, uuid.UUID(out["id"]))
    assert row is not None


def test_owner_saves_tiers(client, firm_a_owner, db):
    """PUT /api/pricing/configs/{config_id}/tiers returns the whole set."""
    catalog = _seed_catalog(db)
    config = _make_config(
        db,
        uuid.UUID(firm_a_owner["firm_id"]),
        catalog["coarse_numeric"].id,
        unit_id=catalog["coarse_unit"].id,
    )

    response = client.put(
        f"{CONFIGS}/{config.id}/tiers",
        json=[
            {"range_min": "0", "range_max": "100", "price": "250.00", "sort_order": 0},
            {"range_min": "100", "range_max": "500", "price": "400.00", "sort_order": 1},
        ],
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 200, response.text
    tiers = response.json()
    assert isinstance(tiers, list)
    assert len(tiers) == 2
    assert [t["sort_order"] for t in tiers] == [0, 1]
    assert _decimal_or_none(tiers[0]["price"]) == Decimal("250.00")
    assert _decimal_or_none(tiers[1]["price"]) == Decimal("400.00")
    assert all(t["config_id"] == str(config.id) for t in tiers)


def test_owner_sets_option_price_preserving_null_versus_zero(
    client, firm_a_owner, db
):
    """PUT /api/pricing/option-prices, and the null-versus-zero law through HTTP.

    price null and price 0.00 are two different requests. This asserts both
    round-trip unchanged, because an `or 0` anywhere in the router or the
    serializer would collapse them and the universal quote law would silently
    stop working for every option priced at zero.
    """
    catalog = _seed_catalog(db)

    zero = client.put(
        OPTION_PRICES,
        json={"option_id": str(catalog["option_one"].id), "price": "0.00"},
        headers=firm_a_owner["headers"],
    )
    assert zero.status_code == 200, zero.text
    assert _decimal_or_none(zero.json()["price"]) == Decimal("0.00")
    assert zero.json()["price"] is not None

    unpriced = client.put(
        OPTION_PRICES,
        json={"option_id": str(catalog["option_two"].id), "price": None},
        headers=firm_a_owner["headers"],
    )
    assert unpriced.status_code == 200, unpriced.text
    assert unpriced.json()["price"] is None

    # And they are genuinely different rows in the database, not one coerced
    # into the other on the way in.
    priced_row = db.execute(
        FirmOptionPrice.__table__.select().where(
            FirmOptionPrice.option_id == catalog["option_one"].id
        )
    ).first()
    unpriced_row = db.execute(
        FirmOptionPrice.__table__.select().where(
            FirmOptionPrice.option_id == catalog["option_two"].id
        )
    ).first()
    assert priced_row.price == Decimal("0.00")
    assert unpriced_row.price is None


def test_owner_moves_config(client, firm_a_owner, db):
    """POST /api/pricing/configs/{config_id}/move with confirm true."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _make_config(db, firm_id, catalog["categorical"].id)
    child = _make_config(
        db,
        firm_id,
        catalog["fine_numeric"].id,
        unit_id=catalog["fine_unit"].id,
        parent_option_id=catalog["option_one"].id,
    )

    response = client.post(
        f"{CONFIGS}/{child.id}/move",
        json={
            "new_parent_tier_id": None,
            "new_parent_option_id": None,
            "confirm": True,
        },
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 200, response.text
    out = response.json()
    assert out["id"] == str(child.id)
    # Both parents cleared: the config is now flat. That is a real destination,
    # not a malformed request.
    assert out["parent_option_id"] is None
    assert out["parent_tier_id"] is None

    db.expire_all()
    assert db.get(FirmDimensionConfig, child.id).parent_option_id is None


def test_owner_deletes_config(client, firm_a_owner, db):
    """DELETE /api/pricing/configs/{config_id}?confirm=true returns 204."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    config = _make_config(
        db, firm_id, catalog["coarse_numeric"].id, unit_id=catalog["coarse_unit"].id
    )
    config_id = config.id

    response = client.delete(
        f"{CONFIGS}/{config_id}?confirm=true", headers=firm_a_owner["headers"]
    )
    assert response.status_code == 204, response.text
    assert response.content == b""

    db.expire_all()
    assert db.get(FirmDimensionConfig, config_id) is None


# ---------------------------------------------------------------------------
# 2. The router's own validation: path and body must agree.
# ---------------------------------------------------------------------------

def test_catalog_path_and_body_mismatch_is_refused(client, firm_a_owner, db):
    """The engagement_type is addressed twice and the two must agree.

    Without this the request would silently write to whichever of the two the
    implementation happened to trust, at an address the caller did not name.
    """
    response = client.put(
        f"{CATALOG}/{EngagementType.tax_return_1040.value}",
        json={
            "engagement_type": EngagementType.bookkeeping_monthly.value,
            "is_offered": True,
            "pricing_mode": PricingMode.fixed.value,
        },
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 422, response.text

    # Nothing was written under EITHER name.
    rows = db.execute(
        ServiceCatalogEntry.__table__.select().where(
            ServiceCatalogEntry.firm_id == uuid.UUID(firm_a_owner["firm_id"])
        )
    ).all()
    assert rows == []


# ---------------------------------------------------------------------------
# 3. RBAC. Manager is refused, ON PURPOSE.
# ---------------------------------------------------------------------------

def test_manager_is_refused_on_catalog_put(client, firm_a_owner, db):
    """Manager is refused today ON PURPOSE, same ruling as GET /api/pricing/config.

    When the deferred firm-owner-configurable per-role permissions session
    ships and an owner can open the fee schedule to managers, this test and its
    sibling below are the ones to rewrite, with a docstring saying what changed
    and why. Do not delete them quietly.
    """
    headers = _make_user(
        db, client, uuid.UUID(firm_a_owner["firm_id"]), UserRole.manager
    )
    response = client.put(
        f"{CATALOG}/{EngagementType.tax_return_1040.value}",
        json={
            "engagement_type": EngagementType.tax_return_1040.value,
            "is_offered": True,
            "pricing_mode": PricingMode.fixed.value,
        },
        headers=headers,
    )
    assert response.status_code == 403, response.text


def test_manager_is_refused_on_config_delete(client, firm_a_owner, db):
    """See test_manager_is_refused_on_catalog_put. Refused before anything is
    read or destroyed: RBAC runs in the dependency graph, ahead of the service.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    config = _make_config(
        db, firm_id, catalog["coarse_numeric"].id, unit_id=catalog["coarse_unit"].id
    )
    headers = _make_user(db, client, firm_id, UserRole.manager)

    response = client.delete(
        f"{CONFIGS}/{config.id}?confirm=true", headers=headers
    )
    assert response.status_code == 403, response.text

    db.expire_all()
    assert db.get(FirmDimensionConfig, config.id) is not None


def test_unauthenticated_is_refused(client):
    response = client.post(CONFIGS, json={})
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# 4. Tenant isolation through HTTP.
# ---------------------------------------------------------------------------

def test_firm_a_cannot_save_tiers_on_firm_b_config(
    client, firm_a_owner, firm_b_owner, db
):
    """Firm A aiming the tier endpoint at Firm B's config gets 404 and writes
    nothing. The config id is real; it simply is not theirs."""
    catalog = _seed_catalog(db)
    b_config = _make_config(
        db,
        uuid.UUID(firm_b_owner["firm_id"]),
        catalog["coarse_numeric"].id,
        unit_id=catalog["coarse_unit"].id,
    )

    response = client.put(
        f"{CONFIGS}/{b_config.id}/tiers",
        json=[
            {"range_min": "0", "range_max": "100", "price": "1.00", "sort_order": 0},
        ],
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 404, response.text

    tiers = db.execute(
        FirmTier.__table__.select().where(FirmTier.config_id == b_config.id)
    ).all()
    assert tiers == []


def test_delete_probe_against_other_firms_config_leaks_nothing(
    client, firm_a_owner, firm_b_owner, db
):
    """THE DELETE PROBE. Firm A sends confirm=false at Firm B's config id.

    The answer must be a bare 404. delete_config loads the config before it
    looks at confirm precisely so this path cannot reach the 422, whose message
    is a census: it names the dimension and counts the configs, tiers and
    option prices that would be destroyed. Handing that to another firm would
    confirm the row exists and describe how much hangs off it, to anyone
    willing to guess a UUID.

    Asserting the status code alone would NOT catch a regression here, because
    a confirm-first ordering returns 422 rather than 404 and the status check
    would go red for the right reason only by luck. So this also asserts the
    body carries none of the census.
    """
    catalog = _seed_catalog(db)
    firm_b_id = uuid.UUID(firm_b_owner["firm_id"])
    b_config = _make_config(
        db, firm_b_id, catalog["coarse_numeric"].id, unit_id=catalog["coarse_unit"].id
    )
    db.add_all(
        [
            FirmTier(
                firm_id=firm_b_id,
                config_id=b_config.id,
                range_min=Decimal("0"),
                range_max=Decimal("100"),
                price=Decimal("250.00"),
                sort_order=0,
            )
        ]
    )
    db.commit()

    response = client.delete(
        f"{CONFIGS}/{b_config.id}?confirm=false", headers=firm_a_owner["headers"]
    )
    assert response.status_code == 404, response.text

    detail = response.json()["detail"]
    assert detail == "Dimension config not found"
    # No blast radius: not the dimension key, not any count, not the language
    # the real refusal uses.
    for leak in ("transaction_volume", "tier", "option price", "permanently", "1"):
        assert leak not in detail, f"delete probe leaked '{leak}' to another firm"

    # And nothing of Firm B's was touched on the way to the refusal.
    db.expire_all()
    assert db.get(FirmDimensionConfig, b_config.id) is not None
    remaining = db.execute(
        FirmTier.__table__.select().where(FirmTier.config_id == b_config.id)
    ).all()
    assert len(remaining) == 1


# ---------------------------------------------------------------------------
# 5. THE VERBATIM DETAIL TEST.
# ---------------------------------------------------------------------------

def test_priced_option_parent_refusal_reaches_the_client_verbatim(
    client, firm_a_owner, db
):
    """The OPTION branch of _assert_parent_is_unpriced, through HTTP, character
    for character.

    THIS IS THE UI'S CONTRACT. The settings screen renders response detail as
    its own copy rather than replacing it with generic failure text, so the
    exact string is an interface. A reworded message, a message wrapped in an
    envelope, or one swallowed into "something went wrong" all break the
    product while leaving the status code correct, which is exactly the class
    of failure a status-only assertion cannot see.

    The expected string is built here from the same parts the service builds it
    from rather than pasted as a literal, so a deliberate rewording fails this
    test loudly at the assertion instead of drifting silently.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # The categorical dimension must be configured in the child's scope, or
    # rule 11 refuses one guard earlier and this test would assert the wrong
    # message. Load-bearing setup, not incidental seed data.
    _make_config(db, firm_id, catalog["categorical"].id)

    priced = client.put(
        OPTION_PRICES,
        json={"option_id": str(catalog["option_one"].id), "price": "75.00"},
        headers=firm_a_owner["headers"],
    )
    assert priced.status_code == 200, priced.text

    response = client.post(
        CONFIGS,
        json={
            "dimension_id": str(catalog["fine_numeric"].id),
            "role": DimensionRole.priced.value,
            "unit_id": str(catalog["fine_unit"].id),
            "parent_option_id": str(catalog["option_one"].id),
        },
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 422, response.text

    stored = db.execute(
        FirmOptionPrice.__table__.select().where(
            FirmOptionPrice.option_id == catalog["option_one"].id
        )
    ).first()
    expected = (
        f"Option {catalog['option_one'].id} is priced at {stored.price}, "
        "so nothing may hang under it. Prices live only at the leaf "
        "of a chain. Clear the parent price first via "
        "change_dimension_direction, then add the child."
    )
    assert response.json()["detail"] == expected

    # Refused means refused: no config was created on the way to the message.
    configs = db.execute(
        FirmDimensionConfig.__table__.select().where(
            FirmDimensionConfig.dimension_id == catalog["fine_numeric"].id
        )
    ).all()
    assert configs == []


# ---------------------------------------------------------------------------
# 6. confirm is required, and a refused call mutates nothing.
# ---------------------------------------------------------------------------

def test_move_without_confirm_is_refused_and_mutates_nothing(
    client, firm_a_owner, db
):
    """Own-firm rows throughout: change_dimension_direction checks confirm
    before it loads anything, so a cross-firm id would answer 422 here rather
    than 404 and would be testing a different thing."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _make_config(db, firm_id, catalog["categorical"].id)
    child = _make_config(
        db,
        firm_id,
        catalog["fine_numeric"].id,
        unit_id=catalog["fine_unit"].id,
        parent_option_id=catalog["option_one"].id,
    )
    db.add(
        FirmTier(
            firm_id=firm_id,
            config_id=child.id,
            range_min=Decimal("0"),
            range_max=Decimal("10"),
            price=Decimal("99.00"),
            sort_order=0,
        )
    )
    db.commit()

    response = client.post(
        f"{CONFIGS}/{child.id}/move",
        json={"new_parent_tier_id": None, "new_parent_option_id": None},
        headers=firm_a_owner["headers"],
    )
    assert response.status_code == 422, response.text
    assert "confirm" in response.json()["detail"]

    # The parent link is intact and the price that a confirmed move would have
    # destroyed is still there. A refused request must not destroy anything on
    # its way to the refusal.
    db.expire_all()
    assert db.get(FirmDimensionConfig, child.id).parent_option_id == (
        catalog["option_one"].id
    )
    tiers = db.execute(
        FirmTier.__table__.select().where(FirmTier.config_id == child.id)
    ).all()
    assert len(tiers) == 1
    assert tiers[0].price == Decimal("99.00")


def test_delete_without_confirm_is_refused_and_mutates_nothing(
    client, firm_a_owner, db
):
    """The owning firm DOES see the census. That asymmetry with the delete
    probe above is the ratified behaviour: the firm that owns the rows is
    entitled to know what it is about to destroy."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    config = _make_config(
        db, firm_id, catalog["coarse_numeric"].id, unit_id=catalog["coarse_unit"].id
    )
    db.add(
        FirmTier(
            firm_id=firm_id,
            config_id=config.id,
            range_min=Decimal("0"),
            range_max=Decimal("100"),
            price=Decimal("250.00"),
            sort_order=0,
        )
    )
    db.commit()

    response = client.delete(
        f"{CONFIGS}/{config.id}?confirm=false", headers=firm_a_owner["headers"]
    )
    assert response.status_code == 422, response.text
    detail = response.json()["detail"]
    assert "transaction_volume" in detail
    assert "confirm=true" in detail

    db.expire_all()
    assert db.get(FirmDimensionConfig, config.id) is not None
    tiers = db.execute(
        FirmTier.__table__.select().where(FirmTier.config_id == config.id)
    ).all()
    assert len(tiers) == 1


def test_delete_defaults_to_refusing_when_confirm_is_omitted(
    client, firm_a_owner, db
):
    """confirm defaults to false. Omitting the query parameter entirely must
    behave exactly like sending confirm=false, not like sending confirm=true."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    config = _make_config(
        db, firm_id, catalog["coarse_numeric"].id, unit_id=catalog["coarse_unit"].id
    )

    response = client.delete(f"{CONFIGS}/{config.id}", headers=firm_a_owner["headers"])
    assert response.status_code == 422, response.text

    db.expire_all()
    assert db.get(FirmDimensionConfig, config.id) is not None
