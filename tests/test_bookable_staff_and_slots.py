# tests/test_bookable_staff_and_slots.py
"""
Tests for the three new endpoints:
  GET /users/bookable-staff
  GET /api/v1/bookings/slots
  GET /api/v1/bookings/ (lead_id filter)
"""

import uuid
from datetime import date, datetime, time, timezone, timedelta

from starlette.testclient import TestClient

from tests.conftest import TestingSessionLocal
from app.models.availability_window import AvailabilityWindow
from app.models.booking import Booking
from app.models.firm import Firm
from app.models.lead import Lead
from app.models.user import User
from app.core.enums import BookingStatus, LeadProvenance, LeadStage, UserRole
from app.core.security import get_password_hash


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_firm_and_owner(slug: str, client: TestClient) -> dict:
    db = TestingSessionLocal()
    try:
        firm = Firm(name=f"Firm {slug}", slug=slug, timezone="UTC")
        db.add(firm)
        db.commit()
        db.refresh(firm)

        from app.services.tax_organizer_service import seed_firm_organizer_templates
        seed_firm_organizer_templates(firm_id=firm.id, db=db)

        email = f"owner-{uuid.uuid4().hex[:6]}@{slug}.com"
        owner = User(
            firm_id=firm.id,
            email=email,
            hashed_password=get_password_hash("password123"),
            full_name="Owner",
            role=UserRole.firm_owner,
        )
        db.add(owner)
        db.commit()
        firm_id = str(firm.id)
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": "password123"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "firm_id": firm_id}


def _make_staff_user(firm_id: str, client: TestClient) -> dict:
    """Create staff user, return headers + user_id."""
    db = TestingSessionLocal()
    try:
        email = f"staff-{uuid.uuid4().hex[:8]}@testfirm.com"
        user = User(
            firm_id=uuid.UUID(firm_id),
            email=email,
            hashed_password=get_password_hash("staffpass"),
            full_name="Staff Member",
            role=UserRole.staff,
        )
        db.add(user)
        db.commit()
        user_id = str(user.id)
    finally:
        db.close()

    login = client.post("/auth/token", json={"username": email, "password": "staffpass"})
    token = login.json()["access_token"]
    return {"headers": {"Authorization": f"Bearer {token}"}, "user_id": user_id, "firm_id": firm_id}


def _add_availability_window(user_id: str, firm_id: str) -> None:
    db = TestingSessionLocal()
    try:
        win = AvailabilityWindow(
            firm_id=uuid.UUID(firm_id),
            user_id=uuid.UUID(user_id),
            day_of_week=0,
            start_time=time(9, 0),
            end_time=time(17, 0),
            meeting_duration_minutes=30,
        )
        db.add(win)
        db.commit()
    finally:
        db.close()


def _make_lead(firm_id: str, name: str = "Test Lead") -> str:
    db = TestingSessionLocal()
    try:
        lead = Lead(
            firm_id=uuid.UUID(firm_id),
            name=name,
            stage=LeadStage.contacted,
            provenance=LeadProvenance.firm_entered,
        )
        db.add(lead)
        db.commit()
        lead_id = str(lead.id)
    finally:
        db.close()
    return lead_id


def _make_booking(firm_id: str, lead_id: str = None, staff_user_id: str = None) -> str:
    db = TestingSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        b = Booking(
            firm_id=uuid.UUID(firm_id),
            lead_id=uuid.UUID(lead_id) if lead_id else None,
            staff_user_id=uuid.UUID(staff_user_id) if staff_user_id else None,
            start_time=now + timedelta(days=1),
            end_time=now + timedelta(days=1, minutes=30),
            status=BookingStatus.scheduled,
        )
        db.add(b)
        db.commit()
        booking_id = str(b.id)
    finally:
        db.close()
    return booking_id


# ===========================================================================
# 1. GET /users/bookable-staff
# ===========================================================================

