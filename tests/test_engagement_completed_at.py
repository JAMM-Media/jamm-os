# tests/test_engagement_completed_at.py

"""engagements.completed_at stamps on every transition into completed.

WHY THIS COLUMN EXISTS

work_unbilled needs to know when an engagement was finished. Before this column
that fact survived only as a status string plus an engagement.completed
behavioral event, and operational control flow is never allowed to read the
behavioral log. updated_at is no substitute: it moves on every write.

WHY ALL THREE PATHS ARE TESTED SEPARATELY

There are three ways an engagement reaches completed status, and they do not
share a code path: the single-engagement update, the bulk status update, and
the automation action. The first version of this work stamped only the first
one, which would have meant work_unbilled silently never firing for anything
completed in bulk or by a rule. Each path gets its own test so that adding a
fourth without stamping shows up as a gap rather than as silence.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.client import Client
from app.models.engagement import Engagement
from app.services.engagement_completion import stamp_completion_transition
from tests.conftest import TestingSessionLocal


def _make_engagement(db, firm_id, status="active"):
    client_row = Client(firm_id=firm_id, name="Completion Client", email=f"{uuid4().hex[:8]}@x.com")
    db.add(client_row)
    db.commit()
    db.refresh(client_row)

    engagement = Engagement(
        firm_id=firm_id,
        client_id=client_row.id,
        name="Completion Engagement",
        status=status,
    )
    db.add(engagement)
    db.commit()
    db.refresh(engagement)
    return engagement


def _reload(engagement_id):
    db = TestingSessionLocal()
    try:
        return db.execute(
            select(Engagement).where(Engagement.id == engagement_id)
        ).scalars().first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# The helper itself
# ---------------------------------------------------------------------------

def test_helper_stamps_only_the_transition_into_completed():
    engagement = Engagement(name="x", status="completed")

    assert stamp_completion_transition(engagement, "active", "completed") is True
    assert engagement.completed_at is not None


def test_helper_ignores_a_resave_of_an_already_completed_engagement():
    """completed_at keeps meaning when it was FIRST completed."""
    engagement = Engagement(name="x", status="completed")
    stamp_completion_transition(engagement, "active", "completed")
    first = engagement.completed_at

    assert stamp_completion_transition(engagement, "completed", "completed") is False
    assert engagement.completed_at == first


def test_helper_ignores_transitions_to_other_statuses():
    engagement = Engagement(name="x", status="in_review")
    assert stamp_completion_transition(engagement, "active", "in_review") is False
    assert engagement.completed_at is None


# ---------------------------------------------------------------------------
# Path 1: the single-engagement update endpoint
# ---------------------------------------------------------------------------

def test_single_engagement_update_stamps(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        engagement_id = _make_engagement(db, firm_id).id
    finally:
        db.close()

    response = client.patch(
        f"/engagements/{engagement_id}",
        headers=firm_a_owner["headers"],
        json={"status": "completed"},
    )
    assert response.status_code in (200, 202), response.text

    assert _reload(engagement_id).completed_at is not None


def test_reopening_does_not_clear_the_stamp(client, firm_a_owner):
    """By ruling. Readers pair completed_at with a current status check."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        engagement_id = _make_engagement(db, firm_id).id
    finally:
        db.close()

    client.patch(
        f"/engagements/{engagement_id}",
        headers=firm_a_owner["headers"],
        json={"status": "completed"},
    )
    stamped = _reload(engagement_id).completed_at
    assert stamped is not None

    client.patch(
        f"/engagements/{engagement_id}",
        headers=firm_a_owner["headers"],
        json={"status": "active"},
    )

    reopened = _reload(engagement_id)
    assert reopened.status == "active"
    assert reopened.completed_at == stamped, "reopening cleared the completion stamp"


# ---------------------------------------------------------------------------
# Path 2: the bulk status update
# ---------------------------------------------------------------------------

def test_bulk_update_stamps(firm_a_owner):
    from app.schemas.engagement import BulkEngagementFieldUpdate
    from app.services.engagement_service import bulk_update_engagements

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        first = _make_engagement(db, firm_id).id
        second = _make_engagement(db, firm_id).id

        bulk_update_engagements(
            db=db,
            ids=[first, second],
            update=BulkEngagementFieldUpdate(status="completed"),
            firm_id=firm_id,
        )
    finally:
        db.close()

    assert _reload(first).completed_at is not None, "bulk path did not stamp"
    assert _reload(second).completed_at is not None, "bulk path did not stamp"


# ---------------------------------------------------------------------------
# Path 3: the automation action
# ---------------------------------------------------------------------------

def test_automation_action_stamps(firm_a_owner):
    from app.services.automation_actions import _handle_update_engagement_status

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        engagement_id = _make_engagement(db, firm_id).id

        _handle_update_engagement_status(
            config={"new_status": "completed"},
            payload={"engagement_id": str(engagement_id), "firm_id": str(firm_id)},
            db=db,
        )
    finally:
        db.close()

    assert _reload(engagement_id).completed_at is not None, (
        "an automation rule completed an engagement without stamping it, so "
        "work_unbilled would never fire for it"
    )
