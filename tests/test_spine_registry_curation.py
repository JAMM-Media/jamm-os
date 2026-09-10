# tests/test_spine_registry_curation.py

"""Registry curation schema and validation service (Sep 10, 2026 session).

Pins rulings R1 to R7: one axes list per metric, axis keys resolved per kind
against their own source of truth, directional related metrics, no
self-relation, curation fields shipping NULL, and 422 for a key that does not
resolve. Every write refusal here is also checked for what it left behind,
because a refusal that writes on its way out is the failure the service's
ordering exists to prevent.

The test database is built from models by create_all, not from migrations,
so the eleven seed rows are inserted here from the same shared list the
migration uses. Catalog rows (complexity flags and dimensions) are seeded
from the models too; the catalog is system-owned and carries no firm_id.
"""

import uuid

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import func, select, text

from app.core.enums import (
    BetterDirection,
    DimensionKind,
    MetricAxisKind,
    MetricEntityType,
    MetricPillar,
    MetricWindowType,
)
from app.core.metric_seed_data import SEED_METRICS
from app.crud import metric_registry as crud
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_flag import ComplexityFlag
from app.models.metric_registry import MetricRegistry
from app.models.metric_registry_axis import MetricRegistryAxis
from app.models.metric_registry_relation import MetricRegistryRelation
from app.schemas.metric_registry import MetricRegistryCreate, MetricRegistryUpdate
from app.schemas.metric_registry_axis import MetricRegistryAxisCreate
from app.schemas.metric_registry_relation import MetricRegistryRelationCreate
from app.services import metric_registry_service as service
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def seeded(db):
    """The eleven locked seed rows, inserted exactly as the migration does,
    with every curation field left at its default."""
    for key, display_name, unit, better_direction, benchmark_eligible, tier, window_type in SEED_METRICS:
        db.add(
            MetricRegistry(
                key=key,
                display_name=display_name,
                unit=unit,
                better_direction=BetterDirection(better_direction),
                benchmark_eligible=benchmark_eligible,
                tier=tier,
                window_type=MetricWindowType(window_type),
            )
        )
    db.commit()
    return {row.key: row for row in db.execute(select(MetricRegistry)).scalars()}


@pytest.fixture
def metric_a(seeded):
    return seeded["engagement_velocity"]


@pytest.fixture
def metric_b(seeded):
    return seeded["invoice_payment_time"]


@pytest.fixture
def catalog(db):
    """One real complexity flag with one real dimension.

    clean_db truncates every table between tests, so the catalog is always
    empty here and is seeded from the models. No firm_id: the catalog is
    system-owned (August 13, 2026 carve-out).
    """
    flag = ComplexityFlag(key="crypto", name="Cryptocurrency activity")
    db.add(flag)
    db.flush()
    dimension = ComplexityDimension(
        flag_id=flag.id, key="transaction_volume", kind=DimensionKind.boolean
    )
    db.add(dimension)
    db.commit()
    return flag, dimension


def _axis(metric, kind, key, sort_order=0):
    return MetricRegistryAxisCreate(
        metric_id=metric.id, axis_kind=kind, axis_key=key, sort_order=sort_order
    )


def _relation(metric, related, sort_order=0):
    return MetricRegistryRelationCreate(
        metric_id=metric.id, related_metric_id=related.id, sort_order=sort_order
    )


def _axes_snapshot(db, metric_id) -> tuple[list, list]:
    """(axes the working session sees after a flush, axes a fresh session sees).

    A refusal that wrote on its way out changes one or both: a row or a
    deletion left pending in the working session changes the first, a
    committed one changes both. Reading only through a fresh session would
    miss the pending flavour, which is the instance-eighteen trap: the test
    would stay green while the service leaked. Load-bearing; keep both reads.
    """
    db.flush()
    query = (
        select(MetricRegistryAxis.axis_kind, MetricRegistryAxis.axis_key)
        .where(MetricRegistryAxis.metric_id == metric_id)
        .order_by(MetricRegistryAxis.axis_kind, MetricRegistryAxis.axis_key)
    )
    in_session = [tuple(row) for row in db.execute(query)]
    other = TestingSessionLocal()
    try:
        committed = [tuple(row) for row in other.execute(query)]
    finally:
        other.close()
    return in_session, committed


