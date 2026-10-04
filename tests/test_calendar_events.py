# tests/test_calendar_events.py

"""
RBAC, validation, behavioral event and tenant-isolation tests for calendar events.
"""

import pytest
from unittest.mock import patch

from app.core.enums import UserRole

_BASE_EVENT = {
    "title": "Client Call",
    "start_at": "2026-10-15T14:00:00Z",
    "end_at": "2026-10-15T15:00:00Z",
}

_RANGE_PARAMS = {"from": "2026-10-01T00:00:00Z", "to": "2026-11-01T00:00:00Z"}


def _create_event(client, headers, payload=None) -> str:
    r = client.post(
        "/api/v1/calendar/events",
        json=payload or _BASE_EVENT,
        headers=headers,
    )
    assert r.status_code == 201, f"Event creation failed: {r.json()}"
    return r.json()["id"]


@pytest.fixture
def firm_a_manager(client, firm_a_owner):
    """Manager user in Firm A."""
    from tests.conftest import TestingSessionLocal
    from app.models.user import User
    from app.core.security import get_password_hash
    import uuid

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
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": "mgrpass123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestCalendarEventsHappyPath:
    def test_create_sets_event_timezone_from_firm(self, client, firm_a_owner):
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.post(
                "/api/v1/calendar/events",
                json=_BASE_EVENT,
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 201
        body = r.json()
        assert body["title"] == "Client Call"
        assert body["event_timezone"] == "America/New_York"
        assert mock_log.called
        call_kwargs = mock_log.call_args[1]
        assert call_kwargs["event_type"] == "calendar_event.created"
        assert call_kwargs["actor_type"] == "staff"
        meta = call_kwargs["metadata"]
        assert "duration_minutes" in meta
        assert meta["duration_minutes"] == 60
        assert "title" not in meta

    def test_manager_create_patch_soft_delete_restore(self, client, firm_a_manager):
        ev_id = _create_event(client, firm_a_manager["headers"])

        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Updated Call"},
            headers=firm_a_manager["headers"],
        )
        assert r.status_code == 200
        assert r.json()["title"] == "Updated Call"

        r = client.delete(
            f"/api/v1/calendar/events/{ev_id}",
            headers=firm_a_manager["headers"],
        )
        assert r.status_code == 204

        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/restore",
            headers=firm_a_manager["headers"],
        )
        assert r.status_code == 200
        assert r.json()["id"] == ev_id

    def test_staff_and_manager_can_list_and_get(self, client, firm_a_owner, firm_a_staff):
        ev_id = _create_event(client, firm_a_owner["headers"])

        r = client.get(
            "/api/v1/calendar/events",
            params=_RANGE_PARAMS,
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 200
        ids = [item["id"] for item in r.json()["items"]]
        assert ev_id in ids

        r = client.get(
            f"/api/v1/calendar/events/{ev_id}",
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 200
        assert r.json()["id"] == ev_id

    def test_deleted_event_hidden_from_list_and_returns_404_on_get(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_owner["headers"])

        r = client.get("/api/v1/calendar/events", params=_RANGE_PARAMS, headers=firm_a_owner["headers"])
        ids = [item["id"] for item in r.json()["items"]]
        assert ev_id not in ids

        r = client.get(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_owner["headers"])
        assert r.status_code == 404

    def test_restore_live_event_returns_409(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/restore", headers=firm_a_owner["headers"])
        assert r.status_code == 409


# ---------------------------------------------------------------------------
# Time validation
# ---------------------------------------------------------------------------

class TestCalendarEventsTimeValidation:
    def test_naive_datetime_returns_422(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/calendar/events",
            json={
                "title": "Naive",
                "start_at": "2026-10-15T09:00:00",
                "end_at": "2026-10-15T10:00:00",
            },
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_end_equal_to_start_returns_422(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/calendar/events",
            json={
                "title": "Zero Duration",
                "start_at": "2026-10-15T09:00:00Z",
                "end_at": "2026-10-15T09:00:00Z",
            },
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_end_before_start_returns_422(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/calendar/events",
            json={
                "title": "Backwards",
                "start_at": "2026-10-15T10:00:00Z",
                "end_at": "2026-10-15T09:00:00Z",
            },
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_block_crossing_midnight_in_timezone_returns_422(self, client, firm_a_owner):
        # Firm timezone is America/New_York (UTC-4 in Oct)
        # 2026-10-15T03:30:00Z = 2026-10-14T23:30 EDT (start date Oct 14)
        # 2026-10-15T04:30:00Z = 2026-10-15T00:30 EDT (end date Oct 15)
        r = client.post(
            "/api/v1/calendar/events",
            json={
                "title": "Crosses Midnight",
                "start_at": "2026-10-15T03:30:00Z",
                "end_at": "2026-10-15T04:30:00Z",
            },
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

class TestCalendarEventsRBAC:
    def test_staff_cannot_create(self, client, firm_a_staff):
        r = client.post(
            "/api/v1/calendar/events",
            json=_BASE_EVENT,
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 403

    def test_staff_cannot_patch(self, client, firm_a_owner, firm_a_staff):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Staff Patch"},
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 403

    def test_staff_cannot_delete(self, client, firm_a_owner, firm_a_staff):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_staff["headers"])
        assert r.status_code == 403

    def test_staff_cannot_restore(self, client, firm_a_owner, firm_a_staff):
        ev_id = _create_event(client, firm_a_owner["headers"])
        client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_owner["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/restore", headers=firm_a_staff["headers"])
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Cross-firm FK validation
# ---------------------------------------------------------------------------

class TestCalendarEventsCrossFirmValidation:
    def test_category_from_another_firm_refused(self, client, firm_a_owner, firm_b_owner):
        cat_id_b = client.post(
            "/api/v1/calendar/categories",
            json={"name": "Firm B Cat", "color": "#111111"},
            headers=firm_b_owner["headers"],
        ).json()["id"]
        r = client.post(
            "/api/v1/calendar/events",
            json={**_BASE_EVENT, "category_id": cat_id_b},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 404

    def test_inactive_category_cannot_be_assigned(self, client, firm_a_owner):
        cat_id = client.post(
            "/api/v1/calendar/categories",
            json={"name": "Inactive", "color": "#AAAAAA"},
            headers=firm_a_owner["headers"],
        ).json()["id"]
        client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"is_active": False},
            headers=firm_a_owner["headers"],
        )
        r = client.post(
            "/api/v1/calendar/events",
            json={**_BASE_EVENT, "category_id": cat_id},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# Range filter
# ---------------------------------------------------------------------------

class TestCalendarEventsRangeFilter:
    def test_event_overlapping_range_boundary_is_included(self, client, firm_a_owner):
        # Event 14:00-16:00, range 15:00-17:00 => overlaps
        ev_id = _create_event(
            client,
            firm_a_owner["headers"],
            {"title": "Overlap", "start_at": "2026-10-15T14:00:00Z", "end_at": "2026-10-15T16:00:00Z"},
        )
        r = client.get(
            "/api/v1/calendar/events",
            params={"from": "2026-10-15T15:00:00Z", "to": "2026-10-15T17:00:00Z"},
            headers=firm_a_owner["headers"],
        )
        ids = [item["id"] for item in r.json()["items"]]
        assert ev_id in ids

    def test_event_ending_exactly_at_range_start_is_excluded(self, client, firm_a_owner):
        # Event 13:00-15:00, range 15:00-17:00 => end == range start, not overlapping
        ev_id = _create_event(
            client,
            firm_a_owner["headers"],
            {"title": "Just Before", "start_at": "2026-10-15T13:00:00Z", "end_at": "2026-10-15T15:00:00Z"},
        )
        r = client.get(
            "/api/v1/calendar/events",
            params={"from": "2026-10-15T15:00:00Z", "to": "2026-10-15T17:00:00Z"},
            headers=firm_a_owner["headers"],
        )
        ids = [item["id"] for item in r.json()["items"]]
        assert ev_id not in ids

    def test_stable_order_across_pages(self, client, firm_a_owner):
        # Two events with identical start_at to verify tiebreaker ordering
        ev1_id = _create_event(
            client, firm_a_owner["headers"],
            {"title": "Event One", "start_at": "2026-10-15T09:00:00Z", "end_at": "2026-10-15T10:00:00Z"},
        )
        ev2_id = _create_event(
            client, firm_a_owner["headers"],
            {"title": "Event Two", "start_at": "2026-10-15T09:00:00Z", "end_at": "2026-10-15T10:00:00Z"},
        )
        r1 = client.get(
            "/api/v1/calendar/events",
            params={**_RANGE_PARAMS, "limit": 1, "offset": 0},
            headers=firm_a_owner["headers"],
        )
        r2 = client.get(
            "/api/v1/calendar/events",
            params={**_RANGE_PARAMS, "limit": 1, "offset": 1},
            headers=firm_a_owner["headers"],
        )
        page1_id = r1.json()["items"][0]["id"]
        page2_id = r2.json()["items"][0]["id"]
        assert page1_id != page2_id
        assert set([page1_id, page2_id]) == set([ev1_id, ev2_id])


# ---------------------------------------------------------------------------
# Behavioral events
# ---------------------------------------------------------------------------

class TestCalendarEventsBehavioralEvents:
    def test_patch_times_fires_moved_event(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.patch(
                f"/api/v1/calendar/events/{ev_id}",
                json={
                    "start_at": "2026-10-15T15:00:00Z",
                    "end_at": "2026-10-15T16:00:00Z",
                },
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 200
        event_types = [call[1]["event_type"] for call in mock_log.call_args_list]
        assert "calendar_event.moved" in event_types
        moved_call = next(c for c in mock_log.call_args_list if c[1]["event_type"] == "calendar_event.moved")
        meta = moved_call[1]["metadata"]
        assert "old_start_at" in meta
        assert "new_start_at" in meta

    def test_patch_title_fires_updated_not_moved(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.patch(
                f"/api/v1/calendar/events/{ev_id}",
                json={"title": "New Title"},
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 200
        event_types = [call[1]["event_type"] for call in mock_log.call_args_list]
        assert "calendar_event.updated" in event_types
        assert "calendar_event.moved" not in event_types
        updated_call = next(c for c in mock_log.call_args_list if c[1]["event_type"] == "calendar_event.updated")
        meta = updated_call[1]["metadata"]
        assert "changed_fields" in meta
        # The actual title value must not appear in metadata
        assert "New Title" not in str(meta)


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestCalendarEventsTenantIsolation:
    def test_firm_b_cannot_get_firm_a_event(self, client, firm_a_owner, firm_b_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.get(f"/api/v1/calendar/events/{ev_id}", headers=firm_b_owner["headers"])
        assert r.status_code == 404, f"Tenant isolation breach: {r.json()}"

    def test_firm_b_cannot_patch_firm_a_event(self, client, firm_a_owner, firm_b_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Overwritten"},
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404

    def test_firm_b_cannot_delete_firm_a_event(self, client, firm_a_owner, firm_b_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_b_owner["headers"])
        assert r.status_code == 404

    def test_firm_b_cannot_restore_firm_a_event(self, client, firm_a_owner, firm_b_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        client.delete(f"/api/v1/calendar/events/{ev_id}", headers=firm_a_owner["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/restore", headers=firm_b_owner["headers"])
        assert r.status_code == 404

    def test_firm_b_list_never_includes_firm_a_events(self, client, firm_a_owner, firm_b_owner):
        _create_event(client, firm_a_owner["headers"])
        r = client.get("/api/v1/calendar/events", params=_RANGE_PARAMS, headers=firm_b_owner["headers"])
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []


# ---------------------------------------------------------------------------
# Bug fix tests (bugs 1, 2, 5, 6)
# ---------------------------------------------------------------------------

class TestCalendarEventsBugFixes:
    def test_patch_title_when_category_deactivated_returns_200(self, client, firm_a_owner):
        cat_id = client.post(
            "/api/v1/calendar/categories",
            json={"name": "Active Cat", "color": "#111111"},
            headers=firm_a_owner["headers"],
        ).json()["id"]
        ev_id = _create_event(
            client, firm_a_owner["headers"],
            {**_BASE_EVENT, "category_id": cat_id},
        )
        client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"is_active": False},
            headers=firm_a_owner["headers"],
        )
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Updated Title", "category_id": cat_id},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, r.json()
        assert r.json()["category_id"] == cat_id

    def test_patch_title_when_owner_inactive_returns_200(self, client, firm_a_owner):
        from tests.conftest import TestingSessionLocal
        from app.models.user import User
        import uuid
        firm_id = firm_a_owner["firm_id"]
        db = TestingSessionLocal()
        try:
            owner_user = User(
                firm_id=firm_id,
                email=f"owner-{uuid.uuid4()}@firma.com",
                hashed_password="hashed",
                full_name="Owner User",
                role=UserRole.staff,
                is_active=True,
            )
            db.add(owner_user)
            db.commit()
            db.refresh(owner_user)
            owner_id = str(owner_user.id)
        finally:
            db.close()
        ev_id = _create_event(
            client, firm_a_owner["headers"],
            {**_BASE_EVENT, "owner_user_id": owner_id},
        )
        db = TestingSessionLocal()
        try:
            u = db.get(User, owner_id)
            u.is_active = False
            db.commit()
        finally:
            db.close()
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Still Works"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, r.json()
        assert r.json()["owner_user_id"] == owner_id

    def test_assign_different_inactive_category_returns_422(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        cat_id = client.post(
            "/api/v1/calendar/categories",
            json={"name": "Inactive New", "color": "#222222"},
            headers=firm_a_owner["headers"],
        ).json()["id"]
        client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"is_active": False},
            headers=firm_a_owner["headers"],
        )
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"category_id": cat_id},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_patch_null_title_returns_422(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_patch_null_start_at_returns_422(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"start_at": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_patch_null_end_at_returns_422(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"end_at": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_create_null_title_returns_422(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/calendar/events",
            json={**_BASE_EVENT, "title": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_empty_patch_fires_no_log_event(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.patch(
                f"/api/v1/calendar/events/{ev_id}",
                json={},
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 200
        assert not mock_log.called

    def test_patch_same_title_fires_no_log_event(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.patch(
                f"/api/v1/calendar/events/{ev_id}",
                json={"title": "Client Call"},
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 200
        assert not mock_log.called

    def test_patch_same_times_fires_no_moved(self, client, firm_a_owner):
        ev_id = _create_event(client, firm_a_owner["headers"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.patch(
                f"/api/v1/calendar/events/{ev_id}",
                json={
                    "title": "New Title",
                    "start_at": _BASE_EVENT["start_at"],
                    "end_at": _BASE_EVENT["end_at"],
                },
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 200
        event_types = [call[1]["event_type"] for call in mock_log.call_args_list]
        assert "calendar_event.updated" in event_types
        assert "calendar_event.moved" not in event_types
