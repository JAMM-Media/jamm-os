# tests/test_firm_roster_endpoint.py
"""
Guard tests for GET /users/firm-roster.

Tests:
  a. A plain staff-role user can call GET /users/firm-roster and gets 200
     with real results. Watched-fail: temporarily gate with require_firm_owner;
     staff caller gets 403, restore, gets 200.
  b. A client_portal_user is refused 403 on GET /users/firm-roster.
  c. Response contains only id and full_name for each entry -- no email,
     role, cost_rate, or other HR field. Asserts the exact key set so that a
     future accidental field leak would be caught here.
  d. A user from a different firm never appears in firm A's roster response,
     confirmed with a real two-firm fixture.
"""

import uuid

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.core.enums import UserRole
from app.core.security import get_password_hash


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


def _make_staff_user(firm_id: str, client, full_name: str = "Staff Member") -> dict:
    db = TestingSessionLocal()
    try:
        email = f"staff-{uuid.uuid4().hex[:8]}@testfirm.com"
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("staffpass"),
            full_name=full_name,
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


def _make_portal_user_headers(firm_id: str, owner_headers: dict, client) -> dict:
    """Create a client_portal_user in the given firm and return auth headers.
    Uses the same pattern as test_leads_rbac_and_tenant_isolation.py.
    """
    email = f"portal-{uuid.uuid4()}@roster-test.example.com"
    r = client.post("/users/", json={
        "email": email,
        "password": "portalpass123",
        "full_name": "Portal User",
        "role": "client_portal_user",
        "firm_id": firm_id,
    }, headers=owner_headers)
    assert r.status_code == 201, f"Portal user creation failed: {r.json()}"
    login = client.post("/auth/token", json={"username": email, "password": "portalpass123"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# a. Staff-role user can call GET /users/firm-roster
# ---------------------------------------------------------------------------

def test_firm_roster_accessible_by_staff_role(client, firm_a_owner):
    """A staff-role user (not firm_owner) can call GET /users/firm-roster
    and gets 200.

    Watched-fail procedure: temporarily change the dependency in
    list_firm_roster from require_staff_or_above to require_firm_owner,
    run this test -- the staff caller gets 403 instead of 200. Restore
    require_staff_or_above, test returns 200.
    """
    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client)
    r = client.get("/users/firm-roster", headers=staff["headers"])
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# b. client_portal_user is refused 403
# ---------------------------------------------------------------------------

def test_firm_roster_refused_for_portal_user(client, firm_a_owner):
    """A client_portal_user must be refused with 403, not 200.

    require_staff_or_above raises HTTP_403_FORBIDDEN for any role not in
    (firm_owner, manager, staff, system_admin), confirmed from roles.py.
    """
    portal_headers = _make_portal_user_headers(
        firm_a_owner["firm_id"], firm_a_owner["headers"], client
    )
    r = client.get("/users/firm-roster", headers=portal_headers)
    assert r.status_code == 403, (
        f"client_portal_user must be refused 403; got {r.status_code}: {r.text}"
    )


# ---------------------------------------------------------------------------
# c. Response contains only id and full_name -- no leaked HR fields
# ---------------------------------------------------------------------------

def test_firm_roster_response_has_id_and_full_name_only(client, firm_a_owner):
    """Each item in the roster response must have exactly id and full_name
    and nothing else. Asserts the complete key set so that a future accidental
    field addition (email, role, cost_rate) would be caught here.
    """
    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client, full_name="Visible Staff")

    r = client.get("/users/firm-roster", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    items = r.json()
    assert any(item["id"] == staff["user_id"] for item in items), (
        f"Newly created staff not found in roster. ids={[i['id'] for i in items]}"
    )
    for item in items:
        assert set(item.keys()) == {"id", "full_name"}, (
            f"Unexpected keys in roster item: {set(item.keys())}"
        )


# ---------------------------------------------------------------------------
# d. Tenant isolation: firm B user never appears in firm A's roster
# ---------------------------------------------------------------------------

def test_firm_roster_tenant_isolation(client, firm_a_owner):
    """A user created in firm B must never appear in firm A's roster response."""
    firm_b = _make_firm_and_owner(f"roster-iso-{uuid.uuid4().hex[:6]}", client)
    firm_b_staff = _make_staff_user(firm_b["firm_id"], client, full_name="Firm B Staff")

    r = client.get("/users/firm-roster", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    ids = {item["id"] for item in r.json()}
    assert firm_b_staff["user_id"] not in ids, (
        f"Firm B user {firm_b_staff['user_id']} must not appear in firm A's roster"
    )
