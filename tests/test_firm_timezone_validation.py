# tests/test_firm_timezone_validation.py

import pytest
from pydantic import ValidationError

from app.schemas.firm import FirmUpdate


# ---------------------------------------------------------------------------
# Schema-level tests (no database needed)
# ---------------------------------------------------------------------------

class TestFirmUpdateTimezoneValid:

    def test_america_new_york(self):
        u = FirmUpdate(timezone="America/New_York")
        assert u.timezone == "America/New_York"

    def test_asia_kolkata(self):
        u = FirmUpdate(timezone="Asia/Kolkata")
        assert u.timezone == "Asia/Kolkata"

    def test_utc(self):
        u = FirmUpdate(timezone="UTC")
        assert u.timezone == "UTC"

    def test_europe_london(self):
        u = FirmUpdate(timezone="Europe/London")
        assert u.timezone == "Europe/London"

    def test_none_passes(self):
        u = FirmUpdate(timezone=None)
        assert u.timezone is None

    def test_omitted_passes(self):
        # field omitted: default None, validator does not run
        u = FirmUpdate()
        assert u.timezone is None


class TestFirmUpdateTimezoneRejected:

    def _assert_rejected(self, tz: str) -> None:
        with pytest.raises(ValidationError) as exc:
            FirmUpdate(timezone=tz)
        assert "Unknown time zone" in str(exc.value)

    def test_empty_string(self):
        # ZoneInfo('') raises ValueError; caught by validator
        self._assert_rejected("")

    def test_whitespace_only(self):
        # ZoneInfo('   ') raises ZoneInfoNotFoundError; caught by validator
        self._assert_rejected("   ")

    def test_not_a_real_zone(self):
        self._assert_rejected("Not/AReal_Zone")

    def test_space_in_zone_name(self):
        # ZoneInfo('America/New York') raises ZoneInfoNotFoundError
        self._assert_rejected("America/New York")

    def test_garbage_suffix(self):
        self._assert_rejected("EST5EDT garbage")

    def test_path_traversal(self):
        # ZoneInfo('../etc/passwd') raises ValueError (must be relative subpath)
        self._assert_rejected("../etc/passwd")

    def test_200_char_string(self):
        self._assert_rejected("x" * 200)

    def test_lowercase_zone_on_linux(self):
        # On this Linux host (case-sensitive tzdata), 'america/new_york' (lowercase)
        # raises ZoneInfoNotFoundError and is rejected with 422.
        # On macOS (case-insensitive filesystem) ZoneInfo may resolve it; this
        # test pin reflects the Linux behavior observed in this venv.
        self._assert_rejected("america/new_york")

    def test_error_message_contains_unknown_time_zone(self):
        with pytest.raises(ValidationError) as exc:
            FirmUpdate(timezone="Fake/Zone")
        assert "Unknown time zone" in str(exc.value)


# ---------------------------------------------------------------------------
# Router-level test (uses database via conftest client + firm_a_owner fixtures)
# ---------------------------------------------------------------------------

class TestFirmTimezoneRouterValidation:

    def test_patch_firms_me_bad_timezone_returns_422_and_leaves_timezone_unchanged(
        self, client, firm_a_owner
    ):
        # Capture the firm's timezone before the bad PATCH.
        # Firm model has server_default='America/New_York', so new firms start there.
        before = client.get("/users/firm", headers=firm_a_owner["headers"])
        assert before.status_code == 200
        initial_tz = before.json()["timezone"]

        # FastAPI rejects the body at schema validation before the handler runs,
        # so the firm row is never written.
        r = client.patch(
            "/firms/me",
            json={"timezone": "Not/AReal_Zone"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

        # Verify the stored timezone is still the same as before the bad PATCH.
        after = client.get("/users/firm", headers=firm_a_owner["headers"])
        assert after.status_code == 200
        assert after.json()["timezone"] == initial_tz
