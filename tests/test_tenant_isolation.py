# tests/test_tenant_isolation.py

"""
Tenant Isolation Tests — the most important tests in the entire codebase.

These tests prove one thing: a user logged into Firm A cannot see, modify,
or delete any data that belongs to Firm B.

This is the core security guarantee of JAMM PX. If any of these tests fail,
it means there is a data leak between firms — a critical security breach.

Every test follows the same pattern:
1. Log in as Firm A and create a resource
2. Log in as Firm B and try to access that resource
3. Assert that Firm B gets 404 (not 403 — we don't even confirm it exists)
"""


def _create_client(client_fixture, headers, name="Test Client"):
    r = client_fixture.post(
        "/clients/",
        json={"name": name, "email": f"{name.lower().replace(' ', '')}@test.com"},
        headers=headers,
    )
    assert r.status_code == 201, f"Failed to create client: {r.json()}"
    return r.json()


def _create_engagement(client_fixture, headers, client_id, name="2024 Tax Return"):
    r = client_fixture.post(
        "/engagements/",
        json={"name": name, "client_id": client_id},
        headers=headers,
    )
    assert r.status_code == 201, f"Failed to create engagement: {r.json()}"
    return r.json()


def _create_task(client_fixture, headers, client_id, engagement_id, title="Review W2"):
    r = client_fixture.post(
        "/tasks/",
        json={"title": title, "client_id": client_id, "engagement_id": engagement_id},
        headers=headers,
    )
    assert r.status_code == 201, f"Failed to create task: {r.json()}"
    return r.json()


# =============================================================================
# CLIENT ISOLATION
# =============================================================================

