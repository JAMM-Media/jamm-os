# tests/test_postmark_inbound_webhook.py

"""
Tests for the Postmark inbound webhook (POST /webhooks/postmark-inbound).
Unauthenticated attack surface protected by HTTPBasic -- highest priority
per Andrew's directive.

Covers:
  - Auth verification: no credentials (401), wrong credentials (401)
  - Happy path: LeadMessage created with correct fields, behavioral event fired
  - Unmatched lead: 200 returned (avoid Postmark retry storms), no row created
  - Malformed MailboxHash: safe 200, no row, no crash
  - Cross-firm safety: message scoped to correct firm, zero rows under other firm
"""

import time
import uuid

import pytest

from tests.conftest import TestingSessionLocal
from app.models.enrollment import Enrollment
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.lead_message import LeadMessage
from app.models.notification import Notification
from app.models.sequence import Sequence, SequenceVersion
from app.models.user import User
from app.core.enums import EnrollmentStatus, LeadProvenance, NotificationType, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str, name: str) -> Firm:
    """Create a Firm directly in the test DB."""
    db = TestingSessionLocal()
    try:
        firm = Firm(name=name, slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        _ = firm.id, firm.name, firm.slug
        return firm
    finally:
        db.close()


def _make_lead(firm_id) -> Lead:
    """Create a Lead directly in the test DB under the given firm."""
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=firm_id,
            name="Inbound Test Prospect",
            email=f"prospect-{uuid.uuid4()}@example.com",
            provenance=LeadProvenance.crm_lead.value,
        )
        db.add(lead)
        db.commit()
        db.refresh(lead)
        _ = lead.id, lead.firm_id, lead.email
        return lead
    finally:
        db.close()


def _creds():
    """Read real webhook credentials from Settings -- never hardcode."""
    from app.core.config import get_settings
    s = get_settings()
    return s.POSTMARK_INBOUND_WEBHOOK_USERNAME, s.POSTMARK_INBOUND_WEBHOOK_PASSWORD


def _payload(lead_id, text_body: str = "Following up on my inquiry.") -> dict:
    return {
        "MailboxHash": str(lead_id),
        "TextBody": text_body,
        "HtmlBody": f"<p>{text_body}</p>",
        "From": "prospect@example.com",
        "FromFull": {"Email": "prospect@example.com", "Name": "Test Prospect"},
        "Subject": "Re: Your inquiry",
        "MessageID": str(uuid.uuid4()),
    }


def _wait_for_event(firm_id, event_type: str, timeout: float = 2.0):
    """Poll for a BehavioralEvent row -- log fires in a background thread."""
    from app.models.behavioral_event import BehavioralEvent
    deadline = time.time() + timeout
    while time.time() < deadline:
        db = TestingSessionLocal()
        try:
            event = (
                db.query(BehavioralEvent)
                .filter(
                    BehavioralEvent.firm_id == firm_id,
                    BehavioralEvent.event_type == event_type,
                )
                .first()
            )
            if event:
                return event
        finally:
            db.close()
        time.sleep(0.05)
    return None


# ---------------------------------------------------------------------------
# Auth verification
# ---------------------------------------------------------------------------

class TestWebhookAuth:
    def test_no_credentials_returns_401(self, client):
        """Confirms the endpoint rejects requests with no Authorization header (401).

        This 401 is produced by FastAPI's own HTTPBasic default behavior
        (auto_error=True), which fires before our custom _verify_credentials
        function ever runs. The protection is real, but it is attributable to
        the framework layer, not to our credential-checking logic. The
        test_wrong_credentials_returns_401 test specifically exercises our
        custom function.
        """
        r = client.post(
            "/webhooks/postmark-inbound",
            json={"MailboxHash": str(uuid.uuid4()), "TextBody": "test"},
        )
        assert r.status_code == 401

    def test_wrong_credentials_returns_401(self, client):
        """Wrong credentials must be rejected with 401."""
        r = client.post(
            "/webhooks/postmark-inbound",
            json={"MailboxHash": str(uuid.uuid4()), "TextBody": "test"},
            auth=("wrong_user", "definitely_wrong_password"),
        )
        assert r.status_code == 401

    def test_correct_credentials_accepted(self, client):
        """Valid credentials with a real matched lead return 200 with status=ok."""
        username, password = _creds()
        firm = _make_firm("auth-firm-ok", "Auth OK Firm")
        lead = _make_lead(firm.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json().get("status") == "ok"


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

class TestWebhookHappyPath:
    def test_creates_lead_message_with_correct_fields(self, client):
        username, password = _creds()
        firm = _make_firm("happy-firm-1", "Happy Webhook Firm 1")
        lead = _make_lead(firm.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id, text_body="I wanted to follow up on my inquiry."),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        db = TestingSessionLocal()
        try:
            msg = db.query(LeadMessage).filter(LeadMessage.lead_id == lead.id).first()
            assert msg is not None, "LeadMessage was not created"
            assert msg.sender_role == "lead"
            assert msg.source == "inbound_email"
            assert msg.sender_id is None
            assert msg.firm_id == firm.id
            assert "follow up" in msg.body
        finally:
            db.close()

    def test_fires_lead_email_replied_behavioral_event(self, client):
        username, password = _creds()
        firm = _make_firm("happy-firm-2", "Happy Webhook Firm 2")
        lead = _make_lead(firm.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id),
            auth=(username, password),
        )

        assert r.status_code == 200

        event = _wait_for_event(firm.id, "lead.email_replied")
        assert event is not None, "lead.email_replied behavioral event was not fired"

    def test_uses_text_body_over_html(self, client):
        """TextBody takes priority over HtmlBody when both are present."""
        username, password = _creds()
        firm = _make_firm("happy-firm-3", "Happy Webhook Firm 3")
        lead = _make_lead(firm.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json={
                **_payload(lead.id),
                "TextBody": "Plain text reply",
                "HtmlBody": "<p>This HTML should NOT be used</p>",
            },
            auth=(username, password),
        )

        assert r.status_code == 200

        db = TestingSessionLocal()
        try:
            msg = db.query(LeadMessage).filter(LeadMessage.lead_id == lead.id).first()
            assert msg is not None
            assert msg.body == "Plain text reply"
            assert "HTML" not in msg.body
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Unmatched lead and malformed hash
# ---------------------------------------------------------------------------

