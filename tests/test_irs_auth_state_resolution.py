# tests/test_irs_auth_state_resolution.py
"""
Phase F1. Authorization state resolution.

Both check endpoints and the transcript gate answer from one shared function,
crud_auth.resolve_authorization_state. These tests pin the five resolved
states, the fact that either form type opens the transcript gate, and the
rule that the 400 message never claims nothing is on file when a record
exists.

Fixtures that need a status other than what the API writes set it directly on
the row. PATCH /irs-authorizations/{id} sets status without running the
supersede logic, so it cannot produce a superseded row at all: those go
through activate_authorization_for_envelope, which is the only code path that
supersedes anything.
"""

from datetime import date, timedelta
from uuid import UUID

from tests.conftest import TestingSessionLocal

from app.crud import irs_authorization as crud_auth
from app.models.irs_authorization import IrsAuthorization


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(client, headers, name="Resolution Client"):
    r = client.post("/clients/", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def send_auth(client, headers, client_id, form_type="8821", valid_until=None):
    """Create an authorization through the real send flow. Leaves it pending."""
    payload = {
        "client_id": client_id,
        "form_type": form_type,
        "tax_years": [2023, 2024],
    }
    if valid_until is not None:
        payload["valid_until"] = valid_until.isoformat()
    r = client.post("/irs-authorizations/send", json=payload, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def set_status(auth_id, status, valid_until=...):
    """
    Write status straight onto the row.

    'expired' and 'revoked' are written by the nightly sweep and by a manual
    PATCH respectively, neither of which is what these tests are exercising.
    Going direct keeps the fixture about the state, not about how it was
    reached. valid_until is only touched when passed, so the sentinel
    distinguishes "leave it alone" from "set it to None".
    """
    db = TestingSessionLocal()
    try:
        auth = db.get(IrsAuthorization, UUID(auth_id))
        assert auth is not None
        auth.status = status
        if valid_until is not ...:
            auth.valid_until = valid_until
        db.commit()
    finally:
        db.close()


def make_active(client, headers, client_id, form_type="8821", valid_until=None):
    auth_id = send_auth(client, headers, client_id, form_type, valid_until)
    set_status(auth_id, "active")
    return auth_id


def make_active_by_column(client, headers, client_id, form_type="8821", valid_until=None):
    """
    A row the status column calls active, with valid_until written straight
    onto it.

    The whole point of these fixtures is the disagreement between the column
    and the date, so the date is set on the row rather than sent through the
    API. This is exactly the state the database is in between the moment an
    authorization lapses and the moment the nightly sweep reaches it.
    """
    auth_id = send_auth(client, headers, client_id, form_type)
    set_status(auth_id, "active", valid_until=valid_until)
    return auth_id


def make_lapsed(client, headers, client_id, form_type="8821", valid_until=None):
    auth_id = send_auth(client, headers, client_id, form_type)
    set_status(auth_id, "expired", valid_until=valid_until)
    return auth_id


def request_transcript(client, headers, client_id):
    return client.post("/transcript-requests/", json={
        "client_id": client_id,
        "transcript_type": "wage_and_income",
        "tax_year": 2023,
    }, headers=headers)


def auth_check(client, headers, client_id):
    r = client.get(f"/irs-authorizations/check/{client_id}", headers=headers)
    assert r.status_code == 200
    return r.json()


def transcript_check(client, headers, client_id):
    r = client.get(f"/transcript-requests/check/{client_id}", headers=headers)
    assert r.status_code == 200
    return r.json()


# ── active on one form type only ──────────────────────────────────────────────

def test_active_8821_no_2848(client, firm_a_owner):
    """The ordinary case. Gate passes on the 8821, 2848 resolves none."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    make_active(client, headers, cid, "8821")

    assert request_transcript(client, headers, cid).status_code == 201

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "active"
    assert auth_data["state_2848"] == "none"
    assert auth_data["has_active_8821"] is True
    assert auth_data["has_active_2848"] is False
    assert auth_data["2848"] is None

    t_data = transcript_check(client, headers, cid)
    assert t_data["can_request"] is True
    assert t_data["state_8821"] == "active"
    assert t_data["state_2848"] == "none"


def test_active_2848_alone_opens_the_gate(client, firm_a_owner):
    """
    The functional bug this phase fixes. The gate used to demand form type
    8821 specifically, so a firm holding a valid Power of Attorney and
    nothing else was refused outright.
    """
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    make_active(client, headers, cid, "2848")

    assert request_transcript(client, headers, cid).status_code == 201

    t_data = transcript_check(client, headers, cid)
    assert t_data["can_request"] is True
    assert t_data["authorization_status"] == "active"
    assert t_data["state_8821"] == "none"
    assert t_data["state_2848"] == "active"


# ── lapsed ────────────────────────────────────────────────────────────────────

def test_lapsed_8821_active_2848(client, firm_a_owner):
    """The 2848 carries the gate. The 8821 still reports its lapse and date."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    lapsed_on = date.today() - timedelta(days=45)
    make_lapsed(client, headers, cid, "8821", valid_until=lapsed_on)
    make_active(client, headers, cid, "2848")

    assert request_transcript(client, headers, cid).status_code == 201

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "lapsed"
    assert auth_data["expires_on_8821"] == lapsed_on.isoformat()
    assert auth_data["has_active_8821"] is False
    # The record now reaches the frontend, which is the whole point.
    assert auth_data["8821"] is not None
    assert auth_data["8821"]["status"] == "expired"
    assert auth_data["state_2848"] == "active"


def test_both_lapsed_blocks_and_message_names_the_lapse(client, firm_a_owner):
    """
    Gate fails. The message must say the authorizations expired, and must not
    tell a firm that let them lapse that nothing was ever on file.
    """
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    lapsed_8821 = date(2025, 3, 20)
    lapsed_2848 = date(2025, 6, 1)
    make_lapsed(client, headers, cid, "8821", valid_until=lapsed_8821)
    make_lapsed(client, headers, cid, "2848", valid_until=lapsed_2848)

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "8821" in detail
    assert "expired March 20, 2025" in detail
    assert "expired June 1, 2025" in detail
    assert "not on file" not in detail.lower()
    assert "none on file" not in detail.lower()

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "lapsed"
    assert auth_data["state_2848"] == "lapsed"

    t_data = transcript_check(client, headers, cid)
    assert t_data["can_request"] is False
    assert t_data["authorization_status"] == "lapsed"


def test_lapsed_with_null_valid_until(client, firm_a_owner):
    """
    An indefinite 8821 that was swept to expired carries no date. Report the
    lapse without one rather than inventing a date, and do not crash.
    """
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    make_lapsed(client, headers, cid, "8821", valid_until=None)

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "lapsed"
    assert auth_data["expires_on_8821"] is None

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "expired, with no expiry date on record" in detail
    assert "not on file" not in detail.lower()


# ── nothing on file ───────────────────────────────────────────────────────────

def test_neither_form_ever_created(client, firm_a_owner):
    """The one case where 'none on file' is the truth."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "none"
    assert auth_data["state_2848"] == "none"
    assert auth_data["8821"] is None
    assert auth_data["2848"] is None
    assert auth_data["expires_on_8821"] is None

    t_data = transcript_check(client, headers, cid)
    assert t_data["can_request"] is False
    assert t_data["authorization_status"] == "not_on_file"

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Form 8821: none on file" in detail
    assert "Form 2848: none on file" in detail


# ── pending and revoked ───────────────────────────────────────────────────────

def test_pending_signature_only(client, firm_a_owner):
    """Sent, not yet signed. Blocked, and the message says why."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_auth(client, headers, cid, "8821")

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "pending"
    assert auth_data["has_active_8821"] is False
    assert auth_data["8821"]["status"] == "pending_signature"

    t_data = transcript_check(client, headers, cid)
    assert t_data["can_request"] is False
    assert t_data["authorization_status"] == "pending"

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "awaiting signature" in detail
    assert "not on file" not in detail.lower()


def test_revoked_only(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    auth_id = send_auth(client, headers, cid, "8821")
    set_status(auth_id, "revoked")

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "revoked"
    assert auth_data["8821"]["id"] == auth_id

    t_data = transcript_check(client, headers, cid)
    assert t_data["can_request"] is False
    assert t_data["authorization_status"] == "revoked"

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert "Form 8821: revoked" in detail
    assert "not on file" not in detail.lower()


# ── superseded ────────────────────────────────────────────────────────────────

def test_superseded_8821_resolves_to_its_replacement(client, firm_a_owner):
    """
    A renewal retires the prior row. Resolution must read the replacement,
    never the superseded row, and must never report 'superseded' as a state.

    The supersede logic only runs inside activate_authorization_for_envelope,
    so the replacement is activated the way the signature webhook does it
    rather than through PATCH.
    """
    from app.services.irs_auth_service import activate_authorization_for_envelope

    headers = firm_a_owner["headers"]
    firm_id = UUID(firm_a_owner["firm_id"])
    cid = make_client(client, headers)

    old_id = make_active(client, headers, cid, "8821")
    new_id = send_auth(client, headers, cid, "8821")

    db = TestingSessionLocal()
    try:
        replacement = db.get(IrsAuthorization, UUID(new_id))
        activate_authorization_for_envelope(
            db=db,
            envelope_id=replacement.signature_envelope_id,
            firm_id=firm_id,
        )
        prior = db.get(IrsAuthorization, UUID(old_id))
        db.refresh(prior)
        assert prior.status == "superseded", "fixture did not actually supersede"

        resolved = crud_auth.resolve_authorization_state(db, firm_id, UUID(cid), "8821")
        assert resolved.state == "active"
        assert resolved.record.id == UUID(new_id)
    finally:
        db.close()

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "active"
    assert auth_data["8821"]["id"] == new_id
    assert auth_data["has_active_8821"] is True

    assert request_transcript(client, headers, cid).status_code == 201


# ── the date beats the status column (Step 8) ─────────────────────────────────
#
# status only becomes "expired" when the nightly sweep runs. Every fixture
# below is a row the column still calls active, which is what the database
# actually looks like between the moment an authorization lapses and the
# moment the sweep reaches it. Anchored on compute_expiry_cutoff_date, never
# date.today(), because that is the calendar the sweep reasons in.

def test_active_column_past_its_date_resolves_lapsed(client, firm_a_owner):
    """
    The false green this step removes. Nothing has run the sweep, the column
    still says active, and the authorization is dead.
    """
    headers = firm_a_owner["headers"]
    firm_id = UUID(firm_a_owner["firm_id"])
    cid = make_client(client, headers)
    lapsed_on = crud_auth.compute_expiry_cutoff_date() - timedelta(days=1)
    auth_id = make_active_by_column(client, headers, cid, "8821", valid_until=lapsed_on)

    db = TestingSessionLocal()
    try:
        resolved = crud_auth.resolve_authorization_state(db, firm_id, UUID(cid), "8821")
        assert resolved.state == crud_auth.AUTH_STATE_LAPSED
        assert resolved.expires_on == lapsed_on
        assert resolved.record.id == UUID(auth_id)

        # A read and only a read. The column is the sweep's to write.
        db.refresh(resolved.record)
        assert resolved.record.status == "active", "resolution must not write"
    finally:
        db.close()

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "lapsed"
    assert auth_data["expires_on_8821"] == lapsed_on.isoformat()
    assert auth_data["has_active_8821"] is False


def test_active_column_with_no_end_date_stays_active(client, firm_a_owner):
    """An 8821 with no end date is normal and valid indefinitely."""
    headers = firm_a_owner["headers"]
    firm_id = UUID(firm_a_owner["firm_id"])
    cid = make_client(client, headers)
    make_active_by_column(client, headers, cid, "8821", valid_until=None)

    db = TestingSessionLocal()
    try:
        resolved = crud_auth.resolve_authorization_state(db, firm_id, UUID(cid), "8821")
        assert resolved.state == crud_auth.AUTH_STATE_ACTIVE
        assert resolved.expires_on is None
    finally:
        db.close()

    assert request_transcript(client, headers, cid).status_code == 201


def test_active_column_far_in_the_future_stays_active(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    firm_id = UUID(firm_a_owner["firm_id"])
    cid = make_client(client, headers)
    expires_on = crud_auth.compute_expiry_cutoff_date() + timedelta(days=400)
    make_active_by_column(client, headers, cid, "8821", valid_until=expires_on)

    db = TestingSessionLocal()
    try:
        resolved = crud_auth.resolve_authorization_state(db, firm_id, UUID(cid), "8821")
        assert resolved.state == crud_auth.AUTH_STATE_ACTIVE
        assert resolved.expires_on == expires_on
    finally:
        db.close()

    assert request_transcript(client, headers, cid).status_code == 201


def test_expiring_exactly_on_the_anchor_date_agrees_with_the_sweep(client, firm_a_owner):
    """
    The boundary. A row expiring ON the anchor date resolves ACTIVE, because
    the sweep's lapsed query is valid_until < as_of, strictly less than. To
    the sweep that same row is not lapsed either: it sits in the warning
    window as a day-zero notice.

    These two must agree. If resolution used <= the badge would go red and
    the gate would close a full day before the sweep wrote the status, which
    is the same class of contradiction, just pointing the other way.
    """
    headers = firm_a_owner["headers"]
    firm_id = UUID(firm_a_owner["firm_id"])
    cid = make_client(client, headers)
    anchor = crud_auth.compute_expiry_cutoff_date()
    auth_id = make_active_by_column(client, headers, cid, "8821", valid_until=anchor)

    db = TestingSessionLocal()
    try:
        resolved = crud_auth.resolve_authorization_state(db, firm_id, UUID(cid), "8821")
        assert resolved.state == crud_auth.AUTH_STATE_ACTIVE
        assert resolved.expires_on == anchor

        lapsed_ids = {
            row.id for row in crud_auth.get_lapsed_active_authorizations(db, as_of=anchor)
        }
        window_ids = {
            row.id for row in crud_auth.get_authorizations_in_warning_window(
                db, max_days=60, as_of=anchor
            )
        }
        assert UUID(auth_id) not in lapsed_ids, "the sweep would not expire it either"
        assert UUID(auth_id) in window_ids, "the sweep sees it as a day-zero warning"
    finally:
        db.close()

    assert request_transcript(client, headers, cid).status_code == 201


def test_gate_refuses_active_by_column_past_its_date_and_names_the_lapse(
    client, firm_a_owner
):
    """
    The reason this step exists. The gate used to open here, because the only
    row was still marked active.
    """
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    lapsed_on = crud_auth.compute_expiry_cutoff_date() - timedelta(days=30)
    make_active_by_column(client, headers, cid, "8821", valid_until=lapsed_on)

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    detail = r.json()["detail"]
    assert f"expired {lapsed_on:%B} {lapsed_on.day}, {lapsed_on.year}" in detail
    assert "not on file" not in detail.lower()

    t_data = transcript_check(client, headers, cid)
    assert t_data["can_request"] is False
    assert t_data["authorization_status"] == "lapsed"
    assert t_data["state_8821"] == "lapsed"


def test_date_lapsed_8821_with_a_genuinely_active_2848_opens_the_gate(
    client, firm_a_owner
):
    """The 2848 carries it. The 8821 still reports its lapse and its date."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    lapsed_on = crud_auth.compute_expiry_cutoff_date() - timedelta(days=5)
    make_active_by_column(client, headers, cid, "8821", valid_until=lapsed_on)
    make_active_by_column(
        client, headers, cid, "2848",
        valid_until=crud_auth.compute_expiry_cutoff_date() + timedelta(days=90),
    )

    assert request_transcript(client, headers, cid).status_code == 201

    auth_data = auth_check(client, headers, cid)
    assert auth_data["state_8821"] == "lapsed"
    assert auth_data["expires_on_8821"] == lapsed_on.isoformat()
    assert auth_data["state_2848"] == "active"
    assert auth_data["has_active_8821"] is False
    assert auth_data["has_active_2848"] is True


# ── tenant isolation ──────────────────────────────────────────────────────────

def test_tenant_isolation_auth_check(client, firm_a_owner, firm_b_owner):
    """Firm B cannot read Firm A's authorization state off the badge endpoint."""
    a_headers = firm_a_owner["headers"]
    cid_a = make_client(client, a_headers, name="Firm A Resolution Client")
    make_active(client, a_headers, cid_a, "8821")

    r = client.get(f"/irs-authorizations/check/{cid_a}", headers=firm_b_owner["headers"])
    assert r.status_code == 404


def test_tenant_isolation_transcript_check(client, firm_a_owner, firm_b_owner):
    """Same client, same isolation, through the transcript endpoint."""
    a_headers = firm_a_owner["headers"]
    cid_a = make_client(client, a_headers, name="Firm A Transcript Resolution Client")
    make_active(client, a_headers, cid_a, "8821")

    r = client.get(f"/transcript-requests/check/{cid_a}", headers=firm_b_owner["headers"])
    assert r.status_code == 404


def test_resolution_is_scoped_to_firm(client, firm_a_owner, firm_b_owner):
    """
    The shared function itself must not see across firms, independent of the
    404 the endpoints raise on the client lookup.
    """
    a_headers = firm_a_owner["headers"]
    cid_a = make_client(client, a_headers, name="Firm A Scoped Client")
    make_active(client, a_headers, cid_a, "8821")

    db = TestingSessionLocal()
    try:
        as_firm_a = crud_auth.resolve_authorization_state(
            db, UUID(firm_a_owner["firm_id"]), UUID(cid_a), "8821"
        )
        as_firm_b = crud_auth.resolve_authorization_state(
            db, UUID(firm_b_owner["firm_id"]), UUID(cid_a), "8821"
        )
    finally:
        db.close()

    assert as_firm_a.state == "active"
    assert as_firm_b.state == "none"
    assert as_firm_b.record is None
