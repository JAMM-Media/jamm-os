# tests/test_document_requests.py

import uuid

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_client_and_engagement(client, headers):
    """Create a client + engagement under the given auth context."""
    cl = client.post("/clients/", json={"name": "DR Test Client"}, headers=headers)
    assert cl.status_code == 201, cl.text
    client_id = cl.json()["id"]

    eng = client.post(
        "/engagements/",
        json={"name": "DR Test Engagement", "client_id": client_id},
        headers=headers,
    )
    assert eng.status_code == 201, eng.text
    engagement_id = eng.json()["id"]
    return client_id, engagement_id


def _make_checklist_items(item_ids=("item-1", "item-2")):
    return [
        {"id": iid, "label": f"Document {iid}", "is_required": True, "status": "pending"}
        for iid in item_ids
    ]


def _create_request(client, headers, client_id, engagement_id, title="Tax Docs 2024", items=None):
    payload = {
        "client_id": client_id,
        "engagement_id": engagement_id,
        "title": title,
        "checklist_items": items if items is not None else _make_checklist_items(),
    }
    r = client.post("/document-requests/", json=payload, headers=headers)
    return r


# ---------------------------------------------------------------------------
# Document Request CRUD tests
# ---------------------------------------------------------------------------

def test_create_document_request(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    r = _create_request(client, headers, client_id, engagement_id)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Tax Docs 2024"
    assert data["firm_id"] == firm_a_owner["firm_id"]
    assert data["client_id"] == client_id
    assert data["engagement_id"] == engagement_id
    assert data["status"] == "pending"
    assert len(data["checklist_items"]) == 2
    assert data["checklist_items"][0]["id"] == "item-1"
    assert data["checklist_items"][0]["status"] == "pending"


def test_create_document_request_missing_fields(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    # Missing client_id and engagement_id
    r = client.post("/document-requests/", json={"title": "Incomplete"}, headers=headers)
    assert r.status_code == 422


def test_list_document_requests(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    _create_request(client, headers, client_id, engagement_id, title="Request One")
    _create_request(client, headers, client_id, engagement_id, title="Request Two")

    r = client.get("/document-requests/", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    titles = {item["title"] for item in data["items"]}
    assert titles == {"Request One", "Request Two"}


def test_list_document_requests_filter_by_status(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    r1 = _create_request(client, headers, client_id, engagement_id, title="Pending Request")
    req_id = r1.json()["id"]

    # Manually push one request to "complete" via PATCH
    client.patch(
        f"/document-requests/{req_id}",
        json={"status": "complete"},
        headers=headers,
    )

    _create_request(client, headers, client_id, engagement_id, title="Another Pending")

    r = client.get("/document-requests/?status=complete", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 1
    assert data["items"][0]["status"] == "complete"

    r2 = client.get("/document-requests/?status=pending", headers=headers)
    assert r2.json()["total"] == 1


def test_get_document_request(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    created = _create_request(client, headers, client_id, engagement_id)
    req_id = created.json()["id"]

    r = client.get(f"/document-requests/{req_id}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["id"] == req_id
    assert data["title"] == "Tax Docs 2024"
    assert data["firm_id"] == firm_a_owner["firm_id"]


def test_get_document_request_not_found(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = client.get(f"/document-requests/{uuid.uuid4()}", headers=headers)
    assert r.status_code == 404


def test_update_document_request(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    created = _create_request(client, headers, client_id, engagement_id)
    req_id = created.json()["id"]

    r = client.patch(
        f"/document-requests/{req_id}",
        json={"title": "Updated Title"},
        headers=headers,
    )
    assert r.status_code == 200
    assert r.json()["title"] == "Updated Title"


def test_delete_document_request(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    created = _create_request(client, headers, client_id, engagement_id)
    req_id = created.json()["id"]

    r = client.delete(f"/document-requests/{req_id}", headers=headers)
    assert r.status_code == 204

    r2 = client.get(f"/document-requests/{req_id}", headers=headers)
    assert r2.status_code == 404


# ---------------------------------------------------------------------------
# Checklist item status tests
# ---------------------------------------------------------------------------

def test_update_checklist_item_status(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    created = _create_request(client, headers, client_id, engagement_id)
    req_id = created.json()["id"]

    r = client.patch(
        f"/document-requests/{req_id}/items/item-1",
        json={"status": "uploaded"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    items = {i["id"]: i for i in r.json()["checklist_items"]}
    assert items["item-1"]["status"] == "uploaded"
    assert items["item-2"]["status"] == "pending"


def test_auto_complete_when_all_required_items_uploaded(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    created = _create_request(
        client, headers, client_id, engagement_id,
        items=_make_checklist_items(("doc-a", "doc-b")),
    )
    req_id = created.json()["id"]

    client.patch(
        f"/document-requests/{req_id}/items/doc-a",
        json={"status": "uploaded"},
        headers=headers,
    )
    r = client.patch(
        f"/document-requests/{req_id}/items/doc-b",
        json={"status": "uploaded"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["status"] == "complete"
    assert data["completed_at"] is not None


def test_partial_status_when_some_required_items_uploaded(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    created = _create_request(
        client, headers, client_id, engagement_id,
        items=_make_checklist_items(("doc-x", "doc-y")),
    )
    req_id = created.json()["id"]

    r = client.patch(
        f"/document-requests/{req_id}/items/doc-x",
        json={"status": "uploaded"},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "partial"
    assert r.json()["completed_at"] is None


def test_update_checklist_item_bad_item_id(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    created = _create_request(client, headers, client_id, engagement_id)
    req_id = created.json()["id"]

    r = client.patch(
        f"/document-requests/{req_id}/items/nonexistent-item",
        json={"status": "uploaded"},
        headers=headers,
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------

def test_tenant_isolation(client, firm_a_owner, firm_b_owner):
    """Firm B cannot read or delete a document request belonging to Firm A."""
    a_headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, a_headers)
    created = _create_request(client, a_headers, client_id, engagement_id)
    req_id = created.json()["id"]

    # Firm B GET → 404
    r = client.get(f"/document-requests/{req_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404

    # Firm B DELETE → 404
    r2 = client.delete(f"/document-requests/{req_id}", headers=firm_b_owner["headers"])
    assert r2.status_code == 404

    # Firm A can still read it
    r3 = client.get(f"/document-requests/{req_id}", headers=a_headers)
    assert r3.status_code == 200


# ---------------------------------------------------------------------------
# Checklist Template tests
# ---------------------------------------------------------------------------

def _create_template(client, headers, name="Standard 1040", engagement_type="individual_tax"):
    payload = {
        "name": name,
        "engagement_type": engagement_type,
        "items": [
            {"id": "t-item-1", "label": "W-2", "is_required": True, "status": "pending"},
            {"id": "t-item-2", "label": "1099", "is_required": False, "status": "pending"},
        ],
    }
    return client.post("/checklist-templates/", json=payload, headers=headers)


def test_create_template(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    r = _create_template(client, headers)
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["name"] == "Standard 1040"
    assert data["engagement_type"] == "individual_tax"
    assert data["firm_id"] == firm_a_owner["firm_id"]
    assert len(data["items"]) == 2


def test_list_templates(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    _create_template(client, headers, name="Template One")
    _create_template(client, headers, name="Template Two", engagement_type="business_tax")

    r = client.get("/checklist-templates/", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert data["total"] == 2
    names = {item["name"] for item in data["items"]}
    assert names == {"Template One", "Template Two"}


def test_apply_template(client, firm_a_owner):
    """POST /checklist-templates/{id}/apply creates a DocumentRequest with the template's items."""
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    tmpl_r = _create_template(client, headers)
    assert tmpl_r.status_code == 201, tmpl_r.text
    template_id = tmpl_r.json()["id"]

    r = client.post(
        f"/checklist-templates/{template_id}/apply",
        json={"client_id": client_id, "engagement_id": engagement_id},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    # Title defaults to template name
    assert data["title"] == "Standard 1040"
    assert data["client_id"] == client_id
    assert data["engagement_id"] == engagement_id
    assert data["firm_id"] == firm_a_owner["firm_id"]
    item_ids = {i["id"] for i in data["checklist_items"]}
    assert item_ids == {"t-item-1", "t-item-2"}


def test_apply_template_custom_title_and_due_date(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    tmpl_r = _create_template(client, headers)
    template_id = tmpl_r.json()["id"]

    r = client.post(
        f"/checklist-templates/{template_id}/apply",
        json={
            "client_id": client_id,
            "engagement_id": engagement_id,
            "title": "Custom Title",
            "due_date": "2026-04-15",
        },
        headers=headers,
    )
    assert r.status_code == 201, r.text
    data = r.json()
    assert data["title"] == "Custom Title"
    assert data["due_date"] == "2026-04-15"


def test_apply_template_not_found(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    client_id, engagement_id = _make_client_and_engagement(client, headers)

    r = client.post(
        f"/checklist-templates/{uuid.uuid4()}/apply",
        json={"client_id": client_id, "engagement_id": engagement_id},
        headers=headers,
    )
    assert r.status_code == 404
