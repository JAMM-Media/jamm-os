# tests/test_phase13c_extensions.py
"""
Phase 13C — Extension tracking tests.

Tests cover:
- Filing an extension creates Extension record
- extended_deadline auto-set from form_type (4868→Oct 15, 7004→Sep 15)
- Explicit extended_deadline is not overridden
- Filing extension updates Engagement.extended_deadline
- Deadline watch uses extended_deadline (not filing_deadline) after extension
- List/get endpoints work and are firm-scoped
- RBAC: staff can list/get but cannot file
- Tenant isolation: Firm B cannot see Firm A's extensions
- client_id mismatch with engagement returns 400
- Invalid form_type returns 422
- Status update via PATCH
"""

from datetime import date, timedelta
from uuid import uuid4

from sqlalchemy import select

from tests.conftest import TestingSessionLocal
from app.models.behavioral_event import BehavioralEvent


# ── helpers ───────────────────────────────────────────────────────────────────

def make_client(client, headers, name="Extension Client"):
    r = client.post("/clients/", json={"name": name}, headers=headers)
    assert r.status_code == 201
    return r.json()["id"]


def make_engagement(client, headers, client_id, engagement_type="tax_return_1040"):
    r = client.post("/engagements/", json={
        "client_id": client_id,
        "name": "Test Engagement",
        "engagement_type": engagement_type,
    }, headers=headers)
    assert r.status_code == 201
    return r.json()


def file_extension(client, headers, engagement_id, client_id, form_type="4868", **kwargs):
    payload = {
        "engagement_id": engagement_id,
        "client_id": client_id,
        "form_type": form_type,
        **kwargs,
    }
    return client.post("/extensions/file", json=payload, headers=headers)


# ── basic filing ──────────────────────────────────────────────────────────────

def test_file_extension_creates_record(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)

    r = file_extension(client, headers, eng["id"], cid, form_type="4868")
    assert r.status_code == 201
    data = r.json()
    assert data["form_type"] == "4868"
    assert data["status"] == "filed"
    assert data["engagement_id"] == eng["id"]


def test_4868_gets_october_15_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)

    r = file_extension(client, headers, eng["id"], cid, form_type="4868")
    assert r.status_code == 201
    deadline = date.fromisoformat(r.json()["extended_deadline"])
    assert deadline.month == 10 and deadline.day == 15


def test_7004_gets_september_15_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid, engagement_type="tax_return_1120s")

    r = file_extension(client, headers, eng["id"], cid, form_type="7004")
    assert r.status_code == 201
    deadline = date.fromisoformat(r.json()["extended_deadline"])
    assert deadline.month == 9 and deadline.day == 15


def test_8868_gets_november_15_deadline(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)

    r = file_extension(client, headers, eng["id"], cid, form_type="8868")
    assert r.status_code == 201
    deadline = date.fromisoformat(r.json()["extended_deadline"])
    assert deadline.month == 11 and deadline.day == 15


def test_explicit_extended_deadline_respected(client, firm_a_owner):
    """If the firm provides extended_deadline explicitly, use it — don't override."""
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)
    custom = "2025-10-01"

    r = file_extension(client, headers, eng["id"], cid,
                       form_type="4868", extended_deadline=custom)
    assert r.status_code == 201
    assert r.json()["extended_deadline"] == custom


# ── engagement.extended_deadline sync ────────────────────────────────────────

def test_filing_extension_updates_engagement_deadline(client, firm_a_owner):
    """
    The most important test: after filing an extension, the engagement's
    extended_deadline field is updated. This is what the deadline scheduler uses.
    """
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)
    assert eng["extended_deadline"] is None  # starts empty

    r = file_extension(client, headers, eng["id"], cid, form_type="4868")
    assert r.status_code == 201
    extended = r.json()["extended_deadline"]

    # Fetch the engagement and confirm extended_deadline is now set
    r2 = client.get(f"/engagements/{eng['id']}", headers=headers)
    assert r2.status_code == 200
    assert r2.json()["extended_deadline"] == extended


# Offsets from today for the deadline-watch test below, and the two windows
# queried against them. They are offsets rather than calendar dates on
# purpose: see the docstring on the test, and instance fifteen in
# How_We_Work_Process_Rules.md.
NEAR_FILING_OFFSET_DAYS = 5
FAR_EXTENDED_OFFSET_DAYS = 120
NARROW_WINDOW_DAYS = 60
WIDE_WINDOW_DAYS = 200


