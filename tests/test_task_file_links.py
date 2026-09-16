# tests/test_task_file_links.py
"""
Guard tests for filesystem spec Section 13: task-to-document file links.

Five guards, each watched red then green:
(a) Cross-engagement link refused
(b) Access-gate enforcement: non-member staff sees empty list, not 403
(c) Trashed file remains visible with deleted_at populated
(d) INTERNAL task refused with 404
(e) Duplicate link is idempotent
"""

import io
import uuid
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal
from app.models.user import User
from app.models.document import Document
from app.models.engagement_member import EngagementMember
from app.models.task_file_link import TaskFileLink
from app.core.enums import UserRole
from app.core.security import get_password_hash
from datetime import datetime, timezone


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_user(firm_id, role=UserRole.staff):
    email = f"tfl-{uuid.uuid4()}@test.com"
    password = "testpass123"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="TFL Test User",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()
    return email, password, user_id


def _add_member(firm_id, engagement_id, user_id):
    db = TestingSessionLocal()
    try:
        member = EngagementMember(
            firm_id=firm_id,
            engagement_id=engagement_id,
            user_id=user_id,
        )
        db.add(member)
        db.commit()
    finally:
        db.close()


def _login(test_client, email, password):
    r = test_client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_client_and_engagement(test_client, headers, *, client_name=None, eng_name=None):
    cl = test_client.post(
        "/clients/",
        json={"name": client_name or f"TFL-Client-{uuid.uuid4()}"},
        headers=headers,
    )
    assert cl.status_code == 201, cl.text
    client_id = cl.json()["id"]
    eng = test_client.post(
        "/engagements/",
        json={"name": eng_name or f"TFL-Eng-{uuid.uuid4()}", "client_id": client_id},
        headers=headers,
    )
    assert eng.status_code == 201, eng.text
    return client_id, eng.json()["id"]


def _upload_doc(test_client, headers, client_id, engagement_id, filename="tfl-doc.txt"):
    with patch("app.api.documents.s3_service.upload_fileobj"):
        r = test_client.post(
            f"/documents/upload?client_id={client_id}&engagement_id={engagement_id}",
            files={"file": (filename, io.BytesIO(b"content"), "text/plain")},
            headers=headers,
        )
    assert r.status_code == 201, r.text
    return r.json()


