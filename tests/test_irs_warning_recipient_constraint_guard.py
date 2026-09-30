# tests/test_irs_warning_recipient_constraint_guard.py

"""Guard on the IRS warning recipient uniqueness rule, as the migration chain
actually builds it.

WHAT IS BEING GUARDED

migrations/versions/e4a7c2b91d63_add_recipient_to_irs_auth_warnings.py replaces
uq_irs_auth_warning_auth_threshold (authorization_id, threshold_days) with
uq_irs_auth_warning_auth_threshold_recipient, over
(authorization_id, threshold_days, recipient_user_id), and adds
recipient_user_id with a foreign key to users.id ON DELETE SET NULL.

Three properties have to hold together, and each one fails silently on its own:

  1. The new constraint exists. Without it a tier could record the same
     recipient twice.
  2. It uses NULLS DISTINCT, the Postgres default. Under NULLS NOT DISTINCT
     two null-recipient rows on one tier collide, which would block deleting a
     second user who shares a tier with an already-deleted one, and would
     equally block a pre-Sep-24 row coexisting with a nulled one.
  3. The old two-column constraint is gone. If it survived, per-recipient rows
     would be refused outright and the whole feature would fail closed.

WHY THIS TEST DOES NOT USE THE PYTEST TEST DATABASE

tests/conftest.py builds the test database with Base.metadata.create_all(),
which emits what the models declare. The model declares the new constraint, so
the pytest database would satisfy assertions 1 and 3 even if the migration were
wrong, and dev, production and CI would still be broken. The failure being
guarded lives in migrated databases, so this runs the chain end to end against
a scratch database and reads the live catalog there. Process rule 3: reproduce
the failure in the conditions the failure happens in.

NULLS DISTINCT in particular cannot be read off the model at all. SQLAlchemy's
UniqueConstraint emits nothing for it, because it is the server default, so the
only place the answer exists is pg_index.indnullsnotdistinct in a real database.
"""

import os
import subprocess
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPO_ROOT = Path(__file__).resolve().parent.parent

TABLE_NAME = "irs_authorization_warnings"
NEW_CONSTRAINT = "uq_irs_auth_warning_auth_threshold_recipient"
OLD_CONSTRAINT = "uq_irs_auth_warning_auth_threshold"
RECIPIENT_FK = "fk_irs_auth_warning_recipient_user"
RECIPIENT_INDEX = "ix_irs_authorization_warnings_recipient_user_id"

EXPECTED_COLUMNS = ["authorization_id", "threshold_days", "recipient_user_id"]

SCRATCH_DB_NAME = "jamm_irs_warning_recipient_guard"


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
            "point is measurable until it is fixed."
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
def constraint_rows(migrated_database):
    """Every unique constraint on the table, keyed by name, read from pg_index
    so indnullsnotdistinct can be read on its own.

    pg_get_constraintdef would render the constraint back as text, and NULLS
    DISTINCT does not appear in that text because it is the default. Substring
    matching could therefore never tell the two behaviours apart.
    """
    query = text(
        """
        SELECT
            idx.relname AS name,
            i.indisunique AS is_unique,
            i.indnullsnotdistinct AS nulls_not_distinct,
            ARRAY(
                SELECT pg_get_indexdef(i.indexrelid, k + 1, true)
                FROM generate_subscripts(i.indkey, 1) AS k
            ) AS columns
        FROM pg_index i
        JOIN pg_class idx ON idx.oid = i.indexrelid
        JOIN pg_class tbl ON tbl.oid = i.indrelid
        JOIN pg_namespace ns ON ns.oid = tbl.relnamespace
        WHERE tbl.relname = :table_name
          AND ns.nspname = 'public'
          AND i.indisunique
        """
    )
    with migrated_database.connect() as conn:
        rows = conn.execute(query, {"table_name": TABLE_NAME}).mappings().all()
    return {row["name"]: row for row in rows}


def test_three_column_unique_constraint_exists(constraint_rows):
    """Load-bearing assertion one: the per-recipient constraint is present, is
    unique, and covers exactly the three columns in order."""
    row = constraint_rows.get(NEW_CONSTRAINT)
    assert row is not None, (
        f"{NEW_CONSTRAINT} does not exist on {TABLE_NAME} in a database built "
        "by `alembic upgrade head`. Present constraints: "
        f"{sorted(constraint_rows)}"
    )
    assert row["is_unique"], f"{NEW_CONSTRAINT} exists but is not unique."
    assert list(row["columns"]) == EXPECTED_COLUMNS, (
        f"{NEW_CONSTRAINT} covers {list(row['columns'])}, expected "
        f"{EXPECTED_COLUMNS}."
    )


