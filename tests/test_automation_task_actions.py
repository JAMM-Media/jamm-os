# tests/test_automation_task_actions.py

"""
The two automation task handlers, routed through the service layer.

Two defects are pinned here, and both were invisible before Phase G2:

1. Automation fired no behavioral events for the work it did. The dispatcher
   logged that a rule fired; nothing logged what the rule actually did.
2. The handlers returned strings such as "skipped: task not found" instead of
   raising, and the dispatcher only marks an action failed when it catches an
   exception. A skipped action was recorded as a success, so the execution log
   reported success for work that never happened.

The second is the purer instance of the recurring pattern in
How_We_Work_Process_Rules.md: nothing failed, so nothing was there to notice.
"""

import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(firm_id, role, email_prefix):
    from app.core.enums import UserRole
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"{email_prefix}-{uuid.uuid4()}@firma.com"

    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("automationpass123"),
            full_name=f"{email_prefix.title()} User",
            role=getattr(UserRole, role),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return str(user.id)
    finally:
        db.close()


def _make_client_record(firm_id):
    from app.models.client import Client

    db = TestingSessionLocal()
    try:
        record = Client(firm_id=firm_id, name="Automation Client", email=f"{uuid.uuid4()}@client.com")
        db.add(record)
        db.commit()
        db.refresh(record)
        return str(record.id)
    finally:
        db.close()


