# tests/test_portal_color_validation.py

"""
Guard tests for hex color validation on portal_colors_dark and portal_colors_light
in the Firm.settings blob.

PATCH /users/firm/settings is the only door that currently writes these keys.
A malformed color value (not a 6-digit hex string) must be rejected with 422
before it can be persisted. Color values are injected as raw CSS in the client
portal, making this also a CSS-injection guard in a multi-tenant context.

Behavior under test:
  - Any non-hex string in portal_colors_dark or portal_colors_light is rejected
  - Both keys are independently validated
  - Valid hex values pass through normally
  - Partial color maps (not all 9 keys) are accepted if all present values are hex
"""

import pytest


class TestPortalColorsValidation:

    def test_rejects_non_hex_in_portal_colors_dark(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_dark": {"accent": "not-a-color"}},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "portal_colors_dark" in detail, f"detail should name the key: {detail!r}"
        assert "not-a-color" in detail or "hex" in detail, f"detail should describe the problem: {detail!r}"

    def test_rejects_non_hex_in_portal_colors_light(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_light": {"top_bar": "javascript:alert(1)"}},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "").lower()
        assert "portal_colors_light" in detail, f"detail should name the key: {detail!r}"

    def test_rejects_hex_without_hash_prefix(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_dark": {"page": "EDEEF0"}},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_rejects_five_digit_hex(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_dark": {"accent": "#1F314"}},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_rejects_non_dict_color_map(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_dark": "#1F3148"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"

    def test_accepts_valid_hex_values(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_dark": {"accent": "#4A7FA5", "page": "#2D2D2D"}},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"

    def test_accepts_lowercase_hex(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_light": {"accent": "#1f3148"}},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"

    def test_rejects_if_any_value_invalid_even_with_valid_others(self, client, firm_a_owner):
        r = client.patch(
            "/users/firm/settings",
            json={"portal_colors_dark": {"accent": "#4A7FA5", "page": "bad"}},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 422, f"expected 422, got {r.status_code}: {r.text}"
