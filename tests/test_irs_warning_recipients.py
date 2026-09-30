# tests/test_irs_warning_recipients.py

"""
IRS expiry warnings record who they reached, one row per recipient per tier.

Ruled Sep 22 and Sep 24, 2026. Before this, irs_authorization_warnings held
one row per tier and no recipient at all, so "who was warned" could only be
answered by re-resolving current firm membership, which answers a different
question.

Two records are written, on purpose:

  - the rows, which are the control gate the sweep reads to decide whether a
    tier has fired, and which are deleted when valid_until changes;
  - the irs_authorization.expiry_warning_sent event, which is append-only and
    survives that deletion, and which carries recipient_user_ids (delivered
    in-app) and emailed_user_ids.

Ladder mechanics and tier selection live in test_irs_auth_expiry_ladder.py.
The read path lives in test_irs_auth_warning_ladder_endpoint.py. This file is
about recipients.

log_event runs synchronously under JAMM_TESTING=1 (see behavioral_log), which
is what makes reading behavioral_events straight after a sweep deterministic
rather than a race with a daemon thread.
"""

import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import select

from tests.conftest import TestingSessionLocal


def _cutoff():
    from app.crud.irs_authorization import compute_expiry_cutoff_date
    return compute_expiry_cutoff_date()


def _mk_client(db, firm_id, name="Recipient Test Client"):
    from app.models.client import Client
    c = Client(firm_id=uuid.UUID(firm_id), name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _mk_auth(db, firm_id, client_id, valid_until, form_type="8821", status="active"):
    from app.models.irs_authorization import IrsAuthorization
    a = IrsAuthorization(
        firm_id=uuid.UUID(firm_id), client_id=client_id, form_type=form_type,
        status=status, tax_years=[2024], valid_until=valid_until,
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _mk_user(db, firm_id, email, role):
    from app.models.user import User
    from app.core.security import get_password_hash
    u = User(
        firm_id=uuid.UUID(firm_id), email=email,
        hashed_password=get_password_hash("password123"),
        full_name=email.split("@")[0], role=role,
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _owner(db, firm_id):
    from app.models.user import User
    from app.core.enums import UserRole
    return db.execute(
        select(User).where(
            User.firm_id == uuid.UUID(firm_id),
            User.role == UserRole.firm_owner,
        )
    ).scalars().first()


def _run_sweep():
    from app.services.irs_auth_service import check_expiring_authorizations
    with patch("app.db.session.SessionLocal", TestingSessionLocal):
        return check_expiring_authorizations()


def _warning_rows(db, auth_id):
    from app.models.irs_authorization_warning import IrsAuthorizationWarning
    return db.execute(
        select(IrsAuthorizationWarning)
        .where(IrsAuthorizationWarning.authorization_id == auth_id)
        .order_by(IrsAuthorizationWarning.threshold_days)
    ).scalars().all()


def _warning_events(db, firm_id, auth_id):
    from app.models.behavioral_event import BehavioralEvent
    return db.execute(
        select(BehavioralEvent)
        .where(
            BehavioralEvent.firm_id == uuid.UUID(firm_id),
            BehavioralEvent.event_type == "irs_authorization.expiry_warning_sent",
            BehavioralEvent.entity_id == auth_id,
        )
        .order_by(BehavioralEvent.occurred_at)
    ).scalars().all()


# --- what one tier records -------------------------------------------------

def test_owner_and_manager_produce_two_rows_and_one_event(firm_a_owner):
    """One tier, two recipients, two rows, one event naming both.

    The event fires once per tier however many people it reached, because the
    thing that happened once is the tier firing.
    """
    from app.core.enums import UserRole

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = _owner(db, firm_id)
        manager = _mk_user(db, firm_id, f"mgr-{uuid.uuid4().hex[:8]}@firma.com", UserRole.manager)

        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        _run_sweep()
        db.expire_all()

        rows = _warning_rows(db, auth.id)
        assert len(rows) == 2, "one row per recipient per tier"
        assert {r.threshold_days for r in rows} == {30}
        assert {r.recipient_user_id for r in rows} == {owner.id, manager.id}
        assert len({r.sent_at for r in rows}) == 1, "one send, one timestamp"

        events = _warning_events(db, firm_id, auth.id)
        assert len(events) == 1, "one event per tier, not one per recipient"
        recorded = set(events[0].extra_metadata["recipient_user_ids"])
        assert recorded == {str(owner.id), str(manager.id)}
        assert events[0].extra_metadata["warning_tier"] == 30
        assert set(events[0].extra_metadata["emailed_user_ids"]) <= recorded
    finally:
        db.close()


def test_rerunning_the_sweep_adds_no_rows_and_no_event(firm_a_owner):
    """Fired-once means any row exists for the tier, not one row."""
    from app.core.enums import UserRole

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        _mk_user(db, firm_id, f"mgr-{uuid.uuid4().hex[:8]}@firma.com", UserRole.manager)
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        _run_sweep()
        db.expire_all()
        rows_after_first = [(r.id, r.recipient_user_id, r.sent_at) for r in _warning_rows(db, auth.id)]
        assert len(rows_after_first) == 2

        for _ in range(2):
            _run_sweep()
        db.expire_all()

        rows_after_reruns = [(r.id, r.recipient_user_id, r.sent_at) for r in _warning_rows(db, auth.id)]
        assert rows_after_reruns == rows_after_first, "reruns must not add or rewrite rows"
        assert len(_warning_events(db, firm_id, auth.id)) == 1
    finally:
        db.close()


def test_a_recipient_with_no_in_app_record_gets_no_row(firm_a_owner):
    """create_notification returning None means nothing landed for that person.

    They get no row and they are absent from the event, while the recipient who
    did receive one is recorded normally. A row must mean a warning was
    actually delivered to that recipient.
    """
    from app.core.enums import UserRole
    from app.services.notification_service import NotificationService

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = _owner(db, firm_id)
        manager = _mk_user(db, firm_id, f"mgr-{uuid.uuid4().hex[:8]}@firma.com", UserRole.manager)

        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        real_create = NotificationService.create_notification

        def only_the_owner(*args, **kwargs):
            if kwargs.get("recipient_id") == manager.id:
                return None
            return real_create(*args, **kwargs)

        with patch(
            "app.services.notification_service.NotificationService.create_notification",
            side_effect=only_the_owner,
        ):
            _run_sweep()
        db.expire_all()

        rows = _warning_rows(db, auth.id)
        assert [r.recipient_user_id for r in rows] == [owner.id]

        events = _warning_events(db, firm_id, auth.id)
        assert len(events) == 1
        assert events[0].extra_metadata["recipient_user_ids"] == [str(owner.id)]
        assert str(manager.id) not in events[0].extra_metadata["recipient_user_ids"]
    finally:
        db.close()


# --- what the constraint permits -------------------------------------------

def test_duplicate_recipient_on_one_tier_is_refused(firm_a_owner):
    """The same person cannot be recorded twice for the same tier."""
    from sqlalchemy.exc import IntegrityError
    from app.models.irs_authorization_warning import IrsAuthorizationWarning

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = _owner(db, firm_id)
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))
        now = datetime.now(timezone.utc)

        for _ in range(2):
            db.add(IrsAuthorizationWarning(
                firm_id=uuid.UUID(firm_id), authorization_id=auth.id,
                threshold_days=30, sent_at=now, recipient_user_id=owner.id,
            ))

        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
    finally:
        db.close()


def test_two_null_recipient_rows_on_one_tier_both_insert(firm_a_owner):
    """NULLS DISTINCT. A pre-Sep-24 row and a row nulled by a user deletion
    have to be able to sit on the same tier."""
    from app.models.irs_authorization_warning import IrsAuthorizationWarning

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))
        now = datetime.now(timezone.utc)

        for offset in (2, 1):
            db.add(IrsAuthorizationWarning(
                firm_id=uuid.UUID(firm_id), authorization_id=auth.id,
                threshold_days=30, sent_at=now - timedelta(hours=offset),
                recipient_user_id=None,
            ))
        db.commit()
        db.expire_all()

        rows = _warning_rows(db, auth.id)
        assert len(rows) == 2
        assert all(r.recipient_user_id is None for r in rows)
    finally:
        db.close()


