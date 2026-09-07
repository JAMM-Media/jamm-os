# tests/test_filesystem_phase1_schema_guard.py
"""
Guard tests for Filesystem Phase 1 schema changes.

All assertions that touch the CHECK constraints, backfill correctness, or
the data copy from folders -> document_folders run against a scratch database
built from the real migration chain (alembic upgrade head from empty), NOT the
pytest test database. See the enrollment guard test for the full rationale;
the short version is that conftest.py uses create_all() which may not produce
every constraint declared in migrations.

The portal-upload triage_status regression test uses the ordinary test DB
because it exercises application code, not raw schema.
"""

import os
import subprocess
import sys
import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRATCH_DB_NAME = "jamm_filesystem_phase1_guard"


# ------------------------------------------------------------------ #
# Scratch database fixture                                             #
# ------------------------------------------------------------------ #

@pytest.fixture(scope="module")
def migrated_db():
    """Scratch database built by alembic upgrade head from empty."""
    base_url = make_url(os.environ["DATABASE_URL"])
    assert base_url.database != SCRATCH_DB_NAME

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
            "alembic upgrade head failed against an empty database.\n"
            f"stderr tail:\n{result.stderr[-3000:]}"
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


# ------------------------------------------------------------------ #
# Helpers: use ORM so Python-level defaults (is_active, status, etc.) #
# fire correctly for the scratch DB setup rows.                        #
# The invalid-row inserts that test CHECK constraints use raw SQL.     #
# ------------------------------------------------------------------ #

from sqlalchemy.orm import Session as OrmSession
from app.models.firm import Firm as FirmModel
from app.models.client import Client as ClientModel
from app.models.engagement import Engagement as EngagementModel


def _make_firm(engine) -> uuid.UUID:
    with OrmSession(engine) as sess:
        firm = FirmModel(
            name=f"guard-firm-{uuid.uuid4().hex[:6]}",
            slug=f"gf-{uuid.uuid4().hex[:6]}",
        )
        sess.add(firm)
        sess.commit()
        return firm.id


def _make_client(engine, firm_id: uuid.UUID) -> uuid.UUID:
    with OrmSession(engine) as sess:
        client = ClientModel(firm_id=firm_id, name="Guard Client")
        sess.add(client)
        sess.commit()
        return client.id


def _make_engagement(engine, firm_id: uuid.UUID, client_id: uuid.UUID) -> uuid.UUID:
    with OrmSession(engine) as sess:
        eng = EngagementModel(
            firm_id=firm_id, client_id=client_id, name="Guard Engagement"
        )
        sess.add(eng)
        sess.commit()
        return eng.id


# ------------------------------------------------------------------ #
# 1. Documents CHECK constraint: rejected by Postgres at the DB level  #
# ------------------------------------------------------------------ #

class TestDocumentScopeCheckConstraint:
    """CHECK constraint on documents.scope is enforced at the database level."""

    def test_engagement_scope_without_engagement_id_is_rejected(self, migrated_db):
        """scope='engagement' with a NULL engagement_id violates the CHECK constraint."""
        with migrated_db.connect() as conn:
            fid = _make_firm(migrated_db)
            cid = _make_client(migrated_db, fid)
            conn.commit()

            with pytest.raises(IntegrityError):
                conn.execute(text(
                    "INSERT INTO documents"
                    " (id, firm_id, scope, source, triage_status, client_id,"
                    "  engagement_id, filename, s3_key, content_type, size_bytes)"
                    " VALUES (:id, :fid, 'engagement', 'staff', 'filed', :cid,"
                    "  NULL, 'test.pdf', :s3, 'application/pdf', 1024)"
                ), {
                    "id": uuid.uuid4(), "fid": fid, "cid": cid,
                    "s3": f"guard/{uuid.uuid4()}/test.pdf",
                })
                conn.commit()

    def test_client_scope_with_engagement_id_is_rejected(self, migrated_db):
        """scope='client' with a non-NULL engagement_id violates the CHECK constraint."""
        with migrated_db.connect() as conn:
            fid = _make_firm(migrated_db)
            cid = _make_client(migrated_db, fid)
            eid = _make_engagement(migrated_db, fid, cid)

            with pytest.raises(IntegrityError):
                conn.execute(text(
                    "INSERT INTO documents"
                    " (id, firm_id, scope, source, triage_status, client_id,"
                    "  engagement_id, filename, s3_key, content_type, size_bytes)"
                    " VALUES (:id, :fid, 'client', 'staff', 'filed', :cid,"
                    "  :eid, 'test.pdf', :s3, 'application/pdf', 1024)"
                ), {
                    "id": uuid.uuid4(), "fid": fid, "cid": cid, "eid": eid,
                    "s3": f"guard/{uuid.uuid4()}/test.pdf",
                })
                conn.commit()

    def test_firm_library_scope_with_client_id_is_rejected(self, migrated_db):
        """scope='firm_library' with a non-NULL client_id violates the CHECK constraint."""
        with migrated_db.connect() as conn:
            fid = _make_firm(migrated_db)
            cid = _make_client(migrated_db, fid)
            conn.commit()

            with pytest.raises(IntegrityError):
                conn.execute(text(
                    "INSERT INTO documents"
                    " (id, firm_id, scope, source, triage_status, client_id,"
                    "  engagement_id, filename, s3_key, content_type, size_bytes)"
                    " VALUES (:id, :fid, 'firm_library', 'staff', 'filed', :cid,"
                    "  NULL, 'test.pdf', :s3, 'application/pdf', 1024)"
                ), {
                    "id": uuid.uuid4(), "fid": fid, "cid": cid,
                    "s3": f"guard/{uuid.uuid4()}/test.pdf",
                })
                conn.commit()

    def test_valid_engagement_scoped_document_is_accepted(self, migrated_db):
        """A valid engagement-scoped document (both client_id and engagement_id set) succeeds."""
        fid = _make_firm(migrated_db)
        cid = _make_client(migrated_db, fid)
        eid = _make_engagement(migrated_db, fid, cid)

        with migrated_db.connect() as conn:
            conn.execute(text(
                "INSERT INTO documents"
                " (id, firm_id, scope, source, triage_status, client_id,"
                "  engagement_id, filename, s3_key, content_type, size_bytes)"
                " VALUES (:id, :fid, 'engagement', 'staff', 'filed', :cid,"
                "  :eid, 'test.pdf', :s3, 'application/pdf', 1024)"
            ), {
                "id": uuid.uuid4(), "fid": fid, "cid": cid, "eid": eid,
                "s3": f"guard/{uuid.uuid4()}/test.pdf",
            })
            conn.commit()


