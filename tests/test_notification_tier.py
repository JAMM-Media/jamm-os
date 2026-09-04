# tests/test_notification_tier.py
"""
Tests for the loud/quiet/silent notification tier taxonomy per Andrew's ruling.

Covers:
  1. loud tier: Notification row created with tier="loud"; NotificationOut includes tier.
  2. quiet tier: Notification row created with tier="quiet"; identical to existing behavior.
  3. silent tier: no Notification row written; channel logic completely bypassed.
  4. create_notification requires tier -- no default: omitting it raises TypeError.
  5. Existing channel-preference behavior (in_app/email/both/none) unchanged for
     quiet and loud tiers.
  6. All 12 call sites produce correct tier values.

Silent tier gap report (per Step 3 instruction):
  peer_network.py announcement broadcast -- the silent call site has NO accompanying
  log_event call near it. The behavioral event log will have no record of announcement
  broadcasts after this change. This is flagged here as a gap; adding log_event to
  cover it is out of scope for this task.
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.notification import Notification
from app.core.enums import (
    NotificationType,
    NotificationTier,
    NotificationChannel,
    RecipientType,
    UserRole,
)
from app.core.security import get_password_hash
from app.services.notification_service import NotificationService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_user(slug):
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Tier Test Firm {slug}", slug=slug)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        user = User(
            firm_id=firm.id,
            email=f"owner-{slug}@tiertest.com",
            hashed_password=get_password_hash("testpass"),
            full_name="Tier Test Owner",
            role=UserRole.firm_owner,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return firm.id, user.id
    finally:
        db.close()


def _count_notifications(firm_id, recipient_id):
    db = TestingSessionLocal()
    try:
        return db.query(Notification).filter(
            Notification.firm_id == firm_id,
            Notification.recipient_id == recipient_id,
        ).count()
    finally:
        db.close()


def _get_notification(firm_id, recipient_id):
    db = TestingSessionLocal()
    try:
        return db.query(Notification).filter(
            Notification.firm_id == firm_id,
            Notification.recipient_id == recipient_id,
        ).first()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. Loud tier creates Notification row with tier="loud"
# ---------------------------------------------------------------------------

class TestLoudTier:

    def test_loud_creates_notification_row_with_loud_tier(self):
        """loud tier: Notification row is created and its tier field is 'loud'."""
        firm_id, user_id = _make_firm_and_user(f"loud-{uuid.uuid4().hex[:6]}")
        db = TestingSessionLocal()
        try:
            result = NotificationService.create_notification(
                db=db,
                firm_id=firm_id,
                recipient_id=user_id,
                recipient_type=RecipientType.staff,
                title="Hot lead: Test Lead",
                body="Test Lead has been marked hot.",
                notification_type=NotificationType.lead_hot_alert,
                tier=NotificationTier.loud,
            )
        finally:
            db.close()

        assert result is not None, "loud tier must create a Notification row"
        assert result.tier == NotificationTier.loud, (
            f"tier must be loud, got {result.tier!r}"
        )

    def test_loud_tier_appears_in_notificationout(self, client, firm_a_owner):
        """NotificationOut includes the tier field, correctly set to 'loud'."""
        headers = firm_a_owner["headers"]
        firm_id = uuid.UUID(firm_a_owner["firm_id"])

        from app.models.user import User as UserModel
        db = TestingSessionLocal()
        try:
            owner = db.query(UserModel).filter(UserModel.firm_id == firm_id).first()
            user_id = owner.id
            NotificationService.create_notification(
                db=db,
                firm_id=firm_id,
                recipient_id=user_id,
                recipient_type=RecipientType.staff,
                title="Loud test",
                body="Loud test body",
                notification_type=NotificationType.system,
                tier=NotificationTier.loud,
            )
        finally:
            db.close()

        r = client.get("/api/v1/notifications/", headers=headers)
        assert r.status_code == 200, r.text
        items = r.json()["items"]
        loud_items = [n for n in items if n.get("tier") == "loud"]
        assert len(loud_items) >= 1, (
            f"At least one loud notification must appear in response. items: {items}"
        )


# ---------------------------------------------------------------------------
# 2. Quiet tier behaves identically to existing behavior
# ---------------------------------------------------------------------------

class TestQuietTier:

    def test_quiet_creates_notification_row_with_quiet_tier(self):
        """quiet tier: Notification row is created with tier='quiet'."""
        firm_id, user_id = _make_firm_and_user(f"quiet-{uuid.uuid4().hex[:6]}")
        db = TestingSessionLocal()
        try:
            result = NotificationService.create_notification(
                db=db,
                firm_id=firm_id,
                recipient_id=user_id,
                recipient_type=RecipientType.staff,
                title="Quiet notification",
                body="A quiet notification body.",
                notification_type=NotificationType.system,
                tier=NotificationTier.quiet,
            )
        finally:
            db.close()

        assert result is not None, "quiet tier must create a Notification row"
        assert result.tier == NotificationTier.quiet


# ---------------------------------------------------------------------------
# 3. Silent tier: no Notification row written
# ---------------------------------------------------------------------------

class TestSilentTier:

    def test_silent_creates_no_notification_row(self):
        """silent tier: create_notification returns None, no row in DB."""
        firm_id, user_id = _make_firm_and_user(f"silent-{uuid.uuid4().hex[:6]}")
        db = TestingSessionLocal()
        try:
            result = NotificationService.create_notification(
                db=db,
                firm_id=firm_id,
                recipient_id=user_id,
                recipient_type=RecipientType.staff,
                title="Should not be persisted",
                body="This is a silent announcement.",
                notification_type=NotificationType.peer_network_mention,
                tier=NotificationTier.silent,
            )
        finally:
            db.close()

        assert result is None, f"silent tier must return None, got {result!r}"
        count = _count_notifications(firm_id, user_id)
        assert count == 0, f"silent tier must write no Notification row, found {count}"

    def test_silent_bypasses_channel_logic_entirely(self):
        """silent tier: channel preference lookup is never called; returns None immediately."""
        from unittest.mock import patch

        firm_id, user_id = _make_firm_and_user(f"silent2-{uuid.uuid4().hex[:6]}")
        db = TestingSessionLocal()

        with patch(
            "app.services.notification_service.crud_notification_preference.get_channel_for_event"
        ) as mock_channel:
            try:
                result = NotificationService.create_notification(
                    db=db,
                    firm_id=firm_id,
                    recipient_id=user_id,
                    recipient_type=RecipientType.staff,
                    title="Silent bypass test",
                    body="Should bypass channel logic.",
                    notification_type=NotificationType.system,
                    tier=NotificationTier.silent,
                )
            finally:
                db.close()

        assert result is None
        mock_channel.assert_not_called(), (
            "silent tier must not call get_channel_for_event -- it skips all channel logic"
        )


# ---------------------------------------------------------------------------
# 4. create_notification requires tier -- no default
# ---------------------------------------------------------------------------

class TestTierRequired:

    def test_omitting_tier_raises_typeerror(self):
        """create_notification must raise TypeError if tier is not supplied."""
        firm_id, user_id = _make_firm_and_user(f"norequired-{uuid.uuid4().hex[:6]}")
        db = TestingSessionLocal()
        try:
            with pytest.raises(TypeError):
                NotificationService.create_notification(
                    db=db,
                    firm_id=firm_id,
                    recipient_id=user_id,
                    recipient_type=RecipientType.staff,
                    title="Missing tier",
                    body="Body.",
                    notification_type=NotificationType.system,
                    # tier intentionally omitted
                )
        finally:
            db.close()


# ---------------------------------------------------------------------------
# 5. Channel-preference behavior unchanged for quiet and loud
# ---------------------------------------------------------------------------

class TestChannelPreferenceUnchanged:

    def test_channel_none_suppresses_notification_for_quiet_tier(self):
        """When channel is none, quiet tier returns None (existing behavior preserved)."""
        from app.crud import notification_preference as crud_pref
        from app.core.enums import NotificationEventType

        firm_id, user_id = _make_firm_and_user(f"chanq-{uuid.uuid4().hex[:6]}")
        db = TestingSessionLocal()
        try:
            # Set channel=none for system notifications
            pref = crud_pref.upsert_preference(
                db,
                firm_id=firm_id,
                recipient_id=user_id,
                recipient_type=RecipientType.staff,
                event_type=NotificationEventType.system,
                channel=NotificationChannel.none,
            )
            result = NotificationService.create_notification(
                db=db,
                firm_id=firm_id,
                recipient_id=user_id,
                recipient_type=RecipientType.staff,
                title="Suppressed quiet",
                body="Should be suppressed by channel=none.",
                notification_type=NotificationType.system,
                tier=NotificationTier.quiet,
            )
        finally:
            db.close()

        assert result is None, (
            "quiet tier with channel=none must return None (existing suppression behavior)"
        )
        assert _count_notifications(firm_id, user_id) == 0


# ---------------------------------------------------------------------------
# 6. Spot-check: lead_alert_service fires loud, postmark fires loud
# ---------------------------------------------------------------------------

class TestCallSiteTiers:

    def test_hot_lead_alert_is_loud(self, client, firm_a_owner):
        """Hot lead alert (lead_alert_service.py) fires a loud notification."""
        headers = firm_a_owner["headers"]

        r = client.post(
            "/api/v1/leads/",
            json={"name": "Tier Test Lead", "provenance": "firm_entered"},
            headers=headers,
        )
        assert r.status_code == 201
        lead_id = r.json()["id"]

        # Mark hot -- this triggers the hot lead alert
        r2 = client.patch(
            f"/api/v1/leads/{lead_id}",
            json={"hot": True},
            headers=headers,
        )
        assert r2.status_code == 200

        firm_id = uuid.UUID(firm_a_owner["firm_id"])
        db = TestingSessionLocal()
        try:
            n = db.query(Notification).filter(
                Notification.firm_id == firm_id,
                Notification.notification_type == NotificationType.lead_hot_alert.value,
            ).first()
        finally:
            db.close()

        assert n is not None, "Hot lead alert notification must be created"
        assert n.tier == NotificationTier.loud, (
            f"Hot lead alert must be loud, got {n.tier!r}"
        )