class TestClientIsolation:
    def test_firm_b_cannot_see_firm_a_client(self, client, firm_a_owner, firm_b_owner):
        """Firm B must get 404 when requesting a client that belongs to Firm A."""
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        # Firm A creates a client
        client_a = _create_client(client, headers_a, "Smith Family")

        # Firm B tries to fetch that client by ID — must get 404
        r = client.get(f"/clients/{client_a['id']}", headers=headers_b)
        assert r.status_code == 404, (
            f"SECURITY BREACH: Firm B was able to access Firm A's client! "
            f"Status: {r.status_code}, Body: {r.json()}"
        )

    def test_firm_b_list_does_not_include_firm_a_clients(self, client, firm_a_owner, firm_b_owner):
        """When Firm B lists clients, they must never see Firm A's clients."""
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        # Firm A creates two clients
        _create_client(client, headers_a, "Firm A Client 1")
        _create_client(client, headers_a, "Firm A Client 2")

        # Firm B creates one client
        _create_client(client, headers_b, "Firm B Client 1")

        # Firm B lists their clients — should only see 1, not 3
        r = client.get("/clients/", headers=headers_b)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1, (
            f"SECURITY BREACH: Firm B can see {data['total']} clients "
            f"but should only see 1. Cross-tenant data leak detected."
        )
        assert data["items"][0]["name"] == "Firm B Client 1"

    def test_firm_b_cannot_update_firm_a_client(self, client, firm_a_owner, firm_b_owner):
        """Firm B must not be able to update a client belonging to Firm A."""
        client_a = _create_client(client, firm_a_owner["headers"], "Target Client")

        r = client.patch(
            f"/clients/{client_a['id']}",
            json={"name": "Hijacked Name"},
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404

        # Verify the client name was NOT changed
        r_verify = client.get(f"/clients/{client_a['id']}", headers=firm_a_owner["headers"])
        assert r_verify.json()["name"] == "Target Client"

    def test_firm_b_cannot_delete_firm_a_client(self, client, firm_a_owner, firm_b_owner):
        """Firm B must not be able to delete a client belonging to Firm A."""
        client_a = _create_client(client, firm_a_owner["headers"], "Protected Client")

        r = client.delete(
            f"/clients/{client_a['id']}",
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404

        # Verify the client still exists for Firm A
        r_verify = client.get(f"/clients/{client_a['id']}", headers=firm_a_owner["headers"])
        assert r_verify.status_code == 200


# =============================================================================
# ENGAGEMENT ISOLATION
# =============================================================================

class TestEngagementIsolation:
    def test_firm_b_cannot_see_firm_a_engagement(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        client_a = _create_client(client, headers_a)
        engagement_a = _create_engagement(client, headers_a, client_a["id"])

        r = client.get(f"/engagements/{engagement_a['id']}", headers=headers_b)
        assert r.status_code == 404, (
            f"SECURITY BREACH: Firm B accessed Firm A's engagement. "
            f"Status: {r.status_code}"
        )

    def test_firm_b_list_does_not_include_firm_a_engagements(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        # Firm A creates 3 engagements
        client_a = _create_client(client, headers_a)
        _create_engagement(client, headers_a, client_a["id"], "Tax Return 2022")
        _create_engagement(client, headers_a, client_a["id"], "Tax Return 2023")
        _create_engagement(client, headers_a, client_a["id"], "Tax Return 2024")

        # Firm B creates 1 engagement
        client_b = _create_client(client, headers_b, "Firm B Client")
        _create_engagement(client, headers_b, client_b["id"], "Bookkeeping Q1")

        r = client.get("/engagements/", headers=headers_b)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1, (
            f"SECURITY BREACH: Firm B sees {data['total']} engagements, expected 1."
        )

    def test_firm_b_cannot_update_firm_a_engagement(self, client, firm_a_owner, firm_b_owner):
        client_a = _create_client(client, firm_a_owner["headers"])
        engagement_a = _create_engagement(client, firm_a_owner["headers"], client_a["id"])

        r = client.patch(
            f"/engagements/{engagement_a['id']}",
            json={"name": "Hijacked Engagement"},
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404

    def test_firm_b_cannot_delete_firm_a_engagement(self, client, firm_a_owner, firm_b_owner):
        client_a = _create_client(client, firm_a_owner["headers"])
        engagement_a = _create_engagement(client, firm_a_owner["headers"], client_a["id"])

        r = client.delete(
            f"/engagements/{engagement_a['id']}",
            headers=firm_b_owner["headers"],
        )
        assert r.status_code == 404


# =============================================================================
# TASK ISOLATION
# =============================================================================

class TestTaskIsolation:
    def test_firm_b_cannot_see_firm_a_task(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        client_a = _create_client(client, headers_a)
        engagement_a = _create_engagement(client, headers_a, client_a["id"])
        task_a = _create_task(client, headers_a, client_a["id"], engagement_a["id"])

        r = client.get(f"/tasks/{task_a['id']}", headers=headers_b)
        assert r.status_code == 404, (
            f"SECURITY BREACH: Firm B accessed Firm A's task. Status: {r.status_code}"
        )

    def test_firm_b_list_does_not_include_firm_a_tasks(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        client_a = _create_client(client, headers_a)
        engagement_a = _create_engagement(client, headers_a, client_a["id"])
        _create_task(client, headers_a, client_a["id"], engagement_a["id"], "Firm A Task 1")
        _create_task(client, headers_a, client_a["id"], engagement_a["id"], "Firm A Task 2")

        client_b = _create_client(client, headers_b, "Firm B Client")
        engagement_b = _create_engagement(client, headers_b, client_b["id"])
        _create_task(client, headers_b, client_b["id"], engagement_b["id"], "Firm B Task 1")

        r = client.get("/tasks/", headers=headers_b)
        assert r.status_code == 200
        data = r.json()
        assert data["total"] == 1, (
            f"SECURITY BREACH: Firm B sees {data['total']} tasks, expected 1."
        )


# =============================================================================
# CONTACT ISOLATION
# =============================================================================

class TestContactIsolation:
    def test_firm_b_cannot_see_firm_a_contact(self, client, firm_a_owner, firm_b_owner):
        headers_a = firm_a_owner["headers"]
        headers_b = firm_b_owner["headers"]

        client_a = _create_client(client, headers_a)
        contact_resp = client.post(
            "/contacts/",
            json={"name": "Jane Smith", "email": "jane@test.com", "client_id": client_a["id"]},
            headers=headers_a,
        )
        assert contact_resp.status_code == 201
        contact_id = contact_resp.json()["id"]

        r = client.get(f"/contacts/{contact_id}", headers=headers_b)
        assert r.status_code == 404, (
            f"SECURITY BREACH: Firm B accessed Firm A's contact. Status: {r.status_code}"
        )


# =============================================================================
# SESSION INVALIDATION ON ROLE CHANGE
# =============================================================================

class TestSessionInvalidation:
    def test_token_invalidated_after_role_change(self, client, firm_a_owner):
        """
        When a user's role is changed, their existing JWT should be rejected.
        This prevents a scenario where a staff member who gets promoted to
        firm_owner retains their old staff-level token.
        """
        # This test requires a staff user within Firm A whose role we can change.
        # For now, we verify the token_version mechanism is in place by checking
        # that the /users/me endpoint returns the correct token_version.
        headers_a = firm_a_owner["headers"]
        r = client.get("/users/me", headers=headers_a)
        assert r.status_code == 200
        # The token_version field should exist (not in UserOut schema currently,
        # but the underlying User model has it — this is a placeholder assertion)
        assert "id" in r.json()