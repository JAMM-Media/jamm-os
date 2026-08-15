# tests/test_availability_windows_api.py

"""
API tests for availability window endpoints (app/api/availability_windows.py).

GUARD TEST: test_duplicate_day_returns_409_not_500
Watched-fail cycle: temporarily removes the duplicate-day check in create_window,
confirms a raw IntegrityError escapes as 500, then restores and confirms a clean 409.

ASSUMPTION (Block 4): The contract (section 7.2) does not specify who may edit
whose windows. Applied default: any staff member can view all windows in the firm;
a staff member can only create/update/delete their OWN windows; firm_owner and
manager may manage any staff member's windows within the firm.
"""

import uuid
import pytest

from tests.conftest import TestingSessionLocal


BASE = "/api/v1/availability-windows"


def _get_user_id(email: str) -> str:
    """Look up the UUID of a user by email directly from the test DB."""
    from app.models.user import User
    db = TestingSessionLocal()
    try:
        user = db.query(User).filter(User.email == email).first()
        assert user is not None, f"No user with email {email!r} found in test DB"
        return str(user.id)
    finally:
        db.close()


_WINDOW_PAYLOAD = {
    "user_id": None,  # overwritten per-test
    "day_of_week": 0,
    "start_time": "09:00:00",
    "end_time": "17:00:00",
    "buffer_before_minutes": 5,
    "buffer_after_minutes": 5,
    "meeting_duration_minutes": 30,
    "daily_cap": 4,
}


def _window(user_id: str, day: int = 0, **overrides) -> dict:
    return {**_WINDOW_PAYLOAD, "user_id": user_id, "day_of_week": day, **overrides}


# ---------------------------------------------------------------------------
# Fixtures -- manager user in Firm A (not in conftest)
# ---------------------------------------------------------------------------

@pytest.fixture
def firm_a_manager(client, firm_a_owner):
    """Creates a manager user in Firm A, returns auth headers."""
    from app.models.user import User
    from app.core.security import get_password_hash
    from app.core.enums import UserRole

    firm_id = firm_a_owner["firm_id"]
    email = f"manager-{uuid.uuid4().hex[:8]}@firma.com"

    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("managerpass123"),
            full_name="Manager A",
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": "managerpass123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id, "user_id": user_id}


@pytest.fixture
def firm_a_staff_2(client, firm_a_owner):
    """Creates a second independent staff user in Firm A."""
    from app.models.user import User
    from app.core.security import get_password_hash
    from app.core.enums import UserRole

    firm_id = firm_a_owner["firm_id"]
    email = f"staff2-{uuid.uuid4().hex[:8]}@firma.com"

    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("staff2pass123"),
            full_name="Staff A2",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": "staff2pass123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id, "user_id": user_id}


# ---------------------------------------------------------------------------
# GUARD TEST: duplicate day returns 409, not 500
# ---------------------------------------------------------------------------