# ------------------------------------------------------------------ #
# 2. document_folders CHECK constraint                                 #
# ------------------------------------------------------------------ #

class TestDocumentFoldersScopeCheckConstraint:
    """CHECK constraint on document_folders.scope is enforced at the DB level."""

    def test_engagement_scope_without_engagement_id_is_rejected(self, migrated_db):
        with migrated_db.connect() as conn:
            fid = _make_firm(migrated_db)
            cid = _make_client(migrated_db, fid)
            conn.commit()

            with pytest.raises(IntegrityError):
                conn.execute(text(
                    "INSERT INTO document_folders"
                    " (id, firm_id, scope, client_id, engagement_id, name, created_at, updated_at)"
                    " VALUES (:id, :fid, 'engagement', :cid, NULL, 'Bad', now(), now())"
                ), {"id": uuid.uuid4(), "fid": fid, "cid": cid})
                conn.commit()

    def test_client_scope_without_client_id_is_rejected(self, migrated_db):
        with migrated_db.connect() as conn:
            fid = _make_firm(migrated_db)
            conn.commit()

            with pytest.raises(IntegrityError):
                conn.execute(text(
                    "INSERT INTO document_folders"
                    " (id, firm_id, scope, client_id, engagement_id, name, created_at, updated_at)"
                    " VALUES (:id, :fid, 'client', NULL, NULL, 'Bad', now(), now())"
                ), {"id": uuid.uuid4(), "fid": fid})
                conn.commit()

    def test_valid_client_scoped_folder_is_accepted(self, migrated_db):
        with migrated_db.connect() as conn:
            fid = _make_firm(migrated_db)
            cid = _make_client(migrated_db, fid)
            conn.commit()

            conn.execute(text(
                "INSERT INTO document_folders"
                " (id, firm_id, scope, client_id, engagement_id, name, created_at, updated_at)"
                " VALUES (:id, :fid, 'client', :cid, NULL, 'Good Folder', now(), now())"
            ), {"id": uuid.uuid4(), "fid": fid, "cid": cid})
            conn.commit()


# ------------------------------------------------------------------ #
# 3. Backfill correctness (checked against the live dev database)     #
# ------------------------------------------------------------------ #

class TestBackfillCorrectness:
    """Every existing row correctly backfilled: no NULL scope, source, triage_status."""

    def test_no_null_scope_after_migration(self, migrated_db):
        with migrated_db.connect() as conn:
            n = conn.execute(text(
                "SELECT count(id) FROM documents WHERE scope IS NULL"
            )).scalar()
        assert n == 0, f"{n} documents still have NULL scope after migration"

    def test_no_null_source_after_migration(self, migrated_db):
        with migrated_db.connect() as conn:
            n = conn.execute(text(
                "SELECT count(id) FROM documents WHERE source IS NULL"
            )).scalar()
        assert n == 0, f"{n} documents still have NULL source after migration"

    def test_no_null_triage_status_after_migration(self, migrated_db):
        with migrated_db.connect() as conn:
            n = conn.execute(text(
                "SELECT count(id) FROM documents WHERE triage_status IS NULL"
            )).scalar()
        assert n == 0, f"{n} documents still have NULL triage_status after migration"

    def test_scope_rule_holds_for_every_row(self, migrated_db):
        """No document's scope violates the rule that's enforced by the CHECK constraint."""
        with migrated_db.connect() as conn:
            # engagement scope must have both client_id and engagement_id
            bad_engagement = conn.execute(text(
                "SELECT count(id) FROM documents"
                " WHERE scope='engagement'"
                " AND (engagement_id IS NULL OR client_id IS NULL)"
            )).scalar()
            # client scope must have client_id and no engagement_id
            bad_client = conn.execute(text(
                "SELECT count(id) FROM documents"
                " WHERE scope='client'"
                " AND (client_id IS NULL OR engagement_id IS NOT NULL)"
            )).scalar()
        assert bad_engagement == 0, f"{bad_engagement} engagement-scoped docs fail FK rule"
        assert bad_client == 0, f"{bad_client} client-scoped docs fail FK rule"


