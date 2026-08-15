# tests/test_settings_blob_readers.py

"""
Characterization tests for the surviving NON FEE readers of Firm.settings.

Written during the fee blob writer retirement session. The blob inventory
(blob_inventory_report.md, August 14 2026) found ZERO direct test coverage of
Firm.settings anywhere in the test tree: no test read or wrote the blob, so if
a change broke the login session timeout read or the portal branding read,
nothing would have gone red. That is process rules instance nine, an absent
watcher rather than a passing one. This file is the watcher.

These tests pin CURRENT behavior, deliberately. They are not a specification of
what the readers should do; they are a record of what they did before the fee
pathway was cut out, so that any future change to the blob has to argue with
them explicitly.

Every reader is exercised under all THREE blob states, because all three are
real:
  - populated, with the relevant keys present
  - empty, the literal {} that every dev row carries
  - NULL, which is a real production state (Cedar and Vance has settings NULL,
    not {}), and is the state a naive `firm.settings["key"]` reader would crash
    on

The helper below sets the blob with raw SQL and then reads it back and asserts
the state actually landed. That check is not ceremony. A NULL blob test that
silently ran against {} would be green while measuring the wrong world, which
is the exact failure shape section 1 of How_We_Work_Process_Rules.md exists to
catch. The model declares `default=dict`, so the ORM cannot be trusted to
produce a genuine NULL here.
"""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jose import jwt
from sqlalchemy import text

from app.core.config import get_settings
from app.core.enums import TriggerEvent, UserRole
from app.core.security import get_password_hash
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Blob state helper
# ---------------------------------------------------------------------------

POPULATED = "populated"
EMPTY = "empty"
NULL = "null"


def _set_settings_blob(firm_id, value):
    """Force Firm.settings to an exact state, then prove the state landed.

    value is either a dict (written as JSON) or None (written as SQL NULL).
    Raw SQL rather than the ORM because Firm.settings declares default=dict,
    so an ORM assignment is not a reliable way to produce a real NULL.

    Reads the column back as text and asserts it matches what was asked for.
    Without that readback a test could claim to cover the NULL case while
    actually running against {}.
    """
    db = TestingSessionLocal()
    try:
        if value is None:
            db.execute(
                text("UPDATE firms SET settings = NULL WHERE id = CAST(:fid AS uuid)"),
                {"fid": str(firm_id)},
            )
        else:
            db.execute(
                text(
                    "UPDATE firms SET settings = CAST(:val AS json) "
                    "WHERE id = CAST(:fid AS uuid)"
                ),
                {"fid": str(firm_id), "val": json.dumps(value)},
            )
        db.commit()
        raw = db.execute(
            text("SELECT settings::text FROM firms WHERE id = CAST(:fid AS uuid)"),
            {"fid": str(firm_id)},
        ).scalar_one()
    finally:
        db.close()

    if value is None:
        assert raw is None, (
            f"blob state did not land: asked for SQL NULL, column reads {raw!r}. "
            "This test would otherwise have measured the wrong blob state."
        )
    else:
        assert raw is not None, (
            "blob state did not land: asked for a populated blob, column is NULL"
        )
        assert json.loads(raw) == value, (
            f"blob state did not land: asked for {value!r}, column reads {raw!r}"
        )
    return raw


def _blob_for(state, populated_value):
    """Map a state label to the blob value to write."""
    if state == POPULATED:
        return populated_value
    if state == EMPTY:
        return {}
    if state == NULL:
        return None
    raise AssertionError(f"unknown blob state {state!r}")


ALL_STATES = [POPULATED, EMPTY, NULL]
DEFAULTING_STATES = [EMPTY, NULL]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def blob_firm():
    """A firm plus a firm_owner whose credentials the login tests reuse.

    Deliberately not the shared firm_a_owner fixture: these tests need to set
    the blob BEFORE logging in, and firm_a_owner logs in during setup.
    """
    from app.models.firm import Firm
    from app.models.user import User

    suffix = uuid.uuid4().hex[:8]
    email = f"blob-owner-{suffix}@example.com"
    password = "blobpassword123"

    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Blob Reader Firm {suffix}", slug=f"blob-reader-{suffix}")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        firm_id = str(firm.id)

        user = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash(password),
            full_name="Blob Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()

    return {"firm_id": firm_id, "email": email, "password": password}


# ---------------------------------------------------------------------------
# 1. Login flow reads (app/services/auth_service.py)
#    session_timeout_minutes and password_policy.max_failed_attempts
# ---------------------------------------------------------------------------

