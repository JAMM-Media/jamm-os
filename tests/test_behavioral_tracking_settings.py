# tests/test_behavioral_tracking_settings.py

"""
Phase 7 behavioral event wiring: the four settings.py endpoints.

Two kinds of test live here.

Pinning tests (written against the router code BEFORE the writes moved into
firm_service, watched green there, then left unchanged across the move). They
read the firms row directly rather than trusting the endpoint's response,
because the response is shaped by the same code under test.

Event tests. Each endpoint now records firm.setting_changed through
behavioral_log.log_setting_changes, one event per key that actually changed.
log_event is patched at its home module, which is where log_setting_changes
resolves it, so a swallowed write cannot make these tests unable to fail.
"""

import json
from unittest.mock import patch

from sqlalchemy import text

from tests.conftest import TestingSessionLocal


def _read_firm(firm_id):
    db = TestingSessionLocal()
    try:
        row = db.execute(
            text(
                "SELECT settings::text, feature_flags::text, staff_auth_policy "
                "FROM firms WHERE id = CAST(:fid AS uuid)"
            ),
            {"fid": str(firm_id)},
        ).one()
    finally:
        db.close()
    settings = json.loads(row[0]) if row[0] is not None else None
    flags = json.loads(row[1]) if row[1] is not None else None
    return settings, flags, row[2]


def _seed_settings(firm_id, value):
    db = TestingSessionLocal()
    try:
        db.execute(
            text("UPDATE firms SET settings = CAST(:val AS json) WHERE id = CAST(:fid AS uuid)"),
            {"fid": str(firm_id), "val": json.dumps(value)},
        )
        db.commit()
    finally:
        db.close()
    assert _read_firm(firm_id)[0] == value, "seeded settings blob did not land"


def _setting_events(mock_log):
    return [
        c.kwargs for c in mock_log.call_args_list
        if c.kwargs.get("event_type") == "firm.setting_changed"
    ]


# ---------------------------------------------------------------------------
# Pinning tests: behavior of the four endpoints before the service move
# ---------------------------------------------------------------------------

def test_pin_review_refuses_non_https_url_with_400(client, firm_a_owner):
    _seed_settings(firm_a_owner["firm_id"], {"google_review_url": "https://keep.example"})

    r = client.patch(
        "/settings/review",
        json={"google_review_url": "http://insecure.example"},
        headers=firm_a_owner["headers"],
    )

    assert r.status_code == 400
    assert r.json()["detail"] == "google_review_url must start with 'https://'"
    settings, _, _ = _read_firm(firm_a_owner["firm_id"])
    assert settings["google_review_url"] == "https://keep.example"


def test_pin_review_writes_review_requests_enabled_into_feature_flags(client, firm_a_owner):
    r = client.patch(
        "/settings/review",
        json={"google_review_url": "https://r.example", "review_requests_enabled": True},
        headers=firm_a_owner["headers"],
    )

    assert r.status_code == 200, r.text
    settings, flags, _ = _read_firm(firm_a_owner["firm_id"])
    assert flags["review_requests_enabled"] is True
    assert "review_requests_enabled" not in settings


def test_pin_review_omitted_url_removes_the_key(client, firm_a_owner):
    _seed_settings(
        firm_a_owner["firm_id"],
        {"google_review_url": "https://old.example", "portal_display_name": "Keep"},
    )

    r = client.patch("/settings/review", json={}, headers=firm_a_owner["headers"])

    assert r.status_code == 200, r.text
    assert r.json() == {"portal_display_name": "Keep"}
    settings, _, _ = _read_firm(firm_a_owner["firm_id"])
    assert settings == {"portal_display_name": "Keep"}


def test_pin_email_omitted_fields_remove_their_keys(client, firm_a_owner):
    _seed_settings(
        firm_a_owner["firm_id"],
        {"email_reply_to": "old@example.com", "email_display_name": "Old", "other": 1},
    )

    r = client.patch("/settings/email", json={}, headers=firm_a_owner["headers"])

    assert r.status_code == 200, r.text
    assert r.json() == {"other": 1}
    settings, _, _ = _read_firm(firm_a_owner["firm_id"])
    assert settings == {"other": 1}


