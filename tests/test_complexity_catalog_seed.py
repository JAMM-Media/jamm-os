# tests/test_complexity_catalog_seed.py

"""Integrity tests for scripts/seed_complexity_catalog.py.

The seed transcribes docs/complexity_catalog_content_v1.md into the five
system-owned catalog tables. These tests pin the two things a transcription can
get wrong without anything erroring: the counts, and the structural shape each
dimension kind is required to have.

THE PINNED DIMENSION COUNT IS 84, AND THE DOCUMENT ONCE SAID 78.

The content document's Appendix originally recorded "40 flags, 78 dimensions".
Counting the tables in Parts I through VI gives 40 flags and 84 dimensions. The
gap is exactly six. Andrew ruled on August 16, 2026 that the tables are the
ratified content and the Appendix figure was an authoring miscount, and line
381 of the document was corrected to 84 in the same commit that added it.

That history is recorded here rather than left in a commit message because the
next person to read 84 will want to know why it is not the number the document
was first written with. Do not adjust these constants to match a future
transcription's output; reconcile against the document instead.
"""

import pytest
from sqlalchemy import func, select

from app.core.enums import DimensionKind, DimensionRole, EngagementType
from app.models.complexity_dimension import ComplexityDimension
from app.models.complexity_dimension_unit import ComplexityDimensionUnit
from app.models.complexity_flag import ComplexityFlag
from app.models.complexity_flag_engagement_type import ComplexityFlagEngagementType
from app.models.complexity_vocabulary_option import ComplexityVocabularyOption
from app.services import pricing_config_service as svc
from scripts.seed_complexity_catalog import (
    EXPECTED_DIMENSION_COUNT,
    EXPECTED_FLAG_COUNT,
    OTHER_OPTION_KEY,
    seed_complexity_catalog,
)
from tests.conftest import TestingSessionLocal

# Built with chr() rather than written as the character itself, so this file
# obeys the same no-em-dash rule it enforces.
EM_DASH = chr(0x2014)

CATALOG_MODELS = (
    ComplexityFlag,
    ComplexityDimension,
    ComplexityDimensionUnit,
    ComplexityVocabularyOption,
    ComplexityFlagEngagementType,
)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def seeded(db):
    """The catalog, seeded once. conftest's clean_db truncates every table after
    each test, so each test starts from empty and seeds what it needs."""
    seed_complexity_catalog(db)
    db.commit()
    return db


def _row_counts(db) -> dict:
    return {
        model.__tablename__: db.execute(
            select(func.count()).select_from(model)
        ).scalar_one()
        for model in CATALOG_MODELS
    }


# ---------------------------------------------------------------------------
# 1. Idempotency
# ---------------------------------------------------------------------------

def test_second_run_creates_and_updates_nothing(db):
    """The whole point of the upsert design. A second run must be a no-op."""
    first = seed_complexity_catalog(db)
    db.commit()

    assert first.touched > 0, "first run wrote nothing, so this proves nothing"

    second = seed_complexity_catalog(db)
    db.commit()

    for table_name, counts in second.rows():
        assert counts.created == 0, f"{table_name} created rows on the second run"
        assert counts.updated == 0, f"{table_name} updated rows on the second run"
    assert second.touched == 0


def test_row_counts_identical_after_second_run(db):
    seed_complexity_catalog(db)
    db.commit()
    after_first = _row_counts(db)

    seed_complexity_catalog(db)
    db.commit()
    after_second = _row_counts(db)

    assert after_first == after_second


def test_second_run_does_not_rewrite_timestamps(db):
    """Byte-identical means the rows are untouched, not merely the same count.

    WHAT THIS CATCHES, established by negative control rather than by argument.
    The first control tried was making the seed assign every field
    unconditionally instead of comparing first. This test stayed green, because
    SQLAlchemy emits no UPDATE when an assignment produces no net change, so
    updated_at survives that mutation and the test is blind to it by
    construction.

    The control that does turn it red is a genuine write during a run the
    summary reports as unchanged. That is the real defect class here: not an
    unnecessary assignment, but a seed that rewrites rows while telling you it
    wrote nothing. The count assertions above cannot see it, which is why this
    test exists separately from them.
    """
    seed_complexity_catalog(db)
    db.commit()

    def stamps(model):
        return {
            row.id: row.updated_at
            for row in db.execute(select(model)).scalars().all()
        }

    before = {model.__tablename__: stamps(model) for model in CATALOG_MODELS}

    seed_complexity_catalog(db)
    db.commit()
    db.expire_all()

    after = {model.__tablename__: stamps(model) for model in CATALOG_MODELS}

    assert before == after