# --- what happens when people and dates change -----------------------------

def test_deleting_a_recipient_nulls_the_row_and_succeeds(firm_a_owner):
    """SET NULL, not CASCADE. The receipt survives the person."""
    from app.core.enums import UserRole
    from app.models.user import User

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = _owner(db, firm_id)
        manager = _mk_user(db, firm_id, f"mgr-{uuid.uuid4().hex[:8]}@firma.com", UserRole.manager)

        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        _run_sweep()
        db.expire_all()
        assert len(_warning_rows(db, auth.id)) == 2

        db.execute(
            User.__table__.delete().where(User.id == manager.id)
        )
        db.commit()
        db.expire_all()

        rows = _warning_rows(db, auth.id)
        assert len(rows) == 2, "the deleted user's receipt is kept"
        assert sorted(
            [r.recipient_user_id for r in rows], key=lambda v: (v is not None, str(v))
        ) == [None, owner.id]
    finally:
        db.close()


def test_deleting_both_recipients_of_one_tier_succeeds(firm_a_owner):
    """The NULLS DISTINCT case that matters operationally.

    Under NULLS NOT DISTINCT the second delete would raise a unique violation
    from inside an unrelated user delete, because both rows would have collided
    on (authorization, tier, NULL).
    """
    from app.core.enums import UserRole
    from app.models.user import User

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = _owner(db, firm_id)
        manager = _mk_user(db, firm_id, f"mgr-{uuid.uuid4().hex[:8]}@firma.com", UserRole.manager)

        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        _run_sweep()
        db.expire_all()
        assert len(_warning_rows(db, auth.id)) == 2

        for user_id in (manager.id, owner.id):
            db.execute(User.__table__.delete().where(User.id == user_id))
            db.commit()
        db.expire_all()

        rows = _warning_rows(db, auth.id)
        assert len(rows) == 2
        assert all(r.recipient_user_id is None for r in rows)
    finally:
        db.close()


