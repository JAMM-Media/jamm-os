# tests/test_filesystem_pbc_system_key.py
"""
Guard tests for the PBC system_key feature (filesystem spec Section 5 revision).

Tests:
  (a) Rename-survives: approval routes to the PBC folder after it is renamed.
  (b) Roll-forward excludes by key: the system PBC folder is not copied;
      the destination keeps its own.
  (c) Uniqueness at the database: the partial unique index prevents a second
      live folder with system_key='pbc' on the same engagement, while NULL
      keys and soft-deleted rows are not subject to the constraint.

WATCHED-FAIL PROCEDURE:
  (a) BREAK: make get_system_folder return None in app/crud/document_folder.py
      EXPECTED RED: document.folder_id is None instead of the renamed folder id
      RESTORE / CONFIRM GREEN

  (b) BREAK: remove DocumentFolder.system_key.is_(None) filter from
      copy_folder_structure in app/services/document_folder_service.py
      EXPECTED RED: result["folders_created"] == 2 instead of 1
      RESTORE / CONFIRM GREEN

  (c) BREAK: comment out the op.create_index('ux_document_folders_engagement_system_key',...)
      call in the migration, rebuild the scratch DB, run test
      EXPECTED RED: pytest.raises(IntegrityError) block passes without error
      RESTORE / CONFIRM GREEN
"""

import uuid
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session as OrmSession

from tests.conftest import TestingSessionLocal
from tests.test_filesystem_phase1_schema_guard import migrated_db  # noqa: F401

from app.models.client import Client
from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.crud import document_folder as crud_folder
from app.crud import engagement as crud_engagement
from app.schemas.engagement import EngagementCreate
from app.services import document_folder_service
from app.services import document_service
from app.services import portal_service
from fastapi import UploadFile
import io


# ---------------------------------------------------------------------------
# Shared helpers (TestingSessionLocal, not scratch DB)
# ---------------------------------------------------------------------------

def _make_firm_client_and_owner():
    suf = uuid.uuid4().hex[:8]
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"PBC Firm {suf}", slug=f"pbc-{suf}")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        client_obj = Client(
            firm_id=firm.id,
            name=f"PBC Client {suf}",
            email=f"pbc-{suf}@example.com",
        )
        db.add(client_obj)
        db.commit()
        db.refresh(client_obj)

        owner = User(
            firm_id=firm.id,
            email=f"owner-{suf}@example.com",
            hashed_password=get_password_hash("testpass123"),
            full_name="Owner",
            role=UserRole.firm_owner,
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)

        return firm.id, client_obj.id, owner.id
    finally:
        db.close()


def _create_engagement_via_service(firm_id, client_id):
    """Create an engagement through crud.engagement.create_engagement, which
    also creates the PBC starter folder with system_key='pbc'."""
    db = TestingSessionLocal()
    try:
        eng_schema = EngagementCreate(
            name=f"PBC Eng {uuid.uuid4().hex[:6]}",
            client_id=client_id,
        )
        eng = crud_engagement.create_engagement(db=db, engagement_in=eng_schema, firm_id=firm_id)
        return eng.id
    finally:
        db.close()


def _get_system_folder(firm_id, engagement_id, system_key="pbc"):
    db = TestingSessionLocal()
    try:
        return crud_folder.get_system_folder(
            db=db, firm_id=firm_id, engagement_id=engagement_id, system_key=system_key
        )
    finally:
        db.close()


def _fake_file(content=b"test content", filename="upload.txt"):
    return UploadFile(filename=filename, file=io.BytesIO(content))


# ---------------------------------------------------------------------------
# (a) Rename-survives: approval uses system_key, not display name
#
# BREAK: in app/crud/document_folder.py, make get_system_folder return None.
# EXPECTED RED: document.folder_id is None (fallback to root, not renamed folder).
# RESTORE: revert to the real query.
# CONFIRM GREEN: document.folder_id == pbc_folder.id (renamed folder).
# ---------------------------------------------------------------------------

