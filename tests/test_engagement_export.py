# tests/test_engagement_export.py
"""
Guard tests for per-engagement document export (Filesystem spec Section 13).

Tests:
  1. Documents in a nested folder structure land at the correct nested path
     inside the zip (not flattened to the root). Watched red by temporarily
     flattening the zip-write logic to zip_path = doc.filename unconditionally;
     the nested-path assertion fails, confirming the test actually guards the
     behavior. Restored, the test is green.
  2. A document belonging to a different engagement is absent from the zip
     (engagement scoping is real, not accidental via a missing filter).
"""

import io
import uuid
import zipfile
from unittest.mock import MagicMock, patch

from app.core.enums import UserRole
from app.models.client import Client
from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.models.engagement import Engagement
from sqlalchemy import select
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_folder(firm_id, client_id, engagement_id, name, parent_folder_id=None):
    from app.crud.document_folder import create_document_folder
    db = TestingSessionLocal()
    try:
        folder = create_document_folder(
            db=db,
            firm_id=uuid.UUID(firm_id),
            scope="engagement",
            name=name,
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(engagement_id),
            parent_folder_id=uuid.UUID(parent_folder_id) if parent_folder_id else None,
        )
        return str(folder.id)
    finally:
        db.close()


def _make_document(firm_id, client_id, engagement_id, filename, folder_id=None):
    db = TestingSessionLocal()
    try:
        doc = Document(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(engagement_id),
            scope="engagement",
            filename=filename,
            s3_key=f"docs/{uuid.uuid4()}/{filename}",
            content_type="application/pdf",
            size_bytes=512,
            folder_id=uuid.UUID(folder_id) if folder_id else None,
        )
        db.add(doc)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_zip_preserves_nested_folder_structure_and_excludes_other_engagement(
    client, firm_a_owner
):
    """
    Layout:
      Engagement A:
        Folder A/
          Subfolder B/
            deep.pdf      -> must appear at "Folder A/Subfolder B/deep.pdf"
        root.pdf          -> must appear at "root.pdf"
      Engagement B:
        other.pdf         -> must NOT appear in Engagement A's zip
    """
    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Export Test Client"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = client.post(
        "/engagements/", json={"name": "Eng A", "client_id": client_id}, headers=headers
    )
    assert r.status_code == 201, r.text
    eng_a_id = r.json()["id"]

    r = client.post(
        "/engagements/", json={"name": "Eng B", "client_id": client_id}, headers=headers
    )
    assert r.status_code == 201, r.text
    eng_b_id = r.json()["id"]

    folder_a_id = _make_folder(firm_id, client_id, eng_a_id, "Folder A")
    subfolder_b_id = _make_folder(
        firm_id, client_id, eng_a_id, "Subfolder B", parent_folder_id=folder_a_id
    )

    _make_document(firm_id, client_id, eng_a_id, "deep.pdf", folder_id=subfolder_b_id)
    _make_document(firm_id, client_id, eng_a_id, "root.pdf")
    _make_document(firm_id, client_id, eng_b_id, "other.pdf")

    db = TestingSessionLocal()
    try:
        from app.models.user import User
        owner = db.execute(
            select(User).where(User.email == "owner@firma.com")
        ).scalars().first()
        owner_id = owner.id
    finally:
        db.close()

    captured_zip: list = []

    def fake_upload(fileobj, key, content_type):
        captured_zip.append(fileobj.read())

    fake_presigned = MagicMock(return_value="https://s3.example.com/fake")
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.content = b"PDF_CONTENT"

    with (
        patch("app.services.s3.upload_fileobj", side_effect=fake_upload),
        patch("app.services.s3.generate_presigned_url", fake_presigned),
        patch("requests.get", return_value=fake_response),
        patch("app.services.email_service.EmailService.send_notification_email"),
        patch("app.services.behavioral_log.log_event"),
    ):
        from app.services.document_archive_service import _run_engagement_archive
        import logging

        db = TestingSessionLocal()
        try:
            log = logging.getLogger("test_engagement_export")
            _run_engagement_archive(
                uuid.UUID(firm_id), uuid.UUID(eng_a_id), owner_id, db, log
            )
        finally:
            db.close()

    assert captured_zip, "Expected a zip to be uploaded -- archive produced no output"

    zf = zipfile.ZipFile(io.BytesIO(captured_zip[0]))
    names = zf.namelist()

    assert "Folder A/Subfolder B/deep.pdf" in names, (
        f"Nested path 'Folder A/Subfolder B/deep.pdf' missing from zip. Got: {names}"
    )
    assert "root.pdf" in names, (
        f"Root-level 'root.pdf' missing from zip. Got: {names}"
    )
    assert "other.pdf" not in names, (
        f"Document from a different engagement leaked into zip. Got: {names}"
    )


