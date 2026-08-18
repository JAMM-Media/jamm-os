# tests/test_intake_pricing_config.py

"""Tests for GET /intake/{slug}/pricing-config, the public intake question tree.

This endpoint is unauthenticated by design (CRM Build Contract Addendum 1
section 9). The whole reason that is acceptable is that the service layer
strips every commercial fact out of the response, so THE GUARD TEST AT THE TOP
OF THIS FILE IS WHAT MAKES THE ENDPOINT SAFE TO SHIP. If it is ever deleted or
weakened, the endpoint stops being safe to serve without auth.

What is pinned here:

1.  The stripping contract. A richly configured firm (base fee, priced tiers,
    priced options, a guard with a threshold, a chained config) is serialized
    and walked recursively; no forbidden key may appear at any depth, and no
    Decimal-typed value may survive into the model dump.
2.  Config-driven applicability, per Andrew's August 16, 2026 ruling.
3.  Unit selection as part of that same gate.
4.  Deduplication across branches.
5.  Unpriced-but-configured is still asked.
6.  Tenant isolation, asserted on content rather than on counts.
7.  The offered gate, including the empty-questions state.
8.  Inactive flag and inactive vocabulary option filtering.
9.  404 on an unknown slug.
10. Chain invisibility.

The negative control run for the guard test is recorded in the session report.
"""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import func, select

from app.core.enums import (
    ENGAGEMENT_TYPE_LABELS,
    DimensionKind,
    DimensionRole,
    EngagementType,
    PricingMode,
    ServiceCategory,
)
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_dimension_unit import ComplexityDimensionUnit
from app.models.complexity_flag import ComplexityFlag
from app.models.complexity_flag_engagement_type import ComplexityFlagEngagementType
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption
from app.models.firm_dimension_config import FirmDimensionConfig
from app.models.firm_option_price import FirmOptionPrice
from app.models.firm_tier import FirmTier
from app.models.service_catalog_entry import ServiceCatalogEntry
from app.services import pricing_config_service
from app.services.pricing_config_service import get_public_intake_config
from tests.conftest import TestingSessionLocal

FIRM_A_SLUG = "firm-a-cpa"
FIRM_B_SLUG = "firm-b-bookkeeping"

TAX_1040 = EngagementType.tax_return_1040.value
PARTNERSHIP_1065 = EngagementType.tax_return_1065.value


def endpoint(slug):
    return f"/intake/{slug}/pricing-config"


# ---------------------------------------------------------------------------
# Question text constants. Asserted on by value in several tests, so they live
# here rather than being retyped at each use site.
# ---------------------------------------------------------------------------

TXN_COUNT_QUESTION = "How many crypto transactions did you have last year?"
ACCOUNTS_QUESTION = "How many crypto accounts or wallets did you hold?"
PORTFOLIO_QUESTION = "What was the total value of your crypto portfolio?"
WALLET_TYPE_QUESTION = "What kind of wallet did you use?"
STAKING_QUESTION = "Did you earn staking or mining rewards?"
LEGACY_QUESTION = "Did you use the retired legacy workflow?"
RENTAL_QUESTION = "How many rental units does the partnership hold?"


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Seeding. The system catalog is truncated between tests by conftest's
# clean_db, so every test seeds what it needs. None of these rows carry a
# firm_id: they are the August 13, 2026 carve-out tables.
# ---------------------------------------------------------------------------

def _seed_catalog(db):
    """The shared system catalog every test in this file reads.

    One active flag on the 1040 carrying all three dimension kinds, one
    INACTIVE flag on the same engagement type, and one active flag on a
    different engagement type. The last two exist so the filtering tests are
    asserting against rows that really are present in the database rather than
    against rows that were simply never seeded.
    """
    crypto = ComplexityFlag(key="crypto", name="Crypto activity", is_active=True)
    legacy = ComplexityFlag(key="legacy", name="Legacy workflow", is_active=False)
    rental = ComplexityFlag(key="rental", name="Rental activity", is_active=True)
    db.add_all([crypto, legacy, rental])
    db.commit()
    db.refresh(crypto)
    db.refresh(legacy)
    db.refresh(rental)

    db.add_all([
        ComplexityFlagEngagementType(
            flag_id=crypto.id, engagement_type=TAX_1040
        ),
        # The inactive flag is mapped to the SAME engagement type, so anything
        # that excludes it has to be reading is_active and not the mapping.
        ComplexityFlagEngagementType(
            flag_id=legacy.id, engagement_type=TAX_1040
        ),
        # Active flag, different engagement type. Excluded from a 1040-only
        # firm by applicability, not by activity.
        ComplexityFlagEngagementType(
            flag_id=rental.id, engagement_type=PARTNERSHIP_1065
        ),
    ])

    staking = ComplexityDimension(
        flag_id=crypto.id,
        key="has_staking",
        kind=DimensionKind.boolean,
        question_text=STAKING_QUESTION,
        hierarchy_rank=5,
        linkable=True,
    )
    # Coarser than transaction_volume, so a volume config can legitimately hang
    # under one of its tiers. That second branch is the only way a firm can
    # configure one dimension in two different units: the branch-uniqueness
    # constraint is NULLS NOT DISTINCT, so the same dimension cannot be
    # configured flat twice, whatever units the two rows name.
    portfolio = ComplexityDimension(
        flag_id=crypto.id,
        key="portfolio_value",
        kind=DimensionKind.numeric_range,
        question_text="COARSE DIMENSION TEXT THAT MUST NEVER BE SERVED",
        hierarchy_rank=1,
        linkable=True,
    )
    volume = ComplexityDimension(
        flag_id=crypto.id,
        key="transaction_volume",
        kind=DimensionKind.numeric_range,
        # Deliberately set, and deliberately never served. A numeric_range
        # question is phrased by its unit, not by its dimension. If this string
        # ever shows up in a response, the unit lookup has been bypassed.
        question_text="DIMENSION LEVEL TEXT THAT MUST NEVER BE SERVED",
        hierarchy_rank=10,
        linkable=True,
    )
    wallet = ComplexityDimension(
        flag_id=crypto.id,
        key="wallet_type",
        kind=DimensionKind.categorical,
        question_text=WALLET_TYPE_QUESTION,
        hierarchy_rank=20,
        linkable=True,
    )
    legacy_dimension = ComplexityDimension(
        flag_id=legacy.id,
        key="legacy_dimension",
        kind=DimensionKind.boolean,
        question_text=LEGACY_QUESTION,
        hierarchy_rank=10,
        linkable=True,
    )
    rental_dimension = ComplexityDimension(
        flag_id=rental.id,
        key="rental_units",
        kind=DimensionKind.boolean,
        question_text=RENTAL_QUESTION,
        hierarchy_rank=10,
        linkable=True,
    )
    db.add_all([staking, portfolio, volume, wallet, legacy_dimension, rental_dimension])
    db.commit()
    for row in (staking, portfolio, volume, wallet, legacy_dimension, rental_dimension):
        db.refresh(row)

    usd_value = ComplexityDimensionUnit(
        dimension_id=portfolio.id,
        key="usd_value",
        label="US dollars",
        question_text=PORTFOLIO_QUESTION,
    )
    transaction_count = ComplexityDimensionUnit(
        dimension_id=volume.id,
        key="transaction_count",
        label="transactions",
        question_text=TXN_COUNT_QUESTION,
    )
    accounts = ComplexityDimensionUnit(
        dimension_id=volume.id,
        key="accounts",
        label="accounts",
        question_text=ACCOUNTS_QUESTION,
    )
    custodial = ComplexityVocabularyOption(
        dimension_id=wallet.id, key="custodial", label="Custodial exchange", is_active=True
    )
    self_hosted = ComplexityVocabularyOption(
        dimension_id=wallet.id, key="self_hosted", label="Self hosted", is_active=True
    )
    retired = ComplexityVocabularyOption(
        dimension_id=wallet.id, key="retired", label="Retired option", is_active=False
    )
    db.add_all([usd_value, transaction_count, accounts, custodial, self_hosted, retired])
    db.commit()
    for row in (usd_value, transaction_count, accounts, custodial, self_hosted, retired):
        db.refresh(row)

    return {
        "crypto": crypto,
        "legacy": legacy,
        "rental": rental,
        "staking": staking,
        "portfolio": portfolio,
        "usd_value": usd_value,
        "volume": volume,
        "wallet": wallet,
        "legacy_dimension": legacy_dimension,
        "rental_dimension": rental_dimension,
        "transaction_count": transaction_count,
        "accounts": accounts,
        "custodial": custodial,
        "self_hosted": self_hosted,
        "retired": retired,
    }


