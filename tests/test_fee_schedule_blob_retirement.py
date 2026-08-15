# tests/test_fee_schedule_blob_retirement.py

"""
Guard tests for the fee_schedule retirement from the Firm.settings blob.

Three endpoints could write arbitrary keys into the settings blob, including
fee_schedule:

  door 1  PATCH /users/firm/settings   (firm_owner, untyped dict, merges)
  door 2  PATCH /firms/me              (firm_owner, FirmUpdate.settings)
  door 3  PATCH /firms/{firm_id}       (system_admin, FirmUpdate.settings)

Two rulings from Andrew are pinned here.

BLOCKLIST, NOT WHITELIST. Only fee_schedule is refused. Every other key keeps
flowing exactly as before, so these tests assert both halves: the refusal AND
that unrelated keys still round trip through all three doors. A whitelist would
have broken the twenty four other keys the inventory found.

REJECTION IS LOUD. An explicit 422 naming the retirement, never a silent strip.
A silent strip would let the Fee Schedule settings tab keep reporting successful
saves while writing nothing, which is the exact class of failure the process
rules exist to prevent.

Separately, doors 2 and 3 replaced the whole blob via setattr rather than
merging into it, so any caller sending a partial settings object destroyed every
other key. The inventory flagged this as a live footgun. The merge tests below
were watched red against that replace behavior before the fix landed, which is
what proves they catch it.
"""

import uuid

import pytest

from app.core.enums import UserRole
from app.core.security import get_password_hash
from tests.conftest import TestingSessionLocal

# Reused rather than duplicated. The helper writes the blob with raw SQL and
# asserts the state landed, so a test cannot silently run against the wrong one.
from tests.test_settings_blob_readers import _read_blob, _set_settings_blob


# A realistic fee_schedule value, shaped like the one scripts/seed_additions.py
# used to write: a flat dict of engagement type to bare integer string.
FEE_SCHEDULE_VALUE = {
    "tax_return_1040": "850",
    "tax_return_1120": "2400",
    "custom": "",
}


@pytest.fixture
def system_admin(client, firm_a_owner):
    """A system_admin user, needed for door 3 (PATCH /firms/{firm_id})."""
    from app.models.user import User

    email = f"sysadmin-{uuid.uuid4().hex[:8]}@jammpx.com"
    password = "sysadminpass123"

    db = TestingSessionLocal()
    try:
        db.add(User(
            firm_id=firm_a_owner["firm_id"],
            email=email,
            hashed_password=get_password_hash(password),
            full_name="System Admin",
            role=UserRole.system_admin,
        ))
        db.commit()
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": password})
    assert login.status_code == 200, f"system_admin login failed: {login.text}"
    return {"headers": {"Authorization": f"Bearer {login.json()['access_token']}"}}


def _assert_names_the_retirement(response):
    """The 422 has to explain itself, not just refuse."""
    detail = response.json()["detail"]
    assert isinstance(detail, str), f"expected a plain string detail, got {detail!r}"
    lowered = detail.lower()
    assert "fee_schedule" in lowered, f"detail does not name the key: {detail!r}"
    assert "retired" in lowered, f"detail does not say it is retired: {detail!r}"
    assert "fee schedule system" in lowered, (
        f"detail does not point at where pricing lives now: {detail!r}"
    )


# ---------------------------------------------------------------------------
# Door 1: PATCH /users/firm/settings
# ---------------------------------------------------------------------------

