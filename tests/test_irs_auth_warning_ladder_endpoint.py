# tests/test_irs_auth_warning_ladder_endpoint.py

"""
Phase F2 Piece 2. GET /irs-authorizations/{auth_id}/warnings.

The sweep has always recorded which expiry tiers fired. Until this endpoint
nothing could read those rows back, so a firm owner had no way to see what
they were warned about or when.

Ladder mechanics, tier selection and delivery live in
test_irs_auth_expiry_ladder.py. These tests are about the read path only:
shape, ordering, the empty case, tenant isolation and role.

Warning rows are written straight through crud_warning rather than by running
the sweep. The sweep needs recipients, notification preferences and an email
path, none of which this endpoint touches, and pinning sent_at explicitly is
what makes the ordering assertion mean something.
"""

import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import TestingSessionLocal


def _mk_client(db, firm_id, name="Ladder Read Client"):
    from app.models.client import Client
    c = Client(firm_id=uuid.UUID(firm_id), name=name)
    db.add(c)
    db.commit()
    db.refresh(c)
    return c


def _mk_auth(db, firm_id, client_id, form_type="8821"):
    from app.models.irs_authorization import IrsAuthorization
    a = IrsAuthorization(
        firm_id=uuid.UUID(firm_id), client_id=client_id, form_type=form_type,
        status="active", tax_years=[2024],
        valid_until=datetime.now(timezone.utc).date() + timedelta(days=30),
    )
    db.add(a)
    db.commit()
    db.refresh(a)
    return a


def _mk_warning(db, firm_id, auth_id, threshold_days, sent_at):
    from app.crud import irs_authorization_warning as crud_warning
    from app.schemas.irs_authorization_warning import IrsAuthorizationWarningCreate
    return crud_warning.create_warning(
        db=db,
        warning_in=IrsAuthorizationWarningCreate(
            authorization_id=auth_id,
            threshold_days=threshold_days,
            sent_at=sent_at,
        ),
        firm_id=uuid.UUID(firm_id),
    )


# ── happy path ────────────────────────────────────────────────────────────────

def test_ladder_returns_every_tier_that_fired(client, firm_a_owner):
    """
    Three tiers fired, three rows come back, most recent send first.

    The ordering is the point: a firm owner reading this wants the latest
    warning at the top, and it is what crud_warning already guarantees.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id)
        now = datetime.now(timezone.utc)
        # Written out of order on purpose. The endpoint must sort, not
        # accidentally agree with insertion order.
        _mk_warning(db, firm_id, auth.id, 30, now - timedelta(days=30))
        _mk_warning(db, firm_id, auth.id, 60, now - timedelta(days=60))
        _mk_warning(db, firm_id, auth.id, 7, now - timedelta(days=7))
        auth_id = str(auth.id)
    finally:
        db.close()

    r = client.get(
        f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"]
    )
    assert r.status_code == 200
    rows = r.json()
    assert [row["threshold_days"] for row in rows] == [7, 30, 60]

    sent = [row["sent_at"] for row in rows]
    assert sent == sorted(sent, reverse=True), "most recent send first"


def test_ladder_returns_threshold_and_sent_at_only(client, firm_a_owner):
    """
    The response carries the tier and the timestamp, nothing more.

    firm_id comes from the caller's JWT and authorization_id from the URL, so
    echoing either back is noise. Recipients are absent because the table has
    no recipient column, which is a known gap rather than an omission here.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id)
        _mk_warning(db, firm_id, auth.id, 0, datetime.now(timezone.utc))
        auth_id = str(auth.id)
    finally:
        db.close()

    r = client.get(
        f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"]
    )
    assert r.status_code == 200
    assert set(r.json()[0]) == {"threshold_days", "sent_at"}