def _offer(db, firm_id, engagement_type, *, base_fee=None, is_offered=True):
    entry = ServiceCatalogEntry(
        firm_id=firm_id,
        engagement_type=engagement_type,
        is_offered=is_offered,
        pricing_mode=PricingMode.fixed if is_offered else None,
        base_fee=base_fee,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _configure(
    db,
    firm_id,
    dimension,
    *,
    unit=None,
    role=DimensionRole.priced,
    guard_threshold=None,
    parent_tier=None,
    parent_option=None,
    scope=None,
):
    """One firm_dimension_configs row, inserted directly.

    Rows go in through the models rather than through pricing_config_service.
    The save-time rules are already pinned by tests/test_pricing_config_guards.py
    and this file is about what the read returns, which is the same division of
    labour tests/test_pricing_config_endpoint.py uses.

    scope is a ServiceCatalogEntry or None, added August 18, 2026. None is the
    blanket case and is what every test in this file wrote before that date,
    which is exactly why the scoped path had no coverage here at all: the
    helper had no way to express it, so no fixture could reach it.
    """
    config = FirmDimensionConfig(
        firm_id=firm_id,
        dimension_id=dimension.id,
        role=role,
        unit_id=unit.id if unit is not None else None,
        guard_threshold=guard_threshold,
        parent_tier_id=parent_tier.id if parent_tier is not None else None,
        parent_option_id=parent_option.id if parent_option is not None else None,
        service_catalog_entry_id=scope.id if scope is not None else None,
    )
    db.add(config)
    db.commit()
    db.refresh(config)
    return config


def _add_tiers(db, firm_id, config, prices):
    """Contiguous tiers for a config, one per price in the list."""
    tiers = []
    for index, price in enumerate(prices):
        tiers.append(
            FirmTier(
                firm_id=firm_id,
                config_id=config.id,
                range_min=Decimal(index * 100),
                range_max=Decimal((index + 1) * 100),
                price=price,
                sort_order=index,
            )
        )
    db.add_all(tiers)
    db.commit()
    for tier in tiers:
        db.refresh(tier)
    return tiers


def _questions(body, engagement_type=TAX_1040):
    for service in body["services"]:
        if service["engagement_type"] == engagement_type:
            return service["questions"]
    raise AssertionError(
        f"{engagement_type} is not in the response at all. Services present: "
        f"{[s['engagement_type'] for s in body['services']]}"
    )


def _question_texts(body, engagement_type=TAX_1040):
    return [q["question_text"] for q in _questions(body, engagement_type)]


def _dimension_keys(body, engagement_type=TAX_1040):
    return [q["dimension_key"] for q in _questions(body, engagement_type)]


# ---------------------------------------------------------------------------
# 1. THE GUARD TEST
# ---------------------------------------------------------------------------

# Every key the stripping contract forbids, plus the row-identity and
# timestamp keys the contract's last line covers. Matched by exact key name at
# every depth, never by substring, so the legitimate `id` on a vocabulary
# option and the legitimate `label` are not false positives.
FORBIDDEN_KEYS = frozenset({
    "price",
    "base_fee",
    "pricing_mode",
    "guard_threshold",
    "range_min",
    "range_max",
    "sort_order",
    "role",
    "parent_tier_id",
    "parent_option_id",
    "firm_id",
    # Row identity and structure. Not in the session's explicit list but
    # covered by "firm_id, config row IDs, tier IDs, or timestamps".
    "config_id",
    "tier_id",
    "dimension_id",
    "flag_id",
    "unit_id",
    "created_at",
    "updated_at",
})

# Distinctive money values, chosen so that finding one of these strings inside
# a response cannot be a coincidental match against question text or a label.
BASE_FEE = Decimal("4321.99")
TIER_PRICE_ONE = Decimal("1234.56")
TIER_PRICE_TWO = Decimal("2345.67")
OPTION_PRICE = Decimal("777.77")
GUARD_THRESHOLD = Decimal("8888.88")


def _walk_keys(node, path="$"):
    """Every mapping key at every depth, with the path that reached it."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}.{key}", key
            yield from _walk_keys(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _walk_keys(item, f"{path}[{index}]")


def _walk_values(node, path="$"):
    """Every leaf value at every depth, with the path that reached it."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield from _walk_values(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, item in enumerate(node):
            yield from _walk_values(item, f"{path}[{index}]")
    else:
        yield path, node


def _seed_rich_firm(db, firm_id, catalog):
    """A firm configured every way that carries a commercial fact.

    Base fee, priced tiers, a priced option, a guard config with a threshold,
    and a chained config hanging under a priced-sibling tier. If the response
    can be assembled from all of this without leaking any of it, the stripping
    contract holds for the shapes that actually exist.
    """
    _offer(db, firm_id, TAX_1040, base_fee=BASE_FEE)

    # Numeric, flat, with priced tiers.
    volume_config = _configure(
        db, firm_id, catalog["volume"], unit=catalog["transaction_count"]
    )
    tiers = _add_tiers(db, firm_id, volume_config, [TIER_PRICE_ONE, TIER_PRICE_TWO])

    # Categorical, CHAINED under one of those tiers, with a priced option.
    _configure(db, firm_id, catalog["wallet"], parent_tier=tiers[0])
    db.add(
        FirmOptionPrice(
            firm_id=firm_id,
            option_id=catalog["custodial"].id,
            price=OPTION_PRICE,
        )
    )
    db.commit()

    # Boolean, configured as a GUARD with a threshold.
    _configure(
        db,
        firm_id,
        catalog["staking"],
        role=DimensionRole.guard,
        guard_threshold=GUARD_THRESHOLD,
    )


def test_no_commercial_fact_survives_into_the_public_response(client, firm_a_owner, db):
    """THE GUARD. Nothing priced, roled, ranged, chained or owned gets out.

    Walked recursively rather than checked field by field, because the failure
    this is watching for is a field being ADDED later, at a depth nobody
    thought about. A field-by-field assertion list can only ever catch the
    fields somebody already remembered.

    Watched red before being accepted: base_fee was temporarily added to
    IntakeServiceOut and populated in the service, and this test failed on it.
    The three-step restore is recorded in the session report.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _seed_rich_firm(db, firm_id, catalog)

    response = client.get(endpoint(FIRM_A_SLUG))
    assert response.status_code == 200, response.text
    body = response.json()

    # ------------------------------------------------------------------
    # The response has to be RICH before its emptiness proves anything. A
    # walk over {} passes every assertion below while measuring nothing,
    # which is exactly the shape of failure this repo keeps finding.
    # ------------------------------------------------------------------
    questions = _questions(body)
    assert len(body["services"]) == 1, body["services"]
    assert len(questions) == 3, (
        f"Expected three questions (staking, transaction volume, wallet type) "
        f"but got {len(questions)}: {questions}. The walk below would be "
        "measuring an under-populated response."
    )
    assert any(q["options"] for q in questions), (
        "No question came back with options, so the walk never descends into "
        "the deepest level of the response."
    )
    key_count = len(list(_walk_keys(body)))
    assert key_count > 25, (
        f"Only {key_count} keys in the whole response. Too thin to be "
        "evidence of anything."
    )

    # ------------------------------------------------------------------
    # The contract itself.
    # ------------------------------------------------------------------
    offenders = [
        (path, key) for path, key in _walk_keys(body) if key in FORBIDDEN_KEYS
    ]
    assert not offenders, (
        "The public intake response leaks commercial facts. Forbidden keys "
        f"found at: {offenders}"
    )

    # No Decimal-typed value anywhere. This is asserted against the service's
    # own model dump rather than the parsed JSON, ON PURPOSE: JSON has no
    # Decimal type, so a walk over response.json() could never find one and
    # would be a check incapable of failing.
    config = get_public_intake_config(db, firm_id=firm_id)
    dumped = config.model_dump()
    decimals = [
        (path, value)
        for path, value in _walk_values(dumped)
        if isinstance(value, Decimal)
    ]
    assert not decimals, (
        f"Decimal-typed values survived into the response at: {decimals}. "
        "There is no legitimate monetary field in this response."
    )

    # The same forbidden-key walk over the model dump, because a field could be
    # excluded from JSON while still existing on the schema.
    dump_offenders = [
        (path, key) for path, key in _walk_keys(dumped) if key in FORBIDDEN_KEYS
    ]
    assert not dump_offenders, (
        f"Forbidden keys on the schema objects themselves: {dump_offenders}"
    )

    # And by value, so a price renamed to an innocent-looking key is still
    # caught. These numbers are all in the database for this firm.
    serialized = response.text
    for money in (
        str(BASE_FEE),
        str(TIER_PRICE_ONE),
        str(TIER_PRICE_TWO),
        str(OPTION_PRICE),
        str(GUARD_THRESHOLD),
    ):
        assert money not in serialized, (
            f"The value {money} appears in the public response. A commercial "
            "fact is being served under some other name."
        )


# ---------------------------------------------------------------------------
# 2. Config-driven applicability (Andrew, August 16, 2026)
# ---------------------------------------------------------------------------

def test_applicable_but_unconfigured_dimension_is_not_asked(client, firm_a_owner, db):
    """The system catalog says the flag is relevant. That is not enough.

    Configured means asked. A dimension the firm never configured produces no
    question, even though its flag applies to a service the firm offers.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    # The firm configures the boolean only. The wallet_type dimension under the
    # same applicable flag is left unconfigured.
    _configure(db, firm_id, catalog["staking"])

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    assert _dimension_keys(body) == ["has_staking"]
    assert WALLET_TYPE_QUESTION not in _question_texts(body)


def test_the_same_dimension_appears_once_configured(client, firm_a_owner, db):
    """The other half of the rule, and the half that proves the first half is
    not just a broken join returning nothing."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["staking"])

    before = client.get(endpoint(FIRM_A_SLUG)).json()
    assert "wallet_type" not in _dimension_keys(before)

    _configure(db, firm_id, catalog["wallet"])

    after = client.get(endpoint(FIRM_A_SLUG)).json()
    assert "wallet_type" in _dimension_keys(after)
    assert WALLET_TYPE_QUESTION in _question_texts(after)


# ---------------------------------------------------------------------------
# 3. Unit selection is part of the configured gate
# ---------------------------------------------------------------------------

def test_only_the_configured_unit_is_asked_about(client, firm_a_owner, db):
    """The firm configured the accounts unit. It is not asked about
    transaction counts, and the dimension's own text is never used to phrase a
    numeric question."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["volume"], unit=catalog["accounts"])

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    texts = _question_texts(body)

    assert ACCOUNTS_QUESTION in texts
    assert TXN_COUNT_QUESTION not in texts
    assert catalog["volume"].question_text not in texts


def test_two_configured_units_ask_two_questions(client, firm_a_owner, db):
    """One question per DISTINCT unit, per the assembly rule.

    This is the one case where a single dimension legitimately produces more
    than one question, and it must not be collapsed by the deduplication rule
    below.

    The two configs are on DIFFERENT BRANCHES because that is the only place
    this case can arise. uq_firm_dimension_configs_firm_dimension_branch is
    declared NULLS NOT DISTINCT, so a firm cannot configure one dimension flat
    twice no matter which units the two rows name; the second insert is refused
    by the database. So transaction_volume is configured once flat in accounts,
    and once under a tier of the coarser portfolio_value config in transaction
    counts.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    portfolio_config = _configure(
        db, firm_id, catalog["portfolio"], unit=catalog["usd_value"]
    )
    tiers = _add_tiers(db, firm_id, portfolio_config, [None, None])

    _configure(db, firm_id, catalog["volume"], unit=catalog["accounts"])
    _configure(
        db,
        firm_id,
        catalog["volume"],
        unit=catalog["transaction_count"],
        parent_tier=tiers[0],
    )

    body = client.get(endpoint(FIRM_A_SLUG)).json()

    # Ordered by hierarchy_rank (portfolio 1, volume 10), then by unit key
    # within the dimension that produced two questions.
    assert _dimension_keys(body) == [
        "portfolio_value",
        "transaction_volume",
        "transaction_volume",
    ]
    assert _question_texts(body) == [
        PORTFOLIO_QUESTION,
        ACCOUNTS_QUESTION,
        TXN_COUNT_QUESTION,
    ]


def test_a_config_with_no_unit_asks_nothing(client, firm_a_owner, db):
    """The ON DELETE SET NULL case: the system unit was removed from the
    catalog and the firm's config survived without one.

    A numeric question with no unit cannot be phrased to a lead, so it is
    omitted entirely. The answer is then never collected and the service routes
    to quote downstream, which is the designed worst case.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["volume"], unit=None)
    _configure(db, firm_id, catalog["staking"])

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    # The unitless numeric dimension is gone; the rest of the form is intact.
    assert _dimension_keys(body) == ["has_staking"]


