# tests/test_portal_document_upload.py
"""
Tests confirming that portal document uploads create a real Document row
with uploaded_by=None, not the client UUID (which is not in the users table
and would cause a ForeignKeyViolation on insert).
"""

import io
import uuid
from unittest.mock import patch

import pytest

from sqlalchemy import select

from app.models.client import Client
from app.models.document import Document
from app.models.engagement import Engagement
from app.models.firm import Firm
from app.services import portal_service
from tests.conftest import TestingSessionLocal


def _setup_firm_client_engagement():
    """Create a firm, client, and engagement. Returns (client_obj, engagement_id)."""
    suf = uuid.uuid4().hex[:8]
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Portal Upload Firm {suf}", slug=f"pu-{suf}")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        client = Client(
            firm_id=firm.id,
            name="Portal Upload Client",
            email=f"pu-{suf}@example.com",
        )
        db.add(client)
        db.commit()
        db.refresh(client)

        engagement = Engagement(
            firm_id=firm.id,
            client_id=client.id,
            name="Portal Upload Engagement",
        )
        db.add(engagement)
        db.commit()
        db.refresh(engagement)

        return client.id, firm.id, engagement.id
    finally:
        db.close()


def _fake_upload_file(content=b"portal test content", filename="portal_test.txt"):
    from fastapi import UploadFile
    # content_type is a read-only property on UploadFile; omit it and let
    # document_service fall back to "application/octet-stream".
    return UploadFile(filename=filename, file=io.BytesIO(content))


class TestPortalDocumentUpload:

    def test_upload_creates_document_with_uploaded_by_none(self):
        """Portal upload must write uploaded_by=None, not the client UUID.

        Before the D1 fix, portal_service passed current_user_id=client.id
        into document_service.upload_document. That value is a Client UUID
        which is not in the users table, causing a ForeignKeyViolation and a
        generic 500 on every portal upload attempt. The fix passes None instead,
        matching the intended design confirmed by portal.py display logic:
        uploaded_by is None renders as 'client'.
        """
        client_id, firm_id, engagement_id = _setup_firm_client_engagement()

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file()

            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db,
                    file=upload_file,
                    engagement_id=engagement_id,
                    client=client_obj,
                )
        finally:
            db.close()

        # Verify the Document row was actually created
        db = TestingSessionLocal()
        try:
            stmt = select(Document).where(Document.id == doc.id)
            record = db.execute(stmt).scalar_one_or_none()
            assert record is not None, "Document row was not created"
            assert record.uploaded_by is None, (
                f"uploaded_by should be None for portal uploads; got {record.uploaded_by}"
            )
            assert record.source == "client", (
                f"source should be 'client' for portal uploads; got {record.source!r}"
            )
            assert record.source_client_id == client_id, (
                f"source_client_id should be the portal client's UUID; "
                f"got {record.source_client_id}"
            )
            # Portal display logic: None means the upload came from the client side
            displayed_uploader = "client" if record.uploaded_by is None else "firm"
            assert displayed_uploader == "client"
        finally:
            db.close()

    def test_upload_does_not_write_client_uuid_into_uploaded_by(self):
        """The client's own UUID must not be stored in uploaded_by.

        uploaded_by has a FK to users.id. A client UUID is not in that table.
        Writing it there causes a ForeignKeyViolation.
        """
        client_id, firm_id, engagement_id = _setup_firm_client_engagement()

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            upload_file = _fake_upload_file(content=b"second upload", filename="second.txt")

            with patch("app.services.document_service.s3_service.upload_fileobj", return_value=None):
                doc = portal_service.upload_document(
                    db=db,
                    file=upload_file,
                    engagement_id=engagement_id,
                    client=client_obj,
                )
        finally:
            db.close()

        db = TestingSessionLocal()
        try:
            record = db.query(Document).filter(Document.id == doc.id).first()
            assert record is not None
            assert record.uploaded_by != client_id, (
                "uploaded_by must not contain the client UUID (FK points at users, not clients)"
            )
        finally:
            db.close()

    def test_oversized_file_raises_413(self):
        """Files exceeding MAX_UPLOAD_BYTES are rejected with a 413 before S3 is touched."""
        from fastapi import HTTPException
        from app.services.document_service import MAX_UPLOAD_BYTES

        client_id, firm_id, engagement_id = _setup_firm_client_engagement()

        db = TestingSessionLocal()
        try:
            client_obj = db.query(Client).filter(Client.id == client_id).first()
            # One byte over the limit; size check happens before S3 upload so no mock needed.
            oversized = _fake_upload_file(
                content=b'x' * (MAX_UPLOAD_BYTES + 1),
                filename="oversized.pdf",
            )
            with pytest.raises(HTTPException) as exc_info:
                portal_service.upload_document(
                    db=db,
                    file=oversized,
                    engagement_id=engagement_id,
                    client=client_obj,
                )
            assert exc_info.value.status_code == 413
        finally:
            db.close()

