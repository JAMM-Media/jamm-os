# tests/test_send_notification_action.py
"""
Tests for the updated _handle_send_notification backend action.

The action now reads recipient_role from config (not a fixed recipient_id from
payload) and resolves the real recipient at execution time.

Covers:
  1. recipient_role=assigned_staff resolves to the Task.assigned_to user.
  2. recipient_role=firm_owner resolves to the real firm_owner user.
  3. recipient_role=manager resolves to a manager user; falls back to firm_owner
     when no manager exists.
  4. A rule with no recipient_role set (pre-existing rule) skips without crashing.
  5. tier=loud and tier=quiet both pass through to NotificationService correctly.
  6. Tenant isolation: recipient resolution never crosses firm boundaries.
"""

import uuid
from datetime import datetime, timezone

import pytest

from tests.conftest import TestingSessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.task import Task
from app.models.notification import Notification
from app.core.enums import NotificationTier, NotificationType, UserRole


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug=None):
    db = TestingSessionLocal()
    try:
        s = slug or f"notif-act-{uuid.uuid4().hex[:6]}"
        firm = Firm(name=f"Notif Action Firm {s}", slug=s)
        db.add(firm)
        db.commit()
        db.refresh(firm)
        return firm.id
    finally:
        db.close()


def _make_user(firm_id, role: UserRole, suffix=None):
    from app.core.security import get_password_hash
    db = TestingSessionLocal()
    try:
        s = suffix or uuid.uuid4().hex[:6]
        user = User(
            firm_id=firm_id,
            email=f"notif-{role.value}-{s}@test.com",
            hashed_password=get_password_hash("testpass"),
            full_name=f"Notif {role.value} {s}",
            role=role,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user.id
    finally:
        db.close()


def _make_task(firm_id, assigned_to=None):
    db = TestingSessionLocal()
    try:
        task = Task(
            firm_id=firm_id,
            title="Notif action test task",
            assigned_to=assigned_to,
        )
        db.add(task)
        db.commit()
        db.refresh(task)
        return task.id
    finally:
        db.close()


def _run_action(config, payload):
    from app.services.automation_actions import _handle_send_notification
    db = TestingSessionLocal()
    try:
        return _handle_send_notification(config, payload, db)
    finally:
        db.close()


def _get_notifications(firm_id, recipient_id):
    db = TestingSessionLocal()
    try:
        return db.query(Notification).filter(
            Notification.firm_id == firm_id,
            Notification.recipient_id == recipient_id,
        ).all()
    finally:
        db.close()


# ---------------------------------------------------------------------------
# 1. assigned_staff resolves to Task.assigned_to
# ---------------------------------------------------------------------------

class TestAssignedStaffRecipient:

    def test_resolves_to_task_assigned_to_user(self):
        """recipient_role=assigned_staff resolves to the Task's assigned_to user."""
        firm_id = _make_firm()
        staff_id = _make_user(firm_id, UserRole.staff)
        task_id = _make_task(firm_id, assigned_to=staff_id)

        config = {
            "recipient_role": "assigned_staff",
            "tier": "quiet",
            "title": "Test notification",
            "body": "Test body",
        }
        payload = {
            "firm_id": str(firm_id),
            "task_id": str(task_id),
        }

        result = _run_action(config, payload)
        assert "Notification sent" in result, f"Unexpected result: {result}"

        notifs = _get_notifications(firm_id, staff_id)
        assert len(notifs) == 1, f"Expected 1 notification for assigned staff, got {len(notifs)}"

    def test_falls_back_to_firm_owner_when_no_task(self):
        """assigned_staff without a task_id in payload falls back to firm_owner."""
        firm_id = _make_firm()
        owner_id = _make_user(firm_id, UserRole.firm_owner)

        config = {
            "recipient_role": "assigned_staff",
            "tier": "quiet",
            "title": "Fallback test",
            "body": "Body",
        }
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "Notification sent" in result

        notifs = _get_notifications(firm_id, owner_id)
        assert len(notifs) == 1, "Should fall back to firm_owner when no task_id"


# ---------------------------------------------------------------------------
# 2. firm_owner resolution
# ---------------------------------------------------------------------------

class TestFirmOwnerRecipient:

    def test_resolves_to_firm_owner(self):
        """recipient_role=firm_owner resolves to the user with role=firm_owner."""
        firm_id = _make_firm()
        owner_id = _make_user(firm_id, UserRole.firm_owner)
        # Add a staff member to confirm only the owner is targeted
        _make_user(firm_id, UserRole.staff)

        config = {
            "recipient_role": "firm_owner",
            "tier": "quiet",
            "title": "Owner alert",
            "body": "Owner body",
        }
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "Notification sent" in result

        notifs = _get_notifications(firm_id, owner_id)
        assert len(notifs) == 1, f"Expected 1 notification for firm_owner, got {len(notifs)}"


# ---------------------------------------------------------------------------
# 3. manager resolution with fallback
# ---------------------------------------------------------------------------

class TestManagerRecipient:

    def test_resolves_to_manager_when_exists(self):
        """recipient_role=manager resolves to a manager user."""
        firm_id = _make_firm()
        _make_user(firm_id, UserRole.firm_owner)
        manager_id = _make_user(firm_id, UserRole.manager)

        config = {
            "recipient_role": "manager",
            "tier": "quiet",
            "title": "Manager alert",
            "body": "Body",
        }
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "Notification sent" in result

        notifs = _get_notifications(firm_id, manager_id)
        assert len(notifs) == 1, f"Expected notification for manager, got {len(notifs)}"

    def test_falls_back_to_firm_owner_when_no_manager(self):
        """recipient_role=manager falls back to firm_owner when no manager exists."""
        firm_id = _make_firm()
        owner_id = _make_user(firm_id, UserRole.firm_owner)

        config = {
            "recipient_role": "manager",
            "tier": "quiet",
            "title": "Manager fallback",
            "body": "Body",
        }
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "Notification sent" in result

        notifs = _get_notifications(firm_id, owner_id)
        assert len(notifs) == 1, "Should fall back to firm_owner when no manager"


# ---------------------------------------------------------------------------
# 4. Pre-existing rule (no recipient_role) skips without crashing
# ---------------------------------------------------------------------------

class TestBackwardCompatibility:

    def test_missing_recipient_role_skips_gracefully(self):
        """A config without recipient_role returns a skip message, no crash."""
        firm_id = _make_firm()
        _make_user(firm_id, UserRole.firm_owner)

        config = {
            "title": "Old config title",
            "body": "Old body",
        }
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "skipped" in result.lower(), f"Expected skip, got: {result}"

    def test_missing_title_skips_gracefully(self):
        """A config without title returns a skip message, no crash."""
        firm_id = _make_firm()
        config = {"recipient_role": "firm_owner"}
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "skipped" in result.lower(), f"Expected skip, got: {result}"


# ---------------------------------------------------------------------------
# 5. tier=loud and tier=quiet pass through correctly
# ---------------------------------------------------------------------------

class TestTierPassthrough:

    def test_loud_tier_creates_loud_notification(self):
        """tier=loud in config produces a Notification row with tier=loud."""
        firm_id = _make_firm()
        owner_id = _make_user(firm_id, UserRole.firm_owner)

        config = {
            "recipient_role": "firm_owner",
            "tier": "loud",
            "title": "Loud alert",
            "body": "Loud body",
        }
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "Notification sent" in result

        notifs = _get_notifications(firm_id, owner_id)
        assert len(notifs) == 1
        assert notifs[0].tier == NotificationTier.loud, (
            f"Expected loud tier, got {notifs[0].tier!r}"
        )

    def test_quiet_tier_creates_quiet_notification(self):
        """tier=quiet in config produces a Notification row with tier=quiet."""
        firm_id = _make_firm()
        owner_id = _make_user(firm_id, UserRole.firm_owner)

        config = {
            "recipient_role": "firm_owner",
            "tier": "quiet",
            "title": "Quiet alert",
            "body": "Quiet body",
        }
        payload = {"firm_id": str(firm_id)}

        result = _run_action(config, payload)
        assert "Notification sent" in result

        notifs = _get_notifications(firm_id, owner_id)
        assert len(notifs) == 1
        assert notifs[0].tier == NotificationTier.quiet, (
            f"Expected quiet tier, got {notifs[0].tier!r}"
        )


# ---------------------------------------------------------------------------
# 6. Tenant isolation
# ---------------------------------------------------------------------------

class TestTenantIsolation:

    def test_firm_owner_resolution_scoped_to_firm(self):
        """Firm owner resolution never returns users from another firm."""
        firm_a_id = _make_firm("iso-a")
        firm_b_id = _make_firm("iso-b")
        owner_a_id = _make_user(firm_a_id, UserRole.firm_owner, "a")
        owner_b_id = _make_user(firm_b_id, UserRole.firm_owner, "b")

        config = {
            "recipient_role": "firm_owner",
            "tier": "quiet",
            "title": "Isolation test",
            "body": "Body",
        }
        payload = {"firm_id": str(firm_a_id)}

        result = _run_action(config, payload)
        assert "Notification sent" in result

        # Firm A's owner notified
        a_notifs = _get_notifications(firm_a_id, owner_a_id)
        assert len(a_notifs) == 1, "Firm A owner must receive notification"

        # Firm B's owner NOT notified
        b_notifs = _get_notifications(firm_b_id, owner_b_id)
        assert len(b_notifs) == 0, "Firm B owner must NOT receive notification from Firm A's rule"