# ---------------------------------------------------------------------------
# 4. Deduplication across branches
# ---------------------------------------------------------------------------

def test_a_dimension_configured_on_two_branches_is_asked_once(
    client, firm_a_owner, db
):
    """Chains shape pricing, not question visibility (Addendum 2).

    wallet_type is configured twice: once flat and once hanging under a tier of
    the transaction volume config. That is two rows in firm_dimension_configs
    and exactly one question.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    volume_config = _configure(
        db, firm_id, catalog["volume"], unit=catalog["transaction_count"]
    )
    tiers = _add_tiers(db, firm_id, volume_config, [None, None])

    _configure(db, firm_id, catalog["wallet"])
    _configure(db, firm_id, catalog["wallet"], parent_tier=tiers[0])

    # Both rows really are in the database, so the assertion below is about
    # deduplication and not about a failed insert.
    config_row_count = db.execute(
        select(func.count(FirmDimensionConfig.id)).where(
            FirmDimensionConfig.firm_id == firm_id,
            FirmDimensionConfig.dimension_id == catalog["wallet"].id,
        )
    ).scalar_one()
    assert config_row_count == 2

    keys = _dimension_keys(client.get(endpoint(FIRM_A_SLUG)).json())
    assert keys.count("wallet_type") == 1, (
        f"wallet_type was asked {keys.count('wallet_type')} times: {keys}"
    )


# ---------------------------------------------------------------------------
# 5. Unpriced but configured is still asked (Andrew's ruling)
# ---------------------------------------------------------------------------

def test_a_config_whose_tiers_are_all_unpriced_still_asks_its_question(
    client, firm_a_owner, db
):
    """Configured means asked; priced means automated. Two separate gates.

    Every tier here is NULL-priced, so nothing about this dimension is
    automatable. The question is asked anyway. The unpriced answer routes to
    quote at resolution time, which is downstream and none of this endpoint's
    business.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040, base_fee=None)

    config = _configure(
        db, firm_id, catalog["volume"], unit=catalog["transaction_count"]
    )
    tiers = _add_tiers(db, firm_id, config, [None, None])
    assert all(tier.price is None for tier in tiers)

    texts = _question_texts(client.get(endpoint(FIRM_A_SLUG)).json())
    assert TXN_COUNT_QUESTION in texts


