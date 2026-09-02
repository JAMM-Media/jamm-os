# tests/test_surface_index_guard.py

"""Guard on uq_surface_items_open_condition, the dedup rule for surface items.

WHAT IS BEING GUARDED

A partial unique index on (firm_id, kind, item_type, dedup_key) WHERE
resolved_at IS NULL. It is the only thing stopping the same condition from
producing duplicate live rows, and it is also what enforces the ruled behavior
that a not_relevant or was_wrong dismissal never resurfaces: those rows stay
unresolved forever, so they keep occupying the slot their condition would
otherwise refill tomorrow morning.

WHY THIS GUARD READS A MIGRATED DATABASE

tests/conftest.py builds the pytest database with Base.metadata.create_all(),
which emits what the MODELS declare. Dev, production and CI are built by
alembic, which emits what the MIGRATIONS declare. Those are two different
worlds and this repo has been bitten by their divergence more than once, most
sharply by uq_enrollment_active_lead_sequence, which exists in migrations only
and has therefore never existed in any test run.

This index is deliberately declared in BOTH places. So this guard runs the
whole migration chain into a scratch database and reads the live catalog there,
proving the migrated world has it, and a second test proves the model declares
it too. Together they close the gap rather than assuming it.

The structure follows tests/test_enrollment_active_index_guard.py, which is the
working example of this pattern in this repo.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.models.surface_item import SurfaceItem

REPO_ROOT = Path(__file__).resolve().parent.parent

INDEX_NAME = "uq_surface_items_open_condition"
TABLE_NAME = "surface_items"

EXPECTED_COLUMNS = ["firm_id", "kind", "item_type", "dedup_key"]
EXPECTED_PREDICATE = "(resolved_atISNULL)"

SCRATCH_DB_NAME = "jamm_surface_index_guard"


def _normalize(predicate: str) -> str:
    return "".join(predicate.split())


@pytest.fixture(scope="module")
def migrated_database():
    """A scratch database built by `alembic upgrade head` from empty."""
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
            conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB_NAME}" WITH (FORCE)'))
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
            "migration chain does not build from scratch. Nothing below this "
            "point is measurable until that is fixed."
            f"\n\nstderr tail:\n{result.stderr[-3000:]}"
        )

        engine = create_engine(scratch_url)
        try:
            yield engine
        finally:
            engine.dispose()
    finally:
        with admin_engine.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB_NAME}" WITH (FORCE)'))
        admin_engine.dispose()


@pytest.fixture(scope="module")
def index_row(migrated_database):
    """The live catalog entry, read from pg_index so the predicate stands alone.

    Substring matching against the whole CREATE INDEX text would pass on an
    index with the right words in the wrong places.
    """
    query = text(
        """
        SELECT
            i.indisunique AS is_unique,
            pg_get_expr(i.indpred, i.indrelid) AS predicate,
            ARRAY(
                SELECT pg_get_indexdef(i.indexrelid, k + 1, true)
                FROM generate_subscripts(i.indkey, 1) AS k
                ORDER BY k
            ) AS columns
        FROM pg_index i
        JOIN pg_class c ON c.oid = i.indexrelid
        WHERE c.relname = :index_name
        """
    )
    with migrated_database.connect() as conn:
        return conn.execute(query, {"index_name": INDEX_NAME}).mappings().first()


def test_index_exists_in_the_migrated_database(index_row):
    assert index_row is not None, (
        f"{INDEX_NAME} does not exist after a full migration chain from empty. "
        "Every migrated database, including production, is missing the dedup "
        "rule, so the same condition can produce duplicate live rows and a "
        "permanently dismissed item can resurface as a fresh row."
    )


def test_index_is_unique(index_row):
    assert index_row["is_unique"] is True, (
        f"{INDEX_NAME} exists but is not UNIQUE, so it enforces nothing."
    )


def test_index_covers_the_right_columns(index_row):
    assert list(index_row["columns"]) == EXPECTED_COLUMNS, (
        f"{INDEX_NAME} covers {list(index_row['columns'])}, expected "
        f"{EXPECTED_COLUMNS}. Dedup is scoped per firm, per surface, per item "
        "type, per condition instance, and dropping any one of those either "
        "leaks rows between firms or collapses distinct conditions together."
    )


def test_index_predicate_is_unresolved_only(index_row):
    """The predicate IS the ruled behavior, so it is asserted exactly.

    WHERE resolved_at IS NULL means one live row per condition. Widening it to
    exclude dismissed rows would let a not_relevant dismissal be replaced by a
    fresh row the next morning, which is precisely the resurfacing the ruling
    forbids. Narrowing it would block a genuinely recurring condition forever.
    """
    predicate = index_row["predicate"]
    assert predicate is not None, (
        f"{INDEX_NAME} is not a PARTIAL index. Without the predicate it blocks "
        "a second row for a condition that already resolved, so a recurrence "
        "can never be raised again."
    )
    assert _normalize(predicate) == EXPECTED_PREDICATE, (
        f"{INDEX_NAME} predicate is {predicate!r}, expected resolved_at IS NULL."
    )


def test_model_also_declares_the_index():
    """The create_all world must carry it too, or tests measure a different DB.

    This is the half that the enrollment guard could not have: there the index
    lives in migrations only, so the pytest database has never had it. Here it
    is declared on the model as well, and this test is what stops someone
    removing that declaration as redundant.
    """
    declared = {index.name for index in SurfaceItem.__table__.indexes}
    assert INDEX_NAME in declared, (
        f"{INDEX_NAME} is no longer declared on the SurfaceItem model. "
        "conftest builds the test database with create_all(), so the dedup rule "
        "would silently stop existing in every test run while still existing in "
        "dev and production."
    )

    index = next(i for i in SurfaceItem.__table__.indexes if i.name == INDEX_NAME)
    assert index.unique is True
    assert [c.name for c in index.columns] == EXPECTED_COLUMNS