def test_bookable_staff_returns_only_users_with_windows(client, firm_a_owner):
    """Users with an AvailabilityWindow appear; users without do not."""
    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client)

    # Before adding window -- must not appear
    r = client.get("/users/bookable-staff", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    ids_before = [item["id"] for item in r.json()]
    assert staff["user_id"] not in ids_before

    # Add window -- must now appear
    _add_availability_window(staff["user_id"], firm_id)
    r = client.get("/users/bookable-staff", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    ids_after = [item["id"] for item in r.json()]
    assert staff["user_id"] in ids_after


def test_bookable_staff_accessible_by_staff_role(client, firm_a_owner):
    """A staff-role user (not firm_owner) can call GET /users/bookable-staff -- must get 200, not 403."""
    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client)
    r = client.get("/users/bookable-staff", headers=staff["headers"])
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


def test_bookable_staff_response_has_no_email_or_role(client, firm_a_owner):
    """Response must contain id and full_name only -- no email, role, or cost_rate."""
    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client)
    _add_availability_window(staff["user_id"], firm_id)

    r = client.get("/users/bookable-staff", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    items = r.json()
    assert any(item["id"] == staff["user_id"] for item in items), "staff not in results"
    for item in items:
        assert "email" not in item
        assert "role" not in item
        assert "cost_rate" not in item
        assert "id" in item
        assert "full_name" in item


def test_bookable_staff_tenant_isolation(client, firm_a_owner):
    """Firm B's availability window must not appear in Firm A's results."""
    firm_b = _make_firm_and_owner("bookable-iso-b", client)
    firm_b_staff = _make_staff_user(firm_b["firm_id"], client)
    _add_availability_window(firm_b_staff["user_id"], firm_b["firm_id"])

    r = client.get("/users/bookable-staff", headers=firm_a_owner["headers"])
    assert r.status_code == 200
    ids = [item["id"] for item in r.json()]
    assert firm_b_staff["user_id"] not in ids


# ===========================================================================
# 2. GET /api/v1/bookings/slots
# ===========================================================================

def test_slots_matches_compute_available_slots_directly(client, firm_a_owner):
    """HTTP endpoint returns same count as service function called directly."""
    from app.services.slot_computation_service import compute_available_slots

    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client)
    _add_availability_window(staff["user_id"], firm_id)

    start = date.today()
    end = start + timedelta(days=13)

    r = client.get(
        "/api/v1/bookings/slots",
        params={"staff_user_id": staff["user_id"], "start_date": str(start), "end_date": str(end)},
        headers=firm_a_owner["headers"],
    )
    assert r.status_code == 200
    http_slots = r.json()

    db = TestingSessionLocal()
    try:
        direct_slots = compute_available_slots(
            db=db,
            staff_user_id=uuid.UUID(staff["user_id"]),
            firm_id=uuid.UUID(firm_id),
            start_date=start,
            end_date=end,
        )
    finally:
        db.close()

    assert len(http_slots) == len(direct_slots)


def test_slots_accessible_by_staff_role(client, firm_a_owner):
    """A staff-role user can call GET /api/v1/bookings/slots -- must get 200, not 403."""
    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client)
    _add_availability_window(staff["user_id"], firm_id)

    r = client.get(
        "/api/v1/bookings/slots",
        params={"staff_user_id": staff["user_id"]},
        headers=staff["headers"],
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"


def test_slots_tenant_isolation(client, firm_a_owner):
    """Requesting slots for a staff_user_id belonging to Firm B returns 404, not real slots."""
    firm_b = _make_firm_and_owner("slots-iso-b", client)
    firm_b_staff = _make_staff_user(firm_b["firm_id"], client)
    _add_availability_window(firm_b_staff["user_id"], firm_b["firm_id"])

    r = client.get(
        "/api/v1/bookings/slots",
        params={"staff_user_id": firm_b_staff["user_id"]},
        headers=firm_a_owner["headers"],
    )
    assert r.status_code == 404, f"Expected 404, got {r.status_code}: {r.text}"


# ===========================================================================
# 3. GET /api/v1/bookings/ with lead_id filter
# ===========================================================================

def test_list_bookings_by_lead(client, firm_a_owner):
    """GET /api/v1/bookings/?lead_id=X returns only bookings for that lead."""
    firm_id = firm_a_owner["firm_id"]
    lead_a = _make_lead(firm_id, "Lead A")
    lead_b = _make_lead(firm_id, "Lead B")

    booking_a = _make_booking(firm_id, lead_id=lead_a)
    _make_booking(firm_id, lead_id=lead_b)

    r = client.get("/api/v1/bookings/", params={"lead_id": lead_a}, headers=firm_a_owner["headers"])
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["id"] == booking_a


def test_list_bookings_tenant_isolation(client, firm_a_owner):
    """A booking from Firm B does not appear in Firm A's filtered list."""
    firm_b = _make_firm_and_owner("list-iso-b", client)
    shared_lead_id_str = str(uuid.uuid4())

    # Create a real lead in Firm B with a known UUID
    db = TestingSessionLocal()
    try:
        lead_b = Lead(
            id=uuid.UUID(shared_lead_id_str),
            firm_id=uuid.UUID(firm_b["firm_id"]),
            name="Lead B",
            stage=LeadStage.contacted,
            provenance=LeadProvenance.firm_entered,
        )
        db.add(lead_b)
        db.commit()
    finally:
        db.close()

    _make_booking(firm_b["firm_id"], lead_id=shared_lead_id_str)

    r = client.get("/api/v1/bookings/", params={"lead_id": shared_lead_id_str}, headers=firm_a_owner["headers"])
    assert r.status_code == 200
    assert len(r.json()) == 0


def test_list_bookings_accessible_by_staff_role(client, firm_a_owner):
    """A staff-role user can call GET /api/v1/bookings/ -- must get 200, not 403."""
    firm_id = firm_a_owner["firm_id"]
    staff = _make_staff_user(firm_id, client)
    r = client.get("/api/v1/bookings/", headers=staff["headers"])
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
