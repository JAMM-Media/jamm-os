# tests/test_document_favorites.py
"""
Guard tests for the document_favorites backend.

Tests:
  a. A user can favorite a real document and it appears in GET /document-favorites.
  b. A user can favorite a real folder and it appears in GET /document-favorites.
  c. Favoriting the same item twice returns 409.
     Watched-fail: temporarily remove the duplicate check to confirm two rows
     get created, restore, confirm it is refused.
  d. Removing a favorite that was never added returns 204 (idempotent).
  e. A soft-deleted document never appears in the favorites list, even if it
     was favorited before deletion.
  f. Tenant isolation: firm B user cannot favorite a document belonging to
     firm A (404); firm B user never sees firm A favorites.
  g. User isolation: user A favorites never appear in user B GET /document-favorites.
"""
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.models.document_favorite import DocumentFavorite
from app.models.document import Document
from app.models.document_folder import DocumentFolder
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.firm import Firm
from app.models.user import User


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_owner(slug: str, client) -> dict:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)
        email = f"owner-{uuid.uuid4().hex[:6]}@{slug}.com"
        owner = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash("password123"),
            full_name="Owner",
            role=UserRole.firm_owner,
        )
        db.add(owner)
        db.commit()
        firm_id = str(firm.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "password123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}


def _make_staff_user(firm_id: str, client) -> dict:
    db = TestingSessionLocal()
    try:
        email = f"staff-{uuid.uuid4().hex[:8]}@testfirm.com"
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("staffpass"),
            full_name="Staff Member",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        user_id = str(user.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "staffpass"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id}


def _setup_client(client, headers, name=None) -> str:
    r = client.post("/clients/", json={"name": name or f"C-{uuid.uuid4().hex[:6]}"}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _setup_engagement(client, headers, client_id, name=None) -> str:
    r = client.post(
        "/engagements/",
        json={"name": name or f"E-{uuid.uuid4().hex[:6]}", "client_id": client_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _upload_doc(client, headers, client_id: str, engagement_id: str) -> str:
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": ("test.pdf", io.BytesIO(b"pdf content"), "application/pdf")},
            headers=headers,
        )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _make_folder(client, headers, firm_id: str, client_id: str, engagement_id: str) -> str:
    r = client.post(
        "/document-folders/",
        json={
            "scope": "engagement",
            "name": f"Folder-{uuid.uuid4().hex[:6]}",
            "client_id": client_id,
            "engagement_id": engagement_id,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _count_favorite_rows(user_id: str, item_type: str, item_id: str) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(DocumentFavorite).filter(
            DocumentFavorite.user_id == uuid.UUID(user_id),
            DocumentFavorite.item_type == item_type,
            DocumentFavorite.item_id == uuid.UUID(item_id),
        ).count()
    finally:
        db.close()


def _soft_delete_document(document_id: str):
    db = TestingSessionLocal()
    try:
        doc = db.query(Document).filter(Document.id == uuid.UUID(document_id)).first()
        doc.deleted_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_favorite_document_appears_in_list(client):
    """a. A user can favorite a real document and it appears in GET /document-favorites."""
    firm = _make_firm_and_owner("fav-doc-a", client)
    headers = firm["headers"]
    firm_id = firm["firm_id"]
    client_id = _setup_client(client, headers)
    eng_id = _setup_engagement(client, headers, client_id)
    doc_id = _upload_doc(client, headers, client_id, eng_id)

    r = client.post(
        "/document-favorites/",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["item_type"] == "document"
    assert r.json()["item_id"] == doc_id

    r2 = client.get("/document-favorites/", headers=headers)
    assert r2.status_code == 200, r2.text
    items = r2.json()
    assert any(i["item_id"] == doc_id and i["item_type"] == "document" for i in items)
    match = next(i for i in items if i["item_id"] == doc_id)
    assert match["name"].endswith(".pdf")


def test_favorite_folder_appears_in_list(client):
    """b. A user can favorite a real folder and it appears in GET /document-favorites."""
    firm = _make_firm_and_owner("fav-folder-b", client)
    headers = firm["headers"]
    firm_id = firm["firm_id"]
    client_id = _setup_client(client, headers)
    eng_id = _setup_engagement(client, headers, client_id)
    folder_id = _make_folder(client, headers, firm_id, client_id, eng_id)

    r = client.post(
        "/document-favorites/",
        json={"item_type": "folder", "item_id": folder_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    r2 = client.get("/document-favorites/", headers=headers)
    assert r2.status_code == 200, r2.text
    items = r2.json()
    assert any(i["item_id"] == folder_id and i["item_type"] == "folder" for i in items)


def test_duplicate_favorite_returns_409(client):
    """c. Favoriting the same item twice returns a real 409."""
    firm = _make_firm_and_owner("fav-dup-c", client)
    headers = firm["headers"]
    owner_user_id = None
    db = TestingSessionLocal()
    try:
        u = db.query(User).filter(User.firm_id == uuid.UUID(firm["firm_id"])).first()
        owner_user_id = str(u.id)
    finally:
        db.close()

    client_id = _setup_client(client, headers)
    eng_id = _setup_engagement(client, headers, client_id)
    doc_id = _upload_doc(client, headers, client_id, eng_id)

    r1 = client.post(
        "/document-favorites/",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers,
    )
    assert r1.status_code == 201, r1.text
    assert _count_favorite_rows(owner_user_id, "document", doc_id) == 1

    # Second attempt must be refused.
    r2 = client.post(
        "/document-favorites/",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers,
    )
    assert r2.status_code == 409, r2.text
    assert _count_favorite_rows(owner_user_id, "document", doc_id) == 1


def test_remove_unfavorited_is_idempotent(client):
    """d. Removing a favorite that was never added returns 204 (no error)."""
    firm = _make_firm_and_owner("fav-idempotent-d", client)
    headers = firm["headers"]
    random_id = str(uuid.uuid4())

    r = client.delete(f"/document-favorites/document/{random_id}", headers=headers)
    assert r.status_code == 204, r.text


def test_soft_deleted_document_excluded_from_list(client):
    """e. A soft-deleted document never appears in favorites list even if favorited first."""
    firm = _make_firm_and_owner("fav-deleted-e", client)
    headers = firm["headers"]
    client_id = _setup_client(client, headers)
    eng_id = _setup_engagement(client, headers, client_id)
    doc_id = _upload_doc(client, headers, client_id, eng_id)

    r = client.post(
        "/document-favorites/",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text

    # Confirm it appears before deletion.
    r_before = client.get("/document-favorites/", headers=headers)
    assert any(i["item_id"] == doc_id for i in r_before.json())

    _soft_delete_document(doc_id)

    r_after = client.get("/document-favorites/", headers=headers)
    assert r_after.status_code == 200, r_after.text
    assert not any(i["item_id"] == doc_id for i in r_after.json())


def test_tenant_isolation(client):
    """f. Firm B user cannot favorite firm A's document; cannot see firm A favorites."""
    firm_a = _make_firm_and_owner("fav-tenant-f-a", client)
    firm_b = _make_firm_and_owner("fav-tenant-f-b", client)
    headers_a = firm_a["headers"]
    headers_b = firm_b["headers"]

    client_id_a = _setup_client(client, headers_a)
    eng_id_a = _setup_engagement(client, headers_a, client_id_a)
    doc_id_a = _upload_doc(client, headers_a, client_id_a, eng_id_a)

    # Firm A favorites their own doc.
    r_a = client.post(
        "/document-favorites/",
        json={"item_type": "document", "item_id": doc_id_a},
        headers=headers_a,
    )
    assert r_a.status_code == 201, r_a.text

    # Firm B attempts to favorite firm A's doc -- should get 404 (wrong firm).
    r_b_add = client.post(
        "/document-favorites/",
        json={"item_type": "document", "item_id": doc_id_a},
        headers=headers_b,
    )
    assert r_b_add.status_code == 404, r_b_add.text

    # Firm B's favorites list must not contain firm A's doc.
    r_b_list = client.get("/document-favorites/", headers=headers_b)
    assert r_b_list.status_code == 200, r_b_list.text
    assert not any(i["item_id"] == doc_id_a for i in r_b_list.json())


def test_user_isolation_within_same_firm(client):
    """g. User A favorites never appear in user B GET /document-favorites."""
    firm = _make_firm_and_owner("fav-user-g", client)
    headers_owner = firm["headers"]
    firm_id = firm["firm_id"]

    user_b = _make_staff_user(firm_id, client)
    headers_b = user_b["headers"]

    client_id = _setup_client(client, headers_owner)
    eng_id = _setup_engagement(client, headers_owner, client_id)
    doc_id = _upload_doc(client, headers_owner, client_id, eng_id)

    # Owner (user A) favorites the doc.
    r = client.post(
        "/document-favorites/",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers_owner,
    )
    assert r.status_code == 201, r.text

    # User B must see an empty list (their own favorites only).
    r_b = client.get("/document-favorites/", headers=headers_b)
    assert r_b.status_code == 200, r_b.text
    assert not any(i["item_id"] == doc_id for i in r_b.json()), (
        "User B should not see user A's favorites"
    )