def test_an_informational_config_is_asked_like_any_other(client, firm_a_owner, db):
    """role never reaches this endpoint, so an informational config is
    indistinguishable from a priced one in the response."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["staking"], role=DimensionRole.informational)

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    assert _dimension_keys(body) == ["has_staking"]
    assert "role" not in _questions(body)[0]


# ---------------------------------------------------------------------------
# 6. Tenant isolation
# ---------------------------------------------------------------------------

def test_one_firms_configuration_never_appears_in_anothers(
    client, firm_a_owner, firm_b_owner, db
):
    """Asserted on CONTENT, not on counts.

    Both firms offer the same service and configure the same dimension in
    different units, so a leak shows up as the wrong question text rather than
    as a wrong number of questions. Two firms with one question each would pass
    a count-based check while serving each other's forms.
    """
    catalog = _seed_catalog(db)
    firm_a_id = uuid.UUID(firm_a_owner["firm_id"])
    firm_b_id = uuid.UUID(firm_b_owner["firm_id"])

    _offer(db, firm_a_id, TAX_1040, base_fee=BASE_FEE)
    _configure(db, firm_a_id, catalog["volume"], unit=catalog["transaction_count"])
    _configure(db, firm_a_id, catalog["wallet"])

    _offer(db, firm_b_id, TAX_1040, base_fee=Decimal("9999.11"))
    _configure(db, firm_b_id, catalog["volume"], unit=catalog["accounts"])

    body_a = client.get(endpoint(FIRM_A_SLUG)).json()
    body_b = client.get(endpoint(FIRM_B_SLUG)).json()

    assert body_a["slug"] == FIRM_A_SLUG
    assert body_b["slug"] == FIRM_B_SLUG

    texts_a = _question_texts(body_a)
    texts_b = _question_texts(body_b)

    # Firm A asks about transaction counts and wallets, never about accounts.
    assert TXN_COUNT_QUESTION in texts_a
    assert WALLET_TYPE_QUESTION in texts_a
    assert ACCOUNTS_QUESTION not in texts_a, (
        "Firm B's configured unit is being asked about on Firm A's form."
    )

    # Firm B asks about accounts only, and never sees Firm A's wallet config.
    assert ACCOUNTS_QUESTION in texts_b
    assert TXN_COUNT_QUESTION not in texts_b
    assert WALLET_TYPE_QUESTION not in texts_b, (
        "Firm A's configured dimension is being asked about on Firm B's form."
    )
    assert "wallet_type" not in _dimension_keys(body_b)


# ---------------------------------------------------------------------------
# 7. The offered gate
# ---------------------------------------------------------------------------

def test_a_service_that_is_not_offered_is_absent(client, firm_a_owner, db):
    """is_offered false and no row at all are the same fact, and both exclude
    the service."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # is_offered false, with a configured dimension behind it so the exclusion
    # is not just an empty join.
    _offer(db, firm_id, TAX_1040, is_offered=False)
    _configure(db, firm_id, catalog["staking"])
    # 1065 gets no row at all.

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    assert body["services"] == []
    assert body["firm_name"] == "Firm A CPA"