def _relations_snapshot(db, metric_id) -> tuple[list, list]:
    """Same two-sided read for relations. See _axes_snapshot."""
    db.flush()
    query = (
        select(MetricRegistryRelation.related_metric_id)
        .where(MetricRegistryRelation.metric_id == metric_id)
        .order_by(MetricRegistryRelation.sort_order)
    )
    in_session = [row[0] for row in db.execute(query)]
    other = TestingSessionLocal()
    try:
        committed = [row[0] for row in other.execute(query)]
    finally:
        other.close()
    return in_session, committed


# ---------------------------------------------------------------------------
# Seed rows and storage
# ---------------------------------------------------------------------------

def test_existing_seed_rows_survive_with_curation_fields_unset(db, seeded):
    """All eleven seed keys are readable and every curation field is unset:
    pillar, entity_type and attention_weight None, synonyms an empty list.
    NULL means not yet authored (ruling R6)."""
    expected_keys = {key for key, *_ in SEED_METRICS}
    assert set(seeded) == expected_keys
    assert len(seeded) == 11
    for row in seeded.values():
        assert row.pillar is None
        assert row.entity_type is None
        assert row.attention_weight is None
        assert row.synonyms == []


def test_pillar_and_entity_type_and_axis_kind_stored_as_non_native_strings(db, seeded):
    """Copy of test_better_direction_stored_as_non_native_enum_string for the
    three new enum columns: the stored value is a plain string and the column
    type is character varying, never a native enum type."""
    metric = seeded["engagement_velocity"]
    metric.pillar = MetricPillar.performance
    metric.entity_type = MetricEntityType.engagement
    db.add(MetricRegistryAxis(
        metric_id=metric.id,
        axis_kind=MetricAxisKind.engagement_category,
        axis_key="tax",
    ))
    db.commit()

    raw = db.execute(
        text("SELECT pillar, entity_type FROM metric_registry WHERE key = :key"),
        {"key": "engagement_velocity"},
    ).one()
    assert raw == ("performance", "engagement")
    assert all(isinstance(value, str) for value in raw)

    raw_kind = db.execute(
        text("SELECT axis_kind FROM metric_registry_axes WHERE metric_id = :id"),
        {"id": str(metric.id)},
    ).scalar_one()
    assert raw_kind == "engagement_category"
    assert isinstance(raw_kind, str)

    for table, column in (
        ("metric_registry", "pillar"),
        ("metric_registry", "entity_type"),
        ("metric_registry_axes", "axis_kind"),
    ):
        column_type = db.execute(
            text(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_name = :table AND column_name = :column"
            ),
            {"table": table, "column": column},
        ).scalar_one()
        assert column_type in ("character varying", "text"), (table, column, column_type)


def test_synonyms_validator_strips_dedupes_and_refuses_case_duplicates():
    """Whitespace is stripped, empties dropped, and two synonyms differing
    only by letter case are refused with a plain-words message. Both the
    base schema and the update schema apply the same rule."""
    base = dict(
        key="k", display_name="d", unit="u",
        better_direction=BetterDirection.lower,
        window_type=MetricWindowType.weekly_summary,
    )
    cleaned = MetricRegistryCreate(**base, synonyms=[" Speed ", "", "   ", "velocity"])
    assert cleaned.synonyms == ["Speed", "velocity"]

    with pytest.raises(ValidationError) as exc:
        MetricRegistryCreate(**base, synonyms=["Speed", "speed"])
    assert "Synonyms must be unique" in str(exc.value)
    assert "'speed' appears more than once" in str(exc.value)

    with pytest.raises(ValidationError):
        MetricRegistryUpdate(synonyms=["Turnaround", " turnaround "])
    assert MetricRegistryUpdate(synonyms=None).synonyms is None
    assert MetricRegistryUpdate(synonyms=[" a ", "b"]).synonyms == ["a", "b"]


# ---------------------------------------------------------------------------
# Axis resolution, one accept and one refuse per kind (ruling R3)
# ---------------------------------------------------------------------------