class TestLoginSessionTimeoutRead:
    """auth_service line 158: firm_settings.get('session_timeout_minutes', app default)."""

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_app_default_timeout_applies_and_login_succeeds(self, client, blob_firm, state):
        """Empty and NULL blobs both fall back to ACCESS_TOKEN_EXPIRE_MINUTES."""
        _set_settings_blob(blob_firm["firm_id"], _blob_for(state, None))
        expected_minutes = get_settings().ACCESS_TOKEN_EXPIRE_MINUTES

        before = datetime.now(timezone.utc)
        r = client.post(
            "/auth/token",
            json={"username": blob_firm["email"], "password": blob_firm["password"]},
        )

        assert r.status_code == 200, f"login failed on {state} blob: {r.text}"
        claims = jwt.get_unverified_claims(r.json()["access_token"])
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        minutes = (exp - before).total_seconds() / 60
        assert abs(minutes - expected_minutes) < 2, (
            f"{state} blob produced a {minutes:.1f} minute token, "
            f"expected the app default of {expected_minutes}"
        )

    def test_populated_timeout_overrides_the_app_default(self, client, blob_firm):
        """A populated session_timeout_minutes wins over the app default."""
        override = 15
        assert override != get_settings().ACCESS_TOKEN_EXPIRE_MINUTES, (
            "pick an override that differs from the app default or this test proves nothing"
        )
        _set_settings_blob(blob_firm["firm_id"], {"session_timeout_minutes": override})

        before = datetime.now(timezone.utc)
        r = client.post(
            "/auth/token",
            json={"username": blob_firm["email"], "password": blob_firm["password"]},
        )

        assert r.status_code == 200, r.text
        claims = jwt.get_unverified_claims(r.json()["access_token"])
        exp = datetime.fromtimestamp(claims["exp"], tz=timezone.utc)
        minutes = (exp - before).total_seconds() / 60
        assert abs(minutes - override) < 2, (
            f"populated blob produced a {minutes:.1f} minute token, expected {override}"
        )


class TestLoginMaxFailedAttemptsRead:
    """auth_service line 106: password_policy.max_failed_attempts, default 5."""

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_default_of_five_attempts_applies(self, client, blob_firm, state):
        """Empty and NULL blobs both lock on the fifth consecutive failure."""
        _set_settings_blob(blob_firm["firm_id"], _blob_for(state, None))

        for attempt in range(1, 5):
            r = client.post(
                "/auth/token",
                json={"username": blob_firm["email"], "password": "wrongpassword"},
            )
            assert r.status_code == 401, (
                f"{state} blob locked early on attempt {attempt}: {r.status_code}"
            )

        r = client.post(
            "/auth/token",
            json={"username": blob_firm["email"], "password": "wrongpassword"},
        )
        assert r.status_code == 403, (
            f"{state} blob did not lock on the fifth attempt: {r.status_code} {r.text}"
        )

    def test_populated_policy_overrides_the_default(self, client, blob_firm):
        """max_failed_attempts of 2 locks on the second failure, not the fifth."""
        _set_settings_blob(
            blob_firm["firm_id"],
            {"password_policy": {"max_failed_attempts": 2}},
        )

        r1 = client.post(
            "/auth/token",
            json={"username": blob_firm["email"], "password": "wrongpassword"},
        )
        assert r1.status_code == 401, r1.text

        r2 = client.post(
            "/auth/token",
            json={"username": blob_firm["email"], "password": "wrongpassword"},
        )
        assert r2.status_code == 403, (
            f"populated policy did not lock on the second attempt: {r2.status_code}"
        )


# ---------------------------------------------------------------------------
# 2. EmailService.get_firm_email_settings (app/services/email_service.py:89)
#    email_reply_to and email_display_name
# ---------------------------------------------------------------------------

