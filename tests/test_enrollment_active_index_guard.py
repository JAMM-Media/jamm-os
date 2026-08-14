# tests/test_enrollment_active_index_guard.py

"""Guard on uq_enrollment_active_lead_sequence, the one destructive item in the
autogenerate drift inventory.

WHAT IS BEING GUARDED

migrations/versions/f2g3h4i5j6k7_add_enrollment_model.py creates a partial
unique index on enrollments (lead_id, sequence_id) WHERE status = 'active'.
It is the only thing stopping a lead from being enrolled twice in the same
nurture sequence at the same time.

The index is NOT declared on the Enrollment model. Base.metadata therefore has
no record of it, and every `alembic revision --autogenerate` proposes to DROP
it. Applying any such file, once, silently removes the rule from every real
database.

WHY THIS TEST DOES NOT USE THE PYTEST TEST DATABASE

tests/conftest.py builds the test database with Base.metadata.create_all().
create_all() emits only what the models declare, and the models do not declare
this index, so it is absent from the pytest database by construction. A guard
written against that database would be red on a healthy repo and could never
go green, which is the mirror image of the failure this file exists to catch.

The failure being guarded lives in migrated databases: dev, production, and
the CI job that runs `alembic upgrade head`. So the guard runs the migration
chain end to end against a scratch database and reads the live index catalog
there. That is process rule 3, reproduce the failure in the conditions the
failure happens in. Full chain from empty is roughly five seconds.

test_model_does_not_declare_the_index below records the drift itself, and is
written so that it fails and demands a rewrite of this file on the day the
model and the migration are reconciled.
"""

import os
import subprocess
import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from app.models.enrollment import Enrollment

REPO_ROOT = Path(__file__).resolve().parent.parent

INDEX_NAME = "uq_enrollment_active_lead_sequence"
TABLE_NAME = "enrollments"

# The exact clause from f2g3h4i5j6k7, as Postgres renders it back once the
# column type is applied. status is sa.Enum(..., native_enum=False), which is a
# VARCHAR, hence the ::text casts on both sides. Compared with all whitespace
# removed so formatting alone can never fail this.
EXPECTED_PREDICATE = "((status)::text='active'::text)"
EXPECTED_COLUMNS = ["lead_id", "sequence_id"]

SCRATCH_DB_NAME = "jamm_enrollment_index_guard"


def _normalize(predicate: str) -> str:
    return "".join(predicate.split())


@pytest.fixture(scope="module")
def migrated_database():
    """A scratch database built by `alembic upgrade head` from empty.

    Deliberately not the pytest test database. See the module docstring.
    """
    base_url = make_url(os.environ["DATABASE_URL"])

    # conftest already refuses to run at all against anything that looks like
    # production, and this fixture inherits that DATABASE_URL. The extra guard
    # here is that the scratch name is fixed and unmistakable, so the DROP
    # below can only ever hit a database this fixture created.
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
            "migration chain does not build from scratch. This is the same "
            "thing the CI 'Run migrations' step does, so CI cannot be passing "
            "either. Nothing below this point is measurable until it is fixed."
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
    """The live catalog entry for the index, or None if it is not there.

    pg_index is read rather than pg_indexes because the predicate has to be
    read on its own. Substring matching against the whole CREATE INDEX text
    would pass on an index that had the right words in the wrong places.
    """
    query = text(
        """
        SELECT
            i.indisunique AS is_unique,
            pg_get_expr(i.indpred, i.indrelid) AS predicate,
            ARRAY(
                SELECT pg_get_indexdef(i.indexrelid, k + 1, true)
                FROM generate_subscripts(i.indkey, 1) AS k
            ) AS columns,
            pg_get_indexdef(i.indexrelid) AS full_definition
        FROM pg_index i
        JOIN pg_class idx ON idx.oid = i.indexrelid
        JOIN pg_class tbl ON tbl.oid = i.indrelid
        JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
        WHERE idx.relname = :index_name
          AND tbl.relname = :table_name
          AND ns.nspname = 'public'
        """
    )
    with migrated_database.connect() as conn:
        row = conn.execute(
            query, {"index_name": INDEX_NAME, "table_name": TABLE_NAME}
        ).mappings().first()
    return row


def test_partial_unique_index_exists(index_row):
    """Load-bearing assertion one: the index is present at all.

    This is the one an applied autogenerate DROP would trip.
    """
    assert index_row is not None, (
        f"{INDEX_NAME} does not exist on {TABLE_NAME} in a database built by "
        "`alembic upgrade head`. Every autogenerate proposes dropping this "
        "index because the Enrollment model does not declare it. If one of "
        "those files was applied, a lead can now be enrolled twice in the "
        "same sequence concurrently and nothing will complain."
    )


def test_index_is_unique_over_lead_and_sequence(index_row):
    """Load-bearing assertion two: it is UNIQUE, over exactly (lead_id,
    sequence_id), in that order.

    A non-unique index by the same name would satisfy the existence check
    above while enforcing nothing at all.
    """
    assert index_row is not None, f"{INDEX_NAME} is missing entirely."
    assert index_row["is_unique"], (
        f"{INDEX_NAME} exists but is not UNIQUE, so it enforces nothing. "
        f"Definition: {index_row['full_definition']}"
    )
    assert list(index_row["columns"]) == EXPECTED_COLUMNS, (
        f"{INDEX_NAME} covers {list(index_row['columns'])}, expected "
        f"{EXPECTED_COLUMNS}. Keying on anything other than the sequence "
        "would let the same lead be enrolled twice across two versions of one "
        "sequence, which is the case f2g3h4i5j6k7 was written to prevent."
    )


def test_index_predicate_matches_the_migration(index_row):
    """Load-bearing assertion three: the partial WHERE clause is still
    status = 'active'.

    A widened predicate (or no predicate) turns the rule into something
    stricter than intended: a lead who unsubscribed could never be re-enrolled.
    A narrowed one stops covering active rows. Either way the index is still
    present and still unique, so only this assertion notices.
    """
    assert index_row is not None, f"{INDEX_NAME} is missing entirely."
    predicate = index_row["predicate"]
    assert predicate is not None, (
        f"{INDEX_NAME} has no WHERE clause, so it is a full unique index over "
        "(lead_id, sequence_id). That forbids re-enrolling a lead who "
        "unsubscribed or converted, which the migration deliberately allows."
    )
    assert _normalize(predicate) == EXPECTED_PREDICATE, (
        f"{INDEX_NAME} predicate is {predicate!r}, expected the equivalent of "
        "status = 'active' as written in "
        "migrations/versions/f2g3h4i5j6k7_add_enrollment_model.py. If the "
        "clause is semantically right and only the rendering changed (a "
        "Postgres upgrade, or a change to the status column type), update "
        "EXPECTED_PREDICATE in this file and say so in the commit."
    )


def test_model_does_not_declare_the_index():
    """Records the drift itself, so it is visible rather than merely absent.

    This is why the three tests above cannot run against the pytest test
    database. It is written to FAIL the day the model and the migration are
    reconciled, because on that day create_all() starts producing the index,
    the drift item leaves the autogenerate inventory, and this whole file
    should be rewritten to read the ordinary test database instead of paying
    for a scratch migration run.
    """
    declared = {index.name for index in Enrollment.__table__.indexes}
    assert INDEX_NAME not in declared, (
        f"The Enrollment model now declares {INDEX_NAME}. The drift this file "
        "works around is gone: autogenerate no longer proposes dropping the "
        "index, and create_all() now builds it into the pytest test database. "
        "Rewrite this file to read the ordinary test database and drop the "
        "scratch migration fixture."
    )
