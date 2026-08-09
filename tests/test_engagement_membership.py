# tests/test_engagement_membership.py

"""
Engagement membership, and the two axes it creates.

Firm role answers what a person is ALLOWED TO DO. Engagement membership
answers WHOSE WORK an engagement is. These tests exist mostly to pin the
places where the two axes cross and neither one alone gives the answer: a
staff member promoted to administrator on one engagement who can then staff
it, a manager who can act on every engagement without appearing on any
member list, and an administrator whose authority stops dead at the edge of
their own engagement.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(firm_id, role, email_prefix):
    """Creates a user directly and returns (user_id, email, password)."""
    from app.core.enums import UserRole
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"{email_prefix}-{uuid.uuid4()}@firma.com"
    password = "memberpass123"

    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name=f"{email_prefix.title()} User",
            role=getattr(UserRole, role),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return str(user.id), email, password
    finally:
        db.close()


def _login(client, email, password):
    r = client.post("/auth/token", json={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _make_client_record(firm_id, name="Membership Test Client"):
    from app.models.client import Client

    db = TestingSessionLocal()
    try:
        record = Client(firm_id=firm_id, name=name, email=f"{uuid.uuid4()}@client.com")
        db.add(record)
        db.commit()
        db.refresh(record)
        return str(record.id)
    finally:
        db.close()


def _create_engagement(client, headers, client_id, name="Membership Engagement"):
    return client.post(
        "/engagements/",
        headers=headers,
        json={"name": name, "client_id": client_id},
    )


def _member_ids(client, headers, engagement_id):
    r = client.get(f"/engagements/{engagement_id}/members", headers=headers)
    assert r.status_code == 200, r.text
    return [m["user_id"] for m in r.json()["items"]]


@pytest.fixture
def firm_a_manager(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    user_id, email, password = _make_user(firm_id, "manager", "manager")
    return {
        "headers": _login(client, email, password),
        "firm_id": firm_id,
        "user_id": user_id,
    }


@pytest.fixture
def firm_a_staff_two(client, firm_a_owner):
    """A second staff user. firm_a_staff from conftest returns headers but not
    a user id, and several tests below need both."""
    firm_id = firm_a_owner["firm_id"]
    user_id, email, password = _make_user(firm_id, "staff", "staff2")
    return {
        "headers": _login(client, email, password),
        "firm_id": firm_id,
        "user_id": user_id,
    }


@pytest.fixture
def firm_a_staff_three(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    user_id, email, password = _make_user(firm_id, "staff", "staff3")
    return {
        "headers": _login(client, email, password),
        "firm_id": firm_id,
        "user_id": user_id,
    }


@pytest.fixture
def engagement_a(client, firm_a_owner):
    """An engagement in Firm A created by the firm owner, who is therefore
    its administrator."""
    firm_id = firm_a_owner["firm_id"]
    client_id = _make_client_record(firm_id)
    r = _create_engagement(client, firm_a_owner["headers"], client_id)
    assert r.status_code == 201, r.text
    return {"engagement_id": r.json()["id"], "client_id": client_id, "firm_id": firm_id}


# ---------------------------------------------------------------------------
# Engagement creation is restricted, and the creator becomes administrator
# ---------------------------------------------------------------------------

def test_staff_cannot_create_an_engagement(client, firm_a_owner, firm_a_staff):
    client_id = _make_client_record(firm_a_owner["firm_id"])
    r = _create_engagement(client, firm_a_staff["headers"], client_id)
    assert r.status_code == 403, r.text


def test_staff_cannot_bulk_create_engagements(client, firm_a_owner, firm_a_staff):
    """The bulk endpoint is engagement creation too. If it stayed open to
    staff the single-endpoint restriction would be one request away from
    meaningless."""
    client_id = _make_client_record(firm_a_owner["firm_id"])
    r = client.post(
        "/engagements/bulk-create",
        headers=firm_a_staff["headers"],
        json={"client_ids": [client_id], "name": "Bulk Engagement"},
    )
    assert r.status_code == 403, r.text


def test_manager_can_create_an_engagement(client, firm_a_owner, firm_a_manager):
    client_id = _make_client_record(firm_a_owner["firm_id"])
    r = _create_engagement(client, firm_a_manager["headers"], client_id)
    assert r.status_code == 201, r.text


def test_creator_becomes_administrator_of_the_engagement(client, firm_a_owner, firm_a_manager):
    client_id = _make_client_record(firm_a_owner["firm_id"])
    r = _create_engagement(client, firm_a_manager["headers"], client_id)
    assert r.status_code == 201, r.text
    engagement_id = r.json()["id"]

    members = client.get(
        f"/engagements/{engagement_id}/members", headers=firm_a_manager["headers"]
    ).json()["items"]

    assert len(members) == 1
    assert members[0]["user_id"] == firm_a_manager["user_id"]
    assert members[0]["is_administrator"] is True


# ---------------------------------------------------------------------------
# Adding and promoting
# ---------------------------------------------------------------------------

def test_administrator_can_add_a_member(client, firm_a_owner, engagement_a, firm_a_staff_two):
    r = client.post(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )
    assert r.status_code == 201, r.text
    assert r.json()["is_administrator"] is False
    assert r.json()["user_id"] == firm_a_staff_two["user_id"]


def test_administrator_can_promote_a_staff_member_to_administrator(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    added = client.post(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    ).json()

    r = client.patch(
        f"/engagements/{engagement_a['engagement_id']}/members/{added['id']}",
        headers=firm_a_owner["headers"],
        json={"is_administrator": True},
    )
    assert r.status_code == 200, r.text
    assert r.json()["is_administrator"] is True


def test_promoted_staff_member_can_then_add_members(
    client, firm_a_owner, engagement_a, firm_a_staff_two, firm_a_staff_three
):
    """The whole point of per-engagement administration: a senior staff member
    who genuinely runs the work can staff it, even though their firm role is
    staff and staff cannot even create an engagement."""
    engagement_id = engagement_a["engagement_id"]

    added = client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"], "is_administrator": True},
    )
    assert added.status_code == 201, added.text

    r = client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_staff_two["headers"],
        json={"user_id": firm_a_staff_three["user_id"]},
    )
    assert r.status_code == 201, r.text


def test_non_administrator_member_cannot_add_members(
    client, firm_a_owner, engagement_a, firm_a_staff_two, firm_a_staff_three
):
    engagement_id = engagement_a["engagement_id"]

    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )

    r = client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_staff_two["headers"],
        json={"user_id": firm_a_staff_three["user_id"]},
    )
    assert r.status_code == 403, r.text


def test_administrator_on_one_engagement_is_nobody_on_another(
    client, firm_a_owner, engagement_a, firm_a_staff_two, firm_a_staff_three
):
    """Administrator is per-engagement and carries nowhere else."""
    client.post(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"], "is_administrator": True},
    )

    other_client_id = _make_client_record(firm_a_owner["firm_id"], name="Other Client")
    other = _create_engagement(
        client, firm_a_owner["headers"], other_client_id, name="Other Engagement"
    ).json()

    r = client.post(
        f"/engagements/{other['id']}/members",
        headers=firm_a_staff_two["headers"],
        json={"user_id": firm_a_staff_three["user_id"]},
    )
    assert r.status_code == 403, r.text


def test_manager_can_add_without_being_a_member_and_does_not_join_the_list(
    client, firm_a_owner, engagement_a, firm_a_manager, firm_a_staff_two
):
    """Capability without membership. This is what keeps an engagement from
    ever being orphaned when its only administrator leaves."""
    engagement_id = engagement_a["engagement_id"]

    assert firm_a_manager["user_id"] not in _member_ids(
        client, firm_a_owner["headers"], engagement_id
    )

    r = client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_manager["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )
    assert r.status_code == 201, r.text

    ids_after = _member_ids(client, firm_a_owner["headers"], engagement_id)
    assert firm_a_staff_two["user_id"] in ids_after
    assert firm_a_manager["user_id"] not in ids_after


def test_a_user_appears_at_most_once_per_engagement(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    engagement_id = engagement_a["engagement_id"]
    body = {"user_id": firm_a_staff_two["user_id"]}

    assert client.post(
        f"/engagements/{engagement_id}/members", headers=firm_a_owner["headers"], json=body
    ).status_code == 201

    r = client.post(
        f"/engagements/{engagement_id}/members", headers=firm_a_owner["headers"], json=body
    )
    assert r.status_code == 409, r.text


def test_removing_the_only_administrator_is_allowed(client, firm_a_owner, engagement_a):
    """No minimum-administrator constraint. An engagement with no
    administrator is a Morning Briefing item, not a blocked request."""
    engagement_id = engagement_a["engagement_id"]
    members = client.get(
        f"/engagements/{engagement_id}/members", headers=firm_a_owner["headers"]
    ).json()["items"]
    assert len(members) == 1 and members[0]["is_administrator"] is True

    r = client.delete(
        f"/engagements/{engagement_id}/members/{members[0]['id']}",
        headers=firm_a_owner["headers"],
    )
    assert r.status_code == 204, r.text
    assert _member_ids(client, firm_a_owner["headers"], engagement_id) == []


def test_promotion_is_written_to_the_audit_log(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    from app.models.audit_log import AuditLog

    added = client.post(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    ).json()

    client.patch(
        f"/engagements/{engagement_a['engagement_id']}/members/{added['id']}",
        headers=firm_a_owner["headers"],
        json={"is_administrator": True},
    )

    db = TestingSessionLocal()
    try:
        entries = db.query(AuditLog).filter(
            AuditLog.firm_id == uuid.UUID(engagement_a["firm_id"]),
            AuditLog.action == "engagement_member.promoted",
        ).all()
        assert len(entries) == 1
        assert str(entries[0].entity_id) == added["id"]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Task assignment is scoped to members
# ---------------------------------------------------------------------------

def test_assigning_a_client_task_to_a_non_member_is_refused(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    r = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Reconcile Q3",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_a["engagement_id"],
            "assigned_to": firm_a_staff_two["user_id"],
        },
    )
    assert r.status_code == 422, r.text


def test_assigning_a_client_task_to_a_member_succeeds(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    client.post(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )

    r = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Reconcile Q3",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_a["engagement_id"],
            "assigned_to": firm_a_staff_two["user_id"],
        },
    )
    assert r.status_code == 201, r.text
    assert r.json()["assigned_to"] == firm_a_staff_two["user_id"]


def test_reassigning_an_existing_task_to_a_non_member_is_refused(
    client, firm_a_owner, engagement_a, firm_a_staff_two, firm_a_staff_three
):
    """Assignment scoping cannot only apply at creation, or the rule is one
    PATCH away from irrelevant."""
    engagement_id = engagement_a["engagement_id"]
    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )

    task = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Reconcile Q3",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_id,
            "assigned_to": firm_a_staff_two["user_id"],
        },
    ).json()

    r = client.patch(
        f"/tasks/{task['id']}",
        headers=firm_a_owner["headers"],
        json={"assigned_to": firm_a_staff_three["user_id"]},
    )
    assert r.status_code == 422, r.text


def test_bulk_reassignment_to_a_non_member_is_refused(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    task = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Reconcile Q3",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_a["engagement_id"],
        },
    ).json()

    r = client.patch(
        "/tasks/bulk",
        headers=firm_a_owner["headers"],
        json={"ids": [task["id"]], "update": {"assigned_to": firm_a_staff_two["user_id"]}},
    )
    assert r.status_code == 422, r.text


def test_a_member_of_the_engagement_can_create_tasks_for_it(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    """Anyone ON an engagement can create tasks for it, whatever their firm
    role. This staff user cannot create an engagement at all."""
    engagement_id = engagement_a["engagement_id"]
    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )

    r = client.post(
        "/tasks/",
        headers=firm_a_staff_two["headers"],
        json={
            "title": "Pull bank statements",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_id,
        },
    )
    assert r.status_code == 201, r.text


def test_a_non_member_staff_cannot_create_tasks_for_an_engagement(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    r = client.post(
        "/tasks/",
        headers=firm_a_staff_two["headers"],
        json={
            "title": "Pull bank statements",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_a["engagement_id"],
        },
    )
    assert r.status_code == 403, r.text


# ---------------------------------------------------------------------------
# Internal versus client tasks, and self-created tasks
# ---------------------------------------------------------------------------

def test_internal_task_needs_no_engagement(client, firm_a_owner, firm_a_staff_two):
    r = client.post(
        "/tasks/",
        headers=firm_a_staff_two["headers"],
        json={"title": "Update the WISP", "task_type": "internal"},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["task_type"] == "internal"
    assert body["engagement_id"] is None
    assert body["client_id"] is None


def test_internal_task_may_be_assigned_to_any_firm_user(
    client, firm_a_owner, firm_a_staff_two
):
    """No engagement means no member list to scope against, so the pool is
    every internal user of the firm."""
    r = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Update the WISP",
            "task_type": "internal",
            "assigned_to": firm_a_staff_two["user_id"],
        },
    )
    assert r.status_code == 201, r.text


def test_client_task_without_an_engagement_is_refused(client, firm_a_owner, engagement_a):
    r = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={"title": "Orphan", "task_type": "client", "client_id": engagement_a["client_id"]},
    )
    assert r.status_code == 422, r.text


def test_internal_task_carrying_an_engagement_is_refused(client, firm_a_owner, engagement_a):
    r = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Confused",
            "task_type": "internal",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_a["engagement_id"],
        },
    )
    assert r.status_code == 422, r.text


def test_self_created_task_is_distinguishable_from_an_assigned_one(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    engagement_id = engagement_a["engagement_id"]

    owner_members = client.get(
        f"/engagements/{engagement_id}/members", headers=firm_a_owner["headers"]
    ).json()["items"]
    owner_user_id = owner_members[0]["user_id"]

    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )

    self_created = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Mine",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_id,
            "assigned_to": owner_user_id,
        },
    ).json()

    assigned_out = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Theirs",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_id,
            "assigned_to": firm_a_staff_two["user_id"],
        },
    ).json()

    assert self_created["is_self_created"] is True
    assert assigned_out["is_self_created"] is False


def test_is_self_created_survives_a_later_reassignment(
    client, firm_a_owner, engagement_a, firm_a_staff_two
):
    """The reason this is a stored field and not a comparison done at read
    time: reassignment must not rewrite what the Employee Archive says about
    who originally took this on."""
    engagement_id = engagement_a["engagement_id"]
    owner_user_id = client.get(
        f"/engagements/{engagement_id}/members", headers=firm_a_owner["headers"]
    ).json()["items"][0]["user_id"]

    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )

    task = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Mine at first",
            "task_type": "client",
            "client_id": engagement_a["client_id"],
            "engagement_id": engagement_id,
            "assigned_to": owner_user_id,
        },
    ).json()
    assert task["is_self_created"] is True

    reassigned = client.patch(
        f"/tasks/{task['id']}",
        headers=firm_a_owner["headers"],
        json={"assigned_to": firm_a_staff_two["user_id"]},
    )
    assert reassigned.status_code == 200, reassigned.text
    assert reassigned.json()["is_self_created"] is True


# ---------------------------------------------------------------------------
# Tenant isolation, every new endpoint
# ---------------------------------------------------------------------------

def test_firm_b_cannot_list_firm_a_engagement_members(
    client, firm_a_owner, firm_b_owner, engagement_a
):
    r = client.get(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_b_owner["headers"],
    )
    assert r.status_code == 404, r.text


def test_firm_b_cannot_add_a_member_to_a_firm_a_engagement(
    client, firm_a_owner, firm_b_owner, engagement_a, firm_a_staff_two
):
    r = client.post(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_b_owner["headers"],
        json={"user_id": firm_a_staff_two["user_id"]},
    )
    assert r.status_code == 404, r.text


def test_firm_b_cannot_promote_a_firm_a_member(
    client, firm_a_owner, firm_b_owner, engagement_a
):
    member_id = client.get(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
    ).json()["items"][0]["id"]

    r = client.patch(
        f"/engagements/{engagement_a['engagement_id']}/members/{member_id}",
        headers=firm_b_owner["headers"],
        json={"is_administrator": False},
    )
    assert r.status_code == 404, r.text


def test_firm_b_cannot_remove_a_firm_a_member(
    client, firm_a_owner, firm_b_owner, engagement_a
):
    member_id = client.get(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
    ).json()["items"][0]["id"]

    r = client.delete(
        f"/engagements/{engagement_a['engagement_id']}/members/{member_id}",
        headers=firm_b_owner["headers"],
    )
    assert r.status_code == 404, r.text

    assert len(_member_ids(client, firm_a_owner["headers"], engagement_a["engagement_id"])) == 1


def test_a_user_from_another_firm_cannot_be_added_as_a_member(
    client, firm_a_owner, firm_b_owner, engagement_a
):
    """The cross-tenant direction that a path check alone would miss: a valid
    Firm A engagement, a valid Firm A actor, and a user_id belonging to
    Firm B in the body."""
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        firm_b_user = db.query(User).filter(
            User.firm_id == uuid.UUID(firm_b_owner["firm_id"])
        ).first()
        firm_b_user_id = str(firm_b_user.id)
    finally:
        db.close()

    r = client.post(
        f"/engagements/{engagement_a['engagement_id']}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": firm_b_user_id},
    )
    assert r.status_code == 404, r.text


def test_a_user_from_another_firm_cannot_be_assigned_a_task(
    client, firm_a_owner, firm_b_owner, engagement_a
):
    from app.models.user import User

    db = TestingSessionLocal()
    try:
        firm_b_user_id = str(
            db.query(User).filter(User.firm_id == uuid.UUID(firm_b_owner["firm_id"])).first().id
        )
    finally:
        db.close()

    r = client.post(
        "/tasks/",
        headers=firm_a_owner["headers"],
        json={
            "title": "Cross tenant",
            "task_type": "internal",
            "assigned_to": firm_b_user_id,
        },
    )
    assert r.status_code == 422, r.text