class TestEmailSettingsReader:

    def _firm(self, firm_id):
        from app.models.firm import Firm
        db = TestingSessionLocal()
        try:
            return db.query(Firm).filter(Firm.id == uuid.UUID(firm_id)).first()
        finally:
            db.close()

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_falls_back_to_none_without_raising(self, blob_firm, state):
        """Empty and NULL blobs yield None for both keys, and do not raise."""
        from app.services.email_service import EmailService

        _set_settings_blob(blob_firm["firm_id"], _blob_for(state, None))
        firm = self._firm(blob_firm["firm_id"])

        result = EmailService.get_firm_email_settings(firm)

        assert result["reply_to"] is None, f"{state} blob returned {result['reply_to']!r}"
        assert result["display_name"] is None, f"{state} blob returned {result['display_name']!r}"
        # sending_domain is NOT a blob key. It comes from real columns and is
        # gated on sending_domain_verified. Pinned here so a future change that
        # moves it into the blob has to break this line first.
        assert result["sending_domain"] is None

    def test_populated_values_are_returned(self, blob_firm):
        from app.services.email_service import EmailService

        _set_settings_blob(
            blob_firm["firm_id"],
            {
                "email_reply_to": "replies@example.com",
                "email_display_name": "Example CPA",
            },
        )
        firm = self._firm(blob_firm["firm_id"])

        result = EmailService.get_firm_email_settings(firm)

        assert result["reply_to"] == "replies@example.com"
        assert result["display_name"] == "Example CPA"

    def test_empty_string_values_are_normalised_to_none(self, blob_firm):
        """The reader uses `or None`, so empty strings collapse to None.

        Pinned because it is the one place the blob's ambiguous-empty-value
        problem is already handled, and it should not silently change.
        """
        from app.services.email_service import EmailService

        _set_settings_blob(
            blob_firm["firm_id"],
            {"email_reply_to": "", "email_display_name": ""},
        )
        firm = self._firm(blob_firm["firm_id"])

        result = EmailService.get_firm_email_settings(firm)

        assert result["reply_to"] is None
        assert result["display_name"] is None


# ---------------------------------------------------------------------------
# 3. portal_me branding reads (app/api/portal.py:535)
#    portal_logo_s3_key, portal_mode, portal_colors_light,
#    portal_colors_dark, portal_display_name
# ---------------------------------------------------------------------------

class TestPortalMeBrandingReads:

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_returns_dark_defaults_without_erroring(
        self, client, firm_a_owner, portal_client_headers, state
    ):
        """Empty and NULL blobs both render the dark default palette."""
        _set_settings_blob(firm_a_owner["firm_id"], _blob_for(state, None))
        _client_id, headers = portal_client_headers

        r = client.get("/portal/me", headers=headers)

        assert r.status_code == 200, f"{state} blob broke portal_me: {r.text}"
        data = r.json()
        assert data["portal_mode"] == "dark"
        assert data["portal_top_bar_color"] == "#1A2535"
        assert data["portal_page_color"] == "#2D2D2D"
        assert data["portal_text_primary"] == "#EDEEF0"
        assert data["portal_logo_url"] is None
        # Falls back to the firm name, which is a real column not a blob key.
        assert data["portal_display_name"] == "Firm A CPA"

    def test_populated_branding_overrides_defaults(
        self, client, firm_a_owner, portal_client_headers
    ):
        _set_settings_blob(
            firm_a_owner["firm_id"],
            {
                "portal_mode": "light",
                "portal_display_name": "Branded Portal",
                "portal_logo_s3_key": "firms/logo/example.png",
                "portal_colors_light": {"top_bar": "#ABCDEF"},
            },
        )
        _client_id, headers = portal_client_headers

        r = client.get("/portal/me", headers=headers)

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["portal_mode"] == "light"
        assert data["portal_display_name"] == "Branded Portal"
        assert data["portal_logo_url"] is not None
        # The one supplied colour wins, the rest still come from light defaults.
        assert data["portal_top_bar_color"] == "#ABCDEF"
        assert data["portal_page_color"] == "#E4E6EA"

    def test_partial_colour_dict_merges_over_defaults(
        self, client, firm_a_owner, portal_client_headers
    ):
        """A partial portal_colors_dark merges rather than replacing the palette."""
        _set_settings_blob(
            firm_a_owner["firm_id"],
            {"portal_colors_dark": {"accent": "#123456"}},
        )
        _client_id, headers = portal_client_headers

        r = client.get("/portal/me", headers=headers)

        assert r.status_code == 200, r.text
        data = r.json()
        assert data["portal_accent_color"] == "#123456"
        assert data["portal_card_color"] == "#383838"


# ---------------------------------------------------------------------------
# 4. Esign reminder day readers
#    dashboard section (app/api/dashboard.py:232) and
#    esign_reminder_service (app/services/esign_reminder_service.py:41,117)
# ---------------------------------------------------------------------------