def test_valid_until_change_clears_rows_but_not_the_events(firm_a_owner):
    """The reason for the dual write, stated as a test.

    update_authorization deletes the ladder rows when the expiry date moves, so
    after a renewal the table cannot say who was warned before it. The events
    are append-only and still carry their recipient lists.
    """
    from app.core.enums import UserRole
    from app.schemas.irs_authorization import IrsAuthorizationUpdate
    from app.services.irs_auth_service import update_authorization

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = _owner(db, firm_id)
        manager = _mk_user(db, firm_id, f"mgr-{uuid.uuid4().hex[:8]}@firma.com", UserRole.manager)

        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        _run_sweep()
        db.expire_all()
        assert len(_warning_rows(db, auth.id)) == 2

        events_before = _warning_events(db, firm_id, auth.id)
        assert len(events_before) == 1
        recorded = set(events_before[0].extra_metadata["recipient_user_ids"])
        assert recorded == {str(owner.id), str(manager.id)}

        update_authorization(
            db=db,
            authorization=auth,
            firm_id=uuid.UUID(firm_id),
            auth_in=IrsAuthorizationUpdate(valid_until=_cutoff() + timedelta(days=400)),
        )
        db.expire_all()

        assert _warning_rows(db, auth.id) == [], "the ladder resets"

        events_after = _warning_events(db, firm_id, auth.id)
        assert len(events_after) == 1, "the receipt is not deleted with the rows"
        assert set(events_after[0].extra_metadata["recipient_user_ids"]) == recorded
    finally:
        db.close()


# --- the read path ---------------------------------------------------------

def test_ladder_groups_two_recipients_into_one_rung(client, firm_a_owner):
    from app.core.enums import UserRole

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = _owner(db, firm_id)
        manager = _mk_user(db, firm_id, f"mgr-{uuid.uuid4().hex[:8]}@firma.com", UserRole.manager)
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))
        expected = {str(owner.id), str(manager.id)}
        auth_id = str(auth.id)

        _run_sweep()
    finally:
        db.close()

    r = client.get(f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    rungs = r.json()
    assert len(rungs) == 1, "two recipients on one tier is one rung"
    assert rungs[0]["threshold_days"] == 30
    assert set(rungs[0]["recipient_user_ids"]) == expected


def test_ladder_reports_a_legacy_row_as_an_empty_recipient_list(client, firm_a_owner):
    """A row written before Sep 24, 2026 has no recipient and is never
    backfilled. The rung is still reported, with an empty list, because the
    tier did fire and the honest answer about who it reached is "not
    recorded"."""
    from app.models.irs_authorization_warning import IrsAuthorizationWarning

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))
        db.add(IrsAuthorizationWarning(
            firm_id=uuid.UUID(firm_id), authorization_id=auth.id,
            threshold_days=60, sent_at=datetime.now(timezone.utc),
            recipient_user_id=None,
        ))
        db.commit()
        auth_id = str(auth.id)
    finally:
        db.close()

    r = client.get(f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    rungs = r.json()
    assert len(rungs) == 1
    assert rungs[0]["threshold_days"] == 60
    assert rungs[0]["recipient_user_ids"] == []


def test_another_firms_authorization_is_still_404(client, firm_a_owner, firm_b_owner):
    """Unchanged by the grouping, and worth re-pinning because the read path
    moved from the router into the service."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id, name="Firm A Recipient Client")
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))
        auth_id = str(auth.id)
        _run_sweep()
    finally:
        db.close()

    own = client.get(f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"])
    assert own.status_code == 200
    assert len(own.json()) == 1

    other = client.get(f"/irs-authorizations/{auth_id}/warnings", headers=firm_b_owner["headers"])
    assert other.status_code == 404
