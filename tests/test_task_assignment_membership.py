# tests/test_task_assignment_membership.py

"""
Membership on task assignment.

The rule: assignment never grants access beyond what the assigner could
already have granted by hand. Someone who can add members gets the auto-add,
because refusing them only means a trip to the member list and back. Someone
who cannot gets a refusal, and the engagement administrators get told so
somebody who can act, does.

The case worth reading twice is
test_engagement_administrator_who_is_only_staff_can_auto_add. Firm role and
engagement membership are independent axes, and that test is the one that
proves the auto-add follows the membership axis rather than the firm one.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_user(firm_id, role, email_prefix, domain="firma.com"):
    from app.core.enums import UserRole
    from app.core.security import get_password_hash
    from app.models.user import User

    email = f"{email_prefix}-{uuid.uuid4()}@{domain}"
    password = "assignpass123"

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


def _make_client_record(firm_id, name="Assignment Test Client"):
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


def _create_engagement(client, headers, client_id, name="Assignment Engagement"):
    r = client.post(
        "/engagements/",
        headers=headers,
        json={"name": name, "client_id": client_id},
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_task(client, headers, client_id, engagement_id, title="Reconcile Q3", assigned_to=None):
    body = {
        "title": title,
        "task_type": "client",
        "client_id": client_id,
        "engagement_id": engagement_id,
    }
    if assigned_to:
        body["assigned_to"] = assigned_to
    return client.post("/tasks/", headers=headers, json=body)


def _memberships(firm_id, engagement_id):
    """Reads memberships straight from the database rather than through the
    API, so a test asserting nothing was created cannot be fooled by an
    endpoint's own filtering."""
    from app.models.engagement_member import EngagementMember

    db = TestingSessionLocal()
    try:
        return db.query(EngagementMember).filter(
            EngagementMember.firm_id == uuid.UUID(str(firm_id)),
            EngagementMember.engagement_id == uuid.UUID(str(engagement_id)),
        ).all()
    finally:
        db.close()


def _notifications(firm_id, recipient_id=None):
    from app.models.notification import Notification

    db = TestingSessionLocal()
    try:
        q = db.query(Notification).filter(
            Notification.firm_id == uuid.UUID(str(firm_id)),
            Notification.title == "Task assignment refused",
        )
        if recipient_id:
            q = q.filter(Notification.recipient_id == uuid.UUID(str(recipient_id)))
        return q.all()
    finally:
        db.close()


