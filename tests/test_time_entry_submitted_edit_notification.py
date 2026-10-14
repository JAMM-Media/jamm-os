# tests/test_time_entry_submitted_edit_notification.py

"""
PATCH /time-entries/{id}/submitted-edit notifies managers.

Regression guard for the defect found in Phase 7 (Oct 12, 2026): the manager
notification was built without the tier field that NotificationCreate has
required since 237e036 (Sep 4, 2026), so every call failed after the edit had
already committed and no manager was ever told. Nothing caught it because no
test had ever called this route. Tier is quiet, matching every other
manager-awareness notification (ruled Oct 13, 2026).

The entry date is fixed: nothing here is date arithmetic.
"""

import uuid

from sqlalchemy import text

from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.user import User
from tests.conftest import TestingSessionLocal

ENTRY_DATE = "2026-03-02"


def _make_manager(firm_id):
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=f"manager-{uuid.uuid4().hex[:8]}@firma.com",
            hashed_password=get_password_hash("managerpass123"),
            full_name="Manager A",
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def test_submitted_edit_returns_200_and_notifies_the_manager(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    manager_id = _make_manager(firm_a_owner["firm_id"])

    r = client.post("/clients/", json={"name": "Submitted Edit Client"}, headers=headers)
    assert r.status_code == 201, r.text
    r = client.post(
        "/engagements/",
        json={"name": "Submitted Edit", "client_id": r.json()["id"]},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    engagement_id = r.json()["id"]

    r = client.post(
        "/time-entries/",
        json={
            "engagement_id": engagement_id,
            "description": "Research",
            "hours": "2.0",
            "hourly_rate": "150.00",
            "is_billable": True,
            "date": ENTRY_DATE,
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    entry_id = r.json()["id"]
    r = client.post("/time-entries/submit-day", json={"date": ENTRY_DATE}, headers=headers)
    assert r.status_code == 200, r.text

    r = client.patch(
        f"/time-entries/{entry_id}/submitted-edit",
        json={"hours": "3.0", "edit_note": "forgot a call"},
        headers=headers,
    )

    assert r.status_code == 200, r.text
    assert r.json()["hours"] in ("3.00", "3.0", 3.0)

    db = TestingSessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT title, tier FROM notifications "
                "WHERE recipient_id = CAST(:m AS uuid) "
                "AND related_entity_id = CAST(:e AS uuid)"
            ),
            {"m": str(manager_id), "e": entry_id},
        ).all()
    finally:
        db.close()
    assert len(rows) == 1
    assert rows[0][0] == "Timesheet entry edited after submission"
    assert rows[0][1] == "quiet"
