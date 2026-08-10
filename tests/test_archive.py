# tests/test_archive.py

import uuid
import pytest
from tests.conftest import TestingSessionLocal


def test_archive_tenant_isolation(client, firm_a_owner, firm_b_owner):
    """Firm A owner cannot see Firm B's completed tasks in the archive."""
    from app.models.client import Client
    from app.models.engagement import Engagement
    from app.models.task import Task
    from app.models.user import User
    from app.core.security import get_password_hash
    from app.core.enums import UserRole

    firm_b_id = firm_b_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        b_client = Client(firm_id=firm_b_id, name="Firm B Archive Client")
        db.add(b_client)
        db.commit()
        db.refresh(b_client)

        b_engagement = Engagement(
            firm_id=firm_b_id,
            client_id=b_client.id,
            name="Firm B Archive Engagement",
        )
        db.add(b_engagement)
        db.commit()
        db.refresh(b_engagement)

        b_user = User(
            firm_id=firm_b_id,
            email=f"staff-b-{uuid.uuid4()}@firmb.com",
            hashed_password=get_password_hash("pass"),
            full_name="Staff B",
            role=UserRole.staff,
        )
        db.add(b_user)
        db.commit()
        db.refresh(b_user)

        b_task = Task(
            firm_id=firm_b_id,
            client_id=b_client.id,
            engagement_id=b_engagement.id,
            assigned_to=b_user.id,
            title="Firm B Secret Completed Task",
            is_completed=True,
        )
        db.add(b_task)
        db.commit()
    finally:
        db.close()

    r = client.get("/archive/", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    titles = [item["task_title"] for item in r.json()["items"]]
    assert "Firm B Secret Completed Task" not in titles, (
        "Firm A should not see Firm B archived tasks"
    )