def test_no_duplicate_keys(seeded):
    db = seeded

    duplicate_flags = db.execute(
        select(ComplexityFlag.key)
        .group_by(ComplexityFlag.key)
        .having(func.count() > 1)
    ).scalars().all()
    assert duplicate_flags == []

    duplicate_dimensions = db.execute(
        select(ComplexityDimension.flag_id, ComplexityDimension.key)
        .group_by(ComplexityDimension.flag_id, ComplexityDimension.key)
        .having(func.count() > 1)
    ).all()
    assert duplicate_dimensions == []

    duplicate_units = db.execute(
        select(ComplexityDimensionUnit.dimension_id, ComplexityDimensionUnit.key)
        .group_by(ComplexityDimensionUnit.dimension_id, ComplexityDimensionUnit.key)
        .having(func.count() > 1)
    ).all()
    assert duplicate_units == []

    duplicate_options = db.execute(
        select(ComplexityVocabularyOption.dimension_id, ComplexityVocabularyOption.key)
        .group_by(
            ComplexityVocabularyOption.dimension_id, ComplexityVocabularyOption.key
        )
        .having(func.count() > 1)
    ).all()
    assert duplicate_options == []

    duplicate_mappings = db.execute(
        select(
            ComplexityFlagEngagementType.flag_id,
            ComplexityFlagEngagementType.engagement_type,
        )
        .group_by(
            ComplexityFlagEngagementType.flag_id,
            ComplexityFlagEngagementType.engagement_type,
        )
        .having(func.count() > 1)
    ).all()
    assert duplicate_mappings == []


# ---------------------------------------------------------------------------
# 2. Structural integrity
# ---------------------------------------------------------------------------

def test_numeric_dimensions_all_have_at_least_one_unit(seeded):
    """numeric_range is the only kind that carries units, and a firm cannot
    configure one without naming a unit, so a unitless numeric dimension is an
    unusable question."""
    db = seeded
    offenders = []
    for dimension in db.execute(
        select(ComplexityDimension).where(
            ComplexityDimension.kind == DimensionKind.numeric_range
        )
    ).scalars().all():
        unit_count = db.execute(
            select(func.count())
            .select_from(ComplexityDimensionUnit)
            .where(ComplexityDimensionUnit.dimension_id == dimension.id)
        ).scalar_one()
        if unit_count < 1:
            offenders.append(dimension.key)
    assert offenders == []


def test_categorical_dimensions_have_two_options_and_exactly_one_other(seeded):
    db = seeded
    thin = []
    wrong_other_count = []
    for dimension in db.execute(
        select(ComplexityDimension).where(
            ComplexityDimension.kind == DimensionKind.categorical
        )
    ).scalars().all():
        options = db.execute(
            select(ComplexityVocabularyOption).where(
                ComplexityVocabularyOption.dimension_id == dimension.id
            )
        ).scalars().all()
        if len(options) < 2:
            thin.append(dimension.key)
        others = [o for o in options if o.key == OTHER_OPTION_KEY]
        if len(others) != 1:
            wrong_other_count.append((dimension.key, len(others)))

    assert thin == []
    assert wrong_other_count == []


def test_boolean_dimensions_carry_no_units_and_no_options(seeded):
    db = seeded
    offenders = []
    booleans = db.execute(
        select(ComplexityDimension).where(
            ComplexityDimension.kind == DimensionKind.boolean
        )
    ).scalars().all()

    assert booleans, "no boolean dimensions seeded, so this test proves nothing"

    for dimension in booleans:
        unit_count = db.execute(
            select(func.count())
            .select_from(ComplexityDimensionUnit)
            .where(ComplexityDimensionUnit.dimension_id == dimension.id)
        ).scalar_one()
        option_count = db.execute(
            select(func.count())
            .select_from(ComplexityVocabularyOption)
            .where(ComplexityVocabularyOption.dimension_id == dimension.id)
        ).scalar_one()
        if unit_count or option_count:
            offenders.append((dimension.key, unit_count, option_count))
    assert offenders == []


