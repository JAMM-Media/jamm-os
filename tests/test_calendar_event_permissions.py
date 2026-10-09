# tests/test_calendar_event_permissions.py

import uuid
import pytest

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.user import User
from tests.conftest import TestingSessionLocal


_BASE_EVENT = {
    "title": "Meeting",
    "start_at": "2026-10-15T14:00:00Z",
    "end_at": "2026-10-15T15:00:00Z",
}
_RANGE = {"from": "2026-10-01T00:00:00Z", "to": "2026-11-01T00:00:00Z"}


# ---------------------------------------------------------------------------
# Local fixtures
# ---------------------------------------------------------------------------

# Pattern copied from tests/conftest.py firm_a_staff fixture.
# Each fixture also returns user_id captured from db.refresh(user).

@pytest.fixture
def firm_a_staff_with_id(client, firm_a_owner):
    """Staff user in Firm A with user UUID returned."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff1-{uuid.uuid4()}@firma.com",
            hashed_password=get_password_hash("staffpass123"),
            full_name="Staff One",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        email = user.email
        user_id = str(user.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "staffpass123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id, "user_id": user_id}


@pytest.fixture
def firm_a_second_staff(client, firm_a_owner):
    """A second staff user in Firm A with user UUID returned."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staff2-{uuid.uuid4()}@firma.com",
            hashed_password=get_password_hash("staffpass456"),
            full_name="Staff Two",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        email = user.email
        user_id = str(user.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "staffpass456"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id, "user_id": user_id}


