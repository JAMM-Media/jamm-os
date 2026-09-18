# tests/test_engagement_administrator_field.py
"""
Guard tests for current_user_is_administrator on EngagementOut (Section 13 trio gate).

Tests:
  (a) A staff user who holds EngagementMember.is_administrator=True on a specific engagement
      receives current_user_is_administrator=true from GET /engagements/{id}, and
      succeeds (200) on POST /engagements/{id}/finalize despite holding only the staff role.
      Watched red by temporarily hardcoding is_admin=False in the endpoint.

  (b) A plain staff user with no membership row (or is_administrator=False) receives
      current_user_is_administrator=false and gets 422 from POST /engagements/{id}/finalize.
      This is a confirming regression test against assert_can_finalize_engagement's existing
      unmodified behavior -- it does not require a new watched-fail cycle.
"""

import uuid
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.models.engagement_member import EngagementMember
from app.models.user import User
from tests.conftest import TestingSessionLocal


def _create_user(firm_id: str, role: UserRole = UserRole.staff):
    email = f"user-{uuid.uuid4()}@test.com"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("testpass"),
            full_name="Test User",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        user_id = str(user.id)
    finally:
        db.close()
    return email, user_id


def _login(test_client, email):
    r = test_client.post("/auth/token", json={"username": email, "password": "testpass"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _add_member(firm_id: str, engagement_id: str, user_id: str, *, is_administrator: bool):
    db = TestingSessionLocal()
    try:
        member = EngagementMember(
            firm_id=uuid.UUID(firm_id),
            engagement_id=uuid.UUID(engagement_id),
            user_id=uuid.UUID(user_id),
            is_administrator=is_administrator,
        )
        db.add(member)
        db.commit()
    finally:
        db.close()


def _setup(test_client, firm_a_owner):
    """Create a client and engagement via HTTP, return ids."""
    headers = firm_a_owner["headers"]
    r = test_client.post("/clients/", json={"name": "Trio Test Client"}, headers=headers)
    assert r.status_code == 201, r.text
    client_id = r.json()["id"]
    r = test_client.post(
        "/engagements/",
        json={"name": "Trio Test Engagement", "client_id": client_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    return client_id, r.json()["id"]


# ---------------------------------------------------------------------------
# Test (a): is_administrator=True staff user
# ---------------------------------------------------------------------------

def test_administrator_staff_gets_true_field_and_can_finalize(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    _, eng_id = _setup(client, firm_a_owner)

    email, user_id = _create_user(firm_id, UserRole.staff)
    _add_member(firm_id, eng_id, user_id, is_administrator=True)
    headers = _login(client, email)

    r = client.get(f"/engagements/{eng_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["current_user_is_administrator"] is True, (
        f"Expected true, got: {r.json().get('current_user_is_administrator')}"
    )

    r = client.post(f"/engagements/{eng_id}/finalize", headers=headers)
    assert r.status_code == 200, f"Expected 200 from finalize, got {r.status_code}: {r.text}"


# ---------------------------------------------------------------------------
# Test (b): plain staff user with no membership -- confirming regression test,
# not a new watched-fail cycle. assert_can_finalize_engagement is untouched.
# ---------------------------------------------------------------------------

def test_non_administrator_staff_gets_false_field_and_cannot_finalize(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    _, eng_id = _setup(client, firm_a_owner)

    email, _ = _create_user(firm_id, UserRole.staff)
    headers = _login(client, email)

    r = client.get(f"/engagements/{eng_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["current_user_is_administrator"] is False, (
        f"Expected false, got: {r.json().get('current_user_is_administrator')}"
    )

    r = client.post(f"/engagements/{eng_id}/finalize", headers=headers)
    assert r.status_code == 422, f"Expected 422 from finalize, got {r.status_code}: {r.text}"