# ------------------------------------------------------------------ #
# 4. Data copy: folders -> document_folders                           #
# ------------------------------------------------------------------ #

class TestDataCopy:
    """Every folders row has a corresponding document_folders row."""

    def test_document_folders_count_matches_folders(self, migrated_db):
        # Count only the rows that were copied from folders (matching by ID),
        # not the total document_folders count, since earlier constraint tests
        # may have inserted additional rows into document_folders.
        with migrated_db.connect() as conn:
            folders_n = conn.execute(text("SELECT count(id) FROM folders")).scalar()
            copied_n = conn.execute(text(
                "SELECT count(df.id) FROM document_folders df"
                " JOIN folders f ON f.id = df.id"
            )).scalar()
        assert copied_n == folders_n, (
            f"document_folders has {copied_n} rows matching source folders IDs,"
            f" but folders has {folders_n} rows. "
            "The data copy INSERT...SELECT may have missed rows."
        )

    def test_every_copied_row_has_scope_client(self, migrated_db):
        with migrated_db.connect() as conn:
            bad = conn.execute(text(
                "SELECT count(id) FROM document_folders WHERE scope != 'client'"
            )).scalar()
        assert bad == 0, (
            f"{bad} document_folders rows have scope != 'client'. All copied "
            "rows from 'folders' must be client-scoped."
        )

    def test_copied_row_ids_match_source_ids(self, migrated_db):
        with migrated_db.connect() as conn:
            missing = conn.execute(text(
                "SELECT count(f.id) FROM folders f"
                " LEFT JOIN document_folders df ON df.id = f.id"
                " WHERE df.id IS NULL"
            )).scalar()
        assert missing == 0, (
            f"{missing} folders rows have no matching document_folders row. "
            "The copy preserved IDs so each row is traceable."
        )

    def test_copied_rows_preserve_client_id_and_firm_id(self, migrated_db):
        with migrated_db.connect() as conn:
            mismatched = conn.execute(text(
                "SELECT count(f.id) FROM folders f"
                " JOIN document_folders df ON df.id = f.id"
                " WHERE df.client_id != f.client_id OR df.firm_id != f.firm_id"
            )).scalar()
        assert mismatched == 0, (
            f"{mismatched} copied rows have mismatched client_id or firm_id."
        )


# ------------------------------------------------------------------ #
# 5. Portal upload regression: triage_status must default to 'filed'  #
# ------------------------------------------------------------------ #

class TestPortalUploadTriage:
    """Portal uploads must still create documents with triage_status='filed'.

    Changing triage_status to 'pending' before the Phase 5 triage tray is
    built would make client-uploaded files invisible to staff.
    """

    def test_portal_upload_creates_document_with_triage_status_filed(self):
        from app.models.client import Client
        from app.models.document import Document
        from app.services import portal_service
        from sqlalchemy import select
        from tests.conftest import TestingSessionLocal
        import uuid as _uuid
        from app.models.engagement import Engagement
        from app.models.firm import Firm

        suf = _uuid.uuid4().hex[:8]
        db = TestingSessionLocal()
        try:
            firm = Firm(name=f"Triage Guard Firm {suf}", slug=f"tg-{suf}")
            db.add(firm)
            db.commit()
            db.refresh(firm)
            firm_id = firm.id

            client = Client(
                firm_id=firm_id,
                name="Triage Guard Client",
                email=f"tg-{suf}@example.com",
            )
            db.add(client)
            db.commit()
            db.refresh(client)
            client_id = client.id

            eng = Engagement(
                firm_id=firm_id,
                client_id=client_id,
                name="Triage Guard Engagement",
            )
            db.add(eng)
            db.commit()
            db.refresh(eng)
            eng_id = eng.id
        finally:
            db.close()

        import io
        from fastapi import UploadFile

        upload = UploadFile(filename="triage_guard.pdf", file=io.BytesIO(b"content"))

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            with patch("app.services.document_service.s3_service.upload_fileobj",
                       return_value=None):
                doc = portal_service.upload_document(
                    db=db,
                    file=upload,
                    engagement_id=eng_id,
                    client=client_obj,
                )
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            stmt = select(Document).where(Document.id == doc.id)
            record = db.execute(stmt).scalar_one_or_none()
            assert record is not None
            assert record.triage_status == "filed", (
                f"Portal upload created triage_status={record.triage_status!r}. "
                "It must be 'filed' until Phase 5 triage tray is built; "
                "'pending' makes the file invisible to staff."
            )
        finally:
            db.close()
