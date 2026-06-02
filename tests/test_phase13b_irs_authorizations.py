# tests/test_phase13b_irs_authorizations.py
"""
Phase 13B — IRS Authorization tests.
"""

from uuid import uuid4


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(client, headers, name="IRS Test Client"):
    r = client.post(
        "/clients/",
        json={"name": name, "primary_email": f"{uuid4()}@test.com"},
        headers=headers,
    )
    assert r.status_code == 201
    return r.json()["id"]


def send_auth(client, headers, client_id, form_type="8821", tax_years=None):
    return client.post(
        "/irs-authorizations/send",
        json={
            "client_id": client_id,
            "form_type": form_type,
            "tax_years": tax_years or [2023, 2024],
        },
        headers=headers,
    )


# ── basic CRUD ────────────────────────────────────────────────────────────────

def test_send_8821_creates_authorization(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = send_auth(client, headers, cid, form_type="8821")
    assert r.status_code == 201
    data = r.json()
    assert data["form_type"] == "8821"
    assert data["status"] == "pending_signature"
    assert 2023 in data["tax_years"]
    assert 2024 in data["tax_years"]


def test_send_2848_creates_authorization(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = send_auth(client, headers, cid, form_type="2848")
    assert r.status_code == 201
    assert r.json()["form_type"] == "2848"


def test_list_irs_authorizations(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_auth(client, headers, cid, form_type="8821")
    send_auth(client, headers, cid, form_type="2848")
    r = client.get("/irs-authorizations/", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_list_filter_by_client(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid_a = make_client(client, headers, name="Client Alpha")
    cid_b = make_client(client, headers, name="Client Beta")
    send_auth(client, headers, cid_a)
    send_auth(client, headers, cid_b)
    r = client.get(f"/irs-authorizations/?client_id={cid_a}", headers=headers)
    assert r.status_code == 200
    assert all(i["client_id"] == cid_a for i in r.json())


def test_get_single_authorization(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    auth_id = send_auth(client, headers, cid).json()["id"]
    r = client.get(f"/irs-authorizations/{auth_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == auth_id


def test_get_nonexistent_returns_404(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.get(f"/irs-authorizations/{uuid4()}", headers=headers)
    assert r.status_code == 404


# ── validation ────────────────────────────────────────────────────────────────

def test_invalid_form_type_rejected(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = client.post("/irs-authorizations/send", json={
        "client_id": cid, "form_type": "1040", "tax_years": [2024],
    }, headers=headers)
    assert r.status_code == 422


def test_invalid_tax_year_rejected(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = client.post("/irs-authorizations/send", json={
        "client_id": cid, "form_type": "8821", "tax_years": [1850],
    }, headers=headers)
    assert r.status_code == 422


def test_client_not_in_firm_returns_404(client, firm_a_owner, firm_b_owner):
    b_headers = firm_b_owner["headers"]
    cid_b = make_client(client, b_headers, name="Firm B Client")
    a_headers = firm_a_owner["headers"]
    r = client.post("/irs-authorizations/send", json={
        "client_id": cid_b, "form_type": "8821", "tax_years": [2024],
    }, headers=a_headers)
    assert r.status_code == 404


# ── RBAC ──────────────────────────────────────────────────────────────────────

def test_staff_cannot_list_irs_authorizations(client, firm_a_staff):
    r = client.get("/irs-authorizations/", headers=firm_a_staff["headers"])
    assert r.status_code == 403


def test_staff_cannot_send_authorization(client, firm_a_staff, firm_a_owner):
    cid = make_client(client, firm_a_owner["headers"])
    r = client.post("/irs-authorizations/send", json={
        "client_id": cid, "form_type": "8821", "tax_years": [2024],
    }, headers=firm_a_staff["headers"])
    assert r.status_code == 403


# ── status update ─────────────────────────────────────────────────────────────

def test_patch_status_to_active(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    auth_id = send_auth(client, headers, cid).json()["id"]
    r = client.patch(f"/irs-authorizations/{auth_id}", json={"status": "active"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "active"


def test_patch_invalid_status_rejected(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    auth_id = send_auth(client, headers, cid).json()["id"]
    r = client.patch(f"/irs-authorizations/{auth_id}", json={"status": "banana"}, headers=headers)
    assert r.status_code == 422


# ── check status endpoint ─────────────────────────────────────────────────────

def test_check_status_no_auth_on_file(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = client.get(f"/irs-authorizations/check/{cid}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["has_active_8821"] is False
    assert data["has_active_2848"] is False


def test_check_status_after_activating(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    auth_id = send_auth(client, headers, cid, form_type="8821").json()["id"]
    client.patch(f"/irs-authorizations/{auth_id}", json={"status": "active"}, headers=headers)
    r = client.get(f"/irs-authorizations/check/{cid}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["has_active_8821"] is True
    assert data["has_active_2848"] is False


# ── tenant isolation ──────────────────────────────────────────────────────────

def test_tenant_isolation_list(client, firm_a_owner, firm_b_owner):
    a_headers = firm_a_owner["headers"]
    cid_a = make_client(client, a_headers, name="Firm A IRS Client")
    send_auth(client, a_headers, cid_a)
    r = client.get("/irs-authorizations/", headers=firm_b_owner["headers"])
    assert r.status_code == 200
    assert not any(i["client_id"] == cid_a for i in r.json())


def test_tenant_isolation_get(client, firm_a_owner, firm_b_owner):
    a_headers = firm_a_owner["headers"]
    cid_a = make_client(client, a_headers)
    auth_id = send_auth(client, a_headers, cid_a).json()["id"]
    r = client.get(f"/irs-authorizations/{auth_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404


# ── expiry check trigger ──────────────────────────────────────────────────────

def test_run_expiry_check_endpoint(client, firm_a_owner):
    r = client.post("/irs-authorizations/run-expiry-check", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    assert "queued" in r.json()["message"].lower()