class TestRenameDoesNotBreakApproval:

    def test_approve_routes_to_pbc_folder_after_rename(self):
        """Approval finds the PBC folder by system_key even after it is renamed."""
        firm_id, client_id, owner_id = _make_firm_client_and_owner()
        engagement_id = _create_engagement_via_service(firm_id, client_id)

        # Get and rename the PBC folder.
        pbc_folder = _get_system_folder(firm_id, engagement_id)
        assert pbc_folder is not None, "PBC folder must exist after engagement creation"
        pbc_folder_id = pbc_folder.id

        db = TestingSessionLocal()
        try:
            folder_obj = crud_folder.get_document_folder(
                db, folder_id=pbc_folder_id, firm_id=firm_id
            )
            document_folder_service.rename_folder(
                db=db, folder=folder_obj, firm_id=firm_id, name="Client Docs"
            )
        finally:
            db.close()

        # Confirm rename took effect and system_key is still set.
        db = TestingSessionLocal()
        try:
            renamed = crud_folder.get_document_folder(
                db, folder_id=pbc_folder_id, firm_id=firm_id
            )
            assert renamed.name == "Client Docs"
            assert renamed.system_key == "pbc"
        finally:
            db.close()

        # Portal upload -> pending document.
        db = TestingSessionLocal()
        doc_id = None
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db,
                    file=_fake_file(),
                    engagement_id=engagement_id,
                    client=client_obj,
                )
            doc_id = doc.id
        finally:
            db.close()

        assert doc_id is not None

        # Approve via the real service.
        db = TestingSessionLocal()
        try:
            owner = db.query(User).filter(User.id == owner_id).first()
            doc_service_doc = db.query(Document).filter(Document.id == doc_id).first()
            assert doc_service_doc is not None
            document_service.approve_pending_document(
                db=db,
                user=owner,
                document_id=doc_id,
                firm_id=firm_id,
                current_user_id=owner_id,
            )
        finally:
            db.close()

        # The document must land in the renamed PBC folder.
        db = TestingSessionLocal()
        try:
            approved = db.query(Document).filter(Document.id == doc_id).first()
            assert approved is not None
            assert approved.folder_id == pbc_folder_id, (
                f"Expected folder_id={pbc_folder_id} (renamed PBC folder); "
                f"got {approved.folder_id}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# (b) Roll-forward excludes by key
#
# BREAK: remove DocumentFolder.system_key.is_(None) from the filter in
#        copy_folder_structure in app/services/document_folder_service.py.
# EXPECTED RED: result["folders_created"] == 2 (PBC also copied).
# RESTORE: reinstate the system_key.is_(None) filter.
# CONFIRM GREEN: result["folders_created"] == 1; dest has one system folder.
# ---------------------------------------------------------------------------

class TestRollForwardExcludesByKey:

    def test_system_folder_excluded_dest_keeps_own(self):
        """copy_folder_structure skips source's system folders by key.
        The destination engagement's own system folder is not duplicated."""
        firm_id, client_id, owner_id = _make_firm_client_and_owner()
        source_eng_id = _create_engagement_via_service(firm_id, client_id)
        dest_eng_id = _create_engagement_via_service(firm_id, client_id)

        # Rename source PBC folder (proves key, not name, is used for exclusion).
        pbc = _get_system_folder(firm_id, source_eng_id)
        assert pbc is not None
        db = TestingSessionLocal()
        try:
            folder_obj = crud_folder.get_document_folder(db, folder_id=pbc.id, firm_id=firm_id)
            document_folder_service.rename_folder(
                db=db, folder=folder_obj, firm_id=firm_id, name="Renamed PBC"
            )
        finally:
            db.close()

        # Add one ordinary firm-created folder to source.
        db = TestingSessionLocal()
        try:
            source_eng = db.query(Engagement).filter(Engagement.id == source_eng_id).first()
            ord_folder = crud_folder.create_document_folder(
                db=db,
                firm_id=firm_id,
                scope="engagement",
                name="Work Papers",
                client_id=client_id,
                engagement_id=source_eng_id,
            )
            ord_folder_id = ord_folder.id
        finally:
            db.close()

        # Roll forward: only the ordinary folder should be copied.
        db = TestingSessionLocal()
        try:
            result = document_folder_service.copy_folder_structure(
                db=db,
                source_engagement_id=source_eng_id,
                dest_engagement_id=dest_eng_id,
                firm_id=firm_id,
                current_user_id=owner_id,
            )
        finally:
            db.close()

        assert result["folders_created"] == 1, (
            f"Expected 1 folder created (ordinary only); got {result['folders_created']}"
        )

        # Destination must still have exactly one folder with system_key='pbc'.
        db = TestingSessionLocal()
        try:
            dest_system_folders = (
                db.query(DocumentFolder)
                .filter(
                    DocumentFolder.firm_id == firm_id,
                    DocumentFolder.engagement_id == dest_eng_id,
                    DocumentFolder.system_key == "pbc",
                    DocumentFolder.deleted_at.is_(None),
                )
                .all()
            )
            assert len(dest_system_folders) == 1, (
                f"Expected exactly 1 pbc system folder in dest; "
                f"got {len(dest_system_folders)}"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# (c) Uniqueness enforced at the database level
#
# BREAK: comment out the op.create_index('ux_document_folders_engagement_system_key',...)
#        lines in the migration. Rebuild the scratch database. Run the test.
# EXPECTED RED: pytest.raises(IntegrityError) completes without the expected
#               exception -- the duplicate insert succeeds.
# RESTORE: uncomment the lines. Rebuild. Confirm green.
# ---------------------------------------------------------------------------

def _scratch_firm(engine) -> uuid.UUID:
    with OrmSession(engine) as sess:
        firm = Firm(name=f"sk-firm-{uuid.uuid4().hex[:6]}", slug=f"sk-{uuid.uuid4().hex[:6]}")
        sess.add(firm)
        sess.commit()
        return firm.id


def _scratch_client(engine, firm_id) -> uuid.UUID:
    with OrmSession(engine) as sess:
        c = Client(firm_id=firm_id, name="sk-client")
        sess.add(c)
        sess.commit()
        return c.id


def _scratch_engagement(engine, firm_id, client_id) -> uuid.UUID:
    with OrmSession(engine) as sess:
        e = Engagement(firm_id=firm_id, client_id=client_id, name="sk-eng")
        sess.add(e)
        sess.commit()
        return e.id


class TestUniquenessAtDatabase:

    def test_duplicate_live_pbc_raises_integrity_error(self, migrated_db):
        """Two live folders with system_key='pbc' on the same engagement are rejected."""
        fid = _scratch_firm(migrated_db)
        cid = _scratch_client(migrated_db, fid)
        eid = _scratch_engagement(migrated_db, fid, cid)

        # First live PBC folder: must succeed.
        with OrmSession(migrated_db) as sess:
            f1 = DocumentFolder(
                firm_id=fid, client_id=cid, engagement_id=eid,
                scope="engagement", name="PBC-1", system_key="pbc",
            )
            sess.add(f1)
            sess.commit()

        # Second live PBC folder on the same engagement: must fail.
        with pytest.raises(IntegrityError):
            with OrmSession(migrated_db) as sess:
                f2 = DocumentFolder(
                    firm_id=fid, client_id=cid, engagement_id=eid,
                    scope="engagement", name="PBC-2", system_key="pbc",
                )
                sess.add(f2)
                sess.commit()

    def test_null_system_key_not_subject_to_uniqueness(self, migrated_db):
        """Two live folders with system_key=None on the same engagement are allowed."""
        fid = _scratch_firm(migrated_db)
        cid = _scratch_client(migrated_db, fid)
        eid = _scratch_engagement(migrated_db, fid, cid)

        with OrmSession(migrated_db) as sess:
            for name in ("Folder A", "Folder B"):
                sess.add(DocumentFolder(
                    firm_id=fid, client_id=cid, engagement_id=eid,
                    scope="engagement", name=name, system_key=None,
                ))
            sess.commit()

    def test_soft_deleted_pbc_not_subject_to_uniqueness(self, migrated_db):
        """A soft-deleted pbc folder and a live pbc folder can coexist."""
        fid = _scratch_firm(migrated_db)
        cid = _scratch_client(migrated_db, fid)
        eid = _scratch_engagement(migrated_db, fid, cid)

        with OrmSession(migrated_db) as sess:
            # Soft-deleted row: excluded from partial index.
            f_deleted = DocumentFolder(
                firm_id=fid, client_id=cid, engagement_id=eid,
                scope="engagement", name="Old PBC", system_key="pbc",
                deleted_at=datetime.now(timezone.utc),
            )
            sess.add(f_deleted)
            # Live row: inside the partial index.
            f_live = DocumentFolder(
                firm_id=fid, client_id=cid, engagement_id=eid,
                scope="engagement", name="Current PBC", system_key="pbc",
            )
            sess.add(f_live)
            sess.commit()