def _make_sent_envelope(firm_id, days_ago, reminder_count=0, last_reminder_days_ago=None):
    """One client plus one envelope in 'sent' state, sent days_ago days back."""
    from app.models.client import Client
    from app.models.signature_envelope import SignatureEnvelope

    now = datetime.now(timezone.utc)
    db = TestingSessionLocal()
    try:
        the_client = Client(
            firm_id=uuid.UUID(firm_id),
            name="Esign Test Client",
            email=f"esign-{uuid.uuid4().hex[:8]}@example.com",
        )
        db.add(the_client)
        db.commit()
        db.refresh(the_client)

        envelope = SignatureEnvelope(
            firm_id=uuid.UUID(firm_id),
            client_id=the_client.id,
            status="sent",
            subject="Engagement letter",
            provider_envelope_id=f"env-{uuid.uuid4().hex[:8]}",
            signers=[{"name": "Signer", "email": "signer@example.com"}],
            sent_at=now - timedelta(days=days_ago),
            reminder_count=reminder_count,
            last_reminder_sent_at=(
                now - timedelta(days=last_reminder_days_ago)
                if last_reminder_days_ago is not None
                else None
            ),
        )
        db.add(envelope)
        db.commit()
        db.refresh(envelope)
        return str(envelope.id)
    finally:
        db.close()


class TestDashboardEsignReminderDayReads:
    """dashboard.py:235-237, defaults 2 / 4 / 3.

    The section drops rows whose reminder_state is 'too_new', so an envelope
    sent 3 days ago is visible under the default first_days of 2 and invisible
    under a configured first_days of 10. That difference is what proves the
    default is genuinely being read rather than the row being absent for some
    unrelated reason.
    """

    def _section(self, firm_id):
        from app.api.dashboard import _get_unsigned_documents_section
        from app.models.firm import Firm

        db = TestingSessionLocal()
        try:
            firm = db.query(Firm).filter(Firm.id == uuid.UUID(firm_id)).first()
            return _get_unsigned_documents_section(db, firm)
        finally:
            db.close()

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_default_first_reminder_days_of_two_applies(self, blob_firm, state):
        _set_settings_blob(blob_firm["firm_id"], _blob_for(state, None))
        _make_sent_envelope(blob_firm["firm_id"], days_ago=3)

        section = self._section(blob_firm["firm_id"])

        assert section["unsigned_document_count"] == 1, (
            f"{state} blob: envelope sent 3 days ago should be ready under the "
            f"default first_days of 2, got {section['unsigned_document_count']}"
        )
        assert section["unsigned_documents"][0].reminder_state == "ready_first"

    def test_populated_first_reminder_days_suppresses_the_row(self, blob_firm):
        """first_days of 10 makes the same 3 day old envelope 'too_new'."""
        _set_settings_blob(blob_firm["firm_id"], {"esign_first_reminder_days": 10})
        _make_sent_envelope(blob_firm["firm_id"], days_ago=3)

        section = self._section(blob_firm["firm_id"])

        assert section["unsigned_document_count"] == 0, (
            "configured first_days of 10 should have suppressed a 3 day old envelope"
        )

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_default_second_reminder_days_of_four_applies(self, blob_firm, state):
        """reminder_count 1 with a 5 day old reminder is ready under default 4."""
        _set_settings_blob(blob_firm["firm_id"], _blob_for(state, None))
        _make_sent_envelope(
            blob_firm["firm_id"], days_ago=10, reminder_count=1, last_reminder_days_ago=5
        )

        section = self._section(blob_firm["firm_id"])

        assert section["unsigned_document_count"] == 1, f"{state} blob"
        assert section["unsigned_documents"][0].reminder_state == "ready_second"

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_default_escalation_days_of_three_applies(self, blob_firm, state):
        """reminder_count 2 with a 5 day old reminder escalates under default 3."""
        _set_settings_blob(blob_firm["firm_id"], _blob_for(state, None))
        _make_sent_envelope(
            blob_firm["firm_id"], days_ago=12, reminder_count=2, last_reminder_days_ago=5
        )

        section = self._section(blob_firm["firm_id"])

        assert section["unsigned_document_count"] == 1, f"{state} blob"
        assert section["unsigned_documents"][0].reminder_state == "escalated"

    def test_populated_escalation_days_holds_the_row_in_cooldown(self, blob_firm):
        _set_settings_blob(blob_firm["firm_id"], {"esign_escalation_days": 30})
        _make_sent_envelope(
            blob_firm["firm_id"], days_ago=12, reminder_count=2, last_reminder_days_ago=5
        )

        section = self._section(blob_firm["firm_id"])

        assert section["unsigned_document_count"] == 0, (
            "configured escalation_days of 30 should have held the row in cooldown"
        )


