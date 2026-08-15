# tests/test_google_oauth_scopes.py

"""
Tripwire for the Google OAuth descope of August 15 2026.

gmail.readonly and gmail.send were removed from the requested scope list. The
app no longer asks for mailbox access at all. Calendar and identity scopes stay,
because the Google calendar integration rides this same grant: there is no
separate calendar OAuth flow, so dropping calendar.readonly would break it.

The failure this guards against is quiet. A scope added back to the list costs
nothing visible at development time; it only shows up as a broader consent
screen in front of a real firm owner, and as mailbox access this product no
longer claims to need. Nothing else in the codebase would go red.

Paired with that, email sync ships DISABLED by default. Before this session
nothing in the backend read email_sync_enabled at all: the settings tab wrote
it, the frontend treated anything other than an explicit false as enabled, and
the daily sweep ran for every connected integration regardless of the toggle.
"""

import uuid

import pytest

from app.services.firm_settings import is_email_sync_enabled
from app.services.gmail_service import GMAIL_SCOPES


GMAIL_SCOPE_PREFIX = "https://www.googleapis.com/auth/gmail"


class SweepReachedCredentials(Exception):
    """Sentinel raised in place of the sweep's credential fetch."""


class TestRequestedGoogleScopes:

    def test_no_gmail_scope_is_requested(self):
        """The load bearing assertion. Prefix match, so any gmail scope trips it."""
        offenders = [s for s in GMAIL_SCOPES if s.startswith(GMAIL_SCOPE_PREFIX)]

        assert offenders == [], (
            f"Gmail scopes are requested again: {offenders}. Mailbox access was "
            "descoped on August 15 2026. If this is a deliberate reversal, retire "
            "this test on purpose rather than deleting the assertion."
        )

    def test_calendar_scope_is_still_requested(self):
        """Descoping Gmail must not take calendar with it.

        The counterweight to the test above. Deleting the whole scope list would
        satisfy a no-gmail-scopes assertion perfectly, so the thing that must
        survive is pinned too.
        """
        assert "https://www.googleapis.com/auth/calendar.readonly" in GMAIL_SCOPES

    def test_identity_scopes_are_still_requested(self):
        assert "https://www.googleapis.com/auth/userinfo.email" in GMAIL_SCOPES
        assert "openid" in GMAIL_SCOPES

    def test_the_authorization_url_carries_no_gmail_scope(self):
        """Reads the constant through the flow that actually builds the URL.

        Asserting on the constant alone would not notice a scope injected at
        flow construction time. This checks the string Google would receive.
        """
        from app.services.gmail_service import GmailService

        url = GmailService().get_authorization_url(uuid.uuid4(), uuid.uuid4())

        assert "gmail.readonly" not in url, f"gmail.readonly present in {url}"
        assert "gmail.send" not in url, f"gmail.send present in {url}"
        assert "calendar.readonly" in url, "calendar scope missing from the consent URL"


class TestEmailSyncDefaultsToDisabled:
    """is_email_sync_enabled, default False."""

    class _Firm:
        def __init__(self, settings):
            self.settings = settings

    @pytest.mark.parametrize("settings", [None, {}, {"calendar_sync_enabled": True}])
    def test_absent_empty_and_null_all_mean_disabled(self, settings):
        assert is_email_sync_enabled(self._Firm(settings)) is False

    def test_explicit_false_means_disabled(self):
        assert is_email_sync_enabled(self._Firm({"email_sync_enabled": False})) is False

    def test_explicit_true_means_enabled(self):
        assert is_email_sync_enabled(self._Firm({"email_sync_enabled": True})) is True

    @pytest.mark.parametrize("value", ["true", 1, "yes", {}, []])
    def test_non_boolean_values_do_not_count_as_consent(self, value):
        """Identity against True, not truthiness.

        The blob is unvalidated and accepts any JSON, so a stray string or
        number must not be read as permission to sync a firm's mailbox.
        """
        firm = self._Firm({"email_sync_enabled": value})
        assert is_email_sync_enabled(firm) is False


class TestSweepHonoursTheGate:
    """The gate is wired into the sweep, not merely defined.

    A helper nothing calls is the absent watcher problem in miniature.

    The firm here is given a CONNECTED gmail integration deliberately. An
    earlier version of this test used a firm with no integration, and the
    negative control showed it stayed green with the gate removed, because the
    sweep returned early at the integration check either way. It was measuring
    something adjacent. With a connected integration in place, the only thing
    that can stop the sweep before it reaches for credentials is the gate.
    """

    def _connect_gmail(self, firm_id):
        from app.models.integration import Integration
        from tests.conftest import TestingSessionLocal

        db = TestingSessionLocal()
        try:
            db.add(Integration(
                firm_id=uuid.UUID(firm_id),
                provider="gmail",
                status="connected",
                encrypted_access_token="not-a-real-token",
            ))
            db.commit()
        finally:
            db.close()

    def _run_sweep(self, firm_id, monkeypatch):
        """Run the sweep with the credential step replaced by a raising sentinel.

        It raises rather than returns because the sweep's own handler catches
        any exception there and returns early with the exception name in
        errors. That gives a clean, observable stopping point one step past the
        gate, without letting the run continue into the real Google client.
        """
        from app.services import gmail_signals_service
        from tests.conftest import TestingSessionLocal

        reached = []

        def _sentinel(integration):
            reached.append(1)
            raise SweepReachedCredentials()

        monkeypatch.setattr(gmail_signals_service, "get_fresh_credentials", _sentinel)
        db = TestingSessionLocal()
        try:
            result = gmail_signals_service.extract_gmail_signals(uuid.UUID(firm_id), db)
        finally:
            db.close()
        return result, reached

    def test_sweep_skips_a_firm_with_sync_disabled(self, firm_a_owner, monkeypatch):
        self._connect_gmail(firm_a_owner["firm_id"])

        result, reached = self._run_sweep(firm_a_owner["firm_id"], monkeypatch)

        assert reached == [], (
            "credentials were fetched for a firm with email sync disabled, so "
            "the gate is not in the sweep"
        )
        assert result["threads_processed"] == 0
        assert result["clients_with_signals"] == 0

    def test_sweep_proceeds_past_the_gate_when_sync_is_enabled(
        self, firm_a_owner, monkeypatch
    ):
        """The counterweight: proves the skip above is the gate and not the setup.

        With sync explicitly enabled the sweep must get past the gate and reach
        for credentials. Without this, a sweep that was broken outright, or a
        gate that refused everything unconditionally, would satisfy the test
        above perfectly.
        """
        from tests.test_settings_blob_readers import _set_settings_blob

        self._connect_gmail(firm_a_owner["firm_id"])
        _set_settings_blob(firm_a_owner["firm_id"], {"email_sync_enabled": True})

        result, reached = self._run_sweep(firm_a_owner["firm_id"], monkeypatch)

        assert reached == [1], (
            "sweep did not reach the credential step with email sync enabled, so "
            "the skip test above proves nothing"
        )
        assert result["errors"] == ["SweepReachedCredentials"]
