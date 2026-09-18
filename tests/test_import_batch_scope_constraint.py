# tests/test_import_batch_scope_constraint.py
"""
Guard test for the scope CHECK constraint on import_batches.

Proves that the CHECK constraint in the MIGRATION FILE (not the model's
__table_args__) enforces scope/FK consistency at the database level.

Uses the migration_db_session fixture from conftest, which provisions a real
Postgres scratch database where import_batches and import_items are created
by running the real Alembic migration file. This means the schema for those
two tables comes from the migration file's raw DDL, not from
Base.metadata.create_all(), so a drift between model and migration is caught.

Step 3 watched-fail cycle:
  Temporarily corrupt only the migration file's CHECK constraint text (e.g.
  swap AND for OR in one clause). Run this test. It wrongly passes (bad insert
  succeeds), proving the fixture genuinely runs the migration file's SQL.
  Restore the migration. The test correctly fails again (constraint refuses
  the bad insert). git diff on the restored migration file is empty.
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from app.models.import_batch import ImportBatch


def _seed_firm_and_client(session):
    """Insert a minimal Firm, User, and Client into the migration-built scratch DB
    using the ORM models so all non-nullable columns get their defaults."""
    from app.models.firm import Firm
    from app.models.user import User
    from app.models.client import Client
    from app.core.enums import UserRole
    from app.core.security import get_password_hash

    firm = Firm(name="Scratch Firm", slug=f"scratch-{uuid.uuid4().hex[:8]}")
    session.add(firm)
    session.flush()

    owner = User(
        firm_id=firm.id,
        email=f"owner-{uuid.uuid4().hex[:8]}@scratch.test",
        hashed_password=get_password_hash("x"),
        full_name="Scratch Owner",
        role=UserRole.firm_owner,
    )
    session.add(owner)
    session.flush()

    client = Client(firm_id=firm.id, name="Scratch Client")
    session.add(client)
    session.flush()

    return firm.id, owner.id, client.id


def test_migration_check_constraint_rejects_engagement_scope_with_null_engagement_id(
    migration_db_session,
):
    """
    Inserting an import_batches row with scope='engagement' but engagement_id=NULL
    must raise IntegrityError. This test uses the migration_db_session fixture,
    so the schema comes from the real Alembic migration files -- not from
    Base.metadata.create_all(). If the migration's CHECK constraint text is
    wrong or absent, this test catches it even if the model's __table_args__ is
    correct, because the two are built independently.

    Step 3 watched-fail: temporarily corrupt the migration file's CHECK constraint
    text (e.g. swap AND for OR in one clause), run this test, confirm it
    wrongly passes (bad insert succeeds), restore the migration, confirm it
    fails correctly again.
    """
    db = migration_db_session

    firm_id, user_id, client_id = _seed_firm_and_client(db)

    # Deliberately violate: scope='engagement' but engagement_id is null.
    bad_row = ImportBatch(
        firm_id=firm_id,
        created_by_user_id=user_id,
        scope="engagement",
        client_id=client_id,
        engagement_id=None,   # <-- violates ck_import_batches_scope_fk_consistency
        status="draft",
        conflict_policy="skip",
        total_files=0,
        total_bytes=0,
        completed_files=0,
        failed_files=0,
        skipped_files=0,
    )
    db.add(bad_row)
    with pytest.raises(IntegrityError):
        db.flush()
