# tests/test_irs_auth_expiry_ladder.py

"""
The IRS authorization expiry ladder, state transitions, delivery, isolation
and copy.

Calendar-boundary behaviour lives in test_irs_auth_expiry_sweep.py.

Fixtures anchor on compute_expiry_cutoff_date(), never date.today(). The
sweep reasons in cutoff terms, and a fixture built from the server's local
date lands on the wrong tier whenever the two calendars disagree. That has
already caused two defects in this feature.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from tests.conftest import TestingSessionLocal


def _cutoff():
    from app.crud.irs_authorization import compute_expiry_cutoff_date
    return compute_expiry_cutoff_date()


def _mk_client(db, firm_id, name="Acme Construction"):
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


def _run_sweep():
    from app.services.irs_auth_service import check_expiring_authorizations
    with patch("app.db.session.SessionLocal", TestingSessionLocal):
        return check_expiring_authorizations()


def _tiers(db, firm_id, auth_id):
    from app.crud import irs_authorization_warning as crud_warning
    rows = crud_warning.list_warnings_for_authorization(
        db=db, firm_id=uuid.UUID(firm_id), authorization_id=auth_id
    )
    return sorted(r.threshold_days for r in rows)


def _notifs(db, firm_id, auth_id):
    from sqlalchemy import select
    from app.models.notification import Notification
    return db.execute(
        select(Notification).where(
            Notification.firm_id == uuid.UUID(firm_id),
            Notification.related_entity_id == auth_id,
        )
    ).scalars().all()


# --- The ladder ------------------------------------------------------------

def test_each_tier_fires_exactly_once_across_repeated_runs(firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=60))

        for _ in range(3):
            _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [60]
        assert len(_notifs(db, firm_id, auth.id)) == 1

        for days, expected in ((30, [30, 60]), (7, [7, 30, 60]), (0, [0, 7, 30, 60])):
            auth.valid_until = _cutoff() + timedelta(days=days)
            db.commit()
            _run_sweep()
            _run_sweep()
            db.expire_all()
            assert _tiers(db, firm_id, auth.id) == expected, f"at {days} days"

        assert len(_notifs(db, firm_id, auth.id)) == 4
    finally:
        db.close()


def test_authorization_created_inside_window_skips_less_urgent_tiers(firm_a_owner):
    """Created 10 days out: fires 30, then 7, then 0. Never backfills 60."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=10))

        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [30]

        auth.valid_until = _cutoff() + timedelta(days=7)
        db.commit()
        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [7, 30]

        auth.valid_until = _cutoff()
        db.commit()
        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [0, 7, 30]
        assert 60 not in _tiers(db, firm_id, auth.id), "60 never fired, never stamp it"
    finally:
        db.close()


def test_changing_valid_until_clears_warnings_and_recomputes(firm_a_owner):
    from app.services.irs_auth_service import update_authorization
    from app.schemas.irs_authorization import IrsAuthorizationUpdate

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=7))

        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [7]

        update_authorization(
            db=db, authorization=auth, firm_id=uuid.UUID(firm_id),
            auth_in=IrsAuthorizationUpdate(valid_until=_cutoff() + timedelta(days=365)),
        )
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [], "a renewal resets the ladder"

        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [], "365 days out is beyond every tier"

        auth.valid_until = _cutoff() + timedelta(days=60)
        db.commit()
        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [60], "ladder restarts at the top"
    finally:
        db.close()


def test_unchanged_valid_until_does_not_clear_the_ladder(firm_a_owner):
    from app.services.irs_auth_service import update_authorization
    from app.schemas.irs_authorization import IrsAuthorizationUpdate

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        expiry = _cutoff() + timedelta(days=30)
        auth = _mk_auth(db, firm_id, cl.id, expiry)

        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [30]

        update_authorization(
            db=db, authorization=auth, firm_id=uuid.UUID(firm_id),
            auth_in=IrsAuthorizationUpdate(tax_years=[2023, 2024]),
        )
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [30], "unrelated field must not reset"

        update_authorization(
            db=db, authorization=auth, firm_id=uuid.UUID(firm_id),
            auth_in=IrsAuthorizationUpdate(valid_until=expiry),
        )
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [30], "same date is not a change"
    finally:
        db.close()


# --- State transitions -----------------------------------------------------

def test_lapsed_outside_window_is_caught_and_expired(firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() - timedelta(days=200))

        result = _run_sweep()
        db.expire_all()
        db.refresh(auth)

        assert auth.status == "expired"
        assert result["expired"] == 1
        assert _tiers(db, firm_id, auth.id) == [0], "one final notice on the way out"

        assert _run_sweep()["expired"] == 0, "the query drains itself"
    finally:
        db.close()


