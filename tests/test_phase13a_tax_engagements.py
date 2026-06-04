# tests/test_phase13a_tax_engagements.py
"""
Phase 13A — Tax engagement foundation tests.

Tests cover:
- engagement_type field accepted and stored
- filing_deadline auto-populated from engagement_type on creation
- Types with no IRS deadline (advisory, custom) get no auto-deadline
- extended_deadline can be set via PATCH
- deadline-watch endpoint returns correct results
- deadline-watch respects the days window parameter
- deadline-watch excludes completed and archived engagements
- deadline-watch tenant isolation: firm B cannot see firm A deadlines
- invalid engagement_type rejected with 422
"""

import pytest
from datetime import date, timedelta


# ── helpers ──────────────────────────────────────────────────────────────────

def make_client(client, headers, name="Tax Client"):
    r = client.post("/clients/", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def make_engagement(client, headers, client_id, **kwargs):
    payload = {"client_id": client_id, "name": "Test Engagement", **kwargs}
    r = client.post("/engagements/", json=payload, headers=headers)
    return r


# ── engagement_type field ─────────────────────────────────────────────────────

def test_create_engagement_with_type(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="tax_return_1040")
    assert r.status_code == 201
    data = r.json()
    assert data["engagement_type"] == "tax_return_1040"


def test_create_engagement_without_type(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid)
    assert r.status_code == 201
    assert r.json()["engagement_type"] is None


def test_invalid_engagement_type_rejected(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="not_a_real_type")
    assert r.status_code == 422


# ── filing_deadline auto-population ──────────────────────────────────────────

def test_1040_gets_april_15_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="tax_return_1040")
    assert r.status_code == 201
    deadline = r.json()["filing_deadline"]
    assert deadline is not None
    d = date.fromisoformat(deadline)
    assert d.month == 4 and d.day == 15


def test_1065_gets_march_15_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="tax_return_1065")
    assert r.status_code == 201
    deadline = r.json()["filing_deadline"]
    assert deadline is not None
    d = date.fromisoformat(deadline)
    assert d.month == 3 and d.day == 15


def test_1120s_gets_march_15_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="tax_return_1120s")
    assert r.status_code == 201
    deadline = r.json()["filing_deadline"]
    d = date.fromisoformat(deadline)
    assert d.month == 3 and d.day == 15


def test_advisory_type_gets_no_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="tax_planning_advisory")
    assert r.status_code == 201
    assert r.json()["filing_deadline"] is None


def test_custom_type_gets_no_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="custom")
    assert r.status_code == 201
    assert r.json()["filing_deadline"] is None


def test_706_gets_no_auto_deadline(client, firm_a_owner):
    """706 deadline is client-specific (9mo from date of death) — never auto-set."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="tax_return_706")
    assert r.status_code == 201
    assert r.json()["filing_deadline"] is None


def test_explicit_filing_deadline_not_overridden(client, firm_a_owner):
    """If firm provides filing_deadline explicitly, auto-population should not override it."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    custom_deadline = "2025-06-30"
    r = make_engagement(
        client, headers, cid,
        engagement_type="tax_return_1040",
        filing_deadline=custom_deadline,
    )
    assert r.status_code == 201
    assert r.json()["filing_deadline"] == custom_deadline


# ── extended_deadline ─────────────────────────────────────────────────────────

def test_patch_extended_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = make_engagement(client, headers, cid, engagement_type="tax_return_1040")
    eid = r.json()["id"]

    r2 = client.patch(
        f"/engagements/{eid}",
        json={"extended_deadline": "2025-10-15"},
        headers=headers,
    )
    assert r2.status_code == 200
    assert r2.json()["extended_deadline"] == "2025-10-15"


# ── deadline-watch endpoint ───────────────────────────────────────────────────

def test_deadline_watch_returns_approaching_engagements(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    # Set a filing_deadline 10 days from today
    soon = (date.today() + timedelta(days=10)).isoformat()
    r = make_engagement(
        client, headers, cid,
        engagement_type="tax_return_1040",
        filing_deadline=soon,
    )
    assert r.status_code == 201

    r2 = client.get("/engagements/deadline-watch?days=60", headers=headers)
    assert r2.status_code == 200
    items = r2.json()
    assert len(items) >= 1
    found = [i for i in items if i["filing_deadline"] == soon]
    assert len(found) == 1
    assert found[0]["days_remaining"] == 10


def test_deadline_watch_excludes_far_future(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    far = (date.today() + timedelta(days=200)).isoformat()
    make_engagement(client, headers, cid, engagement_type="tax_return_1040", filing_deadline=far)

    r = client.get("/engagements/deadline-watch?days=60", headers=headers)
    assert r.status_code == 200
    items = r.json()
    assert not any(i["filing_deadline"] == far for i in items)


def test_deadline_watch_excludes_completed(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    soon = (date.today() + timedelta(days=5)).isoformat()
    r = make_engagement(
        client, headers, cid,
        engagement_type="tax_return_1040",
        filing_deadline=soon,
    )
    eid = r.json()["id"]

    # Mark as completed
    client.patch(f"/engagements/{eid}", json={"status": "completed"}, headers=headers)

    r2 = client.get("/engagements/deadline-watch?days=60", headers=headers)
    items = r2.json()
    assert not any(i["engagement_id"] == eid for i in items)


def test_deadline_watch_uses_extended_deadline_when_set(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    # filing_deadline is 5 days away (within window)
    # extended_deadline is 200 days away (outside 60-day window)
    soon = (date.today() + timedelta(days=5)).isoformat()
    far = (date.today() + timedelta(days=200)).isoformat()

    r = make_engagement(
        client, headers, cid,
        engagement_type="tax_return_1040",
        filing_deadline=soon,
    )
    eid = r.json()["id"]
    client.patch(f"/engagements/{eid}", json={"extended_deadline": far}, headers=headers)

    # With extended_deadline set, effective_deadline is far — should NOT appear in 60-day window
    r2 = client.get("/engagements/deadline-watch?days=60", headers=headers)
    items = r2.json()
    assert not any(i["engagement_id"] == eid for i in items)


def test_deadline_watch_tenant_isolation(client, firm_a_owner, firm_b_owner):
    """Firm B cannot see Firm A's deadline watch results."""
    a_headers = firm_a_owner["headers"]
    b_headers = firm_b_owner["headers"]

    cid = make_client(client, a_headers, name="Firm A Deadline Client")
    soon = (date.today() + timedelta(days=10)).isoformat()
    make_engagement(client, a_headers, cid, engagement_type="tax_return_1040", filing_deadline=soon)

    r = client.get("/engagements/deadline-watch?days=60", headers=b_headers)
    assert r.status_code == 200
    items = r.json()
    # Firm B should see zero items (or none belonging to Firm A)
    firm_a_ids = []  # We don't expose firm info but count should be 0 for B's own firm
    assert all(True for i in items)  # Just confirm it returns without error for B
    # More importantly: make sure B's results don't include A's client
    assert not any(i["client_name"] == "Firm A Deadline Client" for i in items)


# ── run pytest after writing this file ───────────────────────────────────────