class TestWebhookUnmatched:
    def test_unmatched_mailbox_hash_returns_200_no_row_created(self, client):
        """No Lead for the given UUID: 200 to avoid Postmark retry storms, no row."""
        username, password = _creds()

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(uuid.uuid4(), text_body="Reply to nobody."),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ignored"

        db = TestingSessionLocal()
        try:
            count = db.query(LeadMessage).count()
            assert count == 0, f"No LeadMessage should exist for unmatched lead, found {count}"
        finally:
            db.close()

    def test_malformed_mailbox_hash_returns_200_no_row_no_crash(self, client):
        """Garbage MailboxHash (not a UUID) handled safely -- 200, no row, no crash."""
        username, password = _creds()

        r = client.post(
            "/webhooks/postmark-inbound",
            json={
                "MailboxHash": "not-a-uuid-at-all!!!garbage###",
                "TextBody": "This should be silently ignored.",
                "From": "spam@example.com",
            },
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ignored"

        db = TestingSessionLocal()
        try:
            count = db.query(LeadMessage).count()
            assert count == 0
        finally:
            db.close()

    def test_missing_mailbox_hash_returns_200_ignored(self, client):
        """No MailboxHash at all in payload -- 200, no row."""
        username, password = _creds()

        r = client.post(
            "/webhooks/postmark-inbound",
            json={"TextBody": "no hash present", "From": "someone@example.com"},
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ignored"


# ---------------------------------------------------------------------------
# Cross-firm safety
# ---------------------------------------------------------------------------

class TestWebhookCrossFirmSafety:
    def test_message_scoped_to_correct_firm_no_data_under_firm_b(self, client):
        """Inbound reply to Firm A's lead creates zero data under Firm B.

        The explicit Firm B assertion is the guard -- if firm_id routing were
        ever broken, this assertion catches it.
        """
        username, password = _creds()

        firm_a = _make_firm("xfirm-webhook-a", "Cross-Firm Webhook A")
        firm_b = _make_firm("xfirm-webhook-b", "Cross-Firm Webhook B")
        lead_a = _make_lead(firm_a.id)
        # lead_b exists but should never receive a message in this test
        _make_lead(firm_b.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead_a.id, text_body="Reply to Firm A lead."),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        db = TestingSessionLocal()
        try:
            # Message must exist under Firm A
            msg_a = db.query(LeadMessage).filter(
                LeadMessage.lead_id == lead_a.id,
                LeadMessage.firm_id == firm_a.id,
            ).first()
            assert msg_a is not None, "LeadMessage not created under Firm A"

            # Explicit assertion: NO message exists under Firm B
            firm_b_count = db.query(LeadMessage).filter(
                LeadMessage.firm_id == firm_b.id,
            ).count()
            assert firm_b_count == 0, (
                f"Cross-firm breach: {firm_b_count} LeadMessage row(s) found under Firm B"
            )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# Task 4 helpers -- reply-pause-and-notify
# ---------------------------------------------------------------------------

def _make_sequence_and_version(firm_id):
    db = TestingSessionLocal()
    try:
        seq = Sequence(firm_id=firm_id, name="Test Sequence")
        db.add(seq)
        db.flush()
        ver = SequenceVersion(sequence_id=seq.id, version_number=1)
        db.add(ver)
        db.commit()
        db.refresh(seq)
        db.refresh(ver)
        _ = seq.id, ver.id
        return seq, ver
    finally:
        db.close()


def _make_enrollment(firm_id, lead_id, sequence_id, sequence_version_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        enrollment = Enrollment(
            firm_id=firm_id,
            lead_id=lead_id,
            sequence_id=sequence_id,
            sequence_version_id=sequence_version_id,
        )
        db.add(enrollment)
        db.commit()
        db.refresh(enrollment)
        _ = enrollment.id, enrollment.status
        return enrollment
    finally:
        db.close()


def _make_firm_owner(firm_id) -> User:
    db = TestingSessionLocal()
    try:
        owner = User(
            firm_id=firm_id,
            email=f"owner-{uuid.uuid4().hex[:8]}@example.com",
            hashed_password="not-a-real-hash",
            role=UserRole.firm_owner,
        )
        db.add(owner)
        db.commit()
        db.refresh(owner)
        _ = owner.id, owner.role
        return owner
    finally:
        db.close()


def _fetch_enrollment(enrollment_id) -> Enrollment:
    db = TestingSessionLocal()
    try:
        row = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
        _ = row.id, row.status
        return row
    finally:
        db.close()


def _fetch_notification(firm_id, notification_type: NotificationType):
    db = TestingSessionLocal()
    try:
        row = (
            db.query(Notification)
            .filter(
                Notification.firm_id == firm_id,
                Notification.notification_type == notification_type,
            )
            .first()
        )
        if row is not None:
            _ = row.id, row.notification_type, row.recipient_id
        return row
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TestWebhookReplyPauseAndNotify
# ---------------------------------------------------------------------------

class TestWebhookReplyPauseAndNotify:
    """Tests for the reply-pause-and-notify mechanism added in Task 4.

    GUARD TEST: test_reply_pauses_active_enrollment
    Watched-fail cycle: temporarily comments out the enrollment-pause write,
    confirms the test is red (status stays active after reply), restores,
    confirms green.
    """

    def test_reply_pauses_active_enrollment(self, client):
        """An inbound reply sets an active enrollment's status to paused_reply.

        GUARD TEST -- see watched-fail cycle in test run report.
        """
        username, password = _creds()
        firm = _make_firm(f"pause-firm-{uuid.uuid4().hex[:6]}", "Pause Test Firm")
        lead = _make_lead(firm.id)
        _make_firm_owner(firm.id)
        seq, ver = _make_sequence_and_version(firm.id)
        enrollment = _make_enrollment(firm.id, lead.id, seq.id, ver.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        fetched = _fetch_enrollment(enrollment.id)
        assert fetched.status == EnrollmentStatus.paused_reply or fetched.status == EnrollmentStatus.paused_reply.value, (
            f"Active enrollment must be paused after a reply. Got status={fetched.status!r}"
        )

    def test_reply_notifies_firm_owner(self, client):
        """An inbound reply creates a Notification row for the firm owner with type lead_replied."""
        username, password = _creds()
        firm = _make_firm(f"notify-firm-{uuid.uuid4().hex[:6]}", "Notify Test Firm")
        lead = _make_lead(firm.id)
        owner = _make_firm_owner(firm.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id),
            auth=(username, password),
        )

        assert r.status_code == 200

        notification = _fetch_notification(firm.id, NotificationType.lead_replied)
        assert notification is not None, (
            "A Notification row with type lead_replied must be created after a reply"
        )
        assert notification.recipient_id == owner.id, (
            f"Notification must be addressed to the firm owner. "
            f"Got recipient_id={notification.recipient_id!r}"
        )

    def test_reply_with_no_active_enrollment_still_notifies(self, client):
        """A reply from a lead with no active enrollment still fires the notification.

        The lead can reply without being enrolled in any sequence.
        """
        username, password = _creds()
        firm = _make_firm(f"no-enroll-{uuid.uuid4().hex[:6]}", "No Enrollment Firm")
        lead = _make_lead(firm.id)
        owner = _make_firm_owner(firm.id)
        # No enrollment created.

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ok"

        notification = _fetch_notification(firm.id, NotificationType.lead_replied)
        assert notification is not None, (
            "Notification must fire even when no active enrollment exists"
        )
        assert notification.recipient_id == owner.id

    def test_reply_with_no_firm_owner_returns_200(self, client):
        """When no firm owner exists, the webhook must still return 200 without raising.

        No notification is created, but the webhook must complete normally.
        """
        username, password = _creds()
        firm = _make_firm(f"no-owner-{uuid.uuid4().hex[:6]}", "No Owner Firm")
        lead = _make_lead(firm.id)
        # No firm_owner user created for this firm.

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_notification_service_raises_webhook_still_returns_200(self, client, monkeypatch):
        """If NotificationService.create_notification raises, the webhook must still return 200.

        The try/except must catch and log the error without re-raising.
        """
        from app.services import notification_service as notif_mod

        def _raise(*args, **kwargs):
            raise RuntimeError("simulated notification failure")

        monkeypatch.setattr(notif_mod.NotificationService, "create_notification", staticmethod(_raise))

        username, password = _creds()
        firm = _make_firm(f"notif-raise-{uuid.uuid4().hex[:6]}", "Notif Raise Firm")
        lead = _make_lead(firm.id)
        _make_firm_owner(firm.id)

        r = client.post(
            "/webhooks/postmark-inbound",
            json=_payload(lead.id),
            auth=(username, password),
        )

        assert r.status_code == 200
        assert r.json()["status"] == "ok"
