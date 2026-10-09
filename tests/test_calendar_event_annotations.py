# tests/test_calendar_event_annotations.py

import uuid
import pytest
from unittest.mock import patch

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
# Local fixtures (copied from test_calendar_event_permissions.py)
# ---------------------------------------------------------------------------

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


def _manager_assigned(client, manager, staff_id):
    """Manager creates event owned by staff. Returns event id."""
    payload = {**_BASE_EVENT, "owner_user_id": staff_id}
    return _create(client, manager["headers"], payload)


# ---------------------------------------------------------------------------
# ANNOTATIONS (staff_notes, is_done)
# ---------------------------------------------------------------------------

class TestCalendarAnnotations:
    def test_staff_updates_notes_and_is_done_on_manager_assigned_event_returns_200(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"staff_notes": "review needed", "is_done": True},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["staff_notes"] == "review needed"
        assert body["is_done"] is True
        assert body["completed_at"] is not None

    def test_is_done_true_sets_completed_at(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"is_done": True},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        assert r.json()["completed_at"] is not None

    def test_is_done_false_clears_completed_at(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"is_done": True},
            headers=firm_a_staff_with_id["headers"],
        )
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"is_done": False},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        assert r.json()["completed_at"] is None
        assert r.json()["is_done"] is False

    def test_staff_updating_title_of_manager_assigned_event_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"title": "Changed Title"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_staff_updating_notes_on_firm_wide_event_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        # Manager creates firm-wide event (NULL owner)
        ev_id = _create(client, firm_a_manager["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"staff_notes": "should fail"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_staff_updating_notes_on_another_staff_event_returns_404(
        self, client, firm_a_staff_with_id, firm_a_second_staff
    ):
        other_ev_id = _create(client, firm_a_second_staff["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{other_ev_id}",
            json={"staff_notes": "should 404"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 404

    def test_staff_updates_notes_on_own_created_event_returns_200(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"staff_notes": "my note"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        assert r.json()["staff_notes"] == "my note"

    def test_manager_can_edit_notes_and_is_done_on_any_event(
        self, client, firm_a_manager, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"staff_notes": "manager note", "is_done": True},
            headers=firm_a_manager["headers"],
        )
        assert r.status_code == 200
        assert r.json()["staff_notes"] == "manager note"
        assert r.json()["is_done"] is True

    def test_staff_notes_over_2000_characters_returns_422(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"staff_notes": "x" * 2001},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 422

    def test_empty_staff_notes_saves_null(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.patch(
            f"/api/v1/calendar/events/{ev_id}",
            json={"staff_notes": ""},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        assert r.json()["staff_notes"] is None


# ---------------------------------------------------------------------------
# DELETE REQUEST
# ---------------------------------------------------------------------------

class TestCalendarDeleteRequest:
    def test_delete_request_on_manager_assigned_event_saves_fields(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={"reason": "no longer needed"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200, r.json()
        body = r.json()
        assert body["delete_requested_by"] == firm_a_staff_with_id["user_id"]
        assert body["delete_requested_at"] is not None
        assert body["delete_request_reason"] == "no longer needed"

    def test_delete_request_without_reason_saves_null_reason(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        assert r.json()["delete_request_reason"] is None
        assert r.json()["delete_requested_at"] is not None

    def test_delete_request_on_own_created_event_returns_409_direct_delete(
        self, client, firm_a_staff_with_id
    ):
        ev_id = _create(client, firm_a_staff_with_id["headers"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 409
        assert "directly" in r.json()["detail"]

    def test_second_delete_request_returns_409(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={}, headers=firm_a_staff_with_id["headers"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 409
        assert "pending" in r.json()["detail"].lower()

    def test_delete_request_on_another_staff_event_returns_404(
        self, client, firm_a_staff_with_id, firm_a_second_staff
    ):
        other_ev_id = _create(client, firm_a_second_staff["headers"])
        r = client.post(
            f"/api/v1/calendar/events/{other_ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 404

    def test_delete_request_on_firm_wide_event_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _create(client, firm_a_manager["headers"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 403

    def test_manager_calling_delete_request_returns_409(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_manager["headers"],
        )
        assert r.status_code == 409
        assert "directly" in r.json()["detail"]

    def test_delete_request_does_not_delete_the_event(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        r_list = client.get("/api/v1/calendar/events", params=_RANGE, headers=firm_a_manager["headers"])
        ids = [item["id"] for item in r_list.json()["items"]]
        assert ev_id in ids


# ---------------------------------------------------------------------------
# APPROVE and DENY
# ---------------------------------------------------------------------------

class TestCalendarApproveAndDeny:
    def test_approve_soft_deletes_event_and_disappears_from_list(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={}, headers=firm_a_staff_with_id["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/approve", headers=firm_a_manager["headers"])
        assert r.status_code == 200
        r_list = client.get("/api/v1/calendar/events", params=_RANGE, headers=firm_a_manager["headers"])
        ids = [item["id"] for item in r_list.json()["items"]]
        assert ev_id not in ids

    def test_approve_with_no_pending_request_returns_409(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/approve", headers=firm_a_manager["headers"])
        assert r.status_code == 409

    def test_deny_clears_request_fields_and_event_stays(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={"reason": "please"}, headers=firm_a_staff_with_id["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/deny", headers=firm_a_manager["headers"])
        assert r.status_code == 200
        body = r.json()
        assert body["delete_requested_at"] is None
        assert body["delete_requested_by"] is None
        assert body["delete_request_reason"] is None
        r_list = client.get("/api/v1/calendar/events", params=_RANGE, headers=firm_a_manager["headers"])
        ids = [item["id"] for item in r_list.json()["items"]]
        assert ev_id in ids

    def test_deny_with_no_pending_request_returns_409(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/deny", headers=firm_a_manager["headers"])
        assert r.status_code == 409

    def test_staff_calling_approve_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={}, headers=firm_a_staff_with_id["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/approve", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 403

    def test_staff_calling_deny_returns_403(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={}, headers=firm_a_staff_with_id["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/deny", headers=firm_a_staff_with_id["headers"])
        assert r.status_code == 403

    def test_restore_clears_delete_request_and_staff_can_refile(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={"reason": "old reason"}, headers=firm_a_staff_with_id["headers"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/approve", headers=firm_a_manager["headers"])
        r_restore = client.post(f"/api/v1/calendar/events/{ev_id}/restore", headers=firm_a_manager["headers"])
        assert r_restore.status_code == 200
        body = r_restore.json()
        assert body["delete_requested_at"] is None
        assert body["delete_requested_by"] is None
        assert body["delete_request_reason"] is None
        # Staff can file a new request after restore
        r_new = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={"reason": "new reason"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r_new.status_code == 200


# ---------------------------------------------------------------------------
# NOTIFICATIONS
# ---------------------------------------------------------------------------

class TestCalendarDeleteRequestNotifications:
    def test_notification_created_for_assigning_manager(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        from app.models.notification import Notification
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={"reason": "too old"},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        db = TestingSessionLocal()
        try:
            all_notifs = db.query(Notification).all()
            mgr_notifs = [n for n in all_notifs if str(n.recipient_id) == firm_a_manager["user_id"]]
        finally:
            db.close()
        # One notification total, and it must go to the assigning manager
        assert len(all_notifs) == 1, f"Expected 1 total notif, got {len(all_notifs)}"
        assert len(mgr_notifs) == 1
        n = mgr_notifs[0]
        assert "Staff One" in n.body
        assert "Meeting" in n.body
        assert "too old" in n.body

    def test_notification_goes_to_owners_and_managers_when_created_by_is_null(
        self, client, firm_a_staff_with_id, firm_a_manager, firm_a_owner
    ):
        from app.models.notification import Notification
        from app.models.calendar_event import CalendarEvent as CE
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        # Set created_by to NULL
        db = TestingSessionLocal()
        try:
            ev = db.get(CE, uuid.UUID(ev_id))
            ev.created_by = None
            db.commit()
        finally:
            db.close()
        r = client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        assert r.status_code == 200
        db = TestingSessionLocal()
        try:
            count = db.query(Notification).count()
        finally:
            db.close()
        # At least one notification to firm owner or manager (firm_a_owner is firm_owner)
        assert count >= 1

    def test_no_notification_for_user_in_another_firm(
        self, client, firm_a_staff_with_id, firm_a_manager, firm_b_owner
    ):
        from app.models.notification import Notification
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(
            f"/api/v1/calendar/events/{ev_id}/delete-request",
            json={},
            headers=firm_a_staff_with_id["headers"],
        )
        # No notification row should have firm_id from Firm B
        db = TestingSessionLocal()
        try:
            import uuid as _uuid
            notifs_firm_b = db.query(Notification).filter(
                Notification.firm_id == _uuid.UUID(firm_b_owner["firm_id"]),
            ).all()
        finally:
            db.close()
        assert len(notifs_firm_b) == 0

    def test_failing_notification_does_not_make_delete_request_fail(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        with patch(
            "app.services.notification_service.NotificationService.create_notification",
            side_effect=Exception("simulated notification failure"),
        ):
            r = client.post(
                f"/api/v1/calendar/events/{ev_id}/delete-request",
                json={},
                headers=firm_a_staff_with_id["headers"],
            )
        assert r.status_code == 200


# ---------------------------------------------------------------------------
# BEHAVIORAL LOG
# ---------------------------------------------------------------------------

class TestCalendarDeleteRequestBehavioralLog:
    def test_delete_requested_log_fires_with_has_reason_and_no_reason_text(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.post(
                f"/api/v1/calendar/events/{ev_id}/delete-request",
                json={"reason": "secret reason"},
                headers=firm_a_staff_with_id["headers"],
            )
        assert r.status_code == 200
        calls = {c[1]["event_type"]: c[1] for c in mock_log.call_args_list}
        assert "calendar_event.delete_requested" in calls
        meta = calls["calendar_event.delete_requested"]["metadata"]
        assert meta["has_reason"] is True
        # Reason text must never appear in log metadata
        for call in mock_log.call_args_list:
            assert "secret reason" not in str(call[1].get("metadata", {}))

    def test_delete_request_approved_log_fires(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={"reason": "r"}, headers=firm_a_staff_with_id["headers"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/approve", headers=firm_a_manager["headers"])
        assert r.status_code == 200
        types = [c[1]["event_type"] for c in mock_log.call_args_list]
        assert "calendar_event.delete_request_approved" in types
        approved_call = next(c for c in mock_log.call_args_list if c[1]["event_type"] == "calendar_event.delete_request_approved")
        assert "has_reason" in approved_call[1]["metadata"]

    def test_delete_request_denied_log_fires(
        self, client, firm_a_staff_with_id, firm_a_manager
    ):
        ev_id = _manager_assigned(client, firm_a_manager, firm_a_staff_with_id["user_id"])
        client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={}, headers=firm_a_staff_with_id["headers"])
        with patch("app.services.calendar_event_service.log_event") as mock_log:
            r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/deny", headers=firm_a_manager["headers"])
        assert r.status_code == 200
        types = [c[1]["event_type"] for c in mock_log.call_args_list]
        assert "calendar_event.delete_request_denied" in types


# ---------------------------------------------------------------------------
# TENANT ISOLATION
# ---------------------------------------------------------------------------

class TestCalendarDeleteRequestTenantIsolation:
    def test_firm_b_manager_cannot_request_delete_on_firm_a_event(
        self, client, firm_a_owner, firm_b_owner
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={}, headers=firm_b_owner["headers"])
        assert r.status_code == 404

    def test_firm_b_staff_cannot_request_delete_on_firm_a_event(
        self, client, firm_a_owner, firm_b_staff
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request", json={}, headers=firm_b_staff["headers"])
        assert r.status_code == 404

    def test_firm_b_manager_cannot_approve_on_firm_a_event(
        self, client, firm_a_owner, firm_b_owner
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/approve", headers=firm_b_owner["headers"])
        assert r.status_code == 404

    def test_firm_b_manager_cannot_deny_on_firm_a_event(
        self, client, firm_a_owner, firm_b_owner
    ):
        ev_id = _create(client, firm_a_owner["headers"])
        r = client.post(f"/api/v1/calendar/events/{ev_id}/delete-request/deny", headers=firm_b_owner["headers"])
        assert r.status_code == 404


# ---------------------------------------------------------------------------
# MIGRATION COLUMN GUARD
# ---------------------------------------------------------------------------

class TestCalendarEventPhase2MigrationColumns:
    def test_phase2_columns_exist_with_correct_types(self, migration_db_session):
        """Asserts that migration b66b4394a869 added all five Phase 2 columns
        to calendar_events with the correct types, nullability, and FK rule.
        Runs against a scratch database built by the real migration chain so
        a type or nullability drift between the model and the migration file
        is visible here even if the ordinary test suite stays green."""
        from sqlalchemy import text

        db = migration_db_session

        rows = db.execute(text(
            "SELECT column_name, udt_name, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = 'calendar_events'"
        )).mappings().all()
        cols = {r["column_name"]: r for r in rows}

        for name in (
            "staff_notes", "completed_at", "delete_requested_at",
            "delete_requested_by", "delete_request_reason",
        ):
            assert name in cols, f"column {name!r} missing from calendar_events"

        for name in (
            "staff_notes", "completed_at", "delete_requested_at",
            "delete_requested_by", "delete_request_reason",
        ):
            assert cols[name]["is_nullable"] == "YES", f"{name} must be nullable"

        for name in ("staff_notes", "delete_request_reason"):
            assert cols[name]["udt_name"] == "text", f"{name} must be text type"

        for name in ("completed_at", "delete_requested_at"):
            assert cols[name]["udt_name"] == "timestamptz", (
                f"{name} must be TIMESTAMP WITH TIME ZONE (timestamptz)"
            )

        assert cols["delete_requested_by"]["udt_name"] == "uuid"

        fk_row = db.execute(text(
            "SELECT ref.relname AS ref_table, ref_a.attname AS ref_col, "
            "  CASE c.confdeltype "
            "    WHEN 'n' THEN 'SET NULL' "
            "    WHEN 'c' THEN 'CASCADE' "
            "    WHEN 'a' THEN 'NO ACTION' "
            "    WHEN 'r' THEN 'RESTRICT' "
            "  END AS delete_rule "
            "FROM pg_constraint c "
            "JOIN pg_class tbl ON tbl.oid = c.conrelid "
            "JOIN pg_class ref ON ref.oid = c.confrelid "
            "JOIN pg_namespace ns ON ns.oid = tbl.relnamespace "
            "JOIN pg_attribute a "
            "  ON a.attrelid = c.conrelid AND a.attnum = c.conkey[1] "
            "JOIN pg_attribute ref_a "
            "  ON ref_a.attrelid = c.confrelid AND ref_a.attnum = c.confkey[1] "
            "WHERE c.contype = 'f' "
            "  AND ns.nspname = 'public' "
            "  AND tbl.relname = 'calendar_events' "
            "  AND a.attname = 'delete_requested_by'"
        )).mappings().first()

        assert fk_row is not None, (
            "No FK found on calendar_events.delete_requested_by; "
            "migration b66b4394a869 should have created "
            "fk_calendar_events_delete_requested_by_users"
        )
        assert fk_row["ref_table"] == "users"
        assert fk_row["ref_col"] == "id"
        assert fk_row["delete_rule"] == "SET NULL", (
            "delete_requested_by FK must be ON DELETE SET NULL"
        )