def test_pin_email_calendar_sync_writes_staff_keys_and_returns_firm(client, firm_a_owner):
    _seed_settings(firm_a_owner["firm_id"], {"email_sync_enabled": True})

    r = client.patch(
        "/settings/email-calendar-sync",
        json={"staff_can_disable_email_sync": True, "staff_can_disable_calendar_sync": False},
        headers=firm_a_owner["headers"],
    )

    assert r.status_code == 200, r.text
    body = r.json()
    assert body["id"] == firm_a_owner["firm_id"]
    settings, _, _ = _read_firm(firm_a_owner["firm_id"])
    assert settings == {
        "email_sync_enabled": True,
        "staff_can_disable_email_sync": True,
        "staff_can_disable_calendar_sync": False,
    }


# ---------------------------------------------------------------------------
# Event tests: firm.setting_changed from firm_service
# ---------------------------------------------------------------------------

def _owner_id(firm_id):
    db = TestingSessionLocal()
    try:
        return db.execute(
            text(
                "SELECT id FROM users WHERE firm_id = CAST(:fid AS uuid) "
                "AND role = 'firm_owner'"
            ),
            {"fid": str(firm_id)},
        ).scalar_one()
    finally:
        db.close()


def _assert_event_shape(event, firm_id, actor_id):
    assert event["entity_type"] == "firm"
    assert str(event["entity_id"]) == str(firm_id)
    assert str(event["firm_id"]) == str(firm_id)
    assert event["actor_type"] == "staff"
    assert event["actor_id"] == actor_id
    assert set(event["metadata"]) == {"setting_key", "from_value", "to_value"}


def test_staff_auth_policy_fires_setting_changed(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    _, _, before = _read_firm(firm_id)
    assert before != "password_only"

    with patch("app.services.behavioral_log.log_event") as mock_log:
        r = client.patch(
            "/settings/security/staff-auth-policy",
            json={"staff_auth_policy": "password_only"},
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 200, r.text
    events = _setting_events(mock_log)
    assert len(events) == 1
    _assert_event_shape(events[0], firm_id, _owner_id(firm_id))
    assert events[0]["metadata"] == {
        "setting_key": "staff_auth_policy",
        "from_value": before,
        "to_value": "password_only",
    }


def test_review_settings_fire_setting_changed_per_key(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    _seed_settings(firm_id, {})

    with patch("app.services.behavioral_log.log_event") as mock_log:
        r = client.patch(
            "/settings/review",
            json={"google_review_url": "https://r.example", "review_requests_enabled": True},
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 200, r.text
    events = _setting_events(mock_log)
    actor = _owner_id(firm_id)
    for event in events:
        _assert_event_shape(event, firm_id, actor)
    by_key = {e["metadata"]["setting_key"]: e["metadata"] for e in events}
    assert by_key == {
        "google_review_url": {
            "setting_key": "google_review_url",
            "from_value": None,
            "to_value": "https://r.example",
        },
        "feature_flags.review_requests_enabled": {
            "setting_key": "feature_flags.review_requests_enabled",
            "from_value": None,
            "to_value": True,
        },
    }


def test_email_calendar_sync_fires_setting_changed_for_changed_keys_only(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    _seed_settings(firm_id, {"calendar_sync_enabled": True})

    with patch("app.services.behavioral_log.log_event") as mock_log:
        r = client.patch(
            "/settings/email-calendar-sync",
            json={"email_sync_enabled": True, "calendar_sync_enabled": True},
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 200, r.text
    events = _setting_events(mock_log)
    assert len(events) == 1
    _assert_event_shape(events[0], firm_id, _owner_id(firm_id))
    assert events[0]["metadata"] == {
        "setting_key": "email_sync_enabled",
        "from_value": None,
        "to_value": True,
    }


def test_email_settings_fire_setting_changed(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    _seed_settings(firm_id, {"email_display_name": "Same"})

    with patch("app.services.behavioral_log.log_event") as mock_log:
        r = client.patch(
            "/settings/email",
            json={"reply_to": "replies@example.com", "display_name": "Same"},
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 200, r.text
    events = _setting_events(mock_log)
    assert len(events) == 1
    _assert_event_shape(events[0], firm_id, _owner_id(firm_id))
    assert events[0]["metadata"] == {
        "setting_key": "email_reply_to",
        "from_value": None,
        "to_value": "replies@example.com",
    }