def test_deadline_watch_uses_extended_deadline_after_filing(client, firm_a_owner):
    """
    After filing an extension, deadline-watch uses extended_deadline rather
    than filing_deadline.

    EVERY DATE HERE IS COMPUTED FROM date.today(), the same clock
    app/api/engagements.py deadline_watch reads, and the extended deadline is
    passed EXPLICITLY instead of being left to default from the form type.
    That is instance fifteen. This test used to query a hardcoded 60-day window
    against the defaulted Oct 15 deadline, which sits outside that window for
    most of the year and inside it from Aug 16 onward; it went red on
    Aug 16, 2026 with no code change and would have gone silently green again
    on Oct 15. Expectations computed as offsets from today hold on every
    calendar day instead.

    Leaving the deadline to default would not be enough to fix it. The default
    is date(date.today().year, month, day) in app/crud/extension.py, so from
    Oct 16 to Dec 31 it lands in the PAST, and a past deadline is excluded by
    the today <= effective bound rather than by the window. The test would pass
    for a reason that has nothing to do with the rule it names.
    """
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)

    today = date.today()
    filing = today + timedelta(days=NEAR_FILING_OFFSET_DAYS)
    extended = today + timedelta(days=FAR_EXTENDED_OFFSET_DAYS)

    eng = make_engagement(client, headers, cid)
    client.patch(f"/engagements/{eng['id']}",
                 json={"filing_deadline": filing.isoformat()}, headers=headers)

    r = file_extension(client, headers, eng["id"], cid, form_type="4868",
                       extended_deadline=extended.isoformat())
    assert r.status_code == 201
    assert r.json()["extended_deadline"] == extended.isoformat()

    # The narrow window contains the filing deadline and excludes the extended
    # one BY CONSTRUCTION, so this engagement can only appear if deadline-watch
    # is reading filing_deadline.
    assert NEAR_FILING_OFFSET_DAYS < NARROW_WINDOW_DAYS < FAR_EXTENDED_OFFSET_DAYS
    r = client.get(f"/engagements/deadline-watch?days={NARROW_WINDOW_DAYS}",
                   headers=headers)
    assert r.status_code == 200
    assert not any(i["engagement_id"] == eng["id"] for i in r.json())

    # Positive control. Without it the assertion above passes just as happily
    # against a deadline-watch that returns nothing at all, or that dropped
    # this engagement for some reason unrelated to the window.
    assert WIDE_WINDOW_DAYS > FAR_EXTENDED_OFFSET_DAYS
    r = client.get(f"/engagements/deadline-watch?days={WIDE_WINDOW_DAYS}",
                   headers=headers)
    assert r.status_code == 200
    watched = [i for i in r.json() if i["engagement_id"] == eng["id"]]
    assert len(watched) == 1
    # effective_deadline is the extended one, not the filing one, which is the
    # precedence rule this test is named for, asserted directly.
    assert watched[0]["effective_deadline"] == extended.isoformat()
    assert watched[0]["filing_deadline"] == filing.isoformat()


# ── engagement.extension_filed event ─────────────────────────────────────────

def test_filing_extension_fires_extension_filed_event(client, firm_a_owner):
    """
    Filing an extension fires engagement.extension_filed with metadata:
    extension_id, form_type, original_deadline, new_extended_deadline,
    days_before_original_deadline.
    """
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)

    soon = (date.today() + timedelta(days=20)).isoformat()
    client.patch(f"/engagements/{eng['id']}", json={"filing_deadline": soon}, headers=headers)

    r = file_extension(client, headers, eng["id"], cid, form_type="4868")
    assert r.status_code == 201
    ext = r.json()

    db = TestingSessionLocal()
    try:
        row = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == eng["id"],
                BehavioralEvent.event_type == "engagement.extension_filed",
            )
        ).scalar_one_or_none()
        assert row is not None
        meta = row.extra_metadata
        assert meta["extension_id"] == ext["id"]
        assert meta["form_type"] == "4868"
        assert meta["original_deadline"] == soon
        assert meta["new_extended_deadline"] == ext["extended_deadline"]
        assert meta["days_before_original_deadline"] is not None
    finally:
        db.close()


def test_filing_extension_does_not_double_fire_via_update_engagement(client, firm_a_owner):
    """
    Filing an extension must fire engagement.extension_filed exactly once —
    it must not also trigger update_engagement's own (payload-driven)
    engagement.extension_filed branch, since the two paths are independent.
    """
    headers = firm_a_owner["headers"]
    firm_id = firm_a_owner["firm_id"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)

    file_extension(client, headers, eng["id"], cid, form_type="4868")

    db = TestingSessionLocal()
    try:
        rows = db.execute(
            select(BehavioralEvent).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == eng["id"],
                BehavioralEvent.event_type == "engagement.extension_filed",
            )
        ).scalars().all()
        assert len(rows) == 1
    finally:
        db.close()