def _audit_entries(firm_id, action):
    from app.models.audit_log import AuditLog

    db = TestingSessionLocal()
    try:
        return db.query(AuditLog).filter(
            AuditLog.firm_id == uuid.UUID(str(firm_id)),
            AuditLog.action == action,
        ).all()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def firm_a_manager(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    user_id, email, password = _make_user(firm_id, "manager", "manager")
    return {"headers": _login(client, email, password), "firm_id": firm_id, "user_id": user_id}


@pytest.fixture
def staff_target(client, firm_a_owner):
    """The person being assigned work. Never a member of anything to start."""
    firm_id = firm_a_owner["firm_id"]
    user_id, email, password = _make_user(firm_id, "staff", "target")
    return {"headers": _login(client, email, password), "firm_id": firm_id, "user_id": user_id}


@pytest.fixture
def staff_other(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    user_id, email, password = _make_user(firm_id, "staff", "other")
    return {"headers": _login(client, email, password), "firm_id": firm_id, "user_id": user_id}


@pytest.fixture
def engagement(client, firm_a_owner):
    """Created by the firm owner, who therefore becomes its administrator."""
    firm_id = firm_a_owner["firm_id"]
    client_id = _make_client_record(firm_id)
    return {
        "engagement_id": _create_engagement(client, firm_a_owner["headers"], client_id),
        "client_id": client_id,
        "firm_id": firm_id,
    }


# ---------------------------------------------------------------------------
# Auto-add, for assigners who already hold the authority
# ---------------------------------------------------------------------------

def test_manager_assigning_to_a_non_member_auto_adds_them(
    client, firm_a_owner, firm_a_manager, engagement, staff_target
):
    r = _create_task(
        client, firm_a_manager["headers"],
        engagement["client_id"], engagement["engagement_id"],
        assigned_to=staff_target["user_id"],
    )
    assert r.status_code == 201, r.text
    assert r.json()["assigned_to"] == staff_target["user_id"]

    members = _memberships(engagement["firm_id"], engagement["engagement_id"])
    target = [m for m in members if str(m.user_id) == staff_target["user_id"]]
    assert len(target) == 1, "expected exactly one membership for the assignee"


def test_auto_added_member_is_never_an_administrator(
    client, firm_a_owner, firm_a_manager, engagement, staff_target
):
    """Authority to place someone on an engagement is not authority to make
    them able to place others."""
    _create_task(
        client, firm_a_manager["headers"],
        engagement["client_id"], engagement["engagement_id"],
        assigned_to=staff_target["user_id"],
    )

    members = _memberships(engagement["firm_id"], engagement["engagement_id"])
    target = next(m for m in members if str(m.user_id) == staff_target["user_id"])
    assert target.is_administrator is False


def test_auto_add_writes_an_audit_entry_marked_via_task_assignment(
    client, firm_a_owner, firm_a_manager, engagement, staff_target
):
    """Membership is access to a client's tax data. An addition that leaves no
    trace is what makes a member list unexplainable later."""
    _create_task(
        client, firm_a_manager["headers"],
        engagement["client_id"], engagement["engagement_id"],
        assigned_to=staff_target["user_id"],
    )

    entries = _audit_entries(engagement["firm_id"], "engagement_member.added")
    matching = [
        e for e in entries
        if e.extra_metadata.get("user_id") == staff_target["user_id"]
        and e.extra_metadata.get("via") == "task_assignment"
    ]
    assert len(matching) == 1, f"expected one via=task_assignment entry, got {entries}"
    assert matching[0].extra_metadata["as_administrator"] is False
    assert str(matching[0].actor_id) == firm_a_manager["user_id"]


def test_engagement_administrator_who_is_only_staff_can_auto_add(
    client, firm_a_owner, engagement, staff_target, staff_other
):
    """The case proving membership authority and firm role are independent
    axes. staff_other holds the firm's lowest role and could not create an
    engagement at all, but as an administrator OF THIS ENGAGEMENT they can
    staff it, so the auto-add is theirs to make."""
    engagement_id = engagement["engagement_id"]

    added = client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": staff_other["user_id"], "is_administrator": True},
    )
    assert added.status_code == 201, added.text

    r = _create_task(
        client, staff_other["headers"],
        engagement["client_id"], engagement_id,
        assigned_to=staff_target["user_id"],
    )
    assert r.status_code == 201, r.text

    members = _memberships(engagement["firm_id"], engagement_id)
    target = next(m for m in members if str(m.user_id) == staff_target["user_id"])
    assert target.is_administrator is False


def test_assigning_to_an_existing_member_adds_no_second_membership(
    client, firm_a_owner, firm_a_manager, engagement, staff_target
):
    engagement_id = engagement["engagement_id"]
    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": staff_target["user_id"]},
    )

    before = len(_memberships(engagement["firm_id"], engagement_id))
    r = _create_task(
        client, firm_a_manager["headers"],
        engagement["client_id"], engagement_id,
        assigned_to=staff_target["user_id"],
    )
    assert r.status_code == 201, r.text
    assert len(_memberships(engagement["firm_id"], engagement_id)) == before


# ---------------------------------------------------------------------------
# Refusal, for assigners who do not
# ---------------------------------------------------------------------------

def test_staff_non_administrator_assigning_to_a_non_member_is_refused(
    client, firm_a_owner, engagement, staff_target, staff_other
):
    """staff_other is ON the engagement, so they may create tasks for it, but
    they are not an administrator of it, so they may not staff it."""
    engagement_id = engagement["engagement_id"]
    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": staff_other["user_id"]},
    )

    r = _create_task(
        client, staff_other["headers"],
        engagement["client_id"], engagement_id,
        assigned_to=staff_target["user_id"],
    )
    assert r.status_code == 422, r.text

    members = _memberships(engagement["firm_id"], engagement_id)
    assert not [m for m in members if str(m.user_id) == staff_target["user_id"]], \
        "a refused assignment must create no membership"