def test_expired_authorization_closes_the_transcript_gate(firm_a_owner):
    """
    Once past its date, resolve_authorization_state reports a lapse and
    request_transcript raises. The gate always existed and was decorative
    while nothing ever wrote the status.

    Step 8 moved the gate off the status column and onto valid_until, so the
    row is already lapsed to the resolver BEFORE the sweep runs. The sweep
    then writes status = "expired" and the resolver keeps saying lapsed, off
    the same date. The two are consistent at every point, which is the change:
    this used to report the row as active for as long as it took the sweep to
    reach it, which held the transcript gate open on a dead authorization.
    """
    from app.crud import irs_authorization as crud_auth
    from app.models.firm import Firm
    from app.schemas.transcript_request import TranscriptRequestCreate
    from app.services.transcript_service import request_transcript
    from sqlalchemy import select

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() - timedelta(days=1))
        firm = db.execute(
            select(Firm).where(Firm.id == uuid.UUID(firm_id))
        ).scalars().first()

        before = crud_auth.resolve_authorization_state(
            db, uuid.UUID(firm_id), cl.id, "8821"
        )
        assert before.state == crud_auth.AUTH_STATE_LAPSED, (
            "the date has passed, so it is lapsed even though the column "
            "still says active and the sweep has not run"
        )
        assert before.expires_on == auth.valid_until

        _run_sweep()
        db.expire_all()
        db.refresh(auth)
        assert auth.status == "expired"

        after = crud_auth.resolve_authorization_state(
            db, uuid.UUID(firm_id), cl.id, "8821"
        )
        assert after.state == crud_auth.AUTH_STATE_LAPSED
        assert after.expires_on == auth.valid_until

        with pytest.raises(ValueError):
            request_transcript(
                db=db, firm=firm, client=cl,
                request_in=TranscriptRequestCreate(
                    client_id=cl.id, transcript_type="account", tax_year=2024,
                ),
                requested_by_user_id=uuid.uuid4(),
            )
    finally:
        db.close()


# --- Supersession ----------------------------------------------------------

def test_activating_8821_supersedes_prior_8821_and_spares_the_2848(firm_a_owner):
    from app.services.irs_auth_service import activate_authorization_for_envelope
    from app.crud import signature_envelope as crud_envelope
    from app.schemas.signature_envelope import SignatureEnvelopeCreate

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        old_8821 = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=20), "8821")
        old_2848 = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=200), "2848")

        envelope = crud_envelope.create_signature_envelope(
            db=db,
            schema=SignatureEnvelopeCreate(
                client_id=cl.id, engagement_id=None, document_id=None,
                signers=[{"name": "Acme", "email": "a@b.com", "status": "pending"}],
                subject="Please sign", message="",
            ),
            firm_id=uuid.UUID(firm_id),
        )
        new_8821 = _mk_auth(
            db, firm_id, cl.id, _cutoff() + timedelta(days=400),
            "8821", status="pending_signature",
        )
        new_8821.signature_envelope_id = envelope.id
        db.commit()

        activate_authorization_for_envelope(
            db=db, envelope_id=envelope.id, firm_id=uuid.UUID(firm_id),
        )

        db.expire_all()
        db.refresh(old_8821)
        db.refresh(old_2848)
        db.refresh(new_8821)

        assert new_8821.status == "active"
        assert old_8821.status == "superseded"
        assert old_2848.status == "active", (
            "an active 2848 must survive an 8821 activation, or transcript "
            "access for the other form breaks"
        )
    finally:
        db.close()


def test_superseded_row_survives_with_its_document_and_history(firm_a_owner):
    from app.services.irs_auth_service import _supersede_prior_active_authorizations
    from app.models.irs_authorization import IrsAuthorization
    from app.crud import irs_authorization_warning as crud_warning
    from app.schemas.irs_authorization_warning import IrsAuthorizationWarningCreate
    from sqlalchemy import select

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        prior = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=20))

        # A real Document so the FK holds, proving the link is not just a
        # dangling uuid that happens to survive.
        from app.models.document import Document
        doc = Document(
            firm_id=uuid.UUID(firm_id), client_id=cl.id,
            filename="8821-signed.pdf", s3_key=f"{firm_id}/8821.pdf",
            content_type="application/pdf", size_bytes=1024,
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)

        prior.signed_document_id = doc.id
        db.commit()

        crud_warning.create_warning(
            db=db,
            warning_in=IrsAuthorizationWarningCreate(
                authorization_id=prior.id, threshold_days=60,
                sent_at=datetime.now(timezone.utc),
            ),
            firm_id=uuid.UUID(firm_id),
        )

        replacement = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=400))

        _supersede_prior_active_authorizations(
            db=db, firm_id=uuid.UUID(firm_id), client_id=cl.id,
            form_type="8821", replacement_id=replacement.id,
        )
        db.commit()
        db.expire_all()

        still_there = db.execute(
            select(IrsAuthorization).where(IrsAuthorization.id == prior.id)
        ).scalars().first()
        assert still_there is not None, "superseded rows are never deleted"
        assert still_there.status == "superseded"
        assert still_there.signed_document_id == doc.id, "the document does not move"
        assert _tiers(db, firm_id, prior.id) == [60], (
            "supersession must not clear the ladder: that history is the "
            "renewal lead time signal"
        )
    finally:
        db.close()


