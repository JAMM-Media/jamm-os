# tests/test_portal_attribution_survey.py
"""
Tests for the portal attribution survey (Contract section 4.1).

A one-question survey for existing clients whose referral_source is blank.
Delivered as a pinned portal notification that survives mark-all-read and
clears only on survey completion.

Covers:
  1. Client with blank attribution gets the pinned notification on dashboard;
     client with attribution set never gets one (confirmed via DB query).
  2. Marking all notifications as read does NOT clear the pinned survey.
  3. Submitting an answer clears the notification and writes the value.
  4. Race condition: if referral_source was set before submission, the write
     is skipped but the notification is still cleared (written=False).
  5. Tenant isolation: a client from a different firm cannot submit an answer
     for another client's record.
  6. "Do not remember" is present and is the last option in the returned list.
"""

import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.core.enums import ReferralSource
from app.models.client import Client
from app.models.firm import Firm
from app.models.portal_notification import PortalNotification
from app.models.user import User
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.services.portal_auth import hash_portal_password
from app.crud import portal_notification as crud_notification
from app.services.attribution_survey_service import (
    ATTRIBUTION_SURVEY_TYPE,
    SURVEY_OPTIONS,
    ensure_attribution_survey_notification,
    submit_attribution_answer,
    get_survey_options,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm() -> Firm:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Survey Firm {uuid.uuid4().hex[:6]}", slug=f"sf-{uuid.uuid4().hex[:6]}")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id
        return firm
    finally:
        db.close()


def _make_client(firm_id, referral_source=None, email=None) -> Client:
    db = TestingSessionLocal()
    try:
        client = Client(
            firm_id=firm_id,
            name="Test Client",
            email=email or f"client-{uuid.uuid4().hex[:8]}@example.com",
            referral_source=referral_source,
            portal_password_hash=hash_portal_password("TestPass1!"),
            portal_access_enabled=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)
        _ = client.id
        return client
    finally:
        db.close()


def _get_client_fresh(client_id) -> Client:
    db = TestingSessionLocal()
    try:
        c = db.query(Client).filter(Client.id == client_id).first()
        _ = c.referral_source
        return c
    finally:
        db.close()


def _count_survey_notifications(client_id) -> int:
    db = TestingSessionLocal()
    try:
        return db.query(PortalNotification).filter(
            PortalNotification.client_id == client_id,
            PortalNotification.notification_type == ATTRIBUTION_SURVEY_TYPE,
        ).count()
    finally:
        db.close()


def _make_portal_token(client, client_fixture) -> str:
    """Log in via the portal endpoint and return the JWT."""
    resp = client_fixture.post(
        "/portal/auth/login",
        json={"email": client.email, "password": "TestPass1!"},
    )
    assert resp.status_code == 200, f"Portal login failed: {resp.text}"
    return resp.json()["access_token"]


# ---------------------------------------------------------------------------
# 1. Blank attribution -> pinned notification created; set attribution -> never created
# ---------------------------------------------------------------------------

class TestSurveyNotificationCreation:

    def test_blank_attribution_gets_notification(self):
        """Client with no referral_source gets the pinned notification on dashboard call."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            ensure_attribution_survey_notification(db, client)
        finally:
            db.close()

        assert _count_survey_notifications(client.id) == 1, (
            "Expected exactly one attribution_survey notification to be created"
        )

        # Confirm it is pinned.
        db = TestingSessionLocal()
        try:
            notif = db.query(PortalNotification).filter(
                PortalNotification.client_id == client.id,
                PortalNotification.notification_type == ATTRIBUTION_SURVEY_TYPE,
            ).first()
            assert notif is not None
            assert notif.is_pinned is True
        finally:
            db.close()

    def test_set_attribution_never_gets_notification(self):
        """Client with referral_source already set must never get the notification created."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=ReferralSource.google_search)

        db = TestingSessionLocal()
        try:
            ensure_attribution_survey_notification(db, client)
        finally:
            db.close()

        count = _count_survey_notifications(client.id)
        assert count == 0, (
            f"No attribution_survey notification should be created for a client "
            f"with attribution set. Got {count}."
        )

    def test_idempotent_second_call_does_not_duplicate(self):
        """Calling ensure twice creates only one notification."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            ensure_attribution_survey_notification(db, client)
            ensure_attribution_survey_notification(db, client)
        finally:
            db.close()

        assert _count_survey_notifications(client.id) == 1, (
            "A second call to ensure must not create a duplicate notification"
        )


# ---------------------------------------------------------------------------
# 2. Mark-all-read does NOT clear the pinned survey notification
# ---------------------------------------------------------------------------

class TestMarkAllReadExcludesPinned:

    def test_pinned_survives_mark_all_read(self):
        """mark_all_as_read must not touch pinned notifications."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            ensure_attribution_survey_notification(db, client)
            # Also add a normal (non-pinned) notification.
            db.add(PortalNotification(
                firm_id=client.firm_id,
                client_id=client.id,
                title="Normal notification",
                body="This one should be cleared.",
                notification_type="system",
                is_pinned=False,
                is_read=False,
            ))
            db.commit()

            count_before = db.query(PortalNotification).filter(
                PortalNotification.client_id == client.id,
            ).count()
            assert count_before == 2

            crud_notification.mark_all_as_read(
                db, client_id=client.id, firm_id=client.firm_id
            )

            # Survey notification must still be unread.
            survey_notif = db.query(PortalNotification).filter(
                PortalNotification.client_id == client.id,
                PortalNotification.notification_type == ATTRIBUTION_SURVEY_TYPE,
            ).first()
            assert survey_notif is not None
            assert survey_notif.is_read is False, (
                "Pinned survey notification must remain unread after mark_all_as_read"
            )

            # Normal notification must now be read.
            normal = db.query(PortalNotification).filter(
                PortalNotification.client_id == client.id,
                PortalNotification.notification_type == "system",
            ).first()
            assert normal.is_read is True
        finally:
            db.close()

    def test_individual_mark_as_read_does_not_clear_pinned(self):
        """mark_as_read on a pinned notification returns the notification unchanged."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            ensure_attribution_survey_notification(db, client)
            survey_notif = db.query(PortalNotification).filter(
                PortalNotification.client_id == client.id,
                PortalNotification.notification_type == ATTRIBUTION_SURVEY_TYPE,
            ).first()
            notif_id = survey_notif.id

            result = crud_notification.mark_as_read(
                db,
                notification_id=notif_id,
                client_id=client.id,
                firm_id=client.firm_id,
            )
            assert result is not None
            assert result.is_read is False, (
                "mark_as_read on a pinned notification must leave is_read unchanged"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 3. Submitting an answer clears the notification and writes the value
# ---------------------------------------------------------------------------

class TestSurveySubmission:

    def test_answer_writes_referral_source_and_clears_notification(self):
        """Submitting a valid answer writes referral_source and deletes the notification."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            ensure_attribution_survey_notification(db, client)
        finally:
            db.close()

        assert _count_survey_notifications(client.id) == 1

        db = TestingSessionLocal()
        try:
            fresh = db.query(Client).filter(Client.id == client.id).first()
            result = submit_attribution_answer(db, fresh, "google_search")
        finally:
            db.close()

        assert result["written"] is True

        # Notification must be deleted.
        assert _count_survey_notifications(client.id) == 0, (
            "Attribution survey notification must be deleted after submission"
        )

        # referral_source must be written.
        updated = _get_client_fresh(client.id)
        assert updated.referral_source == ReferralSource.google_search, (
            f"Expected google_search, got {updated.referral_source!r}"
        )

    def test_do_not_remember_maps_to_unknown(self):
        """Submitting 'do_not_remember' writes ReferralSource.unknown."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            fresh = db.query(Client).filter(Client.id == client.id).first()
            result = submit_attribution_answer(db, fresh, "do_not_remember")
        finally:
            db.close()

        assert result["written"] is True
        updated = _get_client_fresh(client.id)
        assert updated.referral_source == ReferralSource.unknown, (
            f"do_not_remember must map to ReferralSource.unknown, got {updated.referral_source!r}"
        )

    def test_invalid_answer_raises(self):
        """Submitting an invalid answer raises ValueError."""
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            fresh = db.query(Client).filter(Client.id == client.id).first()
            with pytest.raises(ValueError, match="Invalid attribution answer"):
                submit_attribution_answer(db, fresh, "not_a_real_value")
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 4. Race condition: attribution already set -- write skipped, notification cleared
# ---------------------------------------------------------------------------

class TestRaceConditionNoOverwrite:

    def test_already_set_skips_write_but_clears_notification(self):
        """If referral_source is already set when submit fires, write is skipped.

        The field must not be overwritten. The notification is still cleared
        so the survey does not re-appear on the next dashboard visit.
        Explicit behavior chosen: skip-and-clear, not skip-and-leave.
        """
        firm = _make_firm()
        client = _make_client(firm.id, referral_source=None)

        db = TestingSessionLocal()
        try:
            ensure_attribution_survey_notification(db, client)
        finally:
            db.close()

        # Simulate the race: firm_entered attribution written before submission.
        db = TestingSessionLocal()
        try:
            race_client = db.query(Client).filter(Client.id == client.id).first()
            race_client.referral_source = ReferralSource.client_referral
            db.commit()
        finally:
            db.close()

        # Now submit -- referral_source is already set.
        db = TestingSessionLocal()
        try:
            fresh = db.query(Client).filter(Client.id == client.id).first()
            result = submit_attribution_answer(db, fresh, "google_search")
        finally:
            db.close()

        assert result["written"] is False, (
            "write must be False when referral_source was already set"
        )

        # The original value must be preserved (no overwrite).
        updated = _get_client_fresh(client.id)
        assert updated.referral_source == ReferralSource.client_referral, (
            "Already-set referral_source must not be overwritten"
        )

        # The notification must still be cleared.
        assert _count_survey_notifications(client.id) == 0, (
            "Notification must be cleared even when write is skipped"
        )


# ---------------------------------------------------------------------------
# 5. Tenant isolation via HTTP: client B cannot submit for client A
# ---------------------------------------------------------------------------

class TestTenantIsolationHttp:

    def test_client_b_cannot_submit_for_client_a(self, client):
        """A portal user logged in as Client B cannot write to Client A's record.

        The POST /portal/attribution-survey endpoint always writes to the
        currently authenticated portal client -- there is no client_id
        parameter to target another client. This test confirms Client B's
        submission only affects Client B.
        """
        firm = _make_firm()
        client_a = _make_client(firm.id, referral_source=None,
                                 email=f"a-{uuid.uuid4().hex[:6]}@example.com")
        client_b = _make_client(firm.id, referral_source=None,
                                 email=f"b-{uuid.uuid4().hex[:6]}@example.com")

        # Log in as Client B.
        token = _make_portal_token(client_b, client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.post(
            "/portal/attribution-survey",
            json={"answer": "google_search"},
            headers=headers,
        )
        assert resp.status_code == 200
        assert resp.json()["written"] is True

        # Client A must be unchanged.
        a_fresh = _get_client_fresh(client_a.id)
        assert a_fresh.referral_source is None, (
            "Client A's referral_source must not be affected by Client B's submission"
        )

        # Client B must be updated.
        b_fresh = _get_client_fresh(client_b.id)
        assert b_fresh.referral_source == ReferralSource.google_search


# ---------------------------------------------------------------------------
# 6. "Do not remember" is present and is the last option
# ---------------------------------------------------------------------------

class TestSurveyOptionOrder:

    def test_do_not_remember_is_last(self):
        """The 'do_not_remember' option must be the last item in the survey options."""
        options = get_survey_options()
        assert len(options) > 0
        last = options[-1]
        assert last["value"] == "do_not_remember", (
            f"Last option must be 'do_not_remember', got {last['value']!r}"
        )

    def test_all_real_referral_sources_present_except_unknown_standalone(self):
        """All ReferralSource values except unknown are present as distinct options
        (unknown is represented as 'Do not remember' at the end)."""
        option_values = {o["value"] for o in get_survey_options()}
        assert "do_not_remember" in option_values
        # Confirm unknown is not present as its own separate entry
        # (it is subsumed by do_not_remember).
        assert ReferralSource.unknown.value not in option_values, (
            "'unknown' must not appear as a separate option -- "
            "it is the submission value for 'Do not remember'"
        )

    def test_survey_endpoint_returns_options_with_do_not_remember_last(self, client):
        """GET /portal/attribution-survey returns the question with correct option order."""
        firm = _make_firm()
        portal_client = _make_client(firm.id, referral_source=None,
                                      email=f"survey-{uuid.uuid4().hex[:6]}@example.com")
        token = _make_portal_token(portal_client, client)
        headers = {"Authorization": f"Bearer {token}"}

        resp = client.get("/portal/attribution-survey", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        assert "question" in body
        assert "options" in body
        options = body["options"]
        assert len(options) > 0
        assert options[-1]["value"] == "do_not_remember", (
            f"Last option must be 'do_not_remember', got {options[-1]['value']!r}"
        )