def test_an_offered_service_with_nothing_configured_has_empty_questions(
    client, firm_a_owner, db
):
    """Empty is a real state, not an error. The service still appears."""
    _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    response = client.get(endpoint(FIRM_A_SLUG))
    assert response.status_code == 200
    body = response.json()

    assert len(body["services"]) == 1
    assert body["services"][0]["engagement_type"] == TAX_1040
    assert body["services"][0]["questions"] == []


def test_a_firm_offering_nothing_returns_an_empty_list_and_200(
    client, firm_a_owner, db
):
    _seed_catalog(db)

    response = client.get(endpoint(FIRM_A_SLUG))
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["services"] == []
    assert body["slug"] == FIRM_A_SLUG
    assert body["firm_name"] == "Firm A CPA"


def test_the_canonical_label_comes_from_the_backend_source_of_truth(
    client, firm_a_owner, db
):
    """label is read from ENGAGEMENT_TYPE_LABELS, not hand-copied into the
    schema layer. The letter templates settings tab drift is the cautionary
    tale for what a second copy of a label list turns into."""
    _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    assert body["services"][0]["label"] == (
        ENGAGEMENT_TYPE_LABELS[EngagementType.tax_return_1040]
    )


# ---------------------------------------------------------------------------
# 8. Inactive filtering
# ---------------------------------------------------------------------------

def test_an_inactive_flags_dimension_is_never_asked(client, firm_a_owner, db):
    """The legacy flag is mapped to the 1040 and the firm HAS configured its
    dimension. It is excluded because the flag is inactive, which is the only
    thing separating it from the crypto flag beside it."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["staking"])
    _configure(db, firm_id, catalog["legacy_dimension"])

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    assert _dimension_keys(body) == ["has_staking"]
    assert LEGACY_QUESTION not in _question_texts(body)


def test_inactive_vocabulary_options_are_not_offered(client, firm_a_owner, db):
    """A lead must not be offered an answer the system has retired."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["wallet"])

    question = _questions(client.get(endpoint(FIRM_A_SLUG)).json())[0]
    labels = [option["label"] for option in question["options"]]

    assert labels == ["Custodial exchange", "Self hosted"], labels
    assert "Retired option" not in labels
    # Ordered by key, as the assembly rule specifies: custodial before
    # self_hosted.
    assert [option["id"] for option in question["options"]] == [
        str(catalog["custodial"].id),
        str(catalog["self_hosted"].id),
    ]


def test_a_flag_that_applies_to_another_service_is_not_asked_here(
    client, firm_a_owner, db
):
    """The rental flag is active and configured. It applies to the 1065, which
    this firm does not offer, so it appears nowhere."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["staking"])
    _configure(db, firm_id, catalog["rental_dimension"])

    body = client.get(endpoint(FIRM_A_SLUG)).json()
    assert _dimension_keys(body) == ["has_staking"]
    assert RENTAL_QUESTION not in _question_texts(body)


# ---------------------------------------------------------------------------
# 9. Unknown slug
# ---------------------------------------------------------------------------

def test_unknown_slug_is_404_with_the_shared_message(client, db):
    """Same status and same message as GET /intake/{slug}/config, so the error
    shape cannot be used to enumerate which firms exist."""
    response = client.get(endpoint("no-such-firm-anywhere"))
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Intake form not found"

    existing = client.get("/intake/no-such-firm-anywhere/config")
    assert existing.status_code == 404
    assert existing.json()["detail"] == response.json()["detail"]


def test_no_authentication_is_required(client, firm_a_owner, db):
    """The endpoint is public on purpose. No header of any kind is sent here."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["staking"])

    response = client.get(endpoint(FIRM_A_SLUG))
    assert response.status_code == 200, response.text
    assert _dimension_keys(response.json()) == ["has_staking"]


# ---------------------------------------------------------------------------
# 10. Chain invisibility, and stable ordering
# ---------------------------------------------------------------------------

