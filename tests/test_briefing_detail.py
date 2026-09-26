# tests/test_briefing_detail.py
"""
Guard tests for build_tier1_summary and GET /api/v1/surface-items/{id}/detail.

Tests:
  a. build_tier1_summary produces the exact expected sentence for known payload values.
  b. Detail endpoint returns "Not recorded" for deadline_with_blockers ISSUED DATE
     and INVOICE/BALANCE.
  c. last_client_communication resolves to the more recent of two competing
     BehavioralEvent rows.
  d. Tenant isolation on the detail endpoint (watched-fail-then-pass).
  e. Staff role gets 403 on the detail endpoint.
"""
import uuid
from datetime import datetime, timezone

import pytest

from app.core.enums import SurfaceKind
from app.models.behavioral_event import BehavioralEvent
from app.models.client import Client
from app.models.firm import Firm
from app.models.surface_item import SurfaceItem
from app.models.user import User
from app.core.enums import UserRole
from app.core.security import get_password_hash
from app.services.surface_item_service import build_tier1_facts, build_tier1_summary
from tests.conftest import TestingSessionLocal


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm(slug: str) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
        db.add(firm)
        db.commit()
        db.refresh(firm)
        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)
        return firm.id
    finally:
        db.close()


def _make_user(firm_id: uuid.UUID, role: UserRole) -> tuple[str, str]:
    db = TestingSessionLocal()
    try:
        email = f"{role.value}-{uuid.uuid4().hex[:6]}@test.com"
        user = User(
            firm_id=firm_id,
            email=email,
            hashed_password=get_password_hash("pass"),
            full_name=f"{role.value} user",
            role=role,
        )
        db.add(user)
        db.commit()
        return email, "pass"
    finally:
        db.close()