def test_expiry_does_not_clear_the_ladder(firm_a_owner):
    """valid_until changing is the ONLY trigger that deletes warning rows."""
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=7))

        _run_sweep()
        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [7]

        auth.valid_until = _cutoff() - timedelta(days=1)
        db.commit()
        _run_sweep()
        db.expire_all()
        db.refresh(auth)

        assert auth.status == "expired"
        assert _tiers(db, firm_id, auth.id) == [0, 7], (
            "expiry keeps the history it accumulated on the way down"
        )
    finally:
        db.close()


# --- Delivery --------------------------------------------------------------

def test_warnings_reach_owner_and_manager_not_staff(firm_a_owner):
    from app.core.enums import UserRole

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        manager = _mk_user(db, firm_id, "mgr@firma.com", UserRole.manager)
        staff = _mk_user(db, firm_id, "staff2@firma.com", UserRole.staff)

        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        _run_sweep()
        db.expire_all()

        recipients = {n.recipient_id for n in _notifs(db, firm_id, auth.id)}
        assert manager.id in recipients
        assert staff.id not in recipients, "staff cannot view IRS authorizations"
        assert len(recipients) == 2, "owner and manager only"
    finally:
        db.close()


def test_in_app_survives_channel_none_while_email_is_suppressed(
    firm_a_owner, mock_email_service
):
    from app.crud import notification_preference as crud_pref
    from app.core.enums import RecipientType, NotificationEventType, NotificationChannel
    from app.models.user import User
    from sqlalchemy import select

    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        owner = db.execute(
            select(User).where(User.firm_id == uuid.UUID(firm_id))
        ).scalars().first()

        crud_pref.upsert_preference(
            db=db, firm_id=uuid.UUID(firm_id), recipient_id=owner.id,
            recipient_type=RecipientType.staff,
            event_type=NotificationEventType.irs_auth_expiry,
            channel=NotificationChannel.none,
        )

        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        mock_email_service.clear()
        _run_sweep()
        db.expire_all()

        assert len(_notifs(db, firm_id, auth.id)) == 1, (
            "a firm may stop the emails, not make the compliance record vanish"
        )
        assert _tiers(db, firm_id, auth.id) == [30]
        assert owner.email not in [e["to_email"] for e in mock_email_service]
    finally:
        db.close()


def test_email_subject_carries_the_firm_name(firm_a_owner, mock_email_service):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        mock_email_service.clear()
        _run_sweep()

        assert len(mock_email_service) == 1
        subject = mock_email_service[0]["subject"]
        assert subject == "[Firm A CPA] Form 8821 expires in 30 days"
        assert not subject.startswith("[]"), "empty firm_name regression"
    finally:
        db.close()


def test_warning_row_requires_a_real_in_app_record(firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        auth = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30))

        with patch(
            "app.services.notification_service.NotificationService.create_notification",
            return_value=None,
        ):
            result = _run_sweep()

        db.expire_all()
        assert _tiers(db, firm_id, auth.id) == [], "no record means no row"
        assert result["alerts_emitted"] == 0
    finally:
        db.close()


def test_one_failing_row_does_not_abort_the_sweep(firm_a_owner):
    firm_id = firm_a_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl = _mk_client(db, firm_id)
        bad = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30), "8821")
        good = _mk_auth(db, firm_id, cl.id, _cutoff() + timedelta(days=30), "2848")

        from app.services import irs_auth_service as svc
        real_build = svc.build_expiry_warning_message

        def exploding(authorization, as_of):
            if authorization.id == bad.id:
                raise RuntimeError("simulated failure on one row")
            return real_build(authorization, as_of)

        with patch.object(svc, "build_expiry_warning_message", exploding):
            _run_sweep()

        db.expire_all()
        assert _tiers(db, firm_id, bad.id) == []
        assert _tiers(db, firm_id, good.id) == [30], (
            "a nightly compliance job must never let one bad row silence "
            "every row after it"
        )
    finally:
        db.close()


# --- Tenant isolation ------------------------------------------------------