def _create_task(test_client, headers, client_id, engagement_id, task_type="client"):
    payload = {"title": f"TFL-Task-{uuid.uuid4()}"}
    if task_type == "client":
        payload["client_id"] = client_id
        payload["engagement_id"] = engagement_id
    else:
        payload["task_type"] = "internal"
    r = test_client.post("/tasks/", json=payload, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()


def _soft_delete_doc(document_id):
    """Directly set deleted_at in the DB (bypasses the API soft-delete flow)."""
    db = TestingSessionLocal()
    try:
        doc = db.get(Document, uuid.UUID(document_id))
        doc.deleted_at = datetime.now(timezone.utc)
        db.commit()
    finally:
        db.close()


def _count_links(task_id, document_id):
    db = TestingSessionLocal()
    try:
        return db.query(TaskFileLink).filter(
            TaskFileLink.task_id == uuid.UUID(task_id),
            TaskFileLink.document_id == uuid.UUID(document_id),
        ).count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# (a) Cross-engagement link refused
# ---------------------------------------------------------------------------

def test_cross_engagement_link_refused(client, firm_a_owner):
    """
    A document on engagement B cannot be linked to a task on engagement A.
    Guard: engagement_id mismatch check in link_file_to_task.
    Watch red: temporarily remove the mismatch check.
    """
    owner_headers = firm_a_owner["headers"]

    # Both engagements under the same client so the upload membership check passes.
    client_id, eng_a_id = _make_client_and_engagement(client, owner_headers)
    eng_b = client.post(
        "/engagements/",
        json={"name": f"TFL-EngB-{uuid.uuid4()}", "client_id": client_id},
        headers=owner_headers,
    )
    assert eng_b.status_code == 201, eng_b.text
    eng_b_id = eng_b.json()["id"]

    task = _create_task(client, owner_headers, client_id, eng_a_id)
    doc = _upload_doc(client, owner_headers, client_id, eng_b_id)

    r = client.post(
        f"/tasks/{task['id']}/files",
        json={"document_id": doc["id"]},
        headers=owner_headers,
    )
    assert r.status_code == 422, f"Expected 422, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# (b) Access-gate enforcement: non-member staff sees empty list
# ---------------------------------------------------------------------------

def test_non_member_staff_sees_empty_list(client, firm_a_owner):
    """
    A staff member not on the task's engagement gets an empty items list
    from GET /tasks/{id}/files, not a 403. The document is silently excluded.
    Guard: filter_accessible_documents in list_task_file_links.
    Watch red: temporarily bypass filter_accessible_documents.
    """
    firm_id = firm_a_owner["firm_id"]
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    task = _create_task(client, owner_headers, client_id, eng_id)
    doc = _upload_doc(client, owner_headers, client_id, eng_id)

    # Owner links the file
    r = client.post(
        f"/tasks/{task['id']}/files",
        json={"document_id": doc["id"]},
        headers=owner_headers,
    )
    assert r.status_code == 201

    # Staff user with NO engagement membership
    email, password, _ = _create_user(firm_id)
    staff_headers = _login(client, email, password)

    r = client.get(f"/tasks/{task['id']}/files", headers=staff_headers)
    assert r.status_code == 200, r.text
    assert r.json()["items"] == [], "Non-member staff should see empty list, not the linked doc"


# ---------------------------------------------------------------------------
# (c) Trashed file stays visible with deleted_at populated
# ---------------------------------------------------------------------------

def test_trashed_file_visible_with_deleted_at(client, firm_a_owner):
    """
    Soft-deleting a linked document must not remove it from the list.
    It should appear with deleted_at set.
    Guard: list_task_file_links does not exclude deleted_at.isnot(None).
    Watch red: temporarily add a deleted_at.is_(None) filter.
    """
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    task = _create_task(client, owner_headers, client_id, eng_id)
    doc = _upload_doc(client, owner_headers, client_id, eng_id)

    r = client.post(
        f"/tasks/{task['id']}/files",
        json={"document_id": doc["id"]},
        headers=owner_headers,
    )
    assert r.status_code == 201

    _soft_delete_doc(doc["id"])

    r = client.get(f"/tasks/{task['id']}/files", headers=owner_headers)
    assert r.status_code == 200
    items = r.json()["items"]
    assert len(items) == 1, "Trashed file must still appear in linked files"
    assert items[0]["deleted_at"] is not None, "deleted_at must be populated for trashed file"


# ---------------------------------------------------------------------------
# (d) INTERNAL task refused
# ---------------------------------------------------------------------------

def test_internal_task_refused(client, firm_a_owner):
    """
    Attempting to link a file to an INTERNAL-type task returns 404.
    Guard: _load_client_task raises 404 when task_type != 'client'.
    Watch red: temporarily remove the task_type check in _load_client_task.
    """
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    internal_task = _create_task(client, owner_headers, client_id, eng_id, task_type="internal")
    doc = _upload_doc(client, owner_headers, client_id, eng_id)

    r = client.post(
        f"/tasks/{internal_task['id']}/files",
        json={"document_id": doc["id"]},
        headers=owner_headers,
    )
    assert r.status_code == 404, f"Expected 404 for INTERNAL task, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# (e) Duplicate link is idempotent
# ---------------------------------------------------------------------------

def test_duplicate_link_is_idempotent(client, firm_a_owner):
    """
    Linking the same document to the same task twice returns no error
    and exactly one row exists in the database.
    """
    owner_headers = firm_a_owner["headers"]

    client_id, eng_id = _make_client_and_engagement(client, owner_headers)
    task = _create_task(client, owner_headers, client_id, eng_id)
    doc = _upload_doc(client, owner_headers, client_id, eng_id)

    r1 = client.post(
        f"/tasks/{task['id']}/files",
        json={"document_id": doc["id"]},
        headers=owner_headers,
    )
    assert r1.status_code == 201

    r2 = client.post(
        f"/tasks/{task['id']}/files",
        json={"document_id": doc["id"]},
        headers=owner_headers,
    )
    assert r2.status_code == 201, f"Second link should not error, got {r2.status_code}: {r2.text}"

    count = _count_links(task["id"], doc["id"])
    assert count == 1, f"Expected exactly 1 link row, found {count}"