def _make_slotted_item(firm_id: uuid.UUID, item_type: str, payload: dict, headline: str) -> uuid.UUID:
    db = TestingSessionLocal()
    try:
        row = SurfaceItem(
            firm_id=firm_id,
            kind=SurfaceKind.briefing,
            item_type=item_type,
            dedup_key=f"test-{uuid.uuid4().hex[:8]}",
            headline=headline,
            payload=payload,
            rank=1,
            slotted_at=datetime.now(timezone.utc),
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return row.id
    finally:
        db.close()


def _login(client, email: str, password: str) -> dict:
    resp = client.post("/auth/token", json={"username": email, "password": password})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


# ---------------------------------------------------------------------------
# Test (a): build_tier1_summary produces exact expected sentence
# ---------------------------------------------------------------------------

class _FakeItem:
    def __init__(self, item_type: str, payload: dict):
        self.item_type = item_type
        self.payload = payload


def test_build_tier1_summary_exact_sentence():
    """build_tier1_summary produces the exact expected sentence for known payloads."""
    items = [
        _FakeItem("invoice_overdue", {"balance": 3000.0, "days_overdue": 5}),
        _FakeItem("invoice_overdue", {"balance": 2100.0, "days_overdue": 12}),
        _FakeItem("irs_auth_expiring", {"days_to_expiry": 30}),
        _FakeItem("deadline_with_blockers", {"open_blockers": 3, "days_remaining": 7}),
    ]
    result = build_tier1_summary(items)
    assert result == (
        "2 invoices overdue, balances totaling $5,100; "
        "1 IRS authorization expiring; "
        "1 deadline with 3 open items."
    ), f"Got: {result}"


def test_build_tier1_summary_empty_returns_caught_up():
    result = build_tier1_summary([])
    assert result == "You're all caught up."


def test_build_tier1_summary_single_invoice():
    items = [_FakeItem("invoice_overdue", {"balance": 500.0, "days_overdue": 3})]
    result = build_tier1_summary(items)
    assert "1 invoice overdue" in result
    assert "$500" in result


# ---------------------------------------------------------------------------
# Test (b): detail endpoint returns "Not recorded" for deadline_with_blockers
#           ISSUED DATE and INVOICE/BALANCE
# ---------------------------------------------------------------------------

def test_detail_not_recorded_for_deadline_fields(client):
    """deadline_with_blockers rows return 'Not recorded' for Issued Date and Invoice/Balance."""
    firm_id = _make_firm(f"ddnr-{uuid.uuid4().hex[:6]}")
    email, pw = _make_user(firm_id, UserRole.firm_owner)
    headers = _login(client, email, pw)

    item_id = _make_slotted_item(
        firm_id,
        "deadline_with_blockers",
        {
            "engagement_id": str(uuid.uuid4()),
            "client_id": str(uuid.uuid4()),
            "engagement_name": "2024 Tax Return",
            "deadline": "2026-10-15",
            "days_remaining": 20,
            "open_blockers": 2,
        },
        "2024 Tax Return is due in 20 days with 2 open items",
    )

    resp = client.get(f"/api/v1/surface-items/{item_id}/detail", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["issued_date"] == "Not recorded", f"issued_date was: {body['issued_date']}"
    assert body["invoice_balance"] == "Not recorded", f"invoice_balance was: {body['invoice_balance']}"


# ---------------------------------------------------------------------------
# Test (c): last_client_communication picks the more recent of two events
# ---------------------------------------------------------------------------

def test_last_client_communication_takes_more_recent(client):
    """
    Given two BehavioralEvent rows for the same client, one older and one newer,
    last_client_communication returns the newer date.
    """
    firm_id = _make_firm(f"lcc-{uuid.uuid4().hex[:6]}")
    email, pw = _make_user(firm_id, UserRole.firm_owner)
    headers = _login(client, email, pw)

    db = TestingSessionLocal()
    try:
        real_client = Client(
            firm_id=firm_id,
            name="LCC Test Client",
            email=f"lcc-{uuid.uuid4().hex[:6]}@example.com",
        )
        db.add(real_client)
        db.commit()
        db.refresh(real_client)
        client_id = real_client.id

        older_dt = datetime(2026, 9, 1, 12, 0, 0, tzinfo=timezone.utc)
        newer_dt = datetime(2026, 9, 20, 15, 30, 0, tzinfo=timezone.utc)

        for dt in (older_dt, newer_dt):
            evt = BehavioralEvent(
                firm_id=firm_id,
                event_type="email.reply_sent",
                entity_type="client",
                entity_id=client_id,
                actor_type="staff",
                occurred_at=dt,
            )
            db.add(evt)
        db.commit()
    finally:
        db.close()

    item_id = _make_slotted_item(
        firm_id,
        "invoice_overdue",
        {
            "invoice_id": str(uuid.uuid4()),
            "invoice_number": "INV-001",
            "client_id": str(client_id),
            "balance": 500.0,
            "days_overdue": 5,
        },
        "Invoice INV-001 is 5 days overdue",
    )

    resp = client.get(f"/api/v1/surface-items/{item_id}/detail", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["last_client_communication"] == "2026-09-20", (
        f"Expected 2026-09-20 (the newer event), got: {body['last_client_communication']}"
    )


# ---------------------------------------------------------------------------
# Test (d): tenant isolation on detail endpoint (watched-fail-then-pass)
# ---------------------------------------------------------------------------

def test_detail_endpoint_tenant_isolation(client):
    """
    GET /api/v1/surface-items/{id}/detail for Firm A's item must return 404
    when called by Firm B's owner, not Firm A's data.

    Watched-fail-then-pass: temporarily removing the firm_id filter from
    get_item_for_firm causes Firm B to receive a 200 instead of a 404.
    The test asserts 404.
    """
    firm_a_id = _make_firm(f"dtisoA-{uuid.uuid4().hex[:6]}")
    firm_b_id = _make_firm(f"dtisoB-{uuid.uuid4().hex[:6]}")

    email_b, pw_b = _make_user(firm_b_id, UserRole.firm_owner)
    headers_b = _login(client, email_b, pw_b)

    item_a_id = _make_slotted_item(
        firm_a_id,
        "invoice_overdue",
        {
            "invoice_id": str(uuid.uuid4()),
            "invoice_number": "INV-A-001",
            "client_id": str(uuid.uuid4()),
            "balance": 999.0,
            "days_overdue": 7,
        },
        "Invoice INV-A-001 is 7 days overdue",
    )

    resp = client.get(f"/api/v1/surface-items/{item_a_id}/detail", headers=headers_b)
    assert resp.status_code == 404, (
        f"Expected 404 (cross-firm probe must learn nothing), got {resp.status_code}: {resp.text}"
    )


# ---------------------------------------------------------------------------
# Test (e): staff role gets 403
# ---------------------------------------------------------------------------

def test_detail_endpoint_staff_gets_403(client):
    firm_id = _make_firm(f"dtstaff-{uuid.uuid4().hex[:6]}")
    email, pw = _make_user(firm_id, UserRole.staff)
    headers = _login(client, email, pw)

    item_id = _make_slotted_item(
        firm_id,
        "invoice_overdue",
        {"invoice_id": str(uuid.uuid4()), "client_id": str(uuid.uuid4()),
         "invoice_number": "INV-S", "balance": 100.0, "days_overdue": 1},
        "Invoice INV-S is 1 day overdue",
    )

    resp = client.get(f"/api/v1/surface-items/{item_id}/detail", headers=headers)
    assert resp.status_code == 403, f"Expected 403, got {resp.status_code}: {resp.text}"


# ---------------------------------------------------------------------------
# Tests (f-h): build_tier1_facts and shared-helper refactor
# ---------------------------------------------------------------------------

def test_build_tier1_facts_correct_list():
    """build_tier1_facts returns the correct list for the same known payloads as the summary test."""
    items = [
        _FakeItem("invoice_overdue", {"balance": 3000.0, "days_overdue": 5}),
        _FakeItem("invoice_overdue", {"balance": 2100.0, "days_overdue": 12}),
        _FakeItem("irs_auth_expiring", {"days_to_expiry": 30}),
        _FakeItem("deadline_with_blockers", {"open_blockers": 3, "days_remaining": 7}),
    ]
    facts = build_tier1_facts(items)
    assert len(facts) == 3, f"Expected 3 entries, got {len(facts)}: {facts}"

    overdue = next((f for f in facts if f["category"] == "overdue_invoices"), None)
    assert overdue is not None, "Missing overdue_invoices entry"
    assert overdue["count"] == 2
    assert overdue["amount"] == 5100.0, f"Expected 5100.0, got {overdue['amount']}"
    assert "5,100" in overdue["text"], f"Missing $5,100 in text: {overdue['text']}"

    irs = next((f for f in facts if f["category"] == "irs_authorizations"), None)
    assert irs is not None, "Missing irs_authorizations entry"
    assert irs["count"] == 1
    assert irs["amount"] is None

    deadline = next((f for f in facts if f["category"] == "deadlines"), None)
    assert deadline is not None, "Missing deadlines entry"
    assert deadline["count"] == 1
    assert deadline["amount"] == 3.0, f"Expected 3.0 (blockers), got {deadline['amount']}"


def test_build_tier1_facts_empty_returns_none_entry():
    """build_tier1_facts with no items returns a single 'none' caught-up entry."""
    facts = build_tier1_facts([])
    assert len(facts) == 1
    assert facts[0]["category"] == "none"
    assert facts[0]["text"] == "You're all caught up."
    assert facts[0]["count"] == 0
    assert facts[0]["amount"] is None


def test_build_tier1_summary_unchanged_after_refactor():
    """Confirm the shared-helper refactor did not change build_tier1_summary output."""
    items = [
        _FakeItem("invoice_overdue", {"balance": 3000.0, "days_overdue": 5}),
        _FakeItem("invoice_overdue", {"balance": 2100.0, "days_overdue": 12}),
        _FakeItem("irs_auth_expiring", {"days_to_expiry": 30}),
        _FakeItem("deadline_with_blockers", {"open_blockers": 3, "days_remaining": 7}),
    ]
    result = build_tier1_summary(items)
    assert result == (
        "2 invoices overdue, balances totaling $5,100; "
        "1 IRS authorization expiring; "
        "1 deadline with 3 open items."
    ), f"Got: {result}"