@pytest.fixture
def firm_a_manager(client, firm_a_owner):
    """Manager user in Firm A with user UUID returned."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"manager-{uuid.uuid4()}@firma.com",
            hashed_password=get_password_hash("mgrpass123"),
            full_name="Manager A",
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        email = user.email
        user_id = str(user.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "mgrpass123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id, "user_id": user_id}


@pytest.fixture
def firm_b_staff(client, firm_b_owner):
    """Staff user in Firm B with user UUID returned."""
    firm_id = firm_b_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"staffb-{uuid.uuid4()}@firmb.com",
            hashed_password=get_password_hash("staffbpass"),
            full_name="Staff B",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        email = user.email
        user_id = str(user.id)
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "staffbpass"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id, "user_id": user_id}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _create(client, headers, payload=None):
    """Create an event and return its id. Asserts 201."""
    r = client.post("/api/v1/calendar/events", json=payload or _BASE_EVENT, headers=headers)
    assert r.status_code == 201, r.json()
    return r.json()["id"]


# ---------------------------------------------------------------------------
# READ
# ---------------------------------------------------------------------------

class TestCalendarPermissionsRead:
    def test_staff_list_own_and_null_owner_events_not_another_staff(
        self, client, firm_a_staff_with_id, firm_a_second_staff, firm_a_manager
    ):
        # NULL-owner event (firm-wide)
        null_id = _create(client, firm_a_manager["headers"])
        # Own event (staff1 creates for themselves)
        own_id = _create(client, firm_a_staff_with_id["headers"])
        # Other staff event (staff2 creates for themselves)
        other_id = _create(client, firm_a_second_staff["headers"])

        r = client.get("/api/v1/calendar/events", params=_RANGE, headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 200
        ids = {item["id"] for item in r.json()["items"]}
        assert null_id in ids
        assert own_id in ids
        assert other_id not in ids

    def test_staff_list_count_matches_visible_set(
        self, client, firm_a_staff_with_id, firm_a_second_staff, firm_a_manager
    ):
        null_id = _create(client, firm_a_manager["headers"])
        own_id = _create(client, firm_a_staff_with_id["headers"])
        _create(client, firm_a_second_staff["headers"])

        r = client.get("/api/v1/calendar/events", params=_RANGE, headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["total"] == len(body["items"])
        assert body["total"] == 2

    def test_staff_list_another_user_owner_id_returns_403(
        self, client, firm_a_staff_with_id, firm_a_second_staff
    ):
        r = client.get(
            "/api/v1/calendar/events",
            params={**_RANGE, "owner_user_id": firm_a_second_staff["user_id"]},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_manager_list_returns_all_firm_events(
        self, client, firm_a_staff_with_id, firm_a_second_staff, firm_a_manager
    ):
        null_id = _create(client, firm_a_manager["headers"])
        own_id = _create(client, firm_a_staff_with_id["headers"])
        other_id = _create(client, firm_a_second_staff["headers"])

        r = client.get("/api/v1/calendar/events", params=_RANGE, headers=firm_a_manager["headers"])
        assert r.status_code == 200
        ids = {item["id"] for item in r.json()["items"]}
        assert null_id in ids
        assert own_id in ids
        assert other_id in ids

    def test_staff_get_another_staff_event_returns_404(
        self, client, firm_a_staff_with_id, firm_a_second_staff
    ):
        other_id = _create(client, firm_a_second_staff["headers"])
        r = client.get(f"/api/v1/calendar/events/{other_id}", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 404

    def test_staff_get_own_and_null_owner_events_returns_200(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        null_id = _create(client, firm_a_manager["headers"])
        own_id = _create(client, firm_a_staff_with_id["headers"])

        r = client.get(f"/api/v1/calendar/events/{null_id}", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 200
        r = client.get(f"/api/v1/calendar/events/{own_id}", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# CREATE
# ---------------------------------------------------------------------------

class TestCalendarPermissionsCreate:
    def test_staff_create_null_owner_forces_self(
        self, client, firm_a_staff_with_id
    ):
        r = client.post("/api/v1/calendar/events", json=_BASE_EVENT, headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 201
        body = r.json()
        assert body["owner_user_id"] == firm_a_staff_with_id["user_id"]
        assert body["created_by"] == firm_a_staff_with_id["user_id"]

    def test_staff_create_another_user_owner_returns_403(
        self, client, firm_a_staff_with_id, firm_a_second_staff
    ):
        payload = {**_BASE_EVENT, "owner_user_id": firm_a_second_staff["user_id"]}
        r = client.post("/api/v1/calendar/events", json=payload, headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 403

    def test_staff_create_with_client_id_returns_403(
        self, client, firm_a_staff_with_id
    ):
        payload = {**_BASE_EVENT, "client_id": str(uuid.uuid4())}
        r = client.post("/api/v1/calendar/events", json=payload, headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 403

    def test_manager_create_null_owner_saves_null(
        self, client, firm_a_manager
    ):
        r = client.post("/api/v1/calendar/events", json=_BASE_EVENT, headers=firm_a_manager["headers"])
        assert r.status_code == 201
        assert r.json()["owner_user_id"] is None

    def test_manager_create_for_staff_saves_owner_and_created_by(
        self, client, firm_a_manager, firm_a_staff_with_id
    ):
        payload = {**_BASE_EVENT, "owner_user_id": firm_a_staff_with_id["user_id"]}
        r = client.post("/api/v1/calendar/events", json=payload, headers=firm_a_manager["headers"])
        assert r.status_code == 201
        body = r.json()
        assert body["owner_user_id"] == firm_a_staff_with_id["user_id"]
        assert body["created_by"] == firm_a_manager["user_id"]

    def test_manager_create_with_client_portal_user_owner_returns_422(
        self, client, firm_a_manager
    ):
        firm_id = firm_a_manager["firm_id"]
        db = TestingSessionLocal()
        try:
            portal_user = User(
                firm_id=firm_id,
                email=f"portal-{uuid.uuid4()}@firma.com",
                hashed_password=get_password_hash("portalpass"),
                full_name="Portal User",
                role=UserRole.client_portal_user,
            )
            db.add(portal_user)
            db.commit()
            db.refresh(portal_user)
            portal_id = str(portal_user.id)
        finally:
            db.close()
        payload = {**_BASE_EVENT, "owner_user_id": portal_id}
        r = client.post("/api/v1/calendar/events", json=payload, headers=firm_a_manager["headers"])
        assert r.status_code == 422
        assert "client portal user" in r.json()["detail"].lower()


# ---------------------------------------------------------------------------
# UPDATE
# ---------------------------------------------------------------------------

class TestCalendarPermissionsUpdate:
    def test_staff_update_own_event_title_returns_200(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Updated"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Updated"

    def test_staff_update_manager_assigned_event_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        # Manager creates event with staff as owner
        payload = {**_BASE_EVENT, "owner_user_id": firm_a_staff_with_id["user_id"]}
        ev_id = _create(client, firm_a_manager["headers"], payload)
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Staff Edit"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_staff_update_firm_wide_null_owner_event_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _create(client, firm_a_manager["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Sneaky"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_staff_update_own_event_setting_owner_to_null_returns_403(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"owner_user_id": None},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_staff_update_own_event_setting_client_id_returns_403(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"client_id": str(uuid.uuid4())},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_staff_update_event_with_created_by_null_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        # Manager creates event owned by staff
        payload = {**_BASE_EVENT, "owner_user_id": firm_a_staff_with_id["user_id"]}
        ev_id = _create(client, firm_a_manager["headers"], payload)
        # Null out created_by directly in DB
        from app.models.calendar_event import CalendarEvent as CE
        db = TestingSessionLocal()
        try:
            import uuid as _uuid
            ev = db.get(CE, _uuid.UUID(ev_id))
            ev.created_by = None
            db.commit()
        finally:
            db.close()
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Should Fail"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_manager_can_update_any_event(
        self, client, firm_a_manager, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Manager Edit"},
            headers=firm_a_manager["headers"],
        )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# DELETE
# ---------------------------------------------------------------------------

class TestCalendarPermissionsDelete:
    def test_staff_delete_own_event_returns_204(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 204

    def test_staff_delete_manager_assigned_event_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        payload = {**_BASE_EVENT, "owner_user_id": firm_a_staff_with_id["user_id"]}
        ev_id = _create(client, firm_a_manager["headers"], payload)
        r = client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 403

    def test_staff_delete_another_staff_event_returns_404(
        self, client, firm_a_staff_with_id, firm_a_second_staff
    ):
        other_id = _create(client, firm_a_second_staff["headers"])
        r = client.delete(f"/api/v1/calendar/events/{other_id}", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 404

    def test_staff_restore_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_staff_with_id["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/restore", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 403

    def test_staff_deleted_true_listing_returns_403(
        self, client, firm_a_staff_with_id
    ):
        r = client.get(
            "/api/v1/calendar/events",
            params={**_RANGE, "deleted": True},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_manager_can_delete_any_event(
        self, client, firm_a_manager, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_manager["headers"])
        assert r.status_code == 204


# ---------------------------------------------------------------------------
# TENANT ISOLATION
# ---------------------------------------------------------------------------

class TestCalendarPermissionsTenantIsolation:
    def test_firm_b_manager_cannot_read_firm_a_event(
        self, client, firm_a_owner, firm_b_owner
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.get(f"/api/v1/calendar/events/{ev_id}", headers=firm_b_owner["headers"])
        assert r.status_code == 404

    def test_firm_b_staff_cannot_read_firm_a_event(
        self, client, firm_a_owner, firm_b_staff
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.get(f"/api/v1/calendar/events/{ev_id}", headers=firm_b_staff["headers"])
        assert r.status_code == 404

    def test_firm_b_staff_cannot_update_firm_a_event(
        self, client, firm_a_owner, firm_b_staff
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Breach"},
            headers=firm_b_staff["headers"],
        )
        assert r.status_code == 404

    def test_firm_b_staff_cannot_delete_firm_a_event(
        self, client, firm_a_owner, firm_b_staff
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_b_staff["headers"])
        assert r.status_code == 404

