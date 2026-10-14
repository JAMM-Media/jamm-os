# tests/test_behavioral_tracking_staff.py

"""
Phase 7 behavioral event wiring: staff joins and hard deletions
(POST and DELETE /users/).

Pinning tests were written against the router-to-crud code BEFORE the writes
moved into user_service, watched green there, and left unchanged across the
move. They read the users table directly.

Payload law: user ids and role only. The new user's password, and its hash,
never appear in an event.
"""

import uuid
from unittest.mock import patch

from sqlalchemy import text

from tests.conftest import TestingSessionLocal


def _user_row(email):
    db = TestingSessionLocal()
    try:
        row = db.execute(
            text("SELECT id, firm_id, role FROM users WHERE email = :e"), {"e": email}
        ).one_or_none()
    finally:
        db.close()
    return row


def _create(client, headers, email, **extra):
    body = {"email": email, "password": "staffpass123", "full_name": "New Staff", "role": "staff"}
    body.update(extra)
    return client.post("/users/", json=body, headers=headers)


# ---------------------------------------------------------------------------
# Pinning tests: behavior before the service move
# ---------------------------------------------------------------------------

def test_pin_create_user_duplicate_email_is_400(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    assert _create(client, headers, "dup@firma.com").status_code == 201

    r = _create(client, headers, "dup@firma.com")

    assert r.status_code == 400
    assert r.json()["detail"] == "Email already registered"


def test_pin_create_user_ignores_firm_id_in_body(client, firm_a_owner, firm_b_owner):
    r = _create(client, firm_a_owner["headers"], "inject@firma.com", firm_id=firm_b_owner["firm_id"])

    assert r.status_code == 201, r.text
    row = _user_row("inject@firma.com")
    assert str(row[1]) == firm_a_owner["firm_id"]


def test_pin_delete_user_is_204_and_row_is_gone(client, firm_a_owner):
    r = _create(client, firm_a_owner["headers"], "gone@firma.com")
    user_id = r.json()["id"]

    r = client.delete(f"/users/{user_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 204
    assert _user_row("gone@firma.com") is None


def test_pin_delete_other_firms_user_is_404_and_row_survives(client, firm_a_owner, firm_b_owner):
    r = _create(client, firm_b_owner["headers"], "keep@firmb.com")
    user_id = r.json()["id"]

    r = client.delete(f"/users/{user_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 404
    assert r.json()["detail"] == "User not found"
    assert _user_row("keep@firmb.com") is not None


def test_pin_delete_missing_user_is_404(client, firm_a_owner):
    r = client.delete(f"/users/{uuid.uuid4()}", headers=firm_a_owner["headers"])
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Event tests: user.created / user.deleted from user_service
# ---------------------------------------------------------------------------

USER_LOG = "app.services.user_service.log_event"


def _events(mock_log, event_type):
    return [c.kwargs for c in mock_log.call_args_list if c.kwargs.get("event_type") == event_type]


def test_create_user_fires_user_created(client, firm_a_owner):
    with patch(USER_LOG) as mock_log:
        r = _create(client, firm_a_owner["headers"], "joined@firma.com", role="manager")

    assert r.status_code == 201, r.text
    events = _events(mock_log, "user.created")
    assert len(events) == 1
    e = events[0]
    assert str(e["firm_id"]) == firm_a_owner["firm_id"]
    assert e["entity_type"] == "user"
    assert str(e["entity_id"]) == r.json()["id"]
    assert e["actor_type"] == "staff"
    assert e["actor_id"] == _user_row("owner@firma.com")[0]
    assert e["metadata"] == {"role": "manager", "is_active": True}
    assert "staffpass123" not in str(e)


def test_delete_user_fires_user_deleted(client, firm_a_owner):
    user_id = _create(client, firm_a_owner["headers"], "leaving@firma.com").json()["id"]

    with patch(USER_LOG) as mock_log:
        r = client.delete(f"/users/{user_id}", headers=firm_a_owner["headers"])

    assert r.status_code == 204
    events = _events(mock_log, "user.deleted")
    assert len(events) == 1
    e = events[0]
    assert str(e["entity_id"]) == user_id
    assert e["actor_id"] == _user_row("owner@firma.com")[0]
    assert e["metadata"] == {"role": "staff"}
