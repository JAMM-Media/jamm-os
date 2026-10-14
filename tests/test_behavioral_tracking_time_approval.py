# tests/test_behavioral_tracking_time_approval.py

"""
Phase 7 behavioral event wiring: time entry submission, post-submission edits
and approval. All three writes already lived in time_entry_service; no router
logic moved. log_event is patched where time_entry_service resolves it.

The entry date is fixed rather than today: nothing here is date arithmetic,
and a fixed date keeps the tests off the wall clock.
"""

from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.conftest import TestingSessionLocal

TIME_LOG = "app.services.time_entry_service.log_event"
ENTRY_DATE = "2026-03-02"


def _owner_id(firm_id):
    db = TestingSessionLocal()
    try:
        return db.execute(
            text("SELECT id FROM users WHERE firm_id = CAST(:f AS uuid) AND role = 'firm_owner'"),
            {"f": str(firm_id)},
        ).scalar_one()
    finally:
        db.close()


def _events(mock_log, event_type):
    return [c.kwargs for c in mock_log.call_args_list if c.kwargs.get("event_type") == event_type]


@pytest.fixture
def engagement_id(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.post("/clients/", json={"name": "Time Events Client"}, headers=headers)
    assert r.status_code == 201, r.text
    r = client.post(
        "/engagements/",
        json={"name": "Time Events", "client_id": r.json()["id"]},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _entry(client, headers, engagement_id, hours="2.0", description="Research"):
    r = client.post(
        "/time-entries/",
        json={
            "engagement_id": engagement_id,
            "description": description,
            "hours": hours,
            "hourly_rate": "150.00",
            "is_billable": True,
            "date": ENTRY_DATE,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _submit(client, headers):
    r = client.post("/time-entries/submit-day", json={"date": ENTRY_DATE}, headers=headers)
    assert r.status_code == 200, r.text
    return r


def test_submit_day_fires_day_submitted(client, firm_a_owner, engagement_id):
    headers = firm_a_owner["headers"]
    _entry(client, headers, engagement_id, hours="2.0")
    _entry(client, headers, engagement_id, hours="1.5")
    owner = _owner_id(firm_a_owner["firm_id"])

    with patch(TIME_LOG) as mock_log:
        r = _submit(client, headers)

    assert r.json()["submitted_count"] == 2
    events = _events(mock_log, "time_entry.day_submitted")
    assert len(events) == 1
    e = events[0]
    assert str(e["firm_id"]) == firm_a_owner["firm_id"]
    assert e["entity_type"] == "user"
    assert e["entity_id"] == owner
    assert e["actor_id"] == owner
    assert e["metadata"] == {"entry_date": ENTRY_DATE, "entry_count": 2, "total_hours": 3.5}


def test_submitted_edit_fires_submitted_edited(client, firm_a_owner, engagement_id):
    """Calls the service directly with the manager notification write patched
    out. The HTTP route cannot be used: the notification it builds after the
    event omits the required tier field (NotificationCreate, required since
    237e036 on Sep 4, 2026), so the request fails after the edit commits. That
    defect is recorded as observed and out of Phase 7 scope; this test must not
    depend on it, and must not encode it as expected behavior either."""
    import uuid as _uuid

    from app.models.user import User
    from app.schemas.time_entry import SubmittedEditPayload
    from app.services import time_entry_service

    headers = firm_a_owner["headers"]
    entry_id = _entry(client, headers, engagement_id, hours="2.0", description="Research")
    _submit(client, headers)

    db = TestingSessionLocal()
    try:
        owner = db.get(User, _owner_id(firm_a_owner["firm_id"]))
        with patch(TIME_LOG) as mock_log, patch(
            "app.services.time_entry_service.NotificationCreate"
        ), patch(
            "app.services.time_entry_service.crud_notification.create_notification"
        ):
            result, error = time_entry_service.edit_submitted_entry(
                db=db,
                entry_id=_uuid.UUID(entry_id),
                payload=SubmittedEditPayload(hours="3.0", description="Research", edit_note="forgot a call"),
                firm_id=_uuid.UUID(firm_a_owner["firm_id"]),
                current_user=owner,
            )
    finally:
        db.close()

    assert error is None
    events = _events(mock_log, "time_entry.submitted_edited")
    assert len(events) == 1
    e = events[0]
    assert e["entity_type"] == "time_entry"
    assert str(e["entity_id"]) == entry_id
    assert e["actor_id"] == _owner_id(firm_a_owner["firm_id"])
    assert e["metadata"] == {
        "changed_fields": {"hours": {"from": "2.00", "to": "3.00"}},
        "has_edit_note": True,
        "engagement_id": engagement_id,
    }
    assert "forgot a call" not in str(e["metadata"])


def test_approve_fires_approved(client, firm_a_owner, engagement_id):
    headers = firm_a_owner["headers"]
    entry_id = _entry(client, headers, engagement_id, hours="2.0")
    _submit(client, headers)
    owner = _owner_id(firm_a_owner["firm_id"])

    with patch(TIME_LOG) as mock_log:
        r = client.post(f"/time-entries/{entry_id}/approve", headers=headers)

    assert r.status_code == 200, r.text
    events = _events(mock_log, "time_entry.approved")
    assert len(events) == 1
    e = events[0]
    assert e["entity_type"] == "time_entry"
    assert str(e["entity_id"]) == entry_id
    assert e["actor_id"] == owner
    assert e["metadata"] == {
        "hours": 2.0,
        "is_billable": True,
        "engagement_id": engagement_id,
        "entry_user_id": str(owner),
        "was_already_approved": False,
    }