def test_a_chained_question_is_shaped_exactly_like_a_flat_one(
    client, firm_a_owner, db
):
    """A dependent config produces an ordinary question.

    Compared key by key against a flat question in the same response, so a
    chained question that carried one extra field would fail here even if that
    field were not on the forbidden list.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    # Flat.
    _configure(db, firm_id, catalog["staking"])
    # Chained: wallet_type hangs under a tier of the transaction volume config.
    volume_config = _configure(
        db, firm_id, catalog["volume"], unit=catalog["transaction_count"]
    )
    tiers = _add_tiers(db, firm_id, volume_config, [None, None])
    chained = _configure(db, firm_id, catalog["wallet"], parent_tier=tiers[0])
    assert chained.parent_tier_id is not None

    questions = _questions(client.get(endpoint(FIRM_A_SLUG)).json())
    by_key = {q["dimension_key"]: q for q in questions}

    flat_question = by_key["has_staking"]
    chained_question = by_key["wallet_type"]

    assert set(flat_question.keys()) == set(chained_question.keys()), (
        "A chained question has a different shape from a flat one, so the "
        "chain is visible to the form."
    )
    assert chained_question["question_text"] == WALLET_TYPE_QUESTION
    assert chained_question["options"], "The chained categorical lost its options."


def test_question_order_is_stable_across_identical_calls(client, firm_a_owner, db):
    """Ordered by flag key, then hierarchy_rank, then dimension key. Same
    input, same output, every call."""
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    # Configured out of hierarchy order on purpose.
    _configure(db, firm_id, catalog["wallet"])
    _configure(db, firm_id, catalog["staking"])
    _configure(db, firm_id, catalog["volume"], unit=catalog["transaction_count"])

    first = client.get(endpoint(FIRM_A_SLUG)).json()
    second = client.get(endpoint(FIRM_A_SLUG)).json()

    assert first == second

    # hierarchy_rank 5, 10, 20 within the one crypto flag.
    assert _dimension_keys(first) == [
        "has_staking",
        "transaction_volume",
        "wallet_type",
    ]


# ---------------------------------------------------------------------------
# 11. SCOPE AWARENESS AND THE PRESENTATION FIELDS (August 18, 2026)
#
# Everything above this line was written when every config in this file was
# blanket, because _configure had no way to express a scope. The endpoint was
# reworked on August 18, 2026 to resolve per engagement type, and these are the
# tests for that. The two failures they pin were both REAL and both present
# before the rework: an override authored for one engagement type was asked on
# every type the flag mapped to, and an override attached to a DORMANT service
# was asked on every ACTIVE one.
# ---------------------------------------------------------------------------

# Distinctive money values for the scoped guard, in the same spirit as the
# blanket ones above: no coincidental substring match is possible.
SCOPED_TIER_PRICE = Decimal("9119.11")
BLANKET_TIER_PRICE = Decimal("6116.61")
EXPLICIT_ZERO = Decimal("0.00")


def _seed_scoped_firm(db, firm_id, catalog):
    """A firm whose 1040 is governed by a SCOPED override, not the blanket tree.

    The blanket transaction_volume config is priced and is the LOSER: the scoped
    root for the same dimension replaces it wholesale for this engagement type.
    The scoped tree's tiers deliberately carry all three price states at once:

        a real price   -> the ordinary commercial fact
        explicit 0.00  -> priced at zero, which is NOT unpriced
        NULL           -> unpriced, which is NOT zero

    The two together are the null-versus-zero law in fixture form. In the
    stripped output all three must be equally invisible, and the question must
    be asked identically regardless of which of the three governs it. A response
    that renders differently for a zero-priced tier than for a null one has
    started leaking pricing through its shape rather than its fields.

    Returns the catalog entry the scope points at.
    """
    entry = _offer(db, firm_id, TAX_1040, base_fee=BASE_FEE)

    # Blanket, priced, phrased in transactions. Loses to the scoped root below.
    blanket_volume = _configure(
        db, firm_id, catalog["volume"], unit=catalog["transaction_count"]
    )
    _add_tiers(db, firm_id, blanket_volume, [BLANKET_TIER_PRICE])

    # Scoped to this firm's own 1040 entry, phrased in accounts. Wins.
    scoped_volume = _configure(
        db, firm_id, catalog["volume"], unit=catalog["accounts"], scope=entry
    )
    _add_tiers(
        db, firm_id, scoped_volume, [SCOPED_TIER_PRICE, EXPLICIT_ZERO, None]
    )
    return entry


def test_no_commercial_fact_survives_from_a_scoped_override(
    client, firm_a_owner, db
):
    """THE GUARD, on the scoped branch. Sibling of the blanket guard above.

    The blanket guard cannot cover this. Every fixture it walks is blanket, so
    it exercises one of the two branches the service now has, and a leak that
    existed only on the scoped branch would pass it. This test is the same
    forbidden-key machinery aimed at the branch the rework added.

    Watched red three times before being accepted, because one control was not
    enough to show this test earns its place:

    1. A `price` field added to IntakeQuestionOut and populated from the
       resolver's scoped tiers. Both this test and the blanket guard went red on
       the forbidden key. That proves the walk works and proves nothing about
       whether THIS test was needed, since the blanket guard caught it too.
    2. The scoped price leaked BY VALUE into flag_name, an entirely legitimate
       key no forbidden-key walk can see, and only on the overridden branch.
       The blanket guard PASSED. This test failed on the by-value assertion.
       That is the one that matters: it is a defect the pre-existing guard is
       structurally incapable of catching, which is this test's whole reason to
       exist.
    3. The same leak narrowed to the EXPLICIT ZERO tier alone, to confirm the
       null-versus-zero arm is live and 0.00 is treated as the real price it is
       rather than as an absence. Red on "The value 0.00 appears".

    The three-step restore is recorded in the session report.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _seed_scoped_firm(db, firm_id, catalog)

    response = client.get(endpoint(FIRM_A_SLUG))
    assert response.status_code == 200, response.text
    body = response.json()

    # ------------------------------------------------------------------
    # PROVE THE SCOPED BRANCH IS WHAT PRODUCED THIS RESPONSE. Without this,
    # the walk below could be measuring the blanket path and would pass just
    # as happily while the scoped branch leaked freely. The scoped tree is
    # phrased in ACCOUNTS and the blanket one in TRANSACTIONS, so the question
    # text is what tells the two apart.
    # ------------------------------------------------------------------
    texts = _question_texts(body)
    assert ACCOUNTS_QUESTION in texts, (
        f"The scoped override did not win, so this test never reached the "
        f"branch it exists to guard. Questions served: {texts}"
    )
    assert TXN_COUNT_QUESTION not in texts, (
        "The blanket config was served alongside the scoped override that "
        "replaced it. Precedence is wholesale, so exactly one of these two "
        f"questions may appear. Questions served: {texts}"
    )

    # ------------------------------------------------------------------
    # The contract itself, on this branch.
    # ------------------------------------------------------------------
    offenders = [
        (path, key) for path, key in _walk_keys(body) if key in FORBIDDEN_KEYS
    ]
    assert not offenders, (
        "The public intake response leaks commercial facts from a SCOPED "
        f"override. Forbidden keys found at: {offenders}"
    )

    config = get_public_intake_config(db, firm_id=firm_id)
    dumped = config.model_dump()
    decimals = [
        (path, value)
        for path, value in _walk_values(dumped)
        if isinstance(value, Decimal)
    ]
    assert not decimals, (
        f"Decimal-typed values survived from the scoped branch at: {decimals}"
    )

    dump_offenders = [
        (path, key) for path, key in _walk_keys(dumped) if key in FORBIDDEN_KEYS
    ]
    assert not dump_offenders, (
        f"Forbidden keys on the schema objects themselves: {dump_offenders}"
    )

    # By value. EXPLICIT_ZERO is in this list on purpose: an explicit 0.00 is a
    # real price a firm chose, and leaking it tells a lead this service is free.
    # It is exactly as forbidden as the four-figure one beside it.
    serialized = response.text
    for money in (
        str(BASE_FEE),
        str(SCOPED_TIER_PRICE),
        str(BLANKET_TIER_PRICE),
        str(EXPLICIT_ZERO),
    ):
        assert money not in serialized, (
            f"The value {money} appears in the public response. A commercial "
            "fact is being served under some other name."
        )