def test_document_in_trashed_folder_appears_at_original_nested_path(client, firm_a_owner):
    """
    A document whose parent folder was soft-deleted but whose own deleted_at is null
    must appear in the zip at its original nested path using the trashed folder's real
    name -- not dropped silently and not re-rooted under its bare filename.

    Before fix (folder excluded by deleted_at.is_(None)):
      zip contents: ['inside_trashed.pdf', 'root_doc.pdf']
      'Trashed Folder/inside_trashed.pdf' absent -- document silently re-rooted.

    After fix (deleted_at filter removed from folder query):
      zip contents: ['Trashed Folder/inside_trashed.pdf', 'root_doc.pdf']
      document appears at its real nested path.
    """
    from app.models.document import Document
    from app.models.document_folder import DocumentFolder
    from sqlalchemy import select
    from datetime import datetime, timezone
    from tests.conftest import TestingSessionLocal

    firm_id = firm_a_owner["firm_id"]
    headers = firm_a_owner["headers"]

    r = client.post("/clients/", json={"name": "Trashed Folder Client"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]

    r = client.post(
        "/engagements/", json={"name": "Trashed Folder Eng", "client_id": client_id}, headers=headers
    )
    assert r.status_code == 201, r.text
    eng_id = r.json()["id"]

    # Create folder and document inside it
    from app.crud.document_folder import create_document_folder
    db = TestingSessionLocal()
    try:
        folder = create_document_folder(
            db=db, firm_id=uuid.UUID(firm_id), scope="engagement", name="Trashed Folder",
            client_id=uuid.UUID(client_id), engagement_id=uuid.UUID(eng_id), parent_folder_id=None,
        )
        folder_id = folder.id
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        doc = Document(
            firm_id=uuid.UUID(firm_id), client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(eng_id), scope="engagement",
            filename="inside_trashed.pdf",
            s3_key=f"docs/{uuid.uuid4()}/inside_trashed.pdf",
            content_type="application/pdf", size_bytes=512,
            folder_id=folder_id,
        )
        db.add(doc)
        root_doc = Document(
            firm_id=uuid.UUID(firm_id), client_id=uuid.UUID(client_id),
            engagement_id=uuid.UUID(eng_id), scope="engagement",
            filename="root_doc.pdf",
            s3_key=f"docs/{uuid.uuid4()}/root_doc.pdf",
            content_type="application/pdf", size_bytes=512,
        )
        db.add(root_doc)
        db.commit()
    finally:
        db.close()

    # Soft-delete the folder only -- document itself stays live
    db = TestingSessionLocal()
    try:
        f = db.query(DocumentFolder).filter(DocumentFolder.id == folder_id).first()
        f.deleted_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()

    captured_zip: list = []

    def fake_upload(fileobj, key, content_type):
        captured_zip.append(fileobj.read())

    fake_presigned = MagicMock(return_value="https://s3.example.com/fake")
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.content = b"PDF_CONTENT"

    with (
        patch("app.services.s3.upload_fileobj", side_effect=fake_upload),
        patch("app.services.s3.generate_presigned_url", fake_presigned),
        patch("requests.get", return_value=fake_response),
        patch("app.services.email_service.EmailService.send_notification_email"),
        patch("app.services.behavioral_log.log_event"),
    ):
        from app.services.document_archive_service import _run_engagement_archive
        import logging

        from app.models.user import User
        db = TestingSessionLocal()
        try:
            owner = db.execute(
                select(User).where(User.email == "owner@firma.com")
            ).scalars().first()
            owner_id = owner.id
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            _run_engagement_archive(
                uuid.UUID(firm_id), uuid.UUID(eng_id), owner_id, db, logging.getLogger("test")
            )
        finally:
            db.close()

    assert captured_zip, "No zip produced"
    zf = zipfile.ZipFile(io.BytesIO(captured_zip[0]))
    names = sorted(zf.namelist())

    assert "Trashed Folder/inside_trashed.pdf" in names, (
        f"Expected 'Trashed Folder/inside_trashed.pdf' in zip but got: {names}"
    )
    assert "root_doc.pdf" in names, (
        f"Expected 'root_doc.pdf' in zip but got: {names}"
    )
