# tests/test_portal_domain.py

"""
End-to-end verification tests for the Portal Custom Domain feature.

Covers:
  - Token generation and database persistence (register)
  - Verification logic against a predictably-failing domain (the .invalid TLD is
    guaranteed not to resolve per RFC 2606, so socket.gaierror is deterministic here)
  - Removal clearing all three Firm fields
  - Authorization -- manager role must be rejected by all four endpoints

What this cannot verify locally:
  - A real DNS TXT lookup succeeding against a real, owned domain whose registrar
    has been configured with the correct _jammpx-verify. TXT record. That step
    requires a real external domain and DNS propagation, neither of which is
    available in this dev environment.
  - Actual portal routing at the custom domain URL (requires Vercel dashboard config).
"""

import uuid

import pytest

from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _read_firm_domain_fields(firm_id: str) -> dict:
    """Read portal_domain fields directly from the DB for the given firm_id."""
    import uuid as _uuid
    from app.models.firm import Firm
    db = TestingSessionLocal()
    try:
        firm = db.get(Firm, _uuid.UUID(firm_id))
        if not firm:
            return {}
        return {
            "portal_domain": firm.portal_domain,
            "portal_domain_verified": firm.portal_domain_verified,
            "portal_domain_verification_token": firm.portal_domain_verification_token,
        }
    finally:
        db.close()


def _create_manager_user(client, firm_id: str) -> dict:
    """Create a manager user for the given firm and return auth headers."""
    from app.models.user import User
    from app.core.enums import UserRole
    from app.core.security import get_password_hash
    email = f"manager-{uuid.uuid4().hex[:8]}@testfirm.com"
    db = TestingSessionLocal()
    try:
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("testpass123"),
            full_name="Manager User",
            role=UserRole.manager,
        )
        db.add(user)
        db.commit()
    finally:
        db.close()
    login = client.post("/auth/token", json={"username": email, "password": "testpass123"})
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# Step 1: registration -- token persistence
# ---------------------------------------------------------------------------