def test_a_scoped_override_is_invisible_to_the_engagement_type_it_is_not_for(
    client, firm_a_owner, db
):
    """The bug the rework fixed, stated as a test.

    Before August 18, 2026 this failed: the service loaded every config the firm
    owned in one query and keyed them by dimension_id, so an override authored
    for the 1040 was asked on the 1065 as well. Nothing about the response said
    so, because the response carries no scope information; the 1065 simply asked
    a question its firm had never configured for it.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # THE CRYPTO FLAG IS MAPPED TO THE 1065 TOO, AND IT IS LOAD-BEARING.
    # The whole claim of this test is that SCOPE is what keeps the override off
    # the 1065. If the flag did not apply to the 1065 in the first place, the
    # applicability filter would drop the question for an unrelated reason and
    # this test would pass against code with no scope handling whatsoever. It
    # was written that way first, and the negative control caught it: the
    # control ran green until this mapping was added.
    db.add(
        ComplexityFlagEngagementType(
            flag_id=catalog["crypto"].id, engagement_type=PARTNERSHIP_1065
        )
    )
    db.commit()

    # Both services active.
    entry_1040 = _offer(db, firm_id, TAX_1040)
    _offer(db, firm_id, PARTNERSHIP_1065)

    # Blanket, so the 1065 has something of its own and the assertion below is
    # not just reading an empty service.
    _configure(db, firm_id, catalog["rental_dimension"])

    # Scoped to the 1040 ONLY.
    _configure(db, firm_id, catalog["wallet"], scope=entry_1040)

    body = client.get(endpoint(FIRM_A_SLUG)).json()

    assert WALLET_TYPE_QUESTION in _question_texts(body, TAX_1040), (
        "The 1040 lost the override that was authored for it."
    )
    assert RENTAL_QUESTION in _question_texts(body, PARTNERSHIP_1065), (
        "The 1065 lost its own blanket question, so this test is not "
        "measuring what it claims to."
    )
    assert WALLET_TYPE_QUESTION not in _question_texts(body, PARTNERSHIP_1065), (
        "A scoped override authored for the 1040 is being asked on the 1065. "
        "This is the exact defect the August 18, 2026 rework fixed."
    )


def test_a_dormant_service_with_a_scoped_override_never_appears(
    client, firm_a_owner, db
):
    """A switched-off service does not shape the form, however configured it is.

    A firm may legitimately author overrides on a service before switching it
    on, so a dormant entry carrying a fully configured scoped tree is a normal
    state and not a broken one. It must contribute NOTHING: not its own entry in
    the payload, and not its questions to anybody else's.

    That second half is not hypothetical. Before the rework the dormant service
    was correctly kept out of the services list while its scoped config was
    still loaded into the shared question pool, so its questions were asked on
    every ACTIVE service the flag mapped to. The service was invisible and its
    configuration was not.

    Watched red twice, one control per half of the claim:

    1. The is_offered filter removed from the entries query. Red on the
       services-list assertion: the dormant service appeared in the payload.
    2. The pre-rework shape restored: every active service reading one global
       pool of the firm's configs, with the dormant service still correctly
       excluded from the services list. Red on the leak assertion, which is the
       half that actually reproduces the old defect.

    Control 2 ran GREEN on the first version of this fixture, which is why the
    crypto mapping above exists. Recorded in the session report.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    # THE CRYPTO FLAG IS MAPPED TO THE 1065 AS WELL, AND THAT IS LOAD-BEARING.
    # Without it the dormant service's override would sit on a flag that only
    # applies to the dormant service, and the "leaked onto somebody else"
    # assertion below could never fail no matter how broken the code was: the
    # applicability filter would drop it for reasons that have nothing to do
    # with dormancy. The two engagement types have to SHARE a flag for the leak
    # this test guards against to be expressible at all.
    db.add(
        ComplexityFlagEngagementType(
            flag_id=catalog["crypto"].id, engagement_type=PARTNERSHIP_1065
        )
    )
    db.commit()

    # Active, and configured, so the response is non-empty and the assertions
    # below are made against a real payload rather than an empty one.
    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["staking"])

    # DORMANT, and carrying a scoped override on a dimension whose flag applies
    # to the ACTIVE service too. This is the row that must reach nobody.
    dormant = _offer(db, firm_id, PARTNERSHIP_1065, is_offered=False)
    _configure(db, firm_id, catalog["wallet"], scope=dormant)

    response = client.get(endpoint(FIRM_A_SLUG))
    assert response.status_code == 200, response.text
    body = response.json()

    # The response has to be non-empty or everything below passes vacuously.
    assert STAKING_QUESTION in _question_texts(body, TAX_1040), (
        "The active service came back with nothing, so the absence of the "
        "dormant one proves nothing."
    )

    served = [service["engagement_type"] for service in body["services"]]
    assert served == [TAX_1040], (
        f"A dormant service appears in the public payload. Served: {served}"
    )

    # And its question reached nobody else either. Asserted against the whole
    # serialized response rather than one service, because the pre-rework
    # failure put it on a DIFFERENT service than the one it belonged to.
    assert WALLET_TYPE_QUESTION not in response.text, (
        "A dormant service's configured question is being asked somewhere in "
        "the public payload. The service was excluded; its configuration was "
        "not."
    )