def test_engagement_category_accepts_tax_and_refuses_payroll_services(db):
    """engagement_category resolves against ServiceCategory; the refusal lists
    the valid categories, built from the enum rather than hard-coded."""
    service.resolve_axis_key(db, MetricAxisKind.engagement_category, "tax")
    with pytest.raises(HTTPException) as exc:
        service.resolve_axis_key(db, MetricAxisKind.engagement_category, "payroll_services")
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        "Unknown engagement category 'payroll_services'. "
        "Valid categories are: tax, bookkeeping, advisory."
    )


def test_complexity_flag_accepts_real_key_and_refuses_unknown(db, catalog):
    """complexity_flag resolves against complexity_flags.key."""
    flag, _ = catalog
    service.resolve_axis_key(db, MetricAxisKind.complexity_flag, flag.key)
    with pytest.raises(HTTPException) as exc:
        service.resolve_axis_key(db, MetricAxisKind.complexity_flag, "no_such_flag")
    assert exc.value.status_code == 422
    assert exc.value.detail == "No complexity flag with key 'no_such_flag' exists in the catalog."


def test_complexity_dimension_accepts_real_pair(db, catalog):
    """complexity_dimension resolves against the (flag key, dimension key)
    pair written flag_key.dimension_key."""
    flag, dimension = catalog
    service.resolve_axis_key(
        db, MetricAxisKind.complexity_dimension, f"{flag.key}.{dimension.key}"
    )


def test_complexity_dimension_refuses_unknown_dimension_naming_flag_by_label(db, catalog):
    """When the flag resolves but the dimension does not, the message names
    the flag by its display name, because a label exists."""
    flag, _ = catalog
    with pytest.raises(HTTPException) as exc:
        service.resolve_axis_key(
            db, MetricAxisKind.complexity_dimension, f"{flag.key}.no_such_dimension"
        )
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        "Complexity flag 'Cryptocurrency activity' has no dimension with key "
        "'no_such_dimension'."
    )


def test_complexity_dimension_refuses_unknown_flag(db, catalog):
    """When the flag part of the pair does not resolve, the flag message is
    used and the dimension part is never looked at."""
    _, dimension = catalog
    with pytest.raises(HTTPException) as exc:
        service.resolve_axis_key(
            db, MetricAxisKind.complexity_dimension, f"no_such_flag.{dimension.key}"
        )
    assert exc.value.status_code == 422
    assert exc.value.detail == "No complexity flag with key 'no_such_flag' exists in the catalog."


def test_complexity_dimension_key_without_dot_refused_at_schema_layer(seeded):
    """Shape is the schema's job: a complexity_dimension key with no dot never
    reaches the service."""
    metric = seeded["engagement_velocity"]
    with pytest.raises(ValidationError) as exc:
        _axis(metric, MetricAxisKind.complexity_dimension, "transaction_volume")
    assert "must be written as flag_key.dimension_key" in str(exc.value)


def test_complexity_dimension_key_without_dot_refused_at_service_layer(db):
    """Belt to the schema's braces: resolve_axis_key called directly with a
    dotless key refuses with the same message rather than guessing."""
    with pytest.raises(HTTPException) as exc:
        service.resolve_axis_key(db, MetricAxisKind.complexity_dimension, "transaction_volume")
    assert exc.value.status_code == 422
    assert exc.value.detail == (
        "A complexity dimension axis key must be written as flag_key.dimension_key."
    )


def test_referral_source_accepts_client_referral_and_refuses_billboard(db):
    """referral_source resolves against ReferralSource."""
    service.resolve_axis_key(db, MetricAxisKind.referral_source, "client_referral")
    with pytest.raises(HTTPException) as exc:
        service.resolve_axis_key(db, MetricAxisKind.referral_source, "billboard")
    assert exc.value.status_code == 422
    assert exc.value.detail == "Unknown referral source 'billboard'."


# ---------------------------------------------------------------------------
# Write ordering and refusals
# ---------------------------------------------------------------------------