class TestEsignReminderServiceDayReads:
    """esign_reminder_service.py:41, esign_first_reminder_days, default 2.

    run_esign_auto_reminders swallows every exception by design, so asserting
    that it 'does not error' proves nothing at all. The only meaningful
    assertion is behavioral: whether the provider was asked to send a reminder.
    """

    def _enable_rule(self, firm_id):
        from app.models.automation_rule import AutomationRule

        db = TestingSessionLocal()
        try:
            rule = AutomationRule(
                firm_id=uuid.UUID(firm_id),
                name="E-Signature Reminder (2-day)",
                is_enabled=True,
                trigger_event=TriggerEvent.esign_sent,
            )
            db.add(rule)
            db.commit()
        finally:
            db.close()

    def _run_capturing_reminders(self, monkeypatch):
        from app.services import dropbox_sign
        from app.services import esign_reminder_service

        sent = []

        def _fake_send_reminder(signature_request_id, signer_email=None):
            sent.append(
                {"signature_request_id": signature_request_id, "signer_email": signer_email}
            )

        monkeypatch.setattr(dropbox_sign, "send_reminder", _fake_send_reminder)
        esign_reminder_service.run_esign_auto_reminders()
        return sent

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_default_of_two_days_sends_the_reminder(self, blob_firm, monkeypatch, state):
        _set_settings_blob(blob_firm["firm_id"], _blob_for(state, None))
        self._enable_rule(blob_firm["firm_id"])
        _make_sent_envelope(blob_firm["firm_id"], days_ago=3)

        sent = self._run_capturing_reminders(monkeypatch)

        assert len(sent) == 1, (
            f"{state} blob: a 3 day old envelope should trigger a reminder under "
            f"the default first_days of 2, captured {sent!r}"
        )

    def test_populated_days_suppress_the_reminder(self, blob_firm, monkeypatch):
        _set_settings_blob(blob_firm["firm_id"], {"esign_first_reminder_days": 10})
        self._enable_rule(blob_firm["firm_id"])
        _make_sent_envelope(blob_firm["firm_id"], days_ago=3)

        sent = self._run_capturing_reminders(monkeypatch)

        assert sent == [], (
            "configured first_days of 10 should have suppressed the reminder"
        )


# ---------------------------------------------------------------------------
# 5. The three settings tab endpoints that legitimately write NON FEE keys
#    still round trip. These are typed endpoints, so they cannot carry
#    fee_schedule at all, which is why they are not doors in phase 2.
# ---------------------------------------------------------------------------

def _read_blob(firm_id):
    db = TestingSessionLocal()
    try:
        raw = db.execute(
            text("SELECT settings::text FROM firms WHERE id = CAST(:fid AS uuid)"),
            {"fid": str(firm_id)},
        ).scalar_one()
    finally:
        db.close()
    return json.loads(raw) if raw is not None else None


class TestSettingsTabRoundTrips:

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_review_settings_round_trip(self, client, firm_a_owner, state):
        """PATCH /settings/review writes google_review_url from empty and NULL."""
        _set_settings_blob(firm_a_owner["firm_id"], _blob_for(state, None))

        r = client.patch(
            "/settings/review",
            json={"google_review_url": "https://example.com/review"},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, f"{state} blob: {r.text}"
        assert _read_blob(firm_a_owner["firm_id"])["google_review_url"] == (
            "https://example.com/review"
        )

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_email_calendar_sync_round_trip(self, client, firm_a_owner, state):
        _set_settings_blob(firm_a_owner["firm_id"], _blob_for(state, None))

        r = client.patch(
            "/settings/email-calendar-sync",
            json={"email_sync_enabled": False, "calendar_sync_enabled": True},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, f"{state} blob: {r.text}"
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["email_sync_enabled"] is False
        assert blob["calendar_sync_enabled"] is True

    @pytest.mark.parametrize("state", DEFAULTING_STATES)
    def test_email_settings_round_trip(self, client, firm_a_owner, state):
        _set_settings_blob(firm_a_owner["firm_id"], _blob_for(state, None))

        r = client.patch(
            "/settings/email",
            json={"reply_to": "replies@example.com", "display_name": "Example CPA"},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, f"{state} blob: {r.text}"
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["email_reply_to"] == "replies@example.com"
        assert blob["email_display_name"] == "Example CPA"

    def test_settings_tabs_preserve_unrelated_keys(self, client, firm_a_owner):
        """Each tab merges into the blob rather than replacing it.

        These three endpoints already merge correctly. Pinned here so the
        phase 2 merge work on the firm PATCH doors cannot regress them, and so
        the contrast with the wholesale replace footgun is on the record.
        """
        _set_settings_blob(
            firm_a_owner["firm_id"],
            {"portal_display_name": "Keep Me", "session_timeout_minutes": 45},
        )

        r = client.patch(
            "/settings/email",
            json={"reply_to": "replies@example.com", "display_name": "Example CPA"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, r.text

        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["portal_display_name"] == "Keep Me"
        assert blob["session_timeout_minutes"] == 45
        assert blob["email_reply_to"] == "replies@example.com"