def test_an_active_service_with_no_configuration_of_its_own_has_no_questions(
    client, firm_a_owner, db
):
    """Active-but-unconfigured is a legitimate state: the lead picks it and the
    engagement routes to quote.

    Stronger than test_an_offered_service_with_nothing_configured_has_empty_questions
    above, which seeds a firm that has configured NOTHING AT ALL. That one cannot
    tell "this service has no questions" apart from "the query returned nothing",
    because both produce the same empty list. Here the firm is configured, the
    other service is asking questions, and this one still has none of its own.

    Watched red before being accepted: the service was made to omit any entry
    whose question list came back empty. Recorded in the session report.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])

    _offer(db, firm_id, TAX_1040)
    _configure(db, firm_id, catalog["staking"])

    # Active, no configs of its own. The rental flag maps here and its dimension
    # is deliberately left unconfigured: applicable is not the same as asked.
    _offer(db, firm_id, PARTNERSHIP_1065)

    response = client.get(endpoint(FIRM_A_SLUG))
    assert response.status_code == 200, response.text
    body = response.json()

    served = [service["engagement_type"] for service in body["services"]]
    # Ordered by engagement_type ascending, which is the service's own ORDER BY.
    assert served == [TAX_1040, PARTNERSHIP_1065], (
        f"The unconfigured service was dropped instead of served empty. "
        f"Served: {served}"
    )
    assert _questions(body, PARTNERSHIP_1065) == []
    # The configured one still works, so the empty list above is a real answer
    # and not a symptom of the whole response having collapsed.
    assert _question_texts(body, TAX_1040) == [STAKING_QUESTION]


# ---------------------------------------------------------------------------
# 12. The presentation fields
# ---------------------------------------------------------------------------

def test_lead_facing_label_falls_back_to_the_canonical_label(
    client, firm_a_owner, db
):
    """LEAD_FACING_LABELS is sparse and empty today, so this is the live path.

    Absence is the designed default here, not a gap: the payload must always
    carry a renderable string so the form never has to implement the fallback
    itself and no two consumers can disagree about it.
    """
    _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    service = client.get(endpoint(FIRM_A_SLUG)).json()["services"][0]

    canonical = ENGAGEMENT_TYPE_LABELS[EngagementType.tax_return_1040]
    assert service["label"] == canonical
    assert service["lead_facing_label"] == canonical, (
        "With no override authored, lead_facing_label must serve the canonical "
        "label rather than null. A null here pushes the fallback onto every "
        "consumer of this endpoint."
    )


def test_lead_facing_label_serves_the_override_when_one_is_authored(
    client, firm_a_owner, db, monkeypatch
):
    """The populated half of the fallback, which no fixture can reach today.

    LEAD_FACING_LABELS ships empty, so the override branch is unreachable
    through data alone and is patched here instead. Patched on the SERVICE
    module rather than on app.core.enums, because the service imported the name
    at import time and rebinding the enums module attribute would leave the
    service reading its own original dict: the test would pass while measuring
    nothing, which is instance seventeen's shape exactly.
    """
    _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    monkeypatch.setattr(
        pricing_config_service,
        "LEAD_FACING_LABELS",
        {EngagementType.tax_return_1040: "Personal Taxes"},
    )

    service = client.get(endpoint(FIRM_A_SLUG)).json()["services"][0]

    assert service["lead_facing_label"] == "Personal Taxes"
    # The canonical label is NOT replaced by the override. They are two fields
    # for two audiences and the formal one still has to be there.
    assert service["label"] == (
        ENGAGEMENT_TYPE_LABELS[EngagementType.tax_return_1040]
    )


def test_category_is_null_when_the_type_is_not_mapped(client, firm_a_owner, db):
    """Null category is a real, permanent state, not a gap awaiting content.

    A type absent from ENGAGEMENT_TYPE_CATEGORIES is uncategorized and the form
    renders it in a flat list. There is deliberately no default bucket: guessing
    would put a service in front of leads under a heading its firm never chose.
    """
    _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    service = client.get(endpoint(FIRM_A_SLUG)).json()["services"][0]
    assert service["category"] is None


def test_category_serves_the_string_value_when_mapped(
    client, firm_a_owner, db, monkeypatch
):
    """Serialized as the plain string value, matching how kind is served.

    Patched on the service module for the same reason as the label override
    above. Ben's form switches on this string, so it has to be the enum's value
    and not its repr.
    """
    _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _offer(db, firm_id, TAX_1040)

    monkeypatch.setattr(
        pricing_config_service,
        "ENGAGEMENT_TYPE_CATEGORIES",
        {EngagementType.tax_return_1040: ServiceCategory.tax},
    )

    service = client.get(endpoint(FIRM_A_SLUG)).json()["services"][0]
    assert service["category"] == "tax"
    assert isinstance(service["category"], str)


def test_the_presentation_fields_are_not_commercial_facts(
    client, firm_a_owner, db, monkeypatch
):
    """The two new fields, populated, still pass the stripping walk.

    They were added to a response whose entire justification is that it carries
    no commercial fact. A bucket name and a friendly service name are not one,
    but that claim is worth a test rather than a comment, and the walk has to be
    run with them POPULATED or it is not walking them at all.
    """
    catalog = _seed_catalog(db)
    firm_id = uuid.UUID(firm_a_owner["firm_id"])
    _seed_rich_firm(db, firm_id, catalog)

    monkeypatch.setattr(
        pricing_config_service,
        "LEAD_FACING_LABELS",
        {EngagementType.tax_return_1040: "Personal Taxes"},
    )
    monkeypatch.setattr(
        pricing_config_service,
        "ENGAGEMENT_TYPE_CATEGORIES",
        {EngagementType.tax_return_1040: ServiceCategory.tax},
    )

    response = client.get(endpoint(FIRM_A_SLUG))
    body = response.json()

    service = body["services"][0]
    assert service["lead_facing_label"] == "Personal Taxes"
    assert service["category"] == "tax"

    offenders = [
        (path, key) for path, key in _walk_keys(body) if key in FORBIDDEN_KEYS
    ]
    assert not offenders, f"Forbidden keys found at: {offenders}"