def test_refusal_notifies_the_engagement_administrators(
    client, firm_a_owner, engagement, staff_target, staff_other
):
    engagement_id = engagement["engagement_id"]
    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": staff_other["user_id"]},
    )

    _create_task(
        client, staff_other["headers"],
        engagement["client_id"], engagement_id,
        assigned_to=staff_target["user_id"],
    )

    # firm_a_owner created the engagement and is therefore its administrator.
    notes = _notifications(engagement["firm_id"])
    assert len(notes) == 1, f"expected exactly one notification, got {len(notes)}"
    assert str(notes[0].related_entity_id) == engagement_id


def test_refusal_with_zero_administrators_falls_back_to_firm_owner(
    client, firm_a_owner, engagement, staff_target, staff_other
):
    """An engagement with no administrator is a real state: remove_member
    deliberately allows removing the last one."""
    engagement_id = engagement["engagement_id"]

    members = client.get(
        f"/engagements/{engagement_id}/members", headers=firm_a_owner["headers"]
    ).json()["items"]
    for member in members:
        if member["is_administrator"]:
            removed = client.delete(
                f"/engagements/{engagement_id}/members/{member['id']}",
                headers=firm_a_owner["headers"],
            )
            assert removed.status_code in (200, 204), removed.text

    remaining = _memberships(engagement["firm_id"], engagement_id)
    assert not [m for m in remaining if m.is_administrator], "setup failed to clear administrators"

    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": staff_other["user_id"]},
    )

    r = _create_task(
        client, staff_other["headers"],
        engagement["client_id"], engagement_id,
        assigned_to=staff_target["user_id"],
    )
    assert r.status_code == 422, r.text

    # The firm owner is no longer an administrator of this engagement, so the
    # only way they receive this is through the firm_owner fallback.
    owner_notes = _notifications(engagement["firm_id"])
    assert len(owner_notes) == 1, f"expected the firm_owner fallback, got {len(owner_notes)}"


def test_deactivated_firm_owner_is_not_used_as_the_fallback(
    client, firm_a_owner, engagement, staff_target, staff_other
):
    """The fallback fires exactly when nobody else can catch the refusal, so a
    deactivated owner standing in as the sole recipient means the refusal
    reaches nobody. Here the only firm_owner is deactivated and a second,
    active one exists, so only the active one may be notified."""
    from app.models.user import User

    engagement_id = engagement["engagement_id"]
    firm_id = engagement["firm_id"]

    active_owner_id, _, _ = _make_user(firm_id, "firm_owner", "activeowner")

    members = client.get(
        f"/engagements/{engagement_id}/members", headers=firm_a_owner["headers"]
    ).json()["items"]
    for member in members:
        if member["is_administrator"]:
            client.delete(
                f"/engagements/{engagement_id}/members/{member['id']}",
                headers=firm_a_owner["headers"],
            )

    client.post(
        f"/engagements/{engagement_id}/members",
        headers=firm_a_owner["headers"],
        json={"user_id": staff_other["user_id"]},
    )

    # Deactivate the original owner only after the setup calls that needed it.
    db = TestingSessionLocal()
    try:
        original = db.query(User).filter(User.email == "owner@firma.com").one()
        original.is_active = False
        original_id = str(original.id)
        db.commit()
    finally:
        db.close()

    r = _create_task(
        client, staff_other["headers"],
        engagement["client_id"], engagement_id,
        assigned_to=staff_target["user_id"],
    )
    assert r.status_code == 422, r.text

    recipients = {str(n.recipient_id) for n in _notifications(firm_id)}
    assert recipients == {active_owner_id}, (
        "only the active firm owner should be notified, got "
        f"{recipients} (deactivated owner is {original_id})"
    )


# ---------------------------------------------------------------------------
# Bulk
# ---------------------------------------------------------------------------

