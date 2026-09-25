# tests/test_engagement_pins.py
"""
Guard tests for the engagement_pins backend.

Tests:
  a. An engagement administrator can pin a real document.
  b. A plain staff member (no administrator status, no firm-wide role) is
     refused 403 attempting to pin.
     Watched-fail: temporarily bypass require_can_manage_membership,
     confirm the wrongly-permitted pin succeeds, restore, confirm refused.
  c. A manager (firm-wide role) can pin without being an engagement member.
  d. Pinning a 6th item when 5 already exist is refused with 422 naming the cap.
  e. Pinning the same item twice is refused with 409.
  f. Pinning an item that belongs to a different engagement is refused (404),
     confirming engagement-scoping is real.
  g. list_pins is visible to a plain engagement member (not just administrators).
  h. Tenant isolation: firm B cannot list or pin against firm A's engagement.
"""
import io
import uuid
from datetime import datetime, timezone
from unittest.mock import patch

from tests.conftest import TestingSessionLocal
from app.models.engagement_member import EngagementMember
from app.models.engagement_pin import EngagementPin
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
        user_id = str(owner.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "password123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id, "user_id": user_id}


def _make_staff_user(firm_id: str, client, role=UserRole.staff) -> dict:
    db = TestingSessionLocal()
    try:
        email = f"staff-{uuid.uuid4().hex[:8]}@testfirm.com"
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("staffpass"),
            full_name="Staff Member",
            role=role,
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


def _add_member(firm_id: str, engagement_id: str, user_id: str, is_administrator: bool = False):
    db = TestingSessionLocal()
    try:
        m = EngagementMember(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(engagement_id),
            user_id=uuid.UUID(user_id),
            is_administrator=is_administrator,
        )
        db.add(m)
        db.commit()
    finally:
        db.close()


def _count_pin_rows(engagement_id: str, item_id: str) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(EngagementPin).filter(
            EngagementPin.engagement_id == uuid.UUID(engagement_id),
            EngagementPin.item_id == uuid.UUID(item_id),
        ).count()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_engagement_admin_can_pin_document(client):
    """a. An engagement administrator can pin a real document."""
    firm = _make_firm_and_owner("pin-a", client)
    headers_owner = firm["headers"]
    firm_id = firm["firm_id"]

    staff = _make_staff_user(firm_id, client)
    client_id = _setup_client(client, headers_owner)
    eng_id = _setup_engagement(client, headers_owner, client_id)
    doc_id = _upload_doc(client, headers_owner, client_id, eng_id)

    # Make staff an engagement administrator.
    _add_member(firm_id, eng_id, staff["user_id"], is_administrator=True)

    r = client.post(
        f"/engagements/{eng_id}/pins",
        json={"item_type": "document", "item_id": doc_id},
        headers=staff["headers"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["item_type"] == "document"
    assert r.json()["item_id"] == doc_id


def test_plain_staff_cannot_pin(client):
    """b. A plain staff member (not administrator, no firm-wide role) is refused 403."""
    firm = _make_firm_and_owner("pin-b", client)
    headers_owner = firm["headers"]
    firm_id = firm["firm_id"]

    staff = _make_staff_user(firm_id, client)
    client_id = _setup_client(client, headers_owner)
    eng_id = _setup_engagement(client, headers_owner, client_id)
    doc_id = _upload_doc(client, headers_owner, client_id, eng_id)

    # Staff is a plain member, NOT an administrator.
    _add_member(firm_id, eng_id, staff["user_id"], is_administrator=False)

    r = client.post(
        f"/engagements/{eng_id}/pins",
        json={"item_type": "document", "item_id": doc_id},
        headers=staff["headers"],
    )
    assert r.status_code == 403, r.text
    assert _count_pin_rows(eng_id, doc_id) == 0


def test_manager_can_pin_without_membership(client):
    """c. A firm-wide manager can pin without being an engagement member."""
    firm = _make_firm_and_owner("pin-c", client)
    headers_owner = firm["headers"]
    firm_id = firm["firm_id"]

    manager = _make_staff_user(firm_id, client, role=UserRole.manager)
    client_id = _setup_client(client, headers_owner)
    eng_id = _setup_engagement(client, headers_owner, client_id)
    doc_id = _upload_doc(client, headers_owner, client_id, eng_id)

    # Manager is NOT added as an engagement member at all.
    r = client.post(
        f"/engagements/{eng_id}/pins",
        json={"item_type": "document", "item_id": doc_id},
        headers=manager["headers"],
    )
    assert r.status_code == 201, r.text


def test_pin_cap_enforced(client):
    """d. Pinning a 6th item when 5 already exist is refused with 422."""
    firm = _make_firm_and_owner("pin-d", client)
    headers_owner = firm["headers"]
    firm_id = firm["firm_id"]
    client_id = _setup_client(client, headers_owner)
    eng_id = _setup_engagement(client, headers_owner, client_id)

    # Pin 5 documents.
    doc_ids = []
    for _ in range(5):
        doc_id = _upload_doc(client, headers_owner, client_id, eng_id)
        doc_ids.append(doc_id)
        r = client.post(
            f"/engagements/{eng_id}/pins",
            json={"item_type": "document", "item_id": doc_id},
            headers=headers_owner,
        )
        assert r.status_code == 201, r.text

    # 6th pin must fail.
    extra_doc_id = _upload_doc(client, headers_owner, client_id, eng_id)
    r6 = client.post(
        f"/engagements/{eng_id}/pins",
        json={"item_type": "document", "item_id": extra_doc_id},
        headers=headers_owner,
    )
    assert r6.status_code == 422, r6.text
    assert "5" in r6.json()["detail"]


def test_duplicate_pin_returns_409(client):
    """e. Pinning the same item twice is refused with 409."""
    firm = _make_firm_and_owner("pin-e", client)
    headers_owner = firm["headers"]
    firm_id = firm["firm_id"]
    client_id = _setup_client(client, headers_owner)
    eng_id = _setup_engagement(client, headers_owner, client_id)
    doc_id = _upload_doc(client, headers_owner, client_id, eng_id)

    r1 = client.post(
        f"/engagements/{eng_id}/pins",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers_owner,
    )
    assert r1.status_code == 201, r1.text
    assert _count_pin_rows(eng_id, doc_id) == 1

    r2 = client.post(
        f"/engagements/{eng_id}/pins",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers_owner,
    )
    assert r2.status_code == 409, r2.text
    assert _count_pin_rows(eng_id, doc_id) == 1


def test_cross_engagement_pin_refused(client):
    """f. Pinning an item that belongs to a different engagement is refused."""
    firm = _make_firm_and_owner("pin-f", client)
    headers_owner = firm["headers"]
    client_id = _setup_client(client, headers_owner)

    eng_a_id = _setup_engagement(client, headers_owner, client_id, name="EngA")
    eng_b_id = _setup_engagement(client, headers_owner, client_id, name="EngB")

    # Upload a document belonging to engagement A.
    doc_id_a = _upload_doc(client, headers_owner, client_id, eng_a_id)

    # Attempt to pin that document under engagement B.
    r = client.post(
        f"/engagements/{eng_b_id}/pins",
        json={"item_type": "document", "item_id": doc_id_a},
        headers=headers_owner,
    )
    assert r.status_code == 404, r.text
    assert _count_pin_rows(eng_b_id, doc_id_a) == 0


def test_list_pins_visible_to_plain_member(client):
    """g. GET /pins is visible to a plain engagement member, not just administrators."""
    firm = _make_firm_and_owner("pin-g", client)
    headers_owner = firm["headers"]
    firm_id = firm["firm_id"]
    client_id = _setup_client(client, headers_owner)
    eng_id = _setup_engagement(client, headers_owner, client_id)
    doc_id = _upload_doc(client, headers_owner, client_id, eng_id)

    # Owner pins the document.
    r_pin = client.post(
        f"/engagements/{eng_id}/pins",
        json={"item_type": "document", "item_id": doc_id},
        headers=headers_owner,
    )
    assert r_pin.status_code == 201, r_pin.text

    # A plain staff member (not administrator) is added as a member.
    staff = _make_staff_user(firm_id, client)
    _add_member(firm_id, eng_id, staff["user_id"], is_administrator=False)

    # They can read the pins list.
    r_list = client.get(f"/engagements/{eng_id}/pins", headers=staff["headers"])
    assert r_list.status_code == 200, r_list.text
    pins = r_list.json()
    assert any(p["item_id"] == doc_id for p in pins)


def test_tenant_isolation(client):
    """h. Firm B cannot list or pin against firm A's engagement."""
    firm_a = _make_firm_and_owner("pin-h-a", client)
    firm_b = _make_firm_and_owner("pin-h-b", client)
    headers_a = firm_a["headers"]
    headers_b = firm_b["headers"]

    client_id_a = _setup_client(client, headers_a)
    eng_id_a = _setup_engagement(client, headers_a, client_id_a)
    doc_id_a = _upload_doc(client, headers_a, client_id_a, eng_id_a)

    # Firm A pins their own doc.
    r_a = client.post(
        f"/engagements/{eng_id_a}/pins",
        json={"item_type": "document", "item_id": doc_id_a},
        headers=headers_a,
    )
    assert r_a.status_code == 201, r_a.text

    # Firm B attempts to list firm A's pins -- should get 404 (not a member, not elevated).
    r_b_list = client.get(f"/engagements/{eng_id_a}/pins", headers=headers_b)
    assert r_b_list.status_code == 404, r_b_list.text

    # Firm B attempts to pin firm A's doc to firm A's engagement -- should get 403 or 404.
    r_b_pin = client.post(
        f"/engagements/{eng_id_a}/pins",
        json={"item_type": "document", "item_id": doc_id_a},
        headers=headers_b,
    )
    assert r_b_pin.status_code in (403, 404), r_b_pin.text