def test_refused_axis_writes_nothing(db, metric_a):
    """A refused add_axis leaves the metric's axes exactly as they were.

    Read through the working session after a flush and through a fresh
    session, so both a pending row and a committed row would show. This is
    what the resolve-before-insert ordering exists for."""
    before = _axes_snapshot(db, metric_a.id)
    assert before == ([], [])
    with pytest.raises(HTTPException) as exc:
        service.add_axis(db, metric_a.id, _axis(metric_a, MetricAxisKind.referral_source, "billboard"))
    assert exc.value.status_code == 422
    assert _axes_snapshot(db, metric_a.id) == before, "the refused axis was written"


def test_add_axis_stores_the_row(db, metric_a):
    """The happy path, so the refusal tests are measured against a door that
    does write when allowed."""
    row = service.add_axis(db, metric_a.id, _axis(metric_a, MetricAxisKind.engagement_category, "tax", 3))
    assert row.id is not None
    stored = crud.list_axes_for_metric(db, metric_a.id)
    assert [(a.axis_kind, a.axis_key, a.sort_order) for a in stored] == [
        (MetricAxisKind.engagement_category, "tax", 3)
    ]


def test_add_axis_refuses_unknown_metric_with_404(db, seeded):
    """The metric must exist before anything is resolved."""
    ghost = uuid.uuid4()
    payload = MetricRegistryAxisCreate(
        metric_id=ghost, axis_kind=MetricAxisKind.engagement_category, axis_key="tax"
    )
    with pytest.raises(HTTPException) as exc:
        service.add_axis(db, ghost, payload)
    assert exc.value.status_code == 404
    assert exc.value.detail == "No metric with that id."


def test_duplicate_axis_is_refused_with_plain_message(db, metric_a):
    """The same (metric, kind, key) twice is refused by a read before insert,
    with our message, not by an IntegrityError."""
    service.add_axis(db, metric_a.id, _axis(metric_a, MetricAxisKind.engagement_category, "tax"))
    before = _axes_snapshot(db, metric_a.id)
    with pytest.raises(HTTPException) as exc:
        service.add_axis(db, metric_a.id, _axis(metric_a, MetricAxisKind.engagement_category, "tax"))
    assert exc.value.status_code == 422
    assert exc.value.detail == "This metric already lists that axis."
    assert _axes_snapshot(db, metric_a.id) == before


def test_self_relation_refused_at_schema_and_at_service(db, metric_a):
    """The schema refuses first. A payload that skips the schema validator
    (model_construct) is refused by the service with the same message, and
    nothing is written either way."""
    with pytest.raises(ValidationError) as exc:
        _relation(metric_a, metric_a)
    assert "A metric cannot list itself as a related metric." in str(exc.value)

    payload = MetricRegistryRelationCreate.model_construct(
        metric_id=metric_a.id, related_metric_id=metric_a.id, sort_order=0
    )
    with pytest.raises(HTTPException) as exc:
        service.add_relation(db, metric_a.id, payload)
    assert exc.value.status_code == 422
    assert exc.value.detail == "A metric cannot list itself as a related metric."
    assert crud.list_relations_for_metric(db, metric_a.id) == []


def test_duplicate_relation_refused(db, metric_a, metric_b):
    """The same (metric, related) pair twice is refused with a plain message."""
    service.add_relation(db, metric_a.id, _relation(metric_a, metric_b))
    with pytest.raises(HTTPException) as exc:
        service.add_relation(db, metric_a.id, _relation(metric_a, metric_b))
    assert exc.value.status_code == 422
    assert exc.value.detail == "This metric already lists that related metric."
    assert len(crud.list_relations_for_metric(db, metric_a.id)) == 1


def test_relation_refuses_missing_related_metric_naming_source_by_key(db, metric_a):
    """The related side missing is a 404 that names the source metric by key,
    because that row can be read."""
    payload = MetricRegistryRelationCreate(
        metric_id=metric_a.id, related_metric_id=uuid.uuid4()
    )
    with pytest.raises(HTTPException) as exc:
        service.add_relation(db, metric_a.id, payload)
    assert exc.value.status_code == 404
    assert exc.value.detail == (
        "Metric 'engagement_velocity' names a related metric that does not exist."
    )