def test_every_mapping_is_a_real_engagement_type(seeded):
    """engagement_type is stored as String(50), so nothing at the database level
    stops a typo. The seed validates on the way in; this reads what actually
    landed."""
    db = seeded
    values = db.execute(
        select(ComplexityFlagEngagementType.engagement_type).distinct()
    ).scalars().all()

    assert values

    unknown = []
    for value in values:
        try:
            EngagementType(value)
        except ValueError:
            unknown.append(value)
    assert unknown == []


def test_hierarchy_ranks_are_unique_within_each_flag(seeded):
    """Ranks are spaced by 10 and are unique within a flag. Two dimensions at
    the same rank could not be chained in either direction, because the
    downhill-only rule rejects equal ranks."""
    db = seeded
    collisions = db.execute(
        select(ComplexityDimension.flag_id, ComplexityDimension.hierarchy_rank)
        .group_by(ComplexityDimension.flag_id, ComplexityDimension.hierarchy_rank)
        .having(func.count() > 1)
    ).all()
    assert collisions == []


def test_ranks_are_multiples_of_ten(seeded):
    """The document's spacing convention: 10, 20, 30, so later insertions never
    renumber existing rows."""
    db = seeded
    ranks = db.execute(select(ComplexityDimension.hierarchy_rank)).scalars().all()
    assert ranks
    assert [r for r in ranks if r <= 0 or r % 10 != 0] == []


def test_no_seeded_string_contains_an_em_dash(seeded):
    """House rule, applied to every string this seed puts in the database."""
    db = seeded
    offenders = []

    for flag in db.execute(select(ComplexityFlag)).scalars().all():
        for value in (flag.key, flag.name, flag.description):
            if value and EM_DASH in value:
                offenders.append(value)

    for dimension in db.execute(select(ComplexityDimension)).scalars().all():
        for value in (dimension.key, dimension.question_text):
            if value and EM_DASH in value:
                offenders.append(value)

    for unit in db.execute(select(ComplexityDimensionUnit)).scalars().all():
        for value in (unit.key, unit.label, unit.question_text):
            if value and EM_DASH in value:
                offenders.append(value)

    for option in db.execute(select(ComplexityVocabularyOption)).scalars().all():
        for value in (option.key, option.label):
            if value and EM_DASH in value:
                offenders.append(value)

    assert offenders == []


def test_question_text_is_seeded_null_everywhere(seeded):
    """Lead-facing wording is a later data edit by design; the columns were
    built nullable for exactly this."""
    db = seeded

    dimension_texts = db.execute(
        select(ComplexityDimension.question_text).distinct()
    ).scalars().all()
    assert dimension_texts == [None]

    unit_texts = db.execute(
        select(ComplexityDimensionUnit.question_text).distinct()
    ).scalars().all()
    assert unit_texts == [None]


def test_default_roles_are_real_enum_members(seeded):
    db = seeded
    roles = db.execute(
        select(ComplexityDimension.default_role).distinct()
    ).scalars().all()
    assert roles
    assert all(isinstance(role, DimensionRole) for role in roles)


def test_seed_other_key_matches_the_pricing_guard(seeded):
    """The seed writes the Other option and pricing_config_service refuses to
    price it. They agree on the key by convention, not by import, so if one is
    ever renamed this is what notices.
    """
    assert OTHER_OPTION_KEY == svc.OTHER_OPTION_KEY

    db = seeded
    other_count = db.execute(
        select(func.count())
        .select_from(ComplexityVocabularyOption)
        .where(ComplexityVocabularyOption.key == svc.OTHER_OPTION_KEY)
    ).scalar_one()
    categorical_count = db.execute(
        select(func.count())
        .select_from(ComplexityDimension)
        .where(ComplexityDimension.kind == DimensionKind.categorical)
    ).scalar_one()
    assert other_count == categorical_count


# ---------------------------------------------------------------------------
# 3. Pinned totals. See the module docstring for the 78-versus-84 history.
# ---------------------------------------------------------------------------

def test_expected_flag_and_dimension_totals(seeded):
    db = seeded

    flag_count = db.execute(
        select(func.count()).select_from(ComplexityFlag)
    ).scalar_one()
    dimension_count = db.execute(
        select(func.count()).select_from(ComplexityDimension)
    ).scalar_one()

    assert flag_count == EXPECTED_FLAG_COUNT == 40
    assert dimension_count == EXPECTED_DIMENSION_COUNT == 84
