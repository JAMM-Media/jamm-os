# tests/test_portal_dashboard_document_requests.py
"""
Tests for the real pending_document_requests query in the portal dashboard.

Covers:
  1. A client with pending/partial document requests sees them in their dashboard.
  2. A completed document request is excluded from the dashboard.
  3. Tenant isolation: a document request belonging to a different firm's client
     cannot appear in another firm's client's dashboard response.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.client import Client
from app.models.engagement import Engagement
from app.models.document_request import DocumentRequest
from app.models.firm import Firm
from app.services.portal_auth import hash_portal_password
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create_portal_client(firm_id: str, email: str | None = None, password: str = "portalpass1!") -> dict:
    """Insert a portal-enabled Client. Returns {client_id, email, firm_id, password}."""
    email = email or f"pclient-{uuid.uuid4().hex[:8]}@example.com"
    db = TestingSessionLocal()
    try:
        c = Client(
            firm_id=uuid.UUID(firm_id),
            name="Portal Test Client",
            email=email,
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password(password),
        )
        db.add(c)
        db.commit()
        db.refresh(c)
        return {"client_id": str(c.id), "email": email, "firm_id": firm_id, "password": password}
    finally:
        db.close()


def _get_firm_slug(firm_id: str) -> str:
    db = TestingSessionLocal()
    try:
        firm = db.get(Firm, uuid.UUID(firm_id))
        return firm.slug
    finally:
        db.close()


def _portal_login(http_client, firm_slug: str, email: str, password: str) -> dict:
    """Log in as a portal client. Returns auth headers."""
    r = http_client.post("/portal/auth/login", json={
        "firm_slug": firm_slug,
        "email": email,
        "password": password,
    })
    assert r.status_code == 200, f"Portal login failed: {r.json()}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _create_engagement_and_request(
    http_client,
    staff_headers: dict,
    client_id: str,
    title: str = "Test Document Request",
    due_date: str | None = None,
) -> tuple[str, str]:
    """Create an engagement + document request via the staff API.
    Returns (engagement_id, document_request_id).
    """
    eng_r = http_client.post(
        "/engagements/",
        json={"name": "Test Engagement", "client_id": client_id},
        headers=staff_headers,
    )
    assert eng_r.status_code == 201, f"Engagement creation failed: {eng_r.json()}"
    engagement_id = eng_r.json()["id"]

    payload: dict = {
        "client_id": client_id,
        "engagement_id": engagement_id,
        "title": title,
        "checklist_items": [
            {"id": "item-1", "label": "Required document", "is_required": True, "status": "pending"},
        ],
    }
    if due_date:
        payload["due_date"] = due_date

    dr_r = http_client.post("/document-requests/", json=payload, headers=staff_headers)
    assert dr_r.status_code == 201, f"Document request creation failed: {dr_r.json()}"
    return engagement_id, dr_r.json()["id"]


def _mark_request_complete(request_id: str, firm_id: str) -> None:
    """Directly set status='complete' with NO completed_at timestamp.
    Used for tests that verify excluded-from-dashboard behavior (NULL completed_at
    means the recency filter skips it).
    """
    db = TestingSessionLocal()
    try:
        dr = db.get(DocumentRequest, uuid.UUID(request_id))
        assert dr is not None
        assert str(dr.firm_id) == firm_id
        dr.status = "complete"
        db.commit()
    finally:
        db.close()


def _mark_request_complete_at(request_id: str, firm_id: str, completed_at: datetime) -> None:
    """Set status='complete' with a specific completed_at timestamp.
    Used for tests that verify the recency window filter.
    """
    db = TestingSessionLocal()
    try:
        dr = db.get(DocumentRequest, uuid.UUID(request_id))
        assert dr is not None
        assert str(dr.firm_id) == firm_id
        dr.status = "complete"
        dr.completed_at = completed_at
        db.commit()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_pending_document_requests_appear_in_dashboard(client, firm_a_owner):
    """A client with pending document requests sees them in their portal dashboard."""
    firm_id = firm_a_owner["firm_id"]
    staff_hdrs = firm_a_owner["headers"]

    # Create portal client in firm A
    portal_data = _create_portal_client(firm_id)
    client_id = portal_data["client_id"]
    firm_slug = _get_firm_slug(firm_id)
    portal_hdrs = _portal_login(client, firm_slug, portal_data["email"], portal_data["password"])

    # Create an engagement + pending document request for this client
    _, dr_id = _create_engagement_and_request(
        client, staff_hdrs, client_id,
        title="2024 W-2 Forms",
        due_date="2025-04-15",
    )

    r = client.get("/portal/dashboard", headers=portal_hdrs)
    assert r.status_code == 200, r.json()
    data = r.json()

    pending = data["pending_document_requests"]
    assert len(pending) == 1
    assert pending[0]["id"] == dr_id
    assert pending[0]["title"] == "2024 W-2 Forms"
    assert pending[0]["due_date"] == "2025-04-15"
    assert pending[0]["status"] == "pending"


def test_completed_document_request_excluded_from_dashboard(client, firm_a_owner):
    """A document request with status 'complete' must not appear in pending_document_requests."""
    firm_id = firm_a_owner["firm_id"]
    staff_hdrs = firm_a_owner["headers"]

    portal_data = _create_portal_client(firm_id)
    client_id = portal_data["client_id"]
    firm_slug = _get_firm_slug(firm_id)
    portal_hdrs = _portal_login(client, firm_slug, portal_data["email"], portal_data["password"])

    # Create two requests: one pending, one that we immediately mark complete
    _, pending_id = _create_engagement_and_request(
        client, staff_hdrs, client_id, title="Pending Request"
    )
    _, complete_id = _create_engagement_and_request(
        client, staff_hdrs, client_id, title="Completed Request"
    )
    _mark_request_complete(complete_id, firm_id)

    r = client.get("/portal/dashboard", headers=portal_hdrs)
    assert r.status_code == 200, r.json()
    data = r.json()

    pending = data["pending_document_requests"]
    ids = [p["id"] for p in pending]

    assert pending_id in ids, "Pending request must appear"
    assert complete_id not in ids, "Completed request must be excluded"


def test_cross_firm_isolation(client, firm_a_owner, firm_b_owner):
    """A document request in firm A must never appear in firm B's portal client's dashboard."""
    firm_a_id = firm_a_owner["firm_id"]
    firm_b_id = firm_b_owner["firm_id"]

    # Create a separate client in firm A (not the portal client) and a document request for them
    client_a_r = client.post(
        "/clients/",
        json={"name": "Firm A Non-Portal Client"},
        headers=firm_a_owner["headers"],
    )
    assert client_a_r.status_code == 201
    client_a_id = client_a_r.json()["id"]

    _, dr_a_id = _create_engagement_and_request(
        client,
        firm_a_owner["headers"],
        client_a_id,
        title="Firm A Secret Request",
    )

    # Create a portal client in firm B and log in
    portal_b = _create_portal_client(firm_b_id)
    slug_b = _get_firm_slug(firm_b_id)
    portal_b_hdrs = _portal_login(client, slug_b, portal_b["email"], portal_b["password"])

    r = client.get("/portal/dashboard", headers=portal_b_hdrs)
    assert r.status_code == 200, r.json()
    data = r.json()

    ids_returned = [p["id"] for p in data["pending_document_requests"]]
    assert dr_a_id not in ids_returned, (
        f"Cross-firm isolation failed: firm A's request {dr_a_id} appeared in firm B's dashboard"
    )


# ---------------------------------------------------------------------------
# Tests for recently-completed requests appearing in the dashboard
# ---------------------------------------------------------------------------

def test_recently_completed_request_appears_in_dashboard(client, firm_a_owner):
    """A document request completed within the current month appears in pending_document_requests
    with status 'complete', so the frontend Completed stat card can count it.
    """
    firm_id = firm_a_owner["firm_id"]
    staff_hdrs = firm_a_owner["headers"]

    portal_data = _create_portal_client(firm_id)
    client_id = portal_data["client_id"]
    firm_slug = _get_firm_slug(firm_id)
    portal_hdrs = _portal_login(client, firm_slug, portal_data["email"], portal_data["password"])

    _, dr_id = _create_engagement_and_request(client, staff_hdrs, client_id, title="Recently Done")

    # Mark complete with a timestamp that is within the current calendar month
    now = datetime.now(timezone.utc)
    _mark_request_complete_at(dr_id, firm_id, completed_at=now)

    r = client.get("/portal/dashboard", headers=portal_hdrs)
    assert r.status_code == 200, r.json()
    data = r.json()

    ids = [p["id"] for p in data["pending_document_requests"]]
    assert dr_id in ids, "Recently-completed request must appear in dashboard"

    matched = next(p for p in data["pending_document_requests"] if p["id"] == dr_id)
    assert matched["status"] == "complete"
    assert matched["title"] == "Recently Done"


def test_old_completed_request_excluded_from_dashboard(client, firm_a_owner):
    """A document request completed 6 months ago is outside the recency window and
    must NOT appear in the dashboard, so the Completed count does not grow unboundedly.
    """
    firm_id = firm_a_owner["firm_id"]
    staff_hdrs = firm_a_owner["headers"]

    portal_data = _create_portal_client(firm_id)
    client_id = portal_data["client_id"]
    firm_slug = _get_firm_slug(firm_id)
    portal_hdrs = _portal_login(client, firm_slug, portal_data["email"], portal_data["password"])

    _, dr_id = _create_engagement_and_request(client, staff_hdrs, client_id, title="Old Completed")

    # Mark complete with a timestamp 6 months in the past (well outside current month)
    six_months_ago = datetime.now(timezone.utc) - timedelta(days=180)
    _mark_request_complete_at(dr_id, firm_id, completed_at=six_months_ago)

    r = client.get("/portal/dashboard", headers=portal_hdrs)
    assert r.status_code == 200, r.json()
    data = r.json()

    ids = [p["id"] for p in data["pending_document_requests"]]
    assert dr_id not in ids, "Old completed request must be excluded by the recency window"


def test_cross_firm_isolation_for_completed_requests(client, firm_a_owner, firm_b_owner):
    """A recently-completed request in firm A must never appear in firm B's dashboard."""
    firm_a_id = firm_a_owner["firm_id"]

    # Create a client in firm A and a recently-completed request for them
    client_a_r = client.post(
        "/clients/",
        json={"name": "Firm A Completed Client"},
        headers=firm_a_owner["headers"],
    )
    assert client_a_r.status_code == 201
    client_a_id = client_a_r.json()["id"]

    _, dr_a_id = _create_engagement_and_request(
        client, firm_a_owner["headers"], client_a_id, title="Firm A Completed Request"
    )
    now = datetime.now(timezone.utc)
    _mark_request_complete_at(dr_a_id, firm_a_id, completed_at=now)

    # Firm B's portal client checks their dashboard
    firm_b_id = firm_b_owner["firm_id"]
    portal_b = _create_portal_client(firm_b_id)
    slug_b = _get_firm_slug(firm_b_id)
    portal_b_hdrs = _portal_login(client, slug_b, portal_b["email"], portal_b["password"])

    r = client.get("/portal/dashboard", headers=portal_b_hdrs)
    assert r.status_code == 200, r.json()
    data = r.json()

    ids_returned = [p["id"] for p in data["pending_document_requests"]]
    assert dr_a_id not in ids_returned, (
        f"Isolation failed: firm A's completed request {dr_a_id} appeared in firm B's dashboard"
    )