def test_tier_zero_is_reported_not_treated_as_absent(client, firm_a_owner):
    """
    threshold_days 0 is the expiry date itself, and it is a real rung.
    Anything that treats the tier as falsy drops the most urgent warning the
    system ever sends, so it is pinned explicitly.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id)
        _mk_warning(db, firm_id, auth.id, 0, datetime.now(timezone.utc))
        auth_id = str(auth.id)
    finally:
        db.close()

    r = client.get(
        f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"]
    )
    assert r.status_code == 200
    assert [row["threshold_days"] for row in r.json()] == [0]


# ── empty ladder is an answer, not a missing resource ─────────────────────────

def test_authorization_with_no_warnings_returns_empty_list(client, firm_a_owner):
    """
    A freshly signed authorization has fired nothing yet. That is 200 and [],
    not 404: the authorization exists and the honest answer about it is that
    nothing has been sent.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id)
        auth_id = str(auth.id)
    finally:
        db.close()

    r = client.get(
        f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"]
    )
    assert r.status_code == 200
    assert r.json() == []


def test_nonexistent_authorization_returns_404(client, firm_a_owner):
    r = client.get(
        f"/irs-authorizations/{uuid.uuid4()}/warnings", headers=firm_a_owner["headers"]
    )
    assert r.status_code == 404


# ── tenant isolation ──────────────────────────────────────────────────────────

def test_firm_b_cannot_read_firm_a_warnings(client, firm_a_owner, firm_b_owner):
    """
    404, and specifically not 403.

    A 403 would confirm the row exists, telling firm B that firm A holds an
    authorization with that id. The response must be indistinguishable from
    the one for an id that was never issued.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id, name="Firm A Ladder Client")
        auth = _mk_auth(db, firm_id, cl.id)
        _mk_warning(db, firm_id, auth.id, 60, datetime.now(timezone.utc))
        auth_id = str(auth.id)
    finally:
        db.close()

    # Firm A can read its own ladder, so the row genuinely exists.
    own = client.get(
        f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"]
    )
    assert own.status_code == 200
    assert len(own.json()) == 1

    r = client.get(
        f"/irs-authorizations/{auth_id}/warnings", headers=firm_b_owner["headers"]
    )
    assert r.status_code == 404
    assert r.status_code != 403

    # Byte for byte the same as an id that never existed.
    unknown = client.get(
        f"/irs-authorizations/{uuid.uuid4()}/warnings", headers=firm_b_owner["headers"]
    )
    assert r.json() == unknown.json()


# ── RBAC ──────────────────────────────────────────────────────────────────────

def test_staff_cannot_read_the_warning_ladder(client, firm_a_owner, firm_a_staff):
    """
    Manager or above, matching every other IRS authorization endpoint. Staff
    read access is blocked on engagement membership existing, so it is a flat
    403 for now rather than a scoped read.
    """
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id)
        _mk_warning(db, firm_id, auth.id, 30, datetime.now(timezone.utc))
        auth_id = str(auth.id)
    finally:
        db.close()

    r = client.get(
        f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_staff["headers"]
    )
    assert r.status_code == 403


def test_unauthenticated_request_is_rejected(client, firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id)
        auth_id = str(auth.id)
    finally:
        db.close()

    r = client.get(f"/irs-authorizations/{auth_id}/warnings")
    assert r.status_code in (401, 403)


# ── read only ─────────────────────────────────────────────────────────────────

def test_reading_the_ladder_writes_nothing(client, firm_a_owner):
    """
    No side effects, not even a lazy backfill. The nightly sweep owns these
    rows and two writers is how they drift.
    """
    from app.crud import irs_authorization_warning as crud_warning

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id)
        _mk_warning(db, firm_id, auth.id, 60, datetime.now(timezone.utc))
        auth_id = str(auth.id)
        before = [
            (w.id, w.threshold_days, w.sent_at)
            for w in crud_warning.list_warnings_for_authorization(
                db=db, firm_id=uuid.UUID(firm_id), authorization_id=auth.id
            )
        ]
    finally:
        db.close()

    for _ in range(3):
        assert client.get(
            f"/irs-authorizations/{auth_id}/warnings", headers=firm_a_owner["headers"]
        ).status_code == 200

    db = TestingSessionLocal()
    try:
        after = [
            (w.id, w.threshold_days, w.sent_at)
            for w in crud_warning.list_warnings_for_authorization(
                db=db, firm_id=uuid.UUID(firm_id), authorization_id=uuid.UUID(auth_id)
            )
        ]
    finally:
        db.close()

    assert before == after