# ── list and get ──────────────────────────────────────────────────────────────

def test_list_extensions(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)
    file_extension(client, headers, eng["id"], cid, form_type="4868")

    r = client.get("/extensions/", headers=headers)
    assert r.status_code == 200
    assert len(r.json()) >= 1


def test_list_filter_by_engagement(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng_a = make_engagement(client, headers, cid)
    eng_b = make_engagement(client, headers, cid)
    file_extension(client, headers, eng_a["id"], cid)
    file_extension(client, headers, eng_b["id"], cid)

    r = client.get(f"/extensions/?engagement_id={eng_a['id']}", headers=headers)
    assert r.status_code == 200
    assert all(i["engagement_id"] == eng_a["id"] for i in r.json())


def test_get_single_extension(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)
    ext_id = file_extension(client, headers, eng["id"], cid).json()["id"]

    r = client.get(f"/extensions/{ext_id}", headers=headers)
    assert r.status_code == 200
    assert r.json()["id"] == ext_id


def test_get_nonexistent_returns_404(client, firm_a_owner):
    r = client.get(f"/extensions/{uuid4()}", headers=firm_a_owner["headers"])
    assert r.status_code == 404


# ── validation ────────────────────────────────────────────────────────────────

def test_invalid_form_type_rejected(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)
    r = file_extension(client, headers, eng["id"], cid, form_type="9999")
    assert r.status_code == 422


def test_client_mismatch_returns_400(client, firm_a_owner):
    """client_id that doesn't match the engagement's client returns 400."""
    headers = firm_a_owner["headers"]
    cid_a = make_client(client, headers, name="Client A")
    cid_b = make_client(client, headers, name="Client B")
    eng = make_engagement(client, headers, cid_a)  # engagement belongs to cid_a

    r = file_extension(client, headers, eng["id"], cid_b)  # wrong client
    assert r.status_code == 400


def test_nonexistent_engagement_returns_404(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    r = file_extension(client, headers, str(uuid4()), cid)
    assert r.status_code == 404


# ── RBAC ──────────────────────────────────────────────────────────────────────

def test_staff_can_list_extensions(client, firm_a_staff):
    """Staff can view extensions — read-only access."""
    r = client.get("/extensions/", headers=firm_a_staff["headers"])
    assert r.status_code == 200


def test_staff_cannot_file_extension(client, firm_a_staff, firm_a_owner):
    """Staff cannot file extensions — manager and firm_owner only."""
    cid = make_client(client, firm_a_owner["headers"])
    eng = make_engagement(client, firm_a_owner["headers"], cid)
    r = file_extension(client, firm_a_staff["headers"], eng["id"], cid)
    assert r.status_code == 403


# ── status update ─────────────────────────────────────────────────────────────

def test_patch_status_to_confirmed(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)
    ext_id = file_extension(client, headers, eng["id"], cid).json()["id"]

    r = client.patch(f"/extensions/{ext_id}", json={"status": "confirmed"}, headers=headers)
    assert r.status_code == 200
    assert r.json()["status"] == "confirmed"


def test_patch_invalid_status_rejected(client, firm_a_owner):
    headers = firm_a_owner["headers"]
    cid = make_client(client, headers)
    eng = make_engagement(client, headers, cid)
    ext_id = file_extension(client, headers, eng["id"], cid).json()["id"]

    r = client.patch(f"/extensions/{ext_id}", json={"status": "banana"}, headers=headers)
    assert r.status_code == 422


# ── tenant isolation ──────────────────────────────────────────────────────────

def test_tenant_isolation_list(client, firm_a_owner, firm_b_owner):
    a_headers = firm_a_owner["headers"]
    cid = make_client(client, a_headers, name="Firm A Ext Client")
    eng = make_engagement(client, a_headers, cid)
    file_extension(client, a_headers, eng["id"], cid)

    r = client.get("/extensions/", headers=firm_b_owner["headers"])
    assert r.status_code == 200
    assert not any(i["client_id"] == cid for i in r.json())


def test_tenant_isolation_get(client, firm_a_owner, firm_b_owner):
    a_headers = firm_a_owner["headers"]
    cid = make_client(client, a_headers)
    eng = make_engagement(client, a_headers, cid)
    ext_id = file_extension(client, a_headers, eng["id"], cid).json()["id"]

    r = client.get(f"/extensions/{ext_id}", headers=firm_b_owner["headers"])
    assert r.status_code == 404
