# tests/test_portal_signed_documents.py
"""
Tests for GET /portal/signed-documents.

Covers: correct filtering on status="signed", tenant isolation,
exclusion of in-progress envelopes, and signer/date data in response.
"""

import uuid
from datetime import datetime, timezone

import pytest

from app.models.client import Client
from app.models.document import Document
from app.models.firm import Firm
from app.models.signature_envelope import SignatureEnvelope
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _setup_firm_and_portal_client():
    suf = uuid.uuid4().hex[:8]
    email = f"portal-signed-{suf}@example.com"
    password = "testpass1!"
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Signed Test Firm {suf}", slug=f"stf-{suf}")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        c = Client(
            firm_id=firm.id,
            name="Signed Test Client",
            email=email,
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password(password),
        )
        db.add(c)
        db.commit()
        db.refresh(c)

        firm_id = str(firm.id)
        client_id = str(c.id)
        slug = firm.slug
    finally:
        db.close()

    return {"firm_id": firm_id, "client_id": client_id, "slug": slug,
            "email": email, "password": password}


def _portal_login(http_client, slug: str, email: str, password: str) -> dict:
    r = http_client.post("/portal/auth/login", json={
        "firm_slug": slug, "email": email, "password": password,
    })
    assert r.status_code == 200, f"Portal login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _insert_signed_envelope(
    firm_id: str,
    client_id: str,
    signers=None,
    completed_at=None,
    status="signed",
):
    """Insert a SignatureEnvelope plus its signed Document row directly."""
    db = TestingSessionLocal()
    try:
        doc = Document(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            scope="client",
            source="system",
            triage_status="filed",
            uploaded_by=None,
            filename="Engagement Letter - Signed.pdf",
            s3_key=f"signed/{uuid.uuid4()}/signed.pdf",
            content_type="application/pdf",
            size_bytes=204800,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        env = SignatureEnvelope(
            firm_id=uuid.UUID(firm_id),
            client_id=uuid.UUID(client_id),
            signed_document_id=doc.id,
            status=status,
            signers=signers or [
                {"name": "Jane Smith", "email": "jane@example.com",
                 "status": "signed", "signed_at": "2026-09-07T10:00:00Z"}
            ],
            subject="Engagement Letter 2026",
            completed_at=completed_at or datetime(2026, 9, 7, 10, 0, 0, tzinfo=timezone.utc),
        )
        db.add(env)
        db.commit()
        db.refresh(env)
        return str(env.id), str(doc.id)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestPortalSignedDocuments:

    def test_signed_envelope_appears_in_response(self, client):
        """A completed (status=signed) envelope is returned by the endpoint."""
        info = _setup_firm_and_portal_client()
        _insert_signed_envelope(info["firm_id"], info["client_id"])
        headers = _portal_login(client, info["slug"], info["email"], info["password"])

        r = client.get("/portal/signed-documents", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data, list)
        assert len(data) == 1
        row = data[0]
        assert row["filename"] == "Engagement Letter - Signed.pdf"
        assert row["subject"] == "Engagement Letter 2026"
        assert len(row["signers"]) == 1
        assert row["signers"][0]["name"] == "Jane Smith"
        assert row["completed_at"] is not None

    def test_sent_envelope_does_not_appear(self, client):
        """An envelope still in 'sent' status does not appear -- only 'signed'."""
        info = _setup_firm_and_portal_client()
        _insert_signed_envelope(info["firm_id"], info["client_id"], status="sent")
        headers = _portal_login(client, info["slug"], info["email"], info["password"])

        r = client.get("/portal/signed-documents", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_tenant_isolation_different_client(self, client):
        """A signed envelope belonging to a different client does not appear."""
        info_a = _setup_firm_and_portal_client()
        info_b = _setup_firm_and_portal_client()
        # Insert envelope under client B
        _insert_signed_envelope(info_b["firm_id"], info_b["client_id"])
        # Log in as client A
        headers = _portal_login(client, info_a["slug"], info_a["email"], info_a["password"])

        r = client.get("/portal/signed-documents", headers=headers)
        assert r.status_code == 200
        assert r.json() == []

    def test_response_includes_signer_name_and_date(self, client):
        """Signer name(s) and completed_at date are present for audit-trail display."""
        info = _setup_firm_and_portal_client()
        signers = [
            {"name": "Alice Owner", "email": "alice@example.com",
             "status": "signed", "signed_at": "2026-09-07T09:30:00Z"},
            {"name": "Bob Client", "email": "bob@example.com",
             "status": "signed", "signed_at": "2026-09-07T09:45:00Z"},
        ]
        _insert_signed_envelope(info["firm_id"], info["client_id"], signers=signers)
        headers = _portal_login(client, info["slug"], info["email"], info["password"])

        r = client.get("/portal/signed-documents", headers=headers)
        assert r.status_code == 200
        data = r.json()
        assert len(data) == 1
        signer_names = [s["name"] for s in data[0]["signers"]]
        assert "Alice Owner" in signer_names
        assert "Bob Client" in signer_names
        assert data[0]["completed_at"] is not None

    def test_unauthenticated_returns_401(self, client):
        """No token returns 401."""
        r = client.get("/portal/signed-documents")
        assert r.status_code in (401, 403)
