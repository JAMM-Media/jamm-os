# tests/test_pricing_scope_migration_guard.py

"""Chain-from-empty guard for the two scope migrations.

WHAT IS BEING GUARDED

    1ed5f6118514  adds firm_dimension_configs.service_catalog_entry_id and
                  rebuilds uq_firm_dimension_configs_firm_dimension_branch as
                  five columns, NULLS NOT DISTINCT.
    62e44a7fd8f1  adds firm_option_prices.service_catalog_entry_id and rebuilds
                  uq_firm_option_prices_firm_option as three columns,
                  NULLS NOT DISTINCT.

Both DROP an existing constraint and CREATE a replacement under the same name.
That is the shape with the worst failure mode available: if the create half is
ever lost, reordered, or silently altered, the drop still happens and the
database ends up with NO uniqueness rule at all while every model, service and
test carries on believing there is one. Nothing in the ordinary suite would
notice, because the service layer does not duplicate these checks.

WHY THIS DOES NOT USE THE PYTEST TEST DATABASE

tests/conftest.py builds that database with Base.metadata.create_all(), which
emits what the MODELS declare. The models and the migrations are two separate
descriptions of the same schema and they are exactly the two things that can
drift apart (process rules instance seven, and instance eleven for the
compiler-drops-it case). A test reading the create_all database would pass on a
migration that never ran, which is the failure this file exists to catch.

So this runs the whole chain from an empty database and reads the resulting
catalog, per process rule 3. tests/test_enrollment_active_index_guard.py is the
pattern being copied. The whole chain takes a few seconds.

NULLS NOT DISTINCT IS READ FROM pg_index, NOT FROM THE CONSTRAINT TEXT. It is
the single most losable property here: a constraint that lost it still exists,
still has the right name, still covers the right columns, and still reads as
UNIQUE in most tooling, while silently permitting exactly the duplicate rows it
was written to forbid (two blanket configs for one dimension, two blanket
prices for one option). Substring matching on pg_get_constraintdef would catch
a rename but is checked alongside indnullsnotdistinct rather than instead of
it.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parent.parent

SCRATCH_DB_NAME = "jamm_pricing_scope_migration_guard"

CONFIG_TABLE = "firm_dimension_configs"
CONFIG_UQ = "uq_firm_dimension_configs_firm_dimension_branch"
CONFIG_FK = "fk_firm_dimension_configs_service_catalog_entry"
CONFIG_UQ_COLUMNS = [
    "firm_id",
    "dimension_id",
    "service_catalog_entry_id",
    "parent_tier_id",
    "parent_option_id",
]

PRICE_TABLE = "firm_option_prices"
PRICE_UQ = "uq_firm_option_prices_firm_option"
PRICE_FK = "fk_firm_option_prices_service_catalog_entry"
PRICE_UQ_COLUMNS = ["firm_id", "option_id", "service_catalog_entry_id"]

SCOPE_COLUMN = "service_catalog_entry_id"


@pytest.fixture(scope="module")
def migrated_database():
    """A scratch database built by `alembic upgrade head` from empty.

    Deliberately not the pytest test database. See the module docstring.
    """
    base_url = make_url(os.environ["DATABASE_URL"])

    # conftest already refuses to run against anything that looks like
    # production and this fixture inherits that DATABASE_URL. The extra guard
    # is that the scratch name is fixed and unmistakable, so the DROP below can
    # only ever hit a database this fixture created.
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
            "migration chain does not build from scratch. This is what the CI "
            "'Run migrations' step does, so CI cannot be passing either. "
            "Nothing below this point is measurable until it is fixed."
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


def _unique_constraint(engine, name: str):
    """Constraint definition plus the underlying index's nulls-not-distinct flag."""
    query = text(
        """
        SELECT
            pg_get_constraintdef(c.oid) AS definition,
            i.indnullsnotdistinct AS nulls_not_distinct,
            ARRAY(
                SELECT a.attname
                FROM unnest(c.conkey) WITH ORDINALITY AS k(attnum, ord)
                JOIN pg_attribute a
                  ON a.attrelid = c.conrelid AND a.attnum = k.attnum
                ORDER BY k.ord
            ) AS columns
        FROM pg_constraint c
        JOIN pg_index i ON i.indexrelid = c.conindid
        WHERE c.conname = :name AND c.contype = 'u'
        """
    )
    with engine.connect() as conn:
        return conn.execute(query, {"name": name}).mappings().first()


def _foreign_key(engine, name: str):
    query = text(
        "SELECT pg_get_constraintdef(oid) AS definition "
        "FROM pg_constraint WHERE conname = :name AND contype = 'f'"
    )
    with engine.connect() as conn:
        return conn.execute(query, {"name": name}).scalar_one_or_none()