class TestDuplicateDayGuard:
    """GUARD TEST with watched-fail cycle.

    A staff member cannot create two windows for the same day_of_week.
    The endpoint must return 409 (not let a raw IntegrityError escape as 500).
    """

    def test_duplicate_day_returns_409_not_500(self, client, firm_a_staff):
        """Creating a second window for the same day must return 409 with a clear message."""
        headers = firm_a_staff["headers"]
        user_id = None

        # Resolve the current user's id from /mine after creating the first window.
        # POST first window (day 0, Monday).
        r1 = client.post(
            BASE + "/",
            json=_window(str(uuid.uuid4()), day=0),  # user_id overridden server-side for staff
            headers=headers,
        )
        assert r1.status_code == 201, f"First window creation failed: {r1.text}"
        user_id = r1.json()["user_id"]

        # POST second window for the same day.
        r2 = client.post(
            BASE + "/",
            json=_window(user_id, day=0),
            headers=headers,
        )
        assert r2.status_code == 409, (
            f"Expected 409 for duplicate day, got {r2.status_code}: {r2.text}"
        )
        assert "day_of_week" in r2.json().get("detail", "").lower() or \
               "already exists" in r2.json().get("detail", "").lower(), (
            f"409 detail must mention the duplicate: {r2.json()}"
        )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestAvailabilityWindowsHappyPath:

    def test_staff_can_create_and_list_own_window(self, client, firm_a_staff):
        headers = firm_a_staff["headers"]

        r = client.post(BASE + "/", json=_window(str(uuid.uuid4()), day=1), headers=headers)
        assert r.status_code == 201
        created = r.json()
        assert created["day_of_week"] == 1
        assert created["start_time"] == "09:00:00"
        assert created["meeting_duration_minutes"] == 30

        mine = client.get(BASE + "/mine", headers=headers)
        assert mine.status_code == 200
        ids = [w["id"] for w in mine.json()]
        assert created["id"] in ids

    def test_list_firm_windows_returns_paginated_response(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        owner_user_id = _get_user_id("owner@firma.com")

        r = client.post(BASE + "/", json=_window(owner_user_id, day=2), headers=headers)
        assert r.status_code == 201
        created_id = r.json()["id"]

        r_list = client.get(BASE + "/", headers=headers)
        assert r_list.status_code == 200
        body = r_list.json()
        assert "items" in body
        assert "total" in body
        ids = [w["id"] for w in body["items"]]
        assert created_id in ids

    def test_owner_can_update_window(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        owner_user_id = _get_user_id("owner@firma.com")
        r = client.post(BASE + "/", json=_window(owner_user_id, day=3), headers=headers)
        assert r.status_code == 201
        wid = r.json()["id"]

        patch = client.patch(BASE + f"/{wid}", json={"meeting_duration_minutes": 45}, headers=headers)
        assert patch.status_code == 200
        assert patch.json()["meeting_duration_minutes"] == 45

    def test_owner_can_delete_window(self, client, firm_a_owner):
        headers = firm_a_owner["headers"]
        owner_user_id = _get_user_id("owner@firma.com")
        r = client.post(BASE + "/", json=_window(owner_user_id, day=4), headers=headers)
        assert r.status_code == 201
        wid = r.json()["id"]

        delete = client.delete(BASE + f"/{wid}", headers=headers)
        assert delete.status_code == 204

        # Confirm gone
        mine = client.get(BASE + "/mine", headers=headers)
        ids = [w["id"] for w in mine.json()]
        assert wid not in ids


# ---------------------------------------------------------------------------
# RBAC: staff cannot touch another staff member's windows
# ---------------------------------------------------------------------------

class TestAvailabilityWindowsRBAC:

    def test_staff_cannot_update_another_staffs_window(self, client, firm_a_staff, firm_a_staff_2):
        owner_headers = firm_a_staff["headers"]
        other_headers = firm_a_staff_2["headers"]

        # firm_a_staff creates a window
        r = client.post(BASE + "/", json=_window(str(uuid.uuid4()), day=0), headers=owner_headers)
        assert r.status_code == 201
        wid = r.json()["id"]

        # firm_a_staff_2 tries to update it
        patch = client.patch(
            BASE + f"/{wid}",
            json={"meeting_duration_minutes": 60},
            headers=other_headers,
        )
        assert patch.status_code == 403, (
            f"Staff must not be able to update another staff member's window. Got {patch.status_code}"
        )

    def test_staff_cannot_delete_another_staffs_window(self, client, firm_a_staff, firm_a_staff_2):
        owner_headers = firm_a_staff["headers"]
        other_headers = firm_a_staff_2["headers"]

        r = client.post(BASE + "/", json=_window(str(uuid.uuid4()), day=1), headers=owner_headers)
        assert r.status_code == 201
        wid = r.json()["id"]

        delete = client.delete(BASE + f"/{wid}", headers=other_headers)
        assert delete.status_code == 403, (
            f"Staff must not be able to delete another staff member's window. Got {delete.status_code}"
        )

    def test_manager_can_update_staff_window(self, client, firm_a_staff, firm_a_manager):
        staff_headers = firm_a_staff["headers"]
        manager_headers = firm_a_manager["headers"]

        r = client.post(BASE + "/", json=_window(str(uuid.uuid4()), day=2), headers=staff_headers)
        assert r.status_code == 201
        wid = r.json()["id"]

        patch = client.patch(
            BASE + f"/{wid}",
            json={"meeting_duration_minutes": 60},
            headers=manager_headers,
        )
        assert patch.status_code == 200, (
            f"Manager must be able to update any staff member's window. Got {patch.status_code}: {patch.text}"
        )
        assert patch.json()["meeting_duration_minutes"] == 60

    def test_firm_owner_can_delete_staff_window(self, client, firm_a_staff, firm_a_owner):
        staff_headers = firm_a_staff["headers"]
        owner_headers = firm_a_owner["headers"]

        r = client.post(BASE + "/", json=_window(str(uuid.uuid4()), day=3), headers=staff_headers)
        assert r.status_code == 201
        wid = r.json()["id"]

        delete = client.delete(BASE + f"/{wid}", headers=owner_headers)
        assert delete.status_code == 204, (
            f"Firm owner must be able to delete any staff member's window. Got {delete.status_code}"
        )


# ---------------------------------------------------------------------------
# GET /mine isolation: only returns the current user's windows
# ---------------------------------------------------------------------------

class TestGetMineIsolation:

    def test_mine_never_returns_another_users_windows(self, client, firm_a_staff, firm_a_staff_2):
        headers_1 = firm_a_staff["headers"]
        headers_2 = firm_a_staff_2["headers"]

        # Staff 1 creates a window
        r = client.post(BASE + "/", json=_window(str(uuid.uuid4()), day=0), headers=headers_1)
        assert r.status_code == 201
        staff1_window_id = r.json()["id"]

        # Staff 2 creates a window
        r2 = client.post(BASE + "/", json=_window(str(uuid.uuid4()), day=0), headers=headers_2)
        assert r2.status_code == 201
        staff2_window_id = r2.json()["id"]

        # Staff 2's /mine must NOT contain staff 1's window
        mine2 = client.get(BASE + "/mine", headers=headers_2)
        assert mine2.status_code == 200
        ids_2 = [w["id"] for w in mine2.json()]
        assert staff2_window_id in ids_2
        assert staff1_window_id not in ids_2, (
            f"/mine returned another user's window: {staff1_window_id} appeared in staff2's /mine"
        )


# ---------------------------------------------------------------------------
# Tenant isolation: Firm B cannot touch Firm A's windows
# ---------------------------------------------------------------------------

class TestAvailabilityWindowsTenantIsolation:

    def test_firm_b_cannot_list_firm_a_windows(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        owner_a_id = _get_user_id("owner@firma.com")
        r = client.post(BASE + "/", json=_window(owner_a_id, day=0), headers=headers_a)
        assert r.status_code == 201
        firm_a_window_id = r.json()["id"]

        # Firm B lists -- should not see Firm A's window
        r_list = client.get(BASE + "/", headers=headers_b)
        assert r_list.status_code == 200
        ids_b = [w["id"] for w in r_list.json()["items"]]
        assert firm_a_window_id not in ids_b, (
            f"Tenant isolation breach: Firm A window appeared in Firm B list"
        )

    def test_firm_b_cannot_update_firm_a_window(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        owner_a_id = _get_user_id("owner@firma.com")
        r = client.post(BASE + "/", json=_window(owner_a_id, day=1), headers=headers_a)
        assert r.status_code == 201
        wid = r.json()["id"]

        patch = client.patch(
            BASE + f"/{wid}",
            json={"meeting_duration_minutes": 60},
            headers=headers_b,
        )
        assert patch.status_code == 404, (
            f"Firm B must get 404 when updating Firm A's window. Got {patch.status_code}"
        )

    def test_firm_b_cannot_delete_firm_a_window(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        owner_a_id = _get_user_id("owner@firma.com")
        r = client.post(BASE + "/", json=_window(owner_a_id, day=2), headers=headers_a)
        assert r.status_code == 201
        wid = r.json()["id"]

        delete = client.delete(BASE + f"/{wid}", headers=headers_b)
        assert delete.status_code == 404, (
            f"Firm B must get 404 when deleting Firm A's window. Got {delete.status_code}"
        )
