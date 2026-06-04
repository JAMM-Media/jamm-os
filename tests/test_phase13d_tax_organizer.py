# tests/test_phase13d_tax_organizer.py
"""
Phase 13D — Tax Organizer tests.
"""

from datetime import date
from uuid import uuid4


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(client, headers, name="Organizer Client"):
    r = client.post("/clients/", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def make_engagement(client, headers, client_id):
    r = client.post("/engagements/", json={
        "client_id": client_id,
        "name": "Tax Engagement",
        "engagement_type": "tax_return_1040",
    }, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def get_first_template(client, headers):
    r = client.get("/tax-organizers/templates", headers=headers)
    assert r.status_code == 200
    templates = r.json()
    assert len(templates) >= 1, "Firm should have seeded templates"
    return templates[0]["id"]


# ── template seeding ──────────────────────────────────────────────────────────

def test_firm_has_seeded_templates(client, firm_a_owner):
    """Firm should have 3 default templates created during firm setup."""
    r = client.get("/tax-organizers/templates", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    templates = r.json()
    assert len(templates) >= 3
    types = {t["organizer_type"] for t in templates}
    assert "individual" in types
    assert "business" in types
    assert "rental" in types


def test_default_templates_have_sections(client, firm_a_owner):
    """Each seeded template must have at least one section with questions."""
    r = client.get("/tax-organizers/templates", headers=firm_a_owner["headers"])
    for template in r.json():
        assert len(template["sections"]) >= 1
        for section in template["sections"]:
            assert "questions" in section
            assert len(section["questions"]) >= 1


def test_create_custom_template(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    payload = {
        "name": "Custom Organizer",
        "organizer_type": "custom",
        "sections": [
            {
                "id": "info",
                "title": "Basic Info",
                "questions": [
                    {"id": "q1", "label": "Question 1",
                     "type": "text", "required": True}
                ]
            }
        ]
    }
    r = client.post("/tax-organizers/templates", json=payload, headers=headers)
    assert r.status_code == 201
    assert r.json()["name"] == "Custom Organizer"
    assert r.json()["is_default"] is False


def test_staff_can_list_templates(client, firm_a_staff):
    r = client.get("/tax-organizers/templates", headers=firm_a_staff["headers"])
    assert r.status_code == 200


def test_staff_cannot_create_template(client, firm_a_staff):
    r = client.post("/tax-organizers/templates", json={
        "name": "Staff Template", "organizer_type": "custom", "sections": []
    }, headers=firm_a_staff["headers"])
    assert r.status_code == 403


# ── send organizer ────────────────────────────────────────────────────────────

def test_send_organizer_creates_record(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eid = make_engagement(client, headers, cid)
    tid = get_first_template(client, headers)

    r = client.post("/tax-organizers/send", json={
        "client_id": cid,
        "engagement_id": eid,
        "template_id": tid,
        "tax_year": date.today().year,
    }, headers=headers)
    assert r.status_code == 201
    data = r.json()
    assert data["status"] == "sent"
    assert data["tax_year"] == date.today().year
    assert data["responses"] == {}


def test_send_organizer_client_mismatch_returns_400(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid_a = make_client(client, headers, name="Client A")
    cid_b = make_client(client, headers, name="Client B")
    eid = make_engagement(client, headers, cid_a)
    tid = get_first_template(client, headers)

    r = client.post("/tax-organizers/send", json={
        "client_id": cid_b,  # wrong client for this engagement
        "engagement_id": eid,
        "template_id": tid,
        "tax_year": 2024,
    }, headers=headers)
    assert r.status_code == 400


def test_send_organizer_invalid_template_returns_404(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eid = make_engagement(client, headers, cid)

    r = client.post("/tax-organizers/send", json={
        "client_id": cid,
        "engagement_id": eid,
        "template_id": str(uuid4()),
        "tax_year": 2024,
    }, headers=headers)
    assert r.status_code == 404


def test_staff_cannot_send_organizer(client, firm_a_staff, firm_a_owner):
    headers_owner = firm_a_owner["headers"]
    cid = make_client(client, headers_owner)
    eid = make_engagement(client, headers_owner, cid)
    tid = get_first_template(client, headers_owner)

    r = client.post("/tax-organizers/send", json={
        "client_id": cid,
        "engagement_id": eid,
        "template_id": tid,
        "tax_year": 2024,
    }, headers=firm_a_staff["headers"])
    assert r.status_code == 403


# ── list and get ──────────────────────────────────────────────────────────────

def test_list_organizers(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eid = make_engagement(client, headers, cid)
    tid = get_first_template(client, headers)
    client.post("/tax-organizers/send", json={
        "client_id": cid, "engagement_id": eid,
        "template_id": tid, "tax_year": 2024,
    }, headers=headers)

    r = client.get("/tax-organizers/", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_get_organizer_includes_template(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eid = make_engagement(client, headers, cid)
    tid = get_first_template(client, headers)
    oid = client.post("/tax-organizers/send", json={
        "client_id": cid, "engagement_id": eid,
        "template_id": tid, "tax_year": 2024,
    }, headers=headers).json()["id"]

    r = client.get(f"/tax-organizers/{oid}", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "template" in data
    assert "sections" in data["template"]
    assert len(data["template"]["sections"]) >= 1


# ── portal endpoints ──────────────────────────────────────────────────────────

def test_portal_save_partial_responses(client, firm_a_owner, portal_client_headers):
    """Client saves partial answers — status should change to in_progress."""
    headers = firm_a_owner["headers"]
    cid, portal_headers = portal_client_headers

    eid = make_engagement(client, headers, cid)
    tid = get_first_template(client, headers)
    oid = client.post("/tax-organizers/send", json={
        "client_id": cid, "engagement_id": eid,
        "template_id": tid, "tax_year": 2024,
    }, headers=headers).json()["id"]

    r = client.post(f"/portal/organizers/{oid}/save", json={
        "responses": {"personal_info": {"filing_status": "Single"}},
        "submit": False,
    }, headers=portal_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "in_progress"


def test_portal_submit_organizer(client, firm_a_owner, portal_client_headers):
    """Client submits organizer — status should change to submitted."""
    headers = firm_a_owner["headers"]
    cid, portal_headers = portal_client_headers

    eid = make_engagement(client, headers, cid)
    tid = get_first_template(client, headers)
    oid = client.post("/tax-organizers/send", json={
        "client_id": cid, "engagement_id": eid,
        "template_id": tid, "tax_year": 2024,
    }, headers=headers).json()["id"]

    r = client.post(f"/portal/organizers/{oid}/save", json={
        "responses": {"personal_info": {"filing_status": "Single"}},
        "submit": True,
    }, headers=portal_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "submitted"
    assert r.json()["submitted_at"] is not None


def test_portal_cannot_edit_submitted_organizer(client, firm_a_owner, portal_client_headers):
    """Once submitted, further saves are rejected."""
    headers = firm_a_owner["headers"]
    cid, portal_headers = portal_client_headers

    eid = make_engagement(client, headers, cid)
    tid = get_first_template(client, headers)
    oid = client.post("/tax-organizers/send", json={
        "client_id": cid, "engagement_id": eid,
        "template_id": tid, "tax_year": 2024,
    }, headers=headers).json()["id"]

    # Submit it
    client.post(f"/portal/organizers/{oid}/save", json={
        "responses": {}, "submit": True,
    }, headers=portal_headers)

    # Try to edit again
    r = client.post(f"/portal/organizers/{oid}/save", json={
        "responses": {"personal_info": {"filing_status": "Married Filing Jointly"}},
        "submit": False,
    }, headers=portal_headers)
    assert r.status_code == 400


def test_portal_list_organizers(client, firm_a_owner, portal_client_headers):
    headers = firm_a_owner["headers"]
    cid, portal_headers = portal_client_headers

    eid = make_engagement(client, headers, cid)
    tid = get_first_template(client, headers)
    client.post("/tax-organizers/send", json={
        "client_id": cid, "engagement_id": eid,
        "template_id": tid, "tax_year": 2024,
    }, headers=headers)

    r = client.get("/portal/organizers", headers=portal_headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_portal_tenant_isolation(client, firm_a_owner, firm_b_owner, portal_client_headers):
    """Portal client from Firm A cannot access Firm B's organizers."""
    b_headers = firm_b_owner["headers"]
    cid_b = make_client(client, b_headers, name="Firm B Client")
    eid_b = make_engagement(client, b_headers, cid_b)
    tid_b = get_first_template(client, b_headers)
    oid_b = client.post("/tax-organizers/send", json={
        "client_id": cid_b, "engagement_id": eid_b,
        "template_id": tid_b, "tax_year": 2024,
    }, headers=b_headers).json()["id"]

    _, portal_headers_a = portal_client_headers
    r = client.get(f"/portal/organizers/{oid_b}", headers=portal_headers_a)
    assert r.status_code == 404


# ── tenant isolation (staff side) ─────────────────────────────────────────────

def test_staff_tenant_isolation(client, firm_a_owner, firm_b_owner):
    a_headers = firm_a_owner["headers"]
    cid = make_client(client, a_headers, name="Firm A Organizer Client")
    eid = make_engagement(client, a_headers, cid)
    tid = get_first_template(client, a_headers)
    client.post("/tax-organizers/send", json={
        "client_id": cid, "engagement_id": eid,
        "template_id": tid, "tax_year": 2024,
    }, headers=a_headers)

    r = client.get("/tax-organizers/", headers=firm_b_owner["headers"])
    assert r.status_code == 200
    assert not any(i["client_id"] == cid for i in r.json())
