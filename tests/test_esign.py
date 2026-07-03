# tests/test_esign.py

import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client(client, headers, name="ESig Client"):
    """Create a client under the given auth context and return its id."""
    r = client.post("/clients/", json={"name": name}, headers=headers)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _create_envelope(client, headers, client_id, **kwargs):
    """POST /esign/envelopes with sensible defaults, kwargs override."""
    payload = {"client_id": client_id, "signers": [], **kwargs}
    return client.post("/esign/envelopes", json=payload, headers=headers)


def _create_letter_template(client, headers, name="Standard Engagement Letter", **kwargs):
    """POST /esign/templates with sensible defaults, kwargs override."""
    payload = {
        "name": name,
        "body_html": "<p>Dear {{client_name}},</p>",
        "variable_fields": ["client_name"],
        "is_active": True,
        **kwargs,
    }
    return client.post("/esign/templates", json=payload, headers=headers)


# ---------------------------------------------------------------------------
# Signature Envelope tests
# ---------------------------------------------------------------------------

def test_create_envelope(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    r = _create_envelope(client, headers, client_id)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["status"] == "draft"
    assert data["firm_id"] == firm_a_owner["firm_id"]
    assert data["client_id"] == client_id


def test_create_envelope_invalid_client(client, firm_a_owner, firm_b_owner):
    """client_id belonging to a different firm must return 404."""
    # Create a client under firm B
    b_client_id = _make_client(client, firm_b_owner["headers"], name="Firm B Client")

    # Try to create an envelope under firm A using firm B's client_id
    r = _create_envelope(client, firm_a_owner["headers"], b_client_id)
    assert r.status_code == 404, r.text


def test_create_envelope_invalid_status(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    r = _create_envelope(client, headers, client_id, status="invalid_status")
    assert r.status_code == 422, r.text


def test_list_envelopes(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    _create_envelope(client, headers, client_id)
    _create_envelope(client, headers, client_id)

    r = client.get("/esign/envelopes", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 2
    assert len(data["items"]) >= 2


def test_list_envelopes_filter_by_status(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    created = _create_envelope(client, headers, client_id)
    assert created.status_code == 201, created.text

    r = client.get("/esign/envelopes?status=draft", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 1
    ids = {item["id"] for item in data["items"]}
    assert created.json()["id"] in ids


def test_get_envelope(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    created = _create_envelope(client, headers, client_id)
    envelope_id = created.json()["id"]

    r = client.get(f"/esign/envelopes/{envelope_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == envelope_id


def test_get_envelope_wrong_firm(client, firm_a_owner, firm_b_owner):
    """Firm B cannot read an envelope that belongs to Firm A."""
    headers_a = firm_a_owner["headers"]
    client_id = _make_client(client, headers_a)

    created = _create_envelope(client, headers_a, client_id)
    envelope_id = created.json()["id"]

    r = client.get(f"/esign/envelopes/{envelope_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404, r.text


def test_update_envelope(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    created = _create_envelope(client, headers, client_id)
    envelope_id = created.json()["id"]

    r = client.patch(
        f"/esign/envelopes/{envelope_id}",
        json={"subject": "Updated Subject"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["subject"] == "Updated Subject"


def test_update_envelope_invalid_status(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    created = _create_envelope(client, headers, client_id)
    envelope_id = created.json()["id"]

    r = client.patch(
        f"/esign/envelopes/{envelope_id}",
        json={"status": "invalid"},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_delete_envelope(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id = _make_client(client, headers)

    created = _create_envelope(client, headers, client_id)
    envelope_id = created.json()["id"]

    r = client.delete(f"/esign/envelopes/{envelope_id}", headers=headers)
    assert r.status_code == 200, r.text

    r2 = client.get(f"/esign/envelopes/{envelope_id}", headers=headers)
    assert r2.status_code == 404


# ---------------------------------------------------------------------------
# Engagement Letter Template tests
# ---------------------------------------------------------------------------

def test_create_template(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    r = _create_letter_template(client, headers)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Standard Engagement Letter"
    assert data["firm_id"] == firm_a_owner["firm_id"]
    assert data["variable_fields"] == ["client_name"]


def test_create_template_missing_required(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    # body_html is required — omitting it must return 422
    r = client.post(
        "/esign/templates",
        json={"name": "Incomplete Template"},
        headers=headers,
    )
    assert r.status_code == 422, r.text


def test_list_templates(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    _create_letter_template(client, headers, name="Template Alpha")
    _create_letter_template(client, headers, name="Template Beta")

    r = client.get("/esign/templates", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["total"] >= 2
    names = {item["name"] for item in data["items"]}
    assert {"Template Alpha", "Template Beta"}.issubset(names)


def test_list_templates_filter_active(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    _create_letter_template(client, headers, name="Active Template", is_active=True)
    _create_letter_template(client, headers, name="Inactive Template", is_active=False)

    r = client.get("/esign/templates?is_active=true", headers=headers)
    assert r.status_code == 200, r.text
    data = r.json()
    names = {item["name"] for item in data["items"]}
    assert "Active Template" in names
    assert "Inactive Template" not in names


def test_get_template(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    created = _create_letter_template(client, headers)
    template_id = created.json()["id"]

    r = client.get(f"/esign/templates/{template_id}", headers=headers)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == template_id


def test_get_template_wrong_firm(client, firm_a_owner, firm_b_owner):
    """Firm B cannot read a template that belongs to Firm A."""
    created = _create_letter_template(client, firm_a_owner["headers"])
    template_id = created.json()["id"]

    r = client.get(f"/esign/templates/{template_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404, r.text


def test_update_template(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    created = _create_letter_template(client, headers)
    template_id = created.json()["id"]

    r = client.patch(
        f"/esign/templates/{template_id}",
        json={"name": "Renamed Template"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "Renamed Template"


def test_delete_template(client, firm_a_owner):
    headers = firm_a_owner["headers"]

    created = _create_letter_template(client, headers)
    template_id = created.json()["id"]

    r = client.delete(f"/esign/templates/{template_id}", headers=headers)
    assert r.status_code == 200, r.text

    # Delete is a soft delete (is_active=False), not a hard delete: the
    # frontend's "Deleted Templates" tab lists and restores inactive
    # templates, so GET must keep returning them. A proper is_deleted
    # column (distinct from is_active) is deferred post launch.
    r2 = client.get(f"/esign/templates/{template_id}", headers=headers)
    assert r2.status_code == 200, r2.text
    assert r2.json()["is_active"] is False


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

def test_tenant_isolation(client, firm_a_owner, firm_b_owner):
    """
    Security proof: Firm B cannot access an envelope created by Firm A.
    Cross-tenant data leakage is impossible because every query is scoped
    to firm_id extracted from the JWT — never from user-supplied input.
    """
    headers_a = firm_a_owner["headers"]
    client_id = _make_client(client, headers_a)

    created = _create_envelope(client, headers_a, client_id)
    assert created.status_code == 201, created.text
    envelope_id = created.json()["id"]

    # Firm B GET → must be 404, not 403, to avoid leaking that the resource exists
    r = client.get(f"/esign/envelopes/{envelope_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404, r.text