def test_bulk_reassignment_auto_adds_across_every_engagement_and_reports_them(
    client, firm_a_owner, firm_a_manager, staff_target
):
    firm_id = firm_a_owner["firm_id"]
    client_id = _make_client_record(firm_id)
    engagement_one = _create_engagement(client, firm_a_owner["headers"], client_id, "Engagement One")
    engagement_two = _create_engagement(client, firm_a_owner["headers"], client_id, "Engagement Two")

    task_one = _create_task(client, firm_a_owner["headers"], client_id, engagement_one).json()
    task_two = _create_task(client, firm_a_owner["headers"], client_id, engagement_two).json()

    r = client.patch(
        "/tasks/bulk",
        headers=firm_a_manager["headers"],
        json={
            "ids": [task_one["id"], task_two["id"]],
            "update": {"assigned_to": staff_target["user_id"]},
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["updated"] == 2
    assert len(body["members_added"]) == 1
    assert body["members_added"][0]["user_id"] == staff_target["user_id"]
    assert sorted(body["members_added"][0]["engagement_ids"]) == sorted(
        [engagement_one, engagement_two]
    )

    for engagement_id in (engagement_one, engagement_two):
        members = _memberships(firm_id, engagement_id)
        assert [m for m in members if str(m.user_id) == staff_target["user_id"]]


def test_bulk_refusal_writes_nothing_and_adds_nobody(
    client, firm_a_owner, firm_a_manager, staff_target, monkeypatch
):
    """All or nothing. One refused task anywhere in the batch refuses the whole
    batch, including any auto-add that would otherwise have happened for the
    tasks evaluated before it.

    The bulk endpoint is gated require_manager_or_above, so can_manage_membership
    is true there in practice today and the refusal path cannot be reached
    through HTTP. The gate can change, and the code implements the rule anyway,
    so this drives the service directly to prove the two-pass ordering holds.
    """
    from fastapi import HTTPException

    import app.services.task_service as task_service
    from app.schemas.task import BulkTaskFieldUpdate

    firm_id = firm_a_owner["firm_id"]
    client_id = _make_client_record(firm_id)
    engagement_one = _create_engagement(client, firm_a_owner["headers"], client_id, "Engagement One")
    engagement_two = _create_engagement(client, firm_a_owner["headers"], client_id, "Engagement Two")

    task_one = _create_task(client, firm_a_owner["headers"], client_id, engagement_one).json()
    task_two = _create_task(client, firm_a_owner["headers"], client_id, engagement_two).json()

    # Refuse only the second engagement, so the first would already have been
    # auto-added if the implementation added as it went.
    real_check = task_service._check_assignable

    def _refuse_second(db, **kwargs):
        if str(kwargs.get("engagement_id")) == str(engagement_two):
            raise HTTPException(status_code=422, detail="refused for test")
        return real_check(db, **kwargs)

    monkeypatch.setattr(task_service, "_check_assignable", _refuse_second)

    db = TestingSessionLocal()
    try:
        with pytest.raises(HTTPException) as excinfo:
            task_service.bulk_update_tasks(
                db=db,
                ids=[uuid.UUID(task_one["id"]), uuid.UUID(task_two["id"])],
                update=BulkTaskFieldUpdate(assigned_to=uuid.UUID(staff_target["user_id"])),
                firm_id=uuid.UUID(firm_id),
                current_user_id=uuid.UUID(firm_a_manager["user_id"]),
            )
        assert excinfo.value.status_code == 422
    finally:
        db.close()

    for engagement_id in (engagement_one, engagement_two):
        members = _memberships(firm_id, engagement_id)
        assert not [m for m in members if str(m.user_id) == staff_target["user_id"]], \
            "a refused batch must add nobody, including on engagements evaluated first"

    fresh = client.get(f"/tasks/{task_one['id']}", headers=firm_a_owner["headers"]).json()
    assert fresh["assigned_to"] is None, "a refused batch must write no assignment"


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

def test_firm_a_cannot_auto_add_a_firm_b_user(
    client, firm_a_owner, firm_b_owner, engagement
):
    """The assignee is a real, valid user, just not of this firm. The auto-add
    must not become the way a user crosses the tenant boundary."""
    firm_b_user_id, _, _ = _make_user(firm_b_owner["firm_id"], "staff", "bstaff", domain="firmb.com")

    r = _create_task(
        client, firm_a_owner["headers"],
        engagement["client_id"], engagement["engagement_id"],
        assigned_to=firm_b_user_id,
    )
    assert r.status_code == 422, r.text

    members = _memberships(engagement["firm_id"], engagement["engagement_id"])
    assert not [m for m in members if str(m.user_id) == firm_b_user_id], \
        "a Firm B user must never land on a Firm A engagement"
