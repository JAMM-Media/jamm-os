# tests/test_phase13e_transcript_requests.py
"""
Phase 13E — Transcript Request tests.
"""

from uuid import uuid4


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(client, headers, name="Transcript Client"):
    r = client.post("/clients/", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def send_8821(client, headers, client_id, activate=True):
    """Send an 8821 and optionally activate it (simulate webhook)."""
    r = client.post("/irs-authorizations/send", json={
        "client_id": client_id,
        "form_type": "8821",
        "tax_years": [2023, 2024],
    }, headers=headers)
    assert r.status_code == 201
    auth_id = r.json()["id"]

    if activate:
        client.patch(
            f"/irs-authorizations/{auth_id}",
            json={"status": "active"},
            headers=headers,
        )
    return auth_id


def request_transcript(client, headers, client_id, transcript_type="wage_and_income", tax_year=2023):
    return client.post("/transcript-requests/", json={
        "client_id": client_id,
        "transcript_type": transcript_type,
        "tax_year": tax_year,
    }, headers=headers)


# ── 8821 authorization gate ───────────────────────────────────────────────────

def test_request_without_8821_returns_400(client, firm_a_owner):
    """Cannot request transcript without active 8821 on file."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    assert "8821" in r.json()["detail"]


def test_request_with_pending_8821_returns_400(client, firm_a_owner):
    """Pending (unsigned) 8821 is not sufficient — must be active."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid, activate=False)  # sent but not signed

    r = request_transcript(client, headers, cid)
    assert r.status_code == 400
    assert "8821" in r.json()["detail"]


def test_request_with_active_8821_succeeds(client, firm_a_owner):
    """Active 8821 allows transcript request."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid, activate=True)

    r = request_transcript(client, headers, cid)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "pending"
    assert data["transcript_type"] == "wage_and_income"
    assert data["tax_year"] == 2023
    assert data["client_id"] == cid


# ── all transcript types ──────────────────────────────────────────────────────

def test_all_transcript_types_accepted(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid)

    for t_type in ["wage_and_income", "account", "tax_return", "record_of_account"]:
        r = request_transcript(client, headers, cid, transcript_type=t_type)
        assert r.status_code == 201, f"Failed for type: {t_type}"
        assert r.json()["transcript_type"] == t_type


def test_invalid_transcript_type_rejected(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid)

    r = client.post("/transcript-requests/", json={
        "client_id": cid,
        "transcript_type": "fake_type",
        "tax_year": 2023,
    }, headers=headers)
    assert r.status_code == 422


def test_future_tax_year_rejected(client, firm_a_owner):
    from datetime import date
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid)

    r = client.post("/transcript-requests/", json={
        "client_id": cid,
        "transcript_type": "wage_and_income",
        "tax_year": date.today().year + 1,
    }, headers=headers)
    assert r.status_code == 422


# ── list and get ──────────────────────────────────────────────────────────────

def test_list_transcript_requests(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid)
    request_transcript(client, headers, cid)
    request_transcript(client, headers, cid, transcript_type="account")

    r = client.get("/transcript-requests/", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 2


def test_list_filter_by_client(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid_a = make_client(client, headers, name="Client A")
    cid_b = make_client(client, headers, name="Client B")
    send_8821(client, headers, cid_a)
    send_8821(client, headers, cid_b)
    request_transcript(client, headers, cid_a)
    request_transcript(client, headers, cid_b)

    r = client.get(f"/transcript-requests/?client_id={cid_a}", headers=headers)
    assert r.status_code == 200
    assert all(i["client_id"] == cid_a for i in r.json())


def test_get_single_request(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid)
    req_id = request_transcript(client, headers, cid).json()["id"]

    r = client.get(f"/transcript-requests/{req_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == req_id


def test_get_nonexistent_returns_404(client, firm_a_owner):
    r = client.get(f"/transcript-requests/{uuid4()}", headers=firm_a_owner["headers"])
    assert r.status_code == 404


# ── check endpoint ────────────────────────────────────────────────────────────

def test_check_without_8821(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    r = client.get(f"/transcript-requests/check/{cid}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["can_request"] is False
    assert data["authorization_status"] == "not_on_file"


def test_check_with_active_8821(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid, activate=True)

    r = client.get(f"/transcript-requests/check/{cid}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["can_request"] is True
    assert data["authorization_status"] == "active"
    assert data["irs_authorization_id"] is not None


# ── RBAC ──────────────────────────────────────────────────────────────────────

def test_staff_cannot_submit_transcript_request(client, firm_a_staff, firm_a_owner):
    cid = make_client(client, firm_a_owner["headers"])
    send_8821(client, firm_a_owner["headers"], cid)

    r = request_transcript(client, firm_a_staff["headers"], cid)
    assert r.status_code == 403


def test_staff_cannot_list_transcript_requests(client, firm_a_staff):
    r = client.get("/transcript-requests/", headers=firm_a_staff["headers"])
    assert r.status_code == 403


# ── status update ─────────────────────────────────────────────────────────────

def test_patch_status_to_failed(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    send_8821(client, headers, cid)
    req_id = request_transcript(client, headers, cid).json()["id"]

    r = client.patch(f"/transcript-requests/{req_id}", json={
        "status": "failed",
        "error_message": "IRS TDS unavailable",
    }, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "failed"
    assert r.json()["error_message"] == "IRS TDS unavailable"


# ── tenant isolation ──────────────────────────────────────────────────────────

def test_tenant_isolation_list(client, firm_a_owner, firm_b_owner):
    a_headers = firm_a_owner["headers"]
    cid_a = make_client(client, a_headers, name="Firm A Transcript Client")
    send_8821(client, a_headers, cid_a)
    request_transcript(client, a_headers, cid_a)

    r = client.get("/transcript-requests/", headers=firm_b_owner["headers"])
    assert r.status_code == 200
    assert not any(i["client_id"] == cid_a for i in r.json())


def test_tenant_isolation_get(client, firm_a_owner, firm_b_owner):
    a_headers = firm_a_owner["headers"]
    cid_a = make_client(client, a_headers)
    send_8821(client, a_headers, cid_a)
    req_id = request_transcript(client, a_headers, cid_a).json()["id"]

    r = client.get(f"/transcript-requests/{req_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404
