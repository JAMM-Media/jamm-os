# tests/test_calendar_categories.py

"""
RBAC and tenant-isolation tests for calendar categories.
"""

import pytest
from unittest.mock import patch

from app.core.enums import UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CAT_PAYLOAD = {"name": "Tax Planning", "color": "#3B82F6", "sort_order": 0}


def _create_cat(client, headers, payload=None) -> str:
    r = client.post("/api/v1/calendar/categories", json=payload or _CAT_PAYLOAD, headers=headers)
    assert r.status_code == 201, f"Category creation failed: {r.json()}"
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

class TestCalendarCategoriesHappyPath:
    def test_create_category_happy_path(self, client, firm_a_owner):
        with patch("app.services.calendar_category_service.log_event") as mock_log:
            r = client.post(
                "/api/v1/calendar/categories",
                json=_CAT_PAYLOAD,
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 201
        body = r.json()
        assert body["name"] == "Tax Planning"
        assert body["color"] == "#3B82F6"
        assert body["is_active"] is True
        assert body["sort_order"] == 0
        assert mock_log.called
        call_kwargs = mock_log.call_args[1]
        assert call_kwargs["event_type"] == "calendar_category.created"
        assert call_kwargs["actor_type"] == "staff"

    def test_list_categories_returns_active_only_for_staff(self, client, firm_a_owner, firm_a_staff):
        _create_cat(client, firm_a_owner["headers"])
        inactive_id = _create_cat(
            client, firm_a_owner["headers"], {"name": "Inactive Cat", "color": "#000000"}
        )
        client.patch(
            f"/api/v1/calendar/categories/{inactive_id}",
            json={"is_active": False},
            headers=firm_a_owner["headers"],
        )
        r = client.get("/api/v1/calendar/categories", headers=firm_a_staff["headers"])
        assert r.status_code == 200
        body = r.json()
        names = [item["name"] for item in body["items"]]
        assert "Tax Planning" in names
        assert "Inactive Cat" not in names

    def test_rename_and_recolor(self, client, firm_a_owner):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"name": "Audit Prep", "color": "#EF4444"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        assert r.json()["name"] == "Audit Prep"
        assert r.json()["color"] == "#EF4444"

    def test_sort_order_respected(self, client, firm_a_owner):
        _create_cat(client, firm_a_owner["headers"], {"name": "Beta", "color": "#000001", "sort_order": 2})
        _create_cat(client, firm_a_owner["headers"], {"name": "Alpha", "color": "#000002", "sort_order": 1})
        r = client.get("/api/v1/calendar/categories", headers=firm_a_owner["headers"])
        names = [item["name"] for item in r.json()["items"]]
        assert names.index("Alpha") < names.index("Beta")

    def test_include_inactive_shows_all_for_manager(self, client, firm_a_owner, firm_a_manager):
        cat_id = _create_cat(client, firm_a_owner["headers"], {"name": "Old Cat", "color": "#111111"})
        client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"is_active": False},
            headers=firm_a_owner["headers"],
        )
        r = client.get(
            "/api/v1/calendar/categories",
            params={"include_inactive": "true"},
            headers=firm_a_manager["headers"],
        )
        assert r.status_code == 200
        names = [item["name"] for item in r.json()["items"]]
        assert "Old Cat" in names


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class TestCalendarCategoriesValidation:
    def test_duplicate_name_returns_409(self, client, firm_a_owner):
        _create_cat(client, firm_a_owner["headers"])
        r = client.post(
            "/api/v1/calendar/categories",
            json=_CAT_PAYLOAD,
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 409

    def test_duplicate_name_case_insensitive_returns_409(self, client, firm_a_owner):
        _create_cat(client, firm_a_owner["headers"], {"name": "Tax Planning", "color": "#111111"})
        r = client.post(
            "/api/v1/calendar/categories",
            json={"name": "TAX PLANNING", "color": "#222222"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 409

    def test_invalid_color_returns_422(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/calendar/categories",
            json={"name": "Bad Color", "color": "blue"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_invalid_color_short_hex_returns_422(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/calendar/categories",
            json={"name": "Bad Color", "color": "#FFF"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422


# ---------------------------------------------------------------------------
# RBAC
# ---------------------------------------------------------------------------

class TestCalendarCategoriesRBAC:
    def test_staff_cannot_create(self, client, firm_a_staff):
        r = client.post(
            "/api/v1/calendar/categories",
            json=_CAT_PAYLOAD,
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 403

    def test_staff_cannot_update(self, client, firm_a_owner, firm_a_staff):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"name": "Hacked"},
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 403

    def test_staff_can_list(self, client, firm_a_staff):
        r = client.get("/api/v1/calendar/categories", headers=firm_a_staff["headers"])
        assert r.status_code == 200
        assert "items" in r.json()

    def test_staff_cannot_include_inactive(self, client, firm_a_staff):
        r = client.get(
            "/api/v1/calendar/categories",
            params={"include_inactive": "true"},
            headers=firm_a_staff["headers"],
        )
        assert r.status_code == 403


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

class TestCalendarCategoriesTenantIsolation:
    def test_firm_b_cannot_update_firm_a_category(self, client, firm_a_owner, firm_b_owner):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"name": "Overwritten"},
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404

    def test_firm_b_list_never_includes_firm_a_categories(self, client, firm_a_owner, firm_b_owner):
        _create_cat(client, firm_a_owner["headers"])
        r = client.get("/api/v1/calendar/categories", headers=firm_b_owner["headers"])
        assert r.status_code == 200
        assert r.json()["total"] == 0
        assert r.json()["items"] == []


# ---------------------------------------------------------------------------
# Bug fix tests (bugs 3, 4, 5, 6)
# ---------------------------------------------------------------------------

class TestCalendarCategoriesBugFixes:
    def test_underscore_name_not_wildcard_conflict(self, client, firm_a_owner):
        _create_cat(client, firm_a_owner["headers"], {"name": "AxB", "color": "#000001"})
        r = client.post(
            "/api/v1/calendar/categories",
            json={"name": "A_B", "color": "#000002"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 201, r.json()

    def test_percent_name_not_wildcard_conflict(self, client, firm_a_owner):
        _create_cat(client, firm_a_owner["headers"], {"name": "50x", "color": "#000003"})
        r = client.post(
            "/api/v1/calendar/categories",
            json={"name": "50%", "color": "#000004"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 201, r.json()

    def test_case_change_duplicate_returns_409(self, client, firm_a_owner):
        _create_cat(client, firm_a_owner["headers"], {"name": "Client Call", "color": "#000005"})
        r = client.post(
            "/api/v1/calendar/categories",
            json={"name": "client call", "color": "#000006"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 409

    def test_patch_null_name_returns_422(self, client, firm_a_owner):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"name": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_patch_null_color_returns_422(self, client, firm_a_owner):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"color": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_patch_null_sort_order_returns_422(self, client, firm_a_owner):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"sort_order": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_patch_null_is_active_returns_422(self, client, firm_a_owner):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        r = client.patch(
            f"/api/v1/calendar/categories/{cat_id}",
            json={"is_active": None},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_create_null_name_returns_422(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/calendar/categories",
            json={"name": None, "color": "#AABBCC"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422

    def test_empty_patch_fires_no_log_event(self, client, firm_a_owner):
        cat_id = _create_cat(client, firm_a_owner["headers"])
        with patch("app.services.calendar_category_service.log_event") as mock_log:
            r = client.patch(
                f"/api/v1/calendar/categories/{cat_id}",
                json={},
                headers=firm_a_owner["headers"],
            )
        assert r.status_code == 200
        assert not mock_log.called