class TestDoorOneUsersFirmSettings:

    def test_rejects_fee_schedule_with_422(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"fee_schedule": FEE_SCHEDULE_VALUE},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        _assert_names_the_retirement(r)

    def test_rejects_even_when_mixed_with_valid_keys(self, client, firm_a_owner):
        """A payload carrying both a retired and a live key is refused whole."""
        r = client.patch(
            "/users/firm/settings",
            json={
                "portal_display_name": "Should Not Land",
                "fee_schedule": FEE_SCHEDULE_VALUE,
            },
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        blob = _read_blob(firm_a_owner["firm_id"]) or {}
        assert "portal_display_name" not in blob, (
            "the refused payload partially landed, which makes the refusal a lie"
        )
        assert "fee_schedule" not in blob

    def test_rejection_precedes_the_s3_logo_side_effect(self, client, firm_a_owner):
        """The refusal must happen before any side effect runs.

        update_firm_settings deletes the previous portal logo from S3 when the
        key changes. If the fee_schedule check ran after that, a refused payload
        would still have destroyed the firm's logo object. Order matters, so it
        is pinned.
        """
        _set_settings_blob(
            firm_a_owner["firm_id"], {"portal_logo_s3_key": "firms/logo/original.png"}
        )

        deleted = []
        from app.services import s3 as s3_service
        original_delete = s3_service.delete_object
        s3_service.delete_object = lambda key: deleted.append(key)
        try:
            r = client.patch(
                "/users/firm/settings",
                json={
                    "portal_logo_s3_key": "firms/logo/replacement.png",
                    "fee_schedule": FEE_SCHEDULE_VALUE,
                },
                headers=firm_a_owner["headers"],
            )
        finally:
            s3_service.delete_object = original_delete

        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        assert deleted == [], (
            f"refused payload still deleted S3 objects {deleted!r}: the "
            "fee_schedule check runs after the side effect"
        )
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["portal_logo_s3_key"] == "firms/logo/original.png"

    def test_non_fee_keys_still_write(self, client, firm_a_owner):
        """Blocklist, not whitelist: everything else flows exactly as before."""
        r = client.patch(
            "/users/firm/settings",
            json={
                "portal_display_name": "Still Works",
                "session_timeout_minutes": 45,
                "esign_first_reminder_days": 7,
            },
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, r.text
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["portal_display_name"] == "Still Works"
        assert blob["session_timeout_minutes"] == 45
        assert blob["esign_first_reminder_days"] == 7

    def test_still_merges_rather_than_replacing(self, client, firm_a_owner):
        """Door 1 already merged. Pinned so the phase 2 work cannot regress it."""
        _set_settings_blob(firm_a_owner["firm_id"], {"portal_display_name": "Keep Me"})

        r = client.patch(
            "/users/firm/settings",
            json={"google_review_url": "https://example.com/review"},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, r.text
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["portal_display_name"] == "Keep Me"
        assert blob["google_review_url"] == "https://example.com/review"


# ---------------------------------------------------------------------------
# Door 2: PATCH /firms/me
# ---------------------------------------------------------------------------

class TestDoorTwoFirmsMe:

    def test_rejects_fee_schedule_with_422(self, client, firm_a_owner):
        r = client.patch(
            "/firms/me",
            json={"settings": {"fee_schedule": FEE_SCHEDULE_VALUE}},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        _assert_names_the_retirement(r)

    def test_merges_settings_instead_of_replacing_the_blob(self, client, firm_a_owner):
        """THE FOOTGUN TEST. Watched red against the pre fix replace behavior.

        A caller sending a partial settings object used to destroy every other
        key in the blob, because crud/firm.py applied it with a plain setattr.
        """
        _set_settings_blob(
            firm_a_owner["firm_id"],
            {"portal_display_name": "Keep Me", "session_timeout_minutes": 45},
        )

        r = client.patch(
            "/firms/me",
            json={"settings": {"google_review_url": "https://example.com/review"}},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, r.text
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["google_review_url"] == "https://example.com/review"
        assert blob["portal_display_name"] == "Keep Me", (
            "partial settings PATCH destroyed an unrelated key: the blob was "
            "replaced wholesale instead of merged"
        )
        assert blob["session_timeout_minutes"] == 45

    def test_merges_into_a_null_blob(self, client, firm_a_owner):
        """A NULL existing blob merges as if it were empty."""
        _set_settings_blob(firm_a_owner["firm_id"], None)

        r = client.patch(
            "/firms/me",
            json={"settings": {"portal_mode": "light"}},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, r.text
        assert _read_blob(firm_a_owner["firm_id"])["portal_mode"] == "light"

    def test_non_settings_fields_still_replace_normally(self, client, firm_a_owner):
        """Only settings gets merge treatment. Other FirmUpdate fields are unchanged."""
        r = client.patch(
            "/firms/me",
            json={"name": "Renamed Firm A"},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, r.text
        assert r.json()["name"] == "Renamed Firm A"

    def test_non_fee_settings_keys_still_write(self, client, firm_a_owner):
        r = client.patch(
            "/firms/me",
            json={"settings": {"portal_display_name": "Door Two Works"}},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, r.text
        assert _read_blob(firm_a_owner["firm_id"])["portal_display_name"] == "Door Two Works"


# ---------------------------------------------------------------------------
# Door 3: PATCH /firms/{firm_id}
# ---------------------------------------------------------------------------

class TestDoorThreeFirmsById:

    def test_rejects_fee_schedule_with_422(self, client, firm_a_owner, system_admin):
        r = client.patch(
            f"/firms/{firm_a_owner['firm_id']}",
            json={"settings": {"fee_schedule": FEE_SCHEDULE_VALUE}},
            headers=system_admin["headers"],
        )

        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        _assert_names_the_retirement(r)

    def test_merges_settings_instead_of_replacing_the_blob(
        self, client, firm_a_owner, system_admin
    ):
        """Same footgun, the system_admin door. Also watched red."""
        _set_settings_blob(
            firm_a_owner["firm_id"],
            {"portal_display_name": "Keep Me", "session_timeout_minutes": 45},
        )

        r = client.patch(
            f"/firms/{firm_a_owner['firm_id']}",
            json={"settings": {"google_review_url": "https://example.com/review"}},
            headers=system_admin["headers"],
        )

        assert r.status_code == 200, r.text
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["google_review_url"] == "https://example.com/review"
        assert blob["portal_display_name"] == "Keep Me", (
            "partial settings PATCH destroyed an unrelated key on the "
            "system_admin door"
        )
        assert blob["session_timeout_minutes"] == 45

    def test_non_fee_settings_keys_still_write(self, client, firm_a_owner, system_admin):
        r = client.patch(
            f"/firms/{firm_a_owner['firm_id']}",
            json={"settings": {"portal_display_name": "Door Three Works"}},
            headers=system_admin["headers"],
        )

        assert r.status_code == 200, r.text
        assert _read_blob(firm_a_owner["firm_id"])["portal_display_name"] == (
            "Door Three Works"
        )


# ---------------------------------------------------------------------------
# Cross cutting
# ---------------------------------------------------------------------------

class TestRetirementIsBlocklistNotWhitelist:

    def test_a_key_that_merely_contains_fee_is_allowed(self, client, firm_a_owner):
        """Only the exact fee_schedule key is retired.

        Guards against a substring match creeping in. The inventory noted that
        catalog sounding names do not confer status, and the same applies here:
        the block is on one exact key, not on anything that looks fee related.
        """
        r = client.patch(
            "/users/firm/settings",
            json={"fee_schedule_migrated_at": "2026-08-15", "last_fee_review": "none"},
            headers=firm_a_owner["headers"],
        )

        assert r.status_code == 200, (
            f"a key merely containing 'fee_schedule' was refused: {r.text}"
        )
        blob = _read_blob(firm_a_owner["firm_id"])
        assert blob["fee_schedule_migrated_at"] == "2026-08-15"