def test_three_column_constraint_is_nulls_distinct(constraint_rows):
    """Load-bearing assertion two: NULLS DISTINCT, the Postgres default.

    Under NULLS NOT DISTINCT every null-recipient row on a tier would collide
    with every other, so deleting a second user who shares a tier with an
    already-deleted one would raise a unique violation from inside an unrelated
    user delete. Ruled Sep 24, 2026.
    """
    row = constraint_rows.get(NEW_CONSTRAINT)
    assert row is not None, f"{NEW_CONSTRAINT} is missing entirely."
    assert row["nulls_not_distinct"] is False, (
        f"{NEW_CONSTRAINT} was built with NULLS NOT DISTINCT. The migration "
        "must not pass postgresql_nulls_not_distinct: legacy rows with no "
        "recipient and rows nulled by user deletion both have to coexist on "
        "one tier."
    )


def test_two_column_constraint_is_gone(constraint_rows):
    """Load-bearing assertion three: the old constraint did not survive.

    If it had, the second recipient's row for a tier would be refused and the
    feature would fail closed while every other assertion here still passed.
    """
    assert OLD_CONSTRAINT not in constraint_rows, (
        f"{OLD_CONSTRAINT} still exists alongside {NEW_CONSTRAINT}. One row "
        "per recipient per tier is impossible while it does."
    )


def test_recipient_foreign_key_is_set_null(migrated_database):
    """Load-bearing assertion four: ON DELETE SET NULL, not CASCADE.

    Users are hard-deleted in this codebase. CASCADE would delete the receipt
    along with the person, which is the compliance record rewriting itself.
    confdeltype is read directly: 'n' is SET NULL, 'c' is CASCADE, 'a' is NO
    ACTION.
    """
    query = text(
        """
        SELECT con.conname, con.confdeltype
        FROM pg_constraint con
        WHERE con.conrelid = 'irs_authorization_warnings'::regclass
          AND con.conname = :fk_name
        """
    )
    with migrated_database.connect() as conn:
        row = conn.execute(query, {"fk_name": RECIPIENT_FK}).mappings().first()

    assert row is not None, (
        f"{RECIPIENT_FK} does not exist. A recipient_user_id with no foreign "
        "key can outlive the user it names."
    )
    assert row["confdeltype"] == "n", (
        f"{RECIPIENT_FK} has confdeltype {row['confdeltype']!r}, expected 'n' "
        "(SET NULL). 'c' would delete the warning receipt when the user is "
        "deleted; 'a' would make the user delete fail outright."
    )


def test_recipient_index_exists(migrated_database):
    with migrated_database.connect() as conn:
        found = conn.execute(
            text("SELECT 1 FROM pg_indexes WHERE tablename = :t AND indexname = :i"),
            {"t": TABLE_NAME, "i": RECIPIENT_INDEX},
        ).first()
    assert found is not None, f"{RECIPIENT_INDEX} is missing."


def test_two_null_recipient_rows_on_one_tier_both_land(migrated_database):
    """The behaviour the NULLS DISTINCT reading above implies, exercised for
    real rather than inferred from a catalog flag.

    Two rows, same authorization, same tier, both with a null recipient. Under
    NULLS NOT DISTINCT the second insert raises. Rows are written with raw SQL
    because the point is what the database permits, not what the ORM does.
    """
    firm_id = uuid.uuid4()
    client_id = uuid.uuid4()
    auth_id = uuid.uuid4()
    now = datetime.now(timezone.utc)

    with migrated_database.connect() as conn:
        conn.execute(
            text("INSERT INTO firms (id, name, slug) VALUES (:i, :n, :s)"),
            {"i": firm_id, "n": "Null Recipient Guard Firm", "s": f"nrg-{firm_id.hex[:8]}"},
        )
        conn.execute(
            text(
                "INSERT INTO clients (id, name, is_active, created_at, updated_at, firm_id) "
                "VALUES (:i, :n, true, now(), now(), :f)"
            ),
            {"i": client_id, "n": "Null Recipient Guard Client", "f": firm_id},
        )
        conn.execute(
            text(
                "INSERT INTO irs_authorizations "
                "(id, firm_id, client_id, form_type, status, valid_until) "
                "VALUES (:i, :f, :c, '8821', 'active', :v)"
            ),
            {"i": auth_id, "f": firm_id, "c": client_id, "v": (now + timedelta(days=30)).date()},
        )

        for offset in (2, 1):
            conn.execute(
                text(
                    "INSERT INTO irs_authorization_warnings "
                    "(id, firm_id, authorization_id, threshold_days, sent_at, "
                    " recipient_user_id, created_at, updated_at) "
                    "VALUES (:i, :f, :a, 30, :s, NULL, now(), now())"
                ),
                {
                    "i": uuid.uuid4(),
                    "f": firm_id,
                    "a": auth_id,
                    "s": now - timedelta(hours=offset),
                },
            )

        landed = conn.execute(
            text(
                "SELECT count(*) FROM irs_authorization_warnings "
                "WHERE authorization_id = :a AND threshold_days = 30 "
                "AND recipient_user_id IS NULL"
            ),
            {"a": auth_id},
        ).scalar()
        conn.commit()

    assert landed == 2, (
        "two null-recipient rows for one tier did not both land, so the "
        "constraint is behaving as NULLS NOT DISTINCT"
    )