def test_relation_is_directional(db, metric_a, metric_b):
    """A lists B. B's related list is empty (ruling R4), through the crud read
    and through the ORM relationship."""
    service.add_relation(db, metric_a.id, _relation(metric_a, metric_b))
    assert [r.related_metric_id for r in crud.list_relations_for_metric(db, metric_a.id)] == [metric_b.id]
    assert crud.list_relations_for_metric(db, metric_b.id) == []
    db.expire_all()
    assert [r.related_metric_id for r in metric_a.related] == [metric_b.id]
    assert metric_b.related == []


def test_replace_axes_is_all_or_nothing(db, metric_a):
    """Two good items and one bad: the replacement is refused and the metric's
    axes are exactly what they were before. Nothing is deleted until every
    item has resolved."""
    service.add_axis(db, metric_a.id, _axis(metric_a, MetricAxisKind.engagement_category, "tax"))
    before = _axes_snapshot(db, metric_a.id)
    assert before == (
        [(MetricAxisKind.engagement_category, "tax")],
        [(MetricAxisKind.engagement_category, "tax")],
    )

    with pytest.raises(HTTPException) as exc:
        service.replace_axes(db, metric_a.id, [
            _axis(metric_a, MetricAxisKind.engagement_category, "bookkeeping", 0),
            _axis(metric_a, MetricAxisKind.engagement_category, "advisory", 1),
            _axis(metric_a, MetricAxisKind.referral_source, "billboard", 2),
        ])
    assert exc.value.status_code == 422
    assert exc.value.detail == "Unknown referral source 'billboard'."
    assert _axes_snapshot(db, metric_a.id) == before, "the refused replacement changed the axes"


def test_replace_axes_replaces_when_every_item_resolves(db, metric_a):
    """The happy path of the seed's door: the old list is gone and the new
    list is stored in sort order."""
    service.add_axis(db, metric_a.id, _axis(metric_a, MetricAxisKind.engagement_category, "tax"))
    rows = service.replace_axes(db, metric_a.id, [
        _axis(metric_a, MetricAxisKind.referral_source, "website", 1),
        _axis(metric_a, MetricAxisKind.engagement_category, "advisory", 0),
    ])
    assert [(a.axis_kind, a.axis_key) for a in rows] == [
        (MetricAxisKind.engagement_category, "advisory"),
        (MetricAxisKind.referral_source, "website"),
    ]


def test_replace_relations_is_all_or_nothing(db, seeded, metric_a, metric_b):
    """Same contract for relations: one bad item, nothing written."""
    service.add_relation(db, metric_a.id, _relation(metric_a, metric_b))
    before = _relations_snapshot(db, metric_a.id)
    assert before == ([metric_b.id], [metric_b.id])
    third = seeded["document_collection_speed"]
    with pytest.raises(HTTPException) as exc:
        service.replace_relations(db, metric_a.id, [
            _relation(metric_a, third, 0),
            MetricRegistryRelationCreate(metric_id=metric_a.id, related_metric_id=uuid.uuid4()),
        ])
    assert exc.value.status_code == 404
    assert _relations_snapshot(db, metric_a.id) == before, "the refused replacement changed the relations"


def test_deleting_a_metric_cascades_its_axes_and_relations(db, seeded, metric_a, metric_b):
    """Deleting a metric removes its axes and every relation on either side,
    through the database's ON DELETE CASCADE (a raw DELETE, so the ORM's own
    cascade is not what is being measured). The other metric survives."""
    service.add_axis(db, metric_a.id, _axis(metric_a, MetricAxisKind.engagement_category, "tax"))
    service.add_relation(db, metric_a.id, _relation(metric_a, metric_b))
    service.add_relation(db, metric_b.id, _relation(metric_b, metric_a))
    a_id, b_id = metric_a.id, metric_b.id

    db.execute(text("DELETE FROM metric_registry WHERE id = :id"), {"id": str(a_id)})
    db.commit()
    db.expire_all()

    assert db.execute(
        select(func.count()).select_from(MetricRegistryAxis).where(MetricRegistryAxis.metric_id == a_id)
    ).scalar_one() == 0
    assert db.execute(
        select(func.count()).select_from(MetricRegistryRelation).where(
            (MetricRegistryRelation.metric_id == a_id) | (MetricRegistryRelation.related_metric_id == a_id)
        )
    ).scalar_one() == 0
    assert crud.get_metric(db, b_id) is not None