def test_firm_a_sweep_never_touches_firm_b(firm_a_owner, firm_b_owner):
    from app.crud import irs_authorization_warning as crud_warning

    firm_a = firm_a_owner["firm_id"]
    firm_b = firm_b_owner["firm_id"]
    db = TestingSessionLocal()
    try:
        cl_a = _mk_client(db, firm_a)
        cl_b = _mk_client(db, firm_b)
        auth_a = _mk_auth(db, firm_a, cl_a.id, _cutoff() + timedelta(days=30))
        auth_b = _mk_auth(db, firm_b, cl_b.id, _cutoff() + timedelta(days=30))

        _run_sweep()
        db.expire_all()

        # The sweep is cross-firm by design, so both firms are warned. What
        # must not leak is who gets told and which firm owns the record.
        assert _tiers(db, firm_a, auth_a.id) == [30]
        assert _tiers(db, firm_b, auth_b.id) == [30]

        a_notifs = _notifs(db, firm_a, auth_a.id)
        b_notifs = _notifs(db, firm_b, auth_b.id)
        assert {n.recipient_id for n in a_notifs}.isdisjoint(
            {n.recipient_id for n in b_notifs}
        )
        assert all(n.firm_id == uuid.UUID(firm_a) for n in a_notifs)
        assert all(n.firm_id == uuid.UUID(firm_b) for n in b_notifs)

        assert crud_warning.list_warnings_for_authorization(
            db=db, firm_id=uuid.UUID(firm_a), authorization_id=auth_b.id
        ) == [], "firm A must not see firm B's warning rows"
    finally:
        db.close()


# --- Copy ------------------------------------------------------------------

BANNED_COPY = (
    "while you have room",
    "worst week of the year",
    "chasing a signature",
    "renewing it now",
    "plenty of time",
    "enough time",
    "median",
    "average",
    "typically",
    "most firms",
    "peers",
    "%",
)


def _msg(form_type, as_of, valid_until):
    from types import SimpleNamespace
    from app.services.irs_auth_service import build_expiry_warning_message
    return build_expiry_warning_message(
        SimpleNamespace(form_type=form_type, valid_until=valid_until), as_of
    )


def test_copy_never_claims_there_is_time_to_renew():
    """
    Pins the ABSENCE of the removed judgment. A test that only checked the
    date appears would pass even if the unearned time claim came back.
    """
    for days in (60, 45, 30, 14, 7, 3, 1, 0, -1, -400):
        for form_type in ("8821", "2848"):
            for as_of in (date(2027, 3, 1), date(2026, 8, 9)):
                title, body = _msg(form_type, as_of, as_of + timedelta(days=days))
                text = f"{title} {body}".lower()
                for phrase in BANNED_COPY:
                    assert phrase not in text, (
                        f"{phrase!r} reappeared at {days} days, {form_type}, {as_of}"
                    )
                assert "—" not in text and "–" not in text, "no dashes"


def test_season_clause_follows_the_expiry_date_not_today():
    """
    The sentence claims the EXPIRY lands in filing season. Checking today's
    date instead produces a false statement whenever the two differ, and the
    four standard renderings hide it because they coincide.
    """
    # Warned inside filing season, expires well outside it.
    _, body = _msg("8821", date(2027, 4, 18), date(2027, 6, 17))
    assert "June 17" in body
    assert "during filing season" not in body, (
        "June 17 is not filing season, whatever today happens to be"
    )

    # Warned outside filing season, expires inside it.
    _, body = _msg("8821", date(2026, 12, 20), date(2027, 2, 18))
    assert "February 18" in body
    assert "during filing season" in body, (
        "silent about a mid-crunch expiry because today happens to be December"
    )


def test_lapsed_copy_carries_no_season_clause():
    for as_of, valid_until in (
        (date(2027, 3, 1), date(2027, 2, 18)),
        (date(2026, 10, 13), date(2025, 9, 8)),
    ):
        _, body = _msg("8821", as_of, valid_until)
        assert "during filing season" not in body
        assert "expired" in body


def test_year_shown_only_outside_the_current_year():
    _, body = _msg("8821", date(2026, 10, 13), date(2026, 9, 8))
    assert "September 8," in body
    assert "2026" not in body

    _, body = _msg("8821", date(2026, 10, 13), date(2025, 9, 8))
    assert "September 8, 2025" in body


def test_consequence_is_form_aware_and_only_near_expiry():
    base = date(2026, 8, 9)

    _, body = _msg("8821", base, base + timedelta(days=30))
    assert "Transcript access" not in body, "far tiers: the date is the message"

    _, body = _msg("8821", base, base + timedelta(days=7))
    assert "Transcript access for this client stops" in body

    # The transcript gate checks 8821, so a 2848 must not claim it.
    _, body = _msg("2848", base, base + timedelta(days=7))
    assert "Transcript access" not in body
    assert "Representation authority for this client ends" in body
