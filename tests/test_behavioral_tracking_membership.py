# tests/test_behavioral_tracking_membership.py

"""
Phase 7 behavioral event wiring: engagement membership.

engagement_member.added fires from both add paths (via "manual" and via
"task_assignment"), and never .promoted on an add, even when the member goes
straight in as an administrator: as_administrator carries that fact.
.promoted and .demoted fire from update_member only. Ruled Oct 12, 2026.

log_event is patched where engagement_member_service resolves it.
"""

import uuid
from unittest.mock import patch

import pytest
from sqlalchemy import text

from tests.conftest import TestingSessionLocal

MEMBER_LOG = "app.services.engagement_member_service.log_event"


def _make_staff(firm_id):
    from app.core.enums import UserRole
    from app.core.security import get_password_hash
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"member-{uuid.uuid4()}@firma.com",
            hashed_password=get_password_hash("memberpass123"),
            full_name="Member Staff",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return str(user.id)
    finally:
        db.close()


def _owner_id(firm_id):
    db = TestingSessionLocal()
    try:
        return db.execute(
            text("SELECT id FROM users WHERE firm_id = CAST(:f AS uuid) AND role = 'firm_owner'"),
            {"f": str(firm_id)},
        ).scalar_one()
    finally:
        db.close()


def _events(mock_log, prefix="engagement_member."):
    return [
        c.kwargs for c in mock_log.call_args_list
        if str(c.kwargs.get("event_type", "")).startswith(prefix)
    ]


@pytest.fixture
def engagement(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    r = client.post("/clients/", json={"name": "Membership Events Client"}, headers=firm_a_owner["headers"])
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]
    r = client.post(
        "/engagements/",
        json={"name": "Membership Events", "client_id": client_id},
        headers=firm_a_owner["headers"],
    )
    assert r.status_code == 201, r.text
    return {"engagement_id": r.json()["id"], "client_id": client_id, "firm_id": firm_id}


def _add(client, headers, engagement_id, user_id, is_administrator=False):
    r = client.post(
        f"/engagements/{engagement_id}/members",
        json={"user_id": user_id, "is_administrator": is_administrator},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_manual_add_fires_added(client, firm_a_owner, engagement):
    staff_id = _make_staff(engagement["firm_id"])

    with patch(MEMBER_LOG) as mock_log:
        member = _add(client, firm_a_owner["headers"], engagement["engagement_id"], staff_id)

    events = _events(mock_log)
    assert [e["event_type"] for e in events] == ["engagement_member.added"]
    e = events[0]
    assert str(e["firm_id"]) == engagement["firm_id"]
    assert e["entity_type"] == "engagement_member"
    assert str(e["entity_id"]) == member["id"]
    assert e["actor_id"] == _owner_id(engagement["firm_id"])
    assert e["metadata"] == {
        "engagement_id": engagement["engagement_id"],
        "user_id": staff_id,
        "as_administrator": False,
        "via": "manual",
    }


def test_add_as_administrator_fires_added_only_never_promoted(client, firm_a_owner, engagement):
    staff_id = _make_staff(engagement["firm_id"])

    with patch(MEMBER_LOG) as mock_log:
        _add(client, firm_a_owner["headers"], engagement["engagement_id"], staff_id, is_administrator=True)

    events = _events(mock_log)
    assert [e["event_type"] for e in events] == ["engagement_member.added"]
    assert events[0]["metadata"]["as_administrator"] is True


def test_task_assignment_add_fires_added_via_task_assignment(client, firm_a_owner, engagement):
    staff_id = _make_staff(engagement["firm_id"])

    with patch(MEMBER_LOG) as mock_log:
        r = client.post(
            "/tasks/",
            json={
                "title": "Reconcile Q3",
                "task_type": "client",
                "client_id": engagement["client_id"],
                "engagement_id": engagement["engagement_id"],
                "assigned_to": staff_id,
            },
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 201, r.text
    events = _events(mock_log)
    assert [e["event_type"] for e in events] == ["engagement_member.added"]
    e = events[0]
    assert e["actor_id"] == _owner_id(engagement["firm_id"])
    assert e["metadata"] == {
        "engagement_id": engagement["engagement_id"],
        "user_id": staff_id,
        "as_administrator": False,
        "via": "task_assignment",
    }


def test_promotion_fires_promoted(client, firm_a_owner, engagement):
    staff_id = _make_staff(engagement["firm_id"])
    member = _add(client, firm_a_owner["headers"], engagement["engagement_id"], staff_id)

    with patch(MEMBER_LOG) as mock_log:
        r = client.patch(
            f"/engagements/{engagement['engagement_id']}/members/{member['id']}",
            json={"is_administrator": True},
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 200, r.text
    events = _events(mock_log)
    assert [e["event_type"] for e in events] == ["engagement_member.promoted"]
    e = events[0]
    assert str(e["entity_id"]) == member["id"]
    assert e["actor_id"] == _owner_id(engagement["firm_id"])
    assert e["metadata"] == {
        "engagement_id": engagement["engagement_id"],
        "user_id": staff_id,
        "is_administrator": True,
    }


def test_demotion_fires_demoted(client, firm_a_owner, engagement):
    staff_id = _make_staff(engagement["firm_id"])
    member = _add(client, firm_a_owner["headers"], engagement["engagement_id"], staff_id, is_administrator=True)

    with patch(MEMBER_LOG) as mock_log:
        r = client.patch(
            f"/engagements/{engagement['engagement_id']}/members/{member['id']}",
            json={"is_administrator": False},
            headers=firm_a_owner["headers"],
        )

    assert r.status_code == 200, r.text
    events = _events(mock_log)
    assert [e["event_type"] for e in events] == ["engagement_member.demoted"]
    assert events[0]["metadata"] == {
        "engagement_id": engagement["engagement_id"],
        "user_id": staff_id,
        "is_administrator": False,
    }


def test_removal_fires_removed(client, firm_a_owner, engagement):
    staff_id = _make_staff(engagement["firm_id"])
    member = _add(client, firm_a_owner["headers"], engagement["engagement_id"], staff_id, is_administrator=True)

    with patch(MEMBER_LOG) as mock_log:
        r = client.delete(
            f"/engagements/{engagement['engagement_id']}/members/{member['id']}",
            headers=firm_a_owner["headers"],
        )

    assert r.status_code in (200, 204), r.text
    events = _events(mock_log)
    assert [e["event_type"] for e in events] == ["engagement_member.removed"]
    e = events[0]
    assert str(e["entity_id"]) == member["id"]
    assert e["actor_id"] == _owner_id(engagement["firm_id"])
    assert e["metadata"] == {
        "engagement_id": engagement["engagement_id"],
        "user_id": staff_id,
        "was_administrator": True,
    }