# ---------------------------------------------------------------------------
# The scope columns exist in migration-built reality.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("table", [CONFIG_TABLE, PRICE_TABLE])
def test_scope_column_exists_and_is_nullable(migrated_database, table):
    """Nullable with no default is the whole semantic: NULL means blanket.

    A NOT NULL column, or one with a default, would make every existing row a
    scoped row pointing at something arbitrary, which is not a migration
    failure that announces itself.
    """
    row = _column(migrated_database, table, SCOPE_COLUMN)
    assert row is not None, (
        f"{table}.{SCOPE_COLUMN} does not exist in a database built by "
        "`alembic upgrade head`. The per-engagement-type override feature has "
        "no column to live in, and every model, service and test asserting "
        "otherwise is measuring the create_all world only."
    )
    assert row["data_type"] == "uuid", f"expected uuid, got {row['data_type']}"
    assert row["is_nullable"] == "YES", (
        f"{table}.{SCOPE_COLUMN} is NOT NULL. NULL is the blanket case and is "
        "the value nearly every row carries."
    )
    assert row["column_default"] is None, (
        f"{table}.{SCOPE_COLUMN} has a server default of "
        f"{row['column_default']!r}. NULL here is a meaningful value, not a "
        "placeholder for one, so nothing may fill it in."
    )


# ---------------------------------------------------------------------------
# The rebuilt unique constraints survived the drop-and-recreate.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "name,expected_columns",
    [(CONFIG_UQ, CONFIG_UQ_COLUMNS), (PRICE_UQ, PRICE_UQ_COLUMNS)],
)
def test_unique_constraint_exists_with_the_scope_column(
    migrated_database, name, expected_columns
):
    """Load-bearing assertion one: the replacement constraint is there, over
    exactly the right columns.

    Both migrations DROP then CREATE under the same name. If the create half
    were ever lost, this is what notices: the table would have no uniqueness
    rule while everything else assumed one.
    """
    row = _unique_constraint(migrated_database, name)
    assert row is not None, (
        f"{name} does not exist in a database built by `alembic upgrade head`. "
        "Both scope migrations drop this constraint and recreate it under the "
        "same name; if the recreate is missing, the rule is simply gone and "
        "duplicate rows can be inserted freely."
    )
    assert list(row["columns"]) == expected_columns, (
        f"{name} covers {list(row['columns'])}, expected {expected_columns}. "
        "Without the scope column a firm cannot configure the same dimension "
        "both blanket and scoped, which is the entire feature."
    )


@pytest.mark.parametrize("name", [CONFIG_UQ, PRICE_UQ])
def test_unique_constraint_is_nulls_not_distinct(migrated_database, name):
    """Load-bearing assertion two, and the one most easily lost.

    Read from pg_index.indnullsnotdistinct rather than from the constraint
    text, because a constraint that lost this property still exists, still has
    the right name, still covers the right columns and still reads as UNIQUE.
    What it stops doing is binding rows whose nullable members are NULL, which
    is the blanket case: two blanket configs for one dimension, or two blanket
    prices for one option, would both insert cleanly. That is the common case,
    so the rule would be un-enforced almost everywhere while appearing intact.
    """
    row = _unique_constraint(migrated_database, name)
    assert row is not None, f"{name} is missing entirely."
    assert row["nulls_not_distinct"] is True, (
        f"{name} exists but is NULLS DISTINCT. Every row whose "
        f"{SCOPE_COLUMN} (and, for the config constraint, whose parent columns) "
        "is NULL now escapes it, because NULL never equals NULL. That is the "
        "blanket case and it is most of the table. "
        f"Definition: {row['definition']}"
    )
    assert "NULLS NOT DISTINCT" in row["definition"], (
        f"pg_index reports nulls_not_distinct for {name} but the rendered "
        f"definition does not say so: {row['definition']!r}. Read both before "
        "trusting either."
    )


# ---------------------------------------------------------------------------
# The foreign keys landed, named, and cascade.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name", [CONFIG_FK, PRICE_FK])
def test_scope_foreign_key_exists_named_and_cascades(migrated_database, name):
    """The FK is created by an explicit, named op.create_foreign_key.

    Named because an unnamed constraint cannot have DROP CONSTRAINT emitted for
    it, which is a live defect elsewhere in this repo (app/models/sequence.py)
    and the thing instance eleven is about.

    CASCADE because SET NULL would demote a scoped row to a blanket one when a
    catalog entry is deleted, silently widening a per-engagement price to every
    engagement type. That is a mispricing, not a cleanup, and for
    firm_option_prices it could also collide with an existing blanket row.
    """
    definition = _foreign_key(migrated_database, name)
    assert definition is not None, (
        f"{name} does not exist in a database built by `alembic upgrade head`, "
        "so nothing stops a config or price from naming a catalog entry that "
        "is not there."
    )
    assert "service_catalog_entries(id)" in definition, (
        f"{name} does not point at service_catalog_entries(id): {definition}"
    )
    assert "ON DELETE CASCADE" in definition, (
        f"{name} is not ON DELETE CASCADE: {definition}. SET NULL or NO ACTION "
        "here changes what deleting a catalog entry means for a firm's prices."
    )