def _create_engagement(client, headers, client_id, name="Automation Engagement"):
    r = client.post(
        "/engagements/", headers=headers,
        json={"name": name, "client_id": client_id},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _events(firm_id, event_type):
    from app.models.behavioral_event import BehavioralEvent

    db = TestingSessionLocal()
    try:
        return db.query(BehavioralEvent).filter(
            BehavioralEvent.firm_id == uuid.UUID(str(firm_id)),
            BehavioralEvent.event_type == event_type,
        ).all()
    finally:
        db.close()


def _memberships(firm_id, engagement_id):
    from app.models.engagement_member import EngagementMember

    db = TestingSessionLocal()
    try:
        return db.query(EngagementMember).filter(
            EngagementMember.firm_id == uuid.UUID(str(firm_id)),
            EngagementMember.engagement_id == uuid.UUID(str(engagement_id)),
        ).all()
    finally:
        db.close()


def _refusal_notifications(firm_id):
    from app.models.notification import Notification

    db = TestingSessionLocal()
    try:
        return db.query(Notification).filter(
            Notification.firm_id == uuid.UUID(str(firm_id)),
            Notification.title == "Task assignment refused",
        ).all()
    finally:
        db.close()


@pytest.fixture
def setup(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    client_id = _make_client_record(firm_id)
    engagement_id = _create_engagement(client, firm_a_owner["headers"], client_id)
    return {
        "firm_id": firm_id,
        "client_id": client_id,
        "engagement_id": engagement_id,
        "headers": firm_a_owner["headers"],
    }


# ---------------------------------------------------------------------------
# C1: create_task fires a real behavioral event
# ---------------------------------------------------------------------------

def test_automation_created_task_fires_task_created_as_automation(setup):
    from app.services import automation_actions

    db = TestingSessionLocal()
    try:
        result = automation_actions.execute(
            action_type="create_task",
            config={"title": "Automated review", "due_days_from_now": 7},
            payload={
                "firm_id": setup["firm_id"],
                "engagement_id": setup["engagement_id"],
                "client_id": setup["client_id"],
            },
            db=db,
        )
    finally:
        db.close()

    assert "Automated review" in result

    events = _events(setup["firm_id"], "task.created")
    assert len(events) == 1, f"expected exactly one task.created event, got {len(events)}"
    event = events[0]
    assert event.actor_type == "automation"
    assert event.actor_id is None
    assert event.extra_metadata["created_by_automation"] is True
    assert event.extra_metadata["is_self_created"] is False


def test_automation_created_task_is_not_self_created(setup):
    """is_self_created is set once at creation and never recomputed. Automation
    is nobody, so it can never be the assignee it created the task for."""
    from app.models.task import Task
    from app.services import automation_actions

    db = TestingSessionLocal()
    try:
        automation_actions.execute(
            action_type="create_task",
            config={"title": "Automated review"},
            payload={
                "firm_id": setup["firm_id"],
                "engagement_id": setup["engagement_id"],
                "client_id": setup["client_id"],
            },
            db=db,
        )
    finally:
        db.close()

    db = TestingSessionLocal()
    try:
        task = db.query(Task).filter(Task.title == "Automated review").one()
        assert task.is_self_created is False
        assert task.task_type == "client"
        assert str(task.engagement_id) == setup["engagement_id"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# C3: failures raise instead of returning a skip string
# ---------------------------------------------------------------------------

def test_create_task_without_a_title_raises(setup):
    from app.services import automation_actions

    db = TestingSessionLocal()
    try:
        with pytest.raises(ValueError):
            automation_actions.execute(
                action_type="create_task",
                config={},
                payload={"firm_id": setup["firm_id"]},
                db=db,
            )
    finally:
        db.close()


def test_assign_task_with_a_missing_task_raises(setup):
    """This is the exact case that used to return
    'assign_task skipped: task not found' and be recorded as a success."""
    from fastapi import HTTPException

    from app.services import automation_actions

    user_id = _make_user(setup["firm_id"], "staff", "assignee")

    db = TestingSessionLocal()
    try:
        with pytest.raises(HTTPException) as excinfo:
            automation_actions.execute(
                action_type="assign_task",
                config={"task_id": str(uuid.uuid4()), "assign_to_user_id": user_id},
                payload={"firm_id": setup["firm_id"]},
                db=db,
            )
        assert excinfo.value.status_code == 404
    finally:
        db.close()


# ---------------------------------------------------------------------------
# C2: assignment through the service layer
# ---------------------------------------------------------------------------

def test_automation_assigning_to_an_existing_member_succeeds_and_fires_the_event(
    client, setup
):
    from app.services import automation_actions

    user_id = _make_user(setup["firm_id"], "staff", "member")
    added = client.post(
        f"/engagements/{setup['engagement_id']}/members",
        headers=setup["headers"],
        json={"user_id": user_id},
    )
    assert added.status_code == 201, added.text

    task = client.post(
        "/tasks/", headers=setup["headers"],
        json={
            "title": "Needs an owner",
            "task_type": "client",
            "client_id": setup["client_id"],
            "engagement_id": setup["engagement_id"],
        },
    ).json()

    db = TestingSessionLocal()
    try:
        automation_actions.execute(
            action_type="assign_task",
            config={"task_id": task["id"], "assign_to_user_id": user_id},
            payload={"firm_id": setup["firm_id"]},
            db=db,
        )
    finally:
        db.close()

    fresh = client.get(f"/tasks/{task['id']}", headers=setup["headers"]).json()
    assert fresh["assigned_to"] == user_id

    events = _events(setup["firm_id"], "task.assigned")
    assert len(events) == 1, f"expected one task.assigned event, got {len(events)}"
    assert events[0].actor_type == "automation"
    assert events[0].actor_id is None


def test_automation_assigning_to_a_non_member_is_refused_and_notifies(client, setup):
    """Automation never carries add-member authority, because a rule has no
    created_by column and therefore no actor whose authority could be checked.
    So this refuses rather than auto-adding, unlike the human path."""
    from fastapi import HTTPException

    from app.services import automation_actions

    non_member_id = _make_user(setup["firm_id"], "staff", "outsider")

    task = client.post(
        "/tasks/", headers=setup["headers"],
        json={
            "title": "Needs an owner",
            "task_type": "client",
            "client_id": setup["client_id"],
            "engagement_id": setup["engagement_id"],
        },
    ).json()

    db = TestingSessionLocal()
    try:
        with pytest.raises(HTTPException) as excinfo:
            automation_actions.execute(
                action_type="assign_task",
                config={"task_id": task["id"], "assign_to_user_id": non_member_id},
                payload={"firm_id": setup["firm_id"]},
                db=db,
            )
        assert excinfo.value.status_code == 422
    finally:
        db.close()

    members = _memberships(setup["firm_id"], setup["engagement_id"])
    assert not [m for m in members if str(m.user_id) == non_member_id], \
        "automation must never auto-add"

    assert len(_refusal_notifications(setup["firm_id"])) == 1

    fresh = client.get(f"/tasks/{task['id']}", headers=setup["headers"]).json()
    assert fresh["assigned_to"] is None


# ---------------------------------------------------------------------------
# C3, end to end: the execution log stops reporting success for work that
# did not happen
# ---------------------------------------------------------------------------

def _make_rule(firm_id, actions, trigger_event):
    from app.models.automation_rule import AutomationRule

    db = TestingSessionLocal()
    try:
        rule = AutomationRule(
            firm_id=uuid.UUID(str(firm_id)),
            name="Assign on engagement created",
            trigger_event=trigger_event,
            trigger_conditions=[],
            actions=actions,
            is_enabled=True,
        )
        db.add(rule)
        db.commit()
        db.refresh(rule)
        return str(rule.id)
    finally:
        db.close()


def _execution_logs(firm_id):
    from app.models.automation_rule import AutomationExecutionLog

    db = TestingSessionLocal()
    try:
        return db.query(AutomationExecutionLog).filter(
            AutomationExecutionLog.firm_id == uuid.UUID(str(firm_id)),
        ).all()
    finally:
        db.close()


def test_execution_log_records_failure_when_the_assignment_is_refused(client, setup):
    """The whole point of C3. Before this, the dispatcher caught nothing, the
    action was recorded as a success, and the rule logged automation.fired for
    an assignment that never happened."""
    from app.core.enums import TriggerEvent
    from app.services import automation_dispatcher

    non_member_id = _make_user(setup["firm_id"], "staff", "outsider")

    task = client.post(
        "/tasks/", headers=setup["headers"],
        json={
            "title": "Needs an owner",
            "task_type": "client",
            "client_id": setup["client_id"],
            "engagement_id": setup["engagement_id"],
        },
    ).json()

    _make_rule(
        setup["firm_id"],
        actions=[{
            "type": "assign_task",
            "order": 0,
            "config": {"task_id": task["id"], "assign_to_user_id": non_member_id},
        }],
        trigger_event=TriggerEvent.engagement_created,
    )

    db = TestingSessionLocal()
    try:
        automation_dispatcher._dispatch_with_db(
            TriggerEvent.engagement_created,
            {"firm_id": setup["firm_id"], "engagement_id": setup["engagement_id"]},
            db,
        )
    finally:
        db.close()

    logs = _execution_logs(setup["firm_id"])
    assert len(logs) == 1, f"expected one execution log, got {len(logs)}"
    assert str(logs[0].status).endswith("failed"), \
        f"a refused assignment must not be logged as success, got {logs[0].status}"
    assert logs[0].actions_executed[0]["status"] == "failed"

    fired = _events(setup["firm_id"], "automation.fired")
    assert not fired, "automation.fired must not be logged for a failed action"
    assert len(_events(setup["firm_id"], "automation.failed")) == 1
