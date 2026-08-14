# tests/test_pricing_config_endpoint.py

"""Tests for GET /api/pricing/config, the pricing service's first HTTP surface.

Four things are pinned here, and each one has been watched to fail against a
deliberately broken copy of the rule it guards before being accepted:

1. Happy path. A firm owner gets the shared catalog and their own pricing back
   in one object.
2. RBAC. firm_owner only. Manager and staff are refused 403.
3. Tenant isolation. Firm A's owner sees none of Firm B's firm pricing, while
   still seeing the same shared system catalog Firm B sees. Both halves matter:
   a response that leaked Firm B's prices and a response that filtered the
   carve-out tables by firm are both wrong, in opposite directions.
4. The null-versus-zero law. NULL stays null (unpriced, routes to quote) and
   0.00 stays 0.00 (explicitly free), on the way out as well as in.

The negative controls run for each are recorded in the session report.
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

ENDPOINT = "/api/pricing/config"


# ---------------------------------------------------------------------------
# Seeding. The system catalog is truncated between tests by conftest's
# clean_db, so every test seeds what it needs.
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


def _seed_catalog(db):
    """One flag, one engagement type mapping, one numeric dimension with a unit,
    one categorical dimension with two options. None of these carry firm_id.
    """
    flag = ComplexityFlag(key="crypto", name="Crypto activity")
    db.add(flag)
    db.commit()
    db.refresh(flag)

    mapping = ComplexityFlagEngagementType(
        flag_id=flag.id,
        engagement_type=EngagementType.tax_return_1040.value,
    )
    db.add(mapping)

    numeric = ComplexityDimension(
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
    db.add_all([numeric, categorical])
    db.commit()
    db.refresh(numeric)
    db.refresh(categorical)

    unit = ComplexityDimensionUnit(
        dimension_id=numeric.id, key="transaction_count", label="transactions"
    )
    option_one = ComplexityVocabularyOption(
        dimension_id=categorical.id, key="custodial", label="Custodial"
    )
    option_two = ComplexityVocabularyOption(
        dimension_id=categorical.id, key="self_hosted", label="Self hosted"
    )
    db.add_all([unit, option_one, option_two])
    db.commit()
    db.refresh(unit)
    db.refresh(option_one)
    db.refresh(option_two)

    return {
        "flag": flag,
        "numeric": numeric,
        "categorical": categorical,
        "unit": unit,
        "option_one": option_one,
        "option_two": option_two,
    }


def _seed_firm_pricing(
    db,
    firm_id,
    catalog,
    *,
    base_fee,
    first_tier_price,
    second_tier_price,
    option_price,
):
    """One firm's attachments to the seeded catalog.

    Prices are parameters rather than constants so two firms can be given
    deliberately different numbers and the isolation test can look for the
    wrong firm's number by value.

    Rows are inserted directly rather than through pricing_config_service. The
    save-time rules are already pinned by tests/test_pricing_config_guards.py,
    and this file is about what the read returns.
    """
    entry = ServiceCatalogEntry(
        firm_id=firm_id,
        engagement_type=EngagementType.tax_return_1040.value,
        is_offered=True,
        pricing_mode=PricingMode.fixed,
        base_fee=base_fee,
    )
    config = FirmDimensionConfig(
        firm_id=firm_id,
        dimension_id=catalog["numeric"].id,
        role=DimensionRole.priced,
        unit_id=catalog["unit"].id,
    )
    db.add_all([entry, config])
    db.commit()
    db.refresh(config)

    tiers = [
        FirmTier(
            firm_id=firm_id,
            config_id=config.id,
            range_min=Decimal("0"),
            range_max=Decimal("100"),
            price=first_tier_price,
            sort_order=0,
        ),
        FirmTier(
            firm_id=firm_id,
            config_id=config.id,
            range_min=Decimal("100"),
            range_max=Decimal("500"),
            price=second_tier_price,
            sort_order=1,
        ),
    ]
    price_row = FirmOptionPrice(
        firm_id=firm_id,
        option_id=catalog["option_one"].id,
        price=option_price,
    )
    db.add_all(tiers + [price_row])
    db.commit()

    return {"config": config, "entry": entry}


def _make_user(db, client, firm_id, role, password="rolepass123"):
    """A user of the given role inside an existing firm, logged in."""
    email = f"{role.value}-{uuid.uuid4().hex[:8]}@firma.com"
    user = User(
        firm_id=firm_id,
        email=email,
        hashed_password=get_password_hash(password),
        full_name=f"{role.value} user",
        role=role,
    )
    db.add(user)
    db.commit()

    login = client.post(
        "/auth/token", json={"username": email, "password": password}
    )
    assert login.status_code == 200, f"login failed for {role}: {login.text}"
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _decimal_or_none(value):
    """JSON numbers and JSON strings both come back through this unchanged in
    meaning. None stays None; it is never turned into Decimal('0')."""
    if value is None:
        return None
    return Decimal(str(value))


# ---------------------------------------------------------------------------
# 1. Happy path
# ---------------------------------------------------------------------------

def test_firm_owner_gets_catalog_and_own_pricing(client, firm_a_owner, db):
    catalog = _seed_catalog(db)
    _seed_firm_pricing(
        db,
        uuid.UUID(firm_a_owner["firm_id"]),
        catalog,
        base_fee=Decimal("500.00"),
        first_tier_price=Decimal("250.00"),
        second_tier_price=Decimal("400.00"),
        option_price=Decimal("75.00"),
    )

    response = client.get(ENDPOINT, headers=firm_a_owner["headers"])
    assert response.status_code == 200, response.text
    body = response.json()

    assert body["firm_id"] == firm_a_owner["firm_id"]

    catalog_block = body["catalog"]
    assert [f["key"] for f in catalog_block["complexity_flags"]] == ["crypto"]
    assert [
        m["engagement_type"] for m in catalog_block["complexity_flag_engagement_types"]
    ] == [EngagementType.tax_return_1040.value]
    assert sorted(d["key"] for d in catalog_block["complexity_dimensions"]) == [
        "transaction_volume",
        "wallet_type",
    ]
    assert [u["key"] for u in catalog_block["complexity_dimension_units"]] == [
        "transaction_count"
    ]
    assert sorted(o["key"] for o in catalog_block["complexity_vocabulary_options"]) == [
        "custodial",
        "self_hosted",
    ]

    entries = catalog_block["service_catalog_entries"]
    assert len(entries) == 1
    assert entries[0]["engagement_type"] == EngagementType.tax_return_1040.value
    assert entries[0]["firm_id"] == firm_a_owner["firm_id"]
    assert _decimal_or_none(entries[0]["base_fee"]) == Decimal("500.00")

    pricing = body["firm_pricing"]
    assert len(pricing["firm_dimension_configs"]) == 1
    assert pricing["firm_dimension_configs"][0]["firm_id"] == firm_a_owner["firm_id"]
    assert [
        _decimal_or_none(t["price"]) for t in pricing["firm_tiers"]
    ] == [Decimal("250.00"), Decimal("400.00")]
    assert len(pricing["firm_option_prices"]) == 1
    assert _decimal_or_none(pricing["firm_option_prices"][0]["price"]) == Decimal(
        "75.00"
    )


def test_empty_firm_gets_the_catalog_and_empty_pricing(client, firm_a_owner, db):
    """A firm that has configured nothing still gets the shared catalog.

    Without this, a response of all empty lists would be indistinguishable from
    a broken catalog query, and the happy path above would be the only thing
    watching a join that returns nothing.
    """
    _seed_catalog(db)

    response = client.get(ENDPOINT, headers=firm_a_owner["headers"])
    assert response.status_code == 200, response.text
    body = response.json()

    assert len(body["catalog"]["complexity_flags"]) == 1
    assert body["catalog"]["service_catalog_entries"] == []
    assert body["firm_pricing"] == {
        "firm_dimension_configs": [],
        "firm_tiers": [],
        "firm_option_prices": [],
    }


# ---------------------------------------------------------------------------
# 2. RBAC. firm_owner only, per the session opener.
# ---------------------------------------------------------------------------

def test_staff_is_refused(client, firm_a_owner, db):
    headers = _make_user(
        db, client, uuid.UUID(firm_a_owner["firm_id"]), UserRole.staff
    )
    response = client.get(ENDPOINT, headers=headers)
    assert response.status_code == 403, response.text


def test_manager_is_refused(client, firm_a_owner, db):
    """Manager is refused today ON PURPOSE.

    This is the assertion a future firm-owner-configurable per-role permissions
    setting is expected to change. When that session ships and an owner can
    open the fee schedule to managers, this test is the one to rewrite, with a
    docstring saying what changed and why. Do not delete it quietly: a test
    that stops asserting the rule it was named for is misinformation.
    """
    headers = _make_user(
        db, client, uuid.UUID(firm_a_owner["firm_id"]), UserRole.manager
    )
    response = client.get(ENDPOINT, headers=headers)
    assert response.status_code == 403, response.text


def test_unauthenticated_is_refused(client):
    response = client.get(ENDPOINT)
    assert response.status_code == 401, response.text


# ---------------------------------------------------------------------------
# 3. Tenant isolation
# ---------------------------------------------------------------------------

def test_firm_a_owner_never_sees_firm_b_pricing(
    client, firm_a_owner, firm_b_owner, db
):
    """Both directions in one test, because they fail independently.

    Firm pricing must be filtered to the caller's firm. The carve-out catalog
    must NOT be, and a fix that over-filtered would leave every firm with an
    empty vocabulary while this file's other tests stayed green.
    """
    catalog = _seed_catalog(db)

    firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
    firm_b_id = uuid.UUID(firm_b_owner["firm_id"])

    _seed_firm_pricing(
        db,
        firm_a_id,
        catalog,
        base_fee=Decimal("500.00"),
        first_tier_price=Decimal("250.00"),
        second_tier_price=Decimal("400.00"),
        option_price=Decimal("75.00"),
    )
    _seed_firm_pricing(
        db,
        firm_b_id,
        catalog,
        base_fee=Decimal("777.00"),
        first_tier_price=Decimal("999.99"),
        second_tier_price=Decimal("888.88"),
        option_price=Decimal("666.66"),
    )

    response = client.get(ENDPOINT, headers=firm_a_owner["headers"])
    assert response.status_code == 200, response.text
    body = response.json()

    # Every firm-owned row belongs to Firm A.
    owned_rows = (
        body["catalog"]["service_catalog_entries"]
        + body["firm_pricing"]["firm_dimension_configs"]
        + body["firm_pricing"]["firm_tiers"]
        + body["firm_pricing"]["firm_option_prices"]
    )
    assert owned_rows, "seeded rows are missing, so this test would pass vacuously"
    foreign = [row for row in owned_rows if row["firm_id"] != firm_a_owner["firm_id"]]
    assert not foreign, (
        f"Firm A's response contains {len(foreign)} row(s) belonging to another "
        f"firm: {foreign}"
    )

    # Look for Firm B's numbers by value as well, so a response that carried
    # them under a rewritten firm_id would still be caught.
    serialized = response.text
    # Firm A's own numbers first. Without this the absence check below would
    # also pass if prices were serialized in some shape these literals could
    # never match, which is a check that cannot fail.
    for firm_a_number in ("500.00", "250.00", "400.00", "75.00"):
        assert firm_a_number in serialized, (
            f"Firm A's own price {firm_a_number} is not in its own response, so "
            "the absence check below is not measuring anything. Prices are "
            "probably serialized in a different shape now."
        )
    for firm_b_number in ("777.00", "999.99", "888.88", "666.66"):
        assert firm_b_number not in serialized, (
            f"Firm B's price {firm_b_number} appears in Firm A's response."
        )

    # The carve-out catalog is shared, not filtered away.
    assert len(body["catalog"]["complexity_flags"]) == 1
    assert len(body["catalog"]["complexity_vocabulary_options"]) == 2

    # And Firm B sees the same catalog with its own pricing.
    response_b = client.get(ENDPOINT, headers=firm_b_owner["headers"])
    assert response_b.status_code == 200, response_b.text
    body_b = response_b.json()
    assert body_b["firm_id"] == firm_b_owner["firm_id"]
    assert [f["key"] for f in body_b["catalog"]["complexity_flags"]] == ["crypto"]
    assert _decimal_or_none(
        body_b["catalog"]["service_catalog_entries"][0]["base_fee"]
    ) == Decimal("777.00")


# ---------------------------------------------------------------------------
# 4. The null-versus-zero law
# ---------------------------------------------------------------------------

def test_null_and_zero_prices_both_survive_the_response(client, firm_a_owner, db):
    """Within one firm: an unpriced tier and a tier priced at zero.

    null means unpriced and routes the lead to a quote. 0.00 means the firm
    charges nothing. Collapsing either into the other changes what a lead is
    told, so the response has to keep them apart.
    """
    catalog = _seed_catalog(db)
    _seed_firm_pricing(
        db,
        uuid.UUID(firm_a_owner["firm_id"]),
        catalog,
        base_fee=None,
        first_tier_price=None,
        second_tier_price=Decimal("0.00"),
        option_price=Decimal("0.00"),
    )

    response = client.get(ENDPOINT, headers=firm_a_owner["headers"])
    assert response.status_code == 200, response.text
    body = response.json()

    tiers = body["firm_pricing"]["firm_tiers"]
    assert len(tiers) == 2
    unpriced, free = tiers[0], tiers[1]

    assert unpriced["price"] is None, (
        f"The unpriced tier came back as {unpriced['price']!r}. NULL was "
        "coerced into a number, so a lead who should have been routed to a "
        "quote is now being quoted a price."
    )
    assert free["price"] is not None, (
        "The tier priced at 0.00 came back as null, so an explicitly free "
        "service now routes to a quote."
    )
    assert _decimal_or_none(free["price"]) == Decimal("0.00")

    option_price = body["firm_pricing"]["firm_option_prices"][0]["price"]
    assert option_price is not None
    assert _decimal_or_none(option_price) == Decimal("0.00")

    base_fee = body["catalog"]["service_catalog_entries"][0]["base_fee"]
    assert base_fee is None, (
        f"An unset base_fee came back as {base_fee!r} instead of null."
    )


def test_null_firm_and_zero_firm_round_trip_independently(
    client, firm_a_owner, firm_b_owner, db
):
    """Across two firms, which is how the session task words it: one firm whose
    price is NULL and one whose price is an explicit 0.00, each reading their
    own config back unchanged.

    Separate from the test above because a bug that reads one firm's prices
    into another firm's response would leave that one green.
    """
    catalog = _seed_catalog(db)

    _seed_firm_pricing(
        db,
        uuid.UUID(firm_a_owner["firm_id"]),
        catalog,
        base_fee=None,
        first_tier_price=None,
        second_tier_price=None,
        option_price=None,
    )
    _seed_firm_pricing(
        db,
        uuid.UUID(firm_b_owner["firm_id"]),
        catalog,
        base_fee=Decimal("0.00"),
        first_tier_price=Decimal("0.00"),
        second_tier_price=Decimal("0.00"),
        option_price=Decimal("0.00"),
    )

    body_a = client.get(ENDPOINT, headers=firm_a_owner["headers"]).json()
    body_b = client.get(ENDPOINT, headers=firm_b_owner["headers"]).json()

    assert [t["price"] for t in body_a["firm_pricing"]["firm_tiers"]] == [None, None]
    assert body_a["firm_pricing"]["firm_option_prices"][0]["price"] is None
    assert body_a["catalog"]["service_catalog_entries"][0]["base_fee"] is None

    assert [
        _decimal_or_none(t["price"]) for t in body_b["firm_pricing"]["firm_tiers"]
    ] == [Decimal("0.00"), Decimal("0.00")]
    assert _decimal_or_none(
        body_b["firm_pricing"]["firm_option_prices"][0]["price"]
    ) == Decimal("0.00")
    assert _decimal_or_none(
        body_b["catalog"]["service_catalog_entries"][0]["base_fee"]
    ) == Decimal("0.00")