class TestRegisterPortalDomain:

    def test_register_returns_dns_records(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.testfirm.example"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["domain"] == "portal.testfirm.example"
        assert data["cname_host"] == "portal.testfirm.example"
        assert data["cname_value"] == "cname.vercel-dns.com"
        assert data["txt_host"] == "_jammpx-verify.portal.testfirm.example"
        assert data["verified"] is False
        assert len(data["txt_value"]) == 32, f"token should be 32 hex chars, got: {data['txt_value']!r}"

    def test_register_persists_to_database(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.dbtest.example"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        returned_token = r.json()["txt_value"]

        fields = _read_firm_domain_fields(firm_a_owner["firm_id"])
        assert fields["portal_domain"] == "portal.dbtest.example", (
            f"portal_domain not persisted: {fields}"
        )
        assert fields["portal_domain_verified"] is False, (
            f"portal_domain_verified should be False immediately after register: {fields}"
        )
        assert fields["portal_domain_verification_token"] == returned_token, (
            f"DB token does not match returned token: {fields['portal_domain_verification_token']!r} vs {returned_token!r}"
        )

    def test_token_is_32_hex_chars(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.tokentest.example"},
            headers=firm_a_owner["headers"],
        )
        token = r.json()["txt_value"]
        assert len(token) == 32
        assert all(c in "0123456789abcdef" for c in token), (
            f"token contains non-hex chars: {token!r}"
        )

    def test_register_strips_https_prefix(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "https://portal.strip.example"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        assert r.json()["domain"] == "portal.strip.example"

    def test_register_rejects_domain_with_path(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.testfirm.example/somepath"},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 400

    def test_register_rejects_empty_domain(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": ""},
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 400


# ---------------------------------------------------------------------------
# Step 2: verification -- predictable failure against .invalid TLD
# ---------------------------------------------------------------------------

class TestVerifyPortalDomain:

    def test_verify_fails_for_nonexistent_domain(self, client, firm_a_owner):
        """
        The .invalid TLD is guaranteed not to resolve per RFC 2606.
        socket.getaddrinfo will raise gaierror, so cname_resolved=False.
        dns.resolver will also raise for the TXT lookup, so txt_verified=False.
        The endpoint must return verified=False and not set portal_domain_verified=True.
        """
        reg = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.this-firm-definitely-does-not-exist.invalid"},
            headers=firm_a_owner["headers"],
        )
        assert reg.status_code == 200

        r = client.post(
            "/api/v1/portal-domain/verify",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200, f"expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["verified"] is False, f"expected verified=False for .invalid domain: {data}"
        assert data["cname_resolved"] is False, f"expected cname_resolved=False for .invalid: {data}"

        fields = _read_firm_domain_fields(firm_a_owner["firm_id"])
        assert fields["portal_domain_verified"] is False, (
            f"portal_domain_verified must not be set to True for a .invalid domain: {fields}"
        )

    def test_verify_without_registered_domain_returns_400(self, client, firm_a_owner):
        r = client.post(
            "/api/v1/portal-domain/verify",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 400

    def test_import_error_fails_safely_not_silently(self, client, firm_a_owner):
        """
        If dnspython is not installed, txt_verified must be False, not True.
        The prior behavior (txt_verified = True on ImportError) would have silently
        bypassed domain ownership verification. This test mocks the ImportError to
        confirm the fixed behavior without requiring dnspython to be absent.
        """
        from unittest.mock import patch

        client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.importerror-test.invalid"},
            headers=firm_a_owner["headers"],
        )

        # Patch dns.resolver inside domain_service to raise ImportError,
        # simulating dnspython being unavailable.
        with patch.dict("sys.modules", {"dns.resolver": None}):
            r = client.post(
                "/api/v1/portal-domain/verify",
                headers=firm_a_owner["headers"],
            )

        assert r.status_code == 200, f"expected 200 from verify endpoint, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["verified"] is False, (
            f"ImportError must cause verified=False (fail safe), not True (silent bypass): {data}"
        )
        assert data["txt_verified"] is False, (
            f"ImportError must cause txt_verified=False: {data}"
        )


# ---------------------------------------------------------------------------
# Step 3: removal -- all three fields cleared
# ---------------------------------------------------------------------------

class TestRemovePortalDomain:

    def test_remove_clears_all_three_fields(self, client, firm_a_owner):
        client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.removetest.example"},
            headers=firm_a_owner["headers"],
        )
        fields_before = _read_firm_domain_fields(firm_a_owner["firm_id"])
        assert fields_before["portal_domain"] is not None

        r = client.delete(
            "/api/v1/portal-domain",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200

        fields_after = _read_firm_domain_fields(firm_a_owner["firm_id"])
        assert fields_after["portal_domain"] is None, (
            f"portal_domain not cleared: {fields_after}"
        )
        assert fields_after["portal_domain_verified"] is False, (
            f"portal_domain_verified not cleared: {fields_after}"
        )
        assert fields_after["portal_domain_verification_token"] is None, (
            f"portal_domain_verification_token not cleared: {fields_after}"
        )


# ---------------------------------------------------------------------------
# Step 4: authorization -- manager role rejected from all four endpoints
# ---------------------------------------------------------------------------

class TestPortalDomainAuthorization:

    def test_unauthenticated_register_rejected(self, client):
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.example.com"},
        )
        assert r.status_code in (401, 403), f"expected auth error, got {r.status_code}"

    def test_manager_cannot_register(self, client, firm_a_owner):
        mgr_headers = _create_manager_user(client, firm_a_owner["firm_id"])
        r = client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.example.com"},
            headers=mgr_headers,
        )
        assert r.status_code == 403, f"expected 403 for manager, got {r.status_code}: {r.text}"

    def test_manager_cannot_verify(self, client, firm_a_owner):
        # Register first as owner so there is a domain to verify
        client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.authtest.example"},
            headers=firm_a_owner["headers"],
        )
        mgr_headers = _create_manager_user(client, firm_a_owner["firm_id"])
        r = client.post(
            "/api/v1/portal-domain/verify",
            headers=mgr_headers,
        )
        assert r.status_code == 403, f"expected 403 for manager, got {r.status_code}"

    def test_manager_cannot_remove(self, client, firm_a_owner):
        client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.removeauth.example"},
            headers=firm_a_owner["headers"],
        )
        mgr_headers = _create_manager_user(client, firm_a_owner["firm_id"])
        r = client.delete(
            "/api/v1/portal-domain",
            headers=mgr_headers,
        )
        assert r.status_code == 403, f"expected 403 for manager, got {r.status_code}"

    def test_manager_cannot_read_records(self, client, firm_a_owner):
        client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.recordsauth.example"},
            headers=firm_a_owner["headers"],
        )
        mgr_headers = _create_manager_user(client, firm_a_owner["firm_id"])
        r = client.get(
            "/api/v1/portal-domain/records",
            headers=mgr_headers,
        )
        assert r.status_code == 403, f"expected 403 for manager, got {r.status_code}"

    def test_firm_owner_can_read_records(self, client, firm_a_owner):
        client.post(
            "/api/v1/portal-domain/register",
            json={"domain": "portal.recordsread.example"},
            headers=firm_a_owner["headers"],
        )
        r = client.get(
            "/api/v1/portal-domain/records",
            headers=firm_a_owner["headers"],
        )
        assert r.status_code == 200
        data = r.json()
        assert data["domain"] == "portal.recordsread.example"
        assert data["txt_host"] == "_jammpx-verify.portal.recordsread.example"
        assert len(data["txt_value"]) == 32
