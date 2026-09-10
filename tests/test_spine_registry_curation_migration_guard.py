# tests/test_spine_registry_curation_migration_guard.py

"""Chain-from-empty guard for migration 3fbbc0560976, the registry curation
schema (Sep 10, 2026 session).

WHAT IS BEING GUARDED

    3fbbc0560976  adds pillar, entity_type, attention_weight and synonyms to
                  metric_registry, and creates metric_registry_relations and
                  metric_registry_axes with their named unique constraints,
                  the not-self check constraint, and three cascading foreign
                  keys.

WHY THIS DOES NOT USE THE PYTEST TEST DATABASE

tests/conftest.py builds that database with Base.metadata.create_all(), which
emits what the MODELS declare. The migration is a second, hand-written
description of the same schema (autogenerate was discarded because it carried
unrelated drift), and the two can diverge without any ordinary test noticing
(process rules instances seven and eleven). So this runs the whole chain from
an empty database and reads the resulting catalog, copying
tests/test_pricing_scope_migration_guard.py.

This file is also the negative control for ck_metric_registry_relations_not_self:
the self-relation rule is checked at the schema and service layers by
tests/test_spine_registry_curation.py, and the constraint's existence in
migrated reality is asserted here rather than by breaking the model.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.core.metric_seed_data import SEED_METRICS

REPO_ROOT = Path(__file__).resolve().parent.parent

SCRATCH_DB_NAME = "jamm_registry_curation_migration_guard"

REGISTRY = "metric_registry"
RELATIONS = "metric_registry_relations"
AXES = "metric_registry_axes"


@pytest.fixture(scope="module")
def migrated_database():
    """A scratch database built by `alembic upgrade head` from empty.

    Deliberately not the pytest test database. See the module docstring.
    """
    base_url = make_url(os.environ["DATABASE_URL"])

    assert base_url.database != SCRATCH_DB_NAME, (
        "DATABASE_URL already points at the scratch guard database. Point it "
        "back at the real test database before running this."
    )

    admin_engine = create_engine(
        base_url.set(database="postgres"), isolation_level="AUTOCOMMIT"
    )
    try:
        with admin_engine.connect() as conn:
            conn.execute(
                text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB_NAME}" WITH (FORCE)')
            )
            conn.execute(text(f'CREATE DATABASE "{SCRATCH_DB_NAME}"'))

        scratch_url = base_url.set(database=SCRATCH_DB_NAME)

        env = dict(os.environ)
        env["DATABASE_URL"] = scratch_url.render_as_string(hide_password=False)
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            env=env,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, (
            "`alembic upgrade head` failed against an empty database, so the "
            "migration chain does not build from scratch."
            f"\n\nstderr tail:\n{result.stderr[-3000:]}"
        )

        engine = create_engine(scratch_url)
        try:
            yield engine
        finally:
            engine.dispose()
    finally:
        with admin_engine.connect() as conn:
            conn.execute(
                text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB_NAME}" WITH (FORCE)')
            )
        admin_engine.dispose()


def _column(engine, table: str, column: str):
    query = text(
        """
        SELECT data_type, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = :table
          AND column_name = :column
        """
    )
    with engine.connect() as conn:
        return conn.execute(query, {"table": table, "column": column}).mappings().first()


def _constraint(engine, name: str, contype: str):
    """Definition plus ordered column names for a named constraint."""
    query = text(
        """
        SELECT
            c.conrelid::regclass::text AS table_name,
            pg_get_constraintdef(c.oid) AS definition,
            ARRAY(
                SELECT a.attname
                FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k.attnum
                ORDER BY k.ord
            ) AS columns
        FROM pg_constraint c
        WHERE c.conname = :name AND c.contype = :contype
        """
    )
    with engine.connect() as conn:
        return conn.execute(query, {"name": name, "contype": contype}).mappings().first()


def _foreign_keys(engine, table: str):
    """Every FK on a table, keyed by its local column, with the delete rule."""
    query = text(
        """
        SELECT
            a.attname AS column_name,
            c.confdeltype AS delete_rule,
            pg_get_constraintdef(c.oid) AS definition
        FROM pg_constraint c
        JOIN pg_attribute a
          ON a.attrelid = c.conrelid AND a.attnum = ANY(c.conkey)
        WHERE c.contype = 'f'
          AND c.conrelid = CAST(:table AS regclass)
        """
    )
    with engine.connect() as conn:
        rows = conn.execute(query, {"table": table}).mappings().all()
    return {row["column_name"]: row for row in rows}


# ---------------------------------------------------------------------------
# The four curation columns exist with the ruled nullability and default.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "column,data_type",
    [("pillar", "character varying"), ("entity_type", "character varying"), ("attention_weight", "integer")],
)
def test_single_value_curation_column_is_nullable_with_no_default(migrated_database, column, data_type):
    """NULL means not yet authored (ruling R6). A NOT NULL column or a default
    would silently author every existing row."""
    row = _column(migrated_database, REGISTRY, column)
    assert row is not None, f"{REGISTRY}.{column} does not exist in a migrated database."
    assert row["data_type"] == data_type, (column, row["data_type"])
    assert row["is_nullable"] == "YES", f"{REGISTRY}.{column} is NOT NULL; NULL is the unauthored state."
    assert row["column_default"] is None, f"{REGISTRY}.{column} has a default: {row['column_default']!r}"


def test_synonyms_is_a_not_null_array_defaulting_to_empty(migrated_database):
    """synonyms is NOT NULL with an empty-array server default, so re-seeding
    from empty and every existing row read as [] rather than NULL."""
    row = _column(migrated_database, REGISTRY, "synonyms")
    assert row is not None, f"{REGISTRY}.synonyms does not exist in a migrated database."
    assert row["data_type"] == "ARRAY", row["data_type"]
    assert row["is_nullable"] == "NO"
    assert row["column_default"] is not None and row["column_default"].startswith("'{}'"), (
        f"synonyms default is {row['column_default']!r}, expected an empty array literal"
    )


def test_no_native_enum_type_was_created(migrated_database):
    """Every enum in this session is native_enum=False; a CREATE TYPE would
    mean the migration was not the hand-written one."""
    with migrated_database.connect() as conn:
        found = conn.execute(text(
            "SELECT typname FROM pg_type WHERE typname IN "
            "('metricpillar', 'metricentitytype', 'metricaxiskind')"
        )).scalars().all()
    assert found == [], f"native enum types exist: {found}"


# ---------------------------------------------------------------------------
# Named constraints landed over the right columns.
# ---------------------------------------------------------------------------

def test_relations_pair_unique_constraint_exists(migrated_database):
    row = _constraint(migrated_database, "uq_metric_registry_relations_pair", "u")
    assert row is not None, "uq_metric_registry_relations_pair is missing from a migrated database."
    assert row["table_name"] == RELATIONS
    assert list(row["columns"]) == ["metric_id", "related_metric_id"]


def test_axes_metric_kind_key_unique_constraint_exists(migrated_database):
    row = _constraint(migrated_database, "uq_metric_registry_axes_metric_kind_key", "u")
    assert row is not None, "uq_metric_registry_axes_metric_kind_key is missing from a migrated database."
    assert row["table_name"] == AXES
    assert list(row["columns"]) == ["metric_id", "axis_kind", "axis_key"]


def test_not_self_check_constraint_exists(migrated_database):
    """The second line of defence for ruling R4. Its negative control is this
    assertion against migrated reality, not a model mutation."""
    row = _constraint(migrated_database, "ck_metric_registry_relations_not_self", "c")
    assert row is not None, "ck_metric_registry_relations_not_self is missing from a migrated database."
    assert row["table_name"] == RELATIONS
    assert "metric_id <> related_metric_id" in row["definition"], row["definition"]


# ---------------------------------------------------------------------------
# The three foreign keys cascade.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "table,column",
    [(RELATIONS, "metric_id"), (RELATIONS, "related_metric_id"), (AXES, "metric_id")],
)
def test_foreign_key_to_registry_cascades(migrated_database, table, column):
    """Deleting a registry row must take its axes and relations with it;
    NO ACTION would make a metric undeletable once curated."""
    fks = _foreign_keys(migrated_database, table)
    assert column in fks, f"{table}.{column} has no foreign key in a migrated database."
    assert "metric_registry(id)" in fks[column]["definition"], fks[column]["definition"]
    assert fks[column]["delete_rule"] == "c", (
        f"{table}.{column} is not ON DELETE CASCADE: {fks[column]['definition']}"
    )


# ---------------------------------------------------------------------------
# Re-seeding from empty still works and ships unauthored.
# ---------------------------------------------------------------------------

def test_seed_rows_exist_from_empty_with_curation_fields_unset(migrated_database):
    """The eleven seed rows inserted by 1e16e4b22bea survive the new columns:
    pillar, entity_type and attention_weight NULL, synonyms empty."""
    with migrated_database.connect() as conn:
        rows = conn.execute(text(
            "SELECT key, pillar, entity_type, attention_weight, synonyms "
            f"FROM {REGISTRY} ORDER BY key"
        )).mappings().all()
    assert {r["key"] for r in rows} == {key for key, *_ in SEED_METRICS}
    assert len(rows) == 11
    for r in rows:
        assert r["pillar"] is None, r
        assert r["entity_type"] is None, r
        assert r["attention_weight"] is None, r
        assert list(r["synonyms"]) == [], r
