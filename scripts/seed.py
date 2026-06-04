"""
scripts/seed.py — Demo seed data for JAMM OS.
Run from inside the container:
    python scripts/seed.py
"""

import sys
from datetime import date

import app.models  # noqa: F401 — registers all ORM models with SQLAlchemy metadata

from app.db.session import SessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.invoice import Invoice
from app.core.enums import UserRole, InvoiceStatus, InvoiceDeliveryMethod
from app.core.security import get_password_hash

db = SessionLocal()

try:
    # ── Guard: skip if already seeded ─────────────────────────────────────────
    existing = db.query(Firm).filter(Firm.name == "Demo Firm").first()
    if existing:
        print("Already seeded, skipping.")
        db.close()
        sys.exit(0)

    # ── FIRM ──────────────────────────────────────────────────────────────────
    firm = Firm(
        name="Demo Firm",
        slug="demo-firm",
    )
    db.add(firm)
    db.flush()  # assigns firm.id

    # ── FIRM OWNER USER ───────────────────────────────────────────────────────
    owner = User(
        firm_id=firm.id,
        email="admin@demofirm.com",
        full_name="Andrew Demo",
        hashed_password=get_password_hash("password123"),
        role=UserRole.firm_owner,
        is_active=True,
    )
    db.add(owner)
    db.flush()  # assigns owner.id

    # ── 5 CLIENTS ─────────────────────────────────────────────────────────────
    clients_data = [
        dict(name="Acme Corp",           entity_type="corporation", is_active=True),
        dict(name="Bright Future LLC",   entity_type=None,          is_active=True),
        dict(name="Goldstein & Partners", entity_type=None,         is_active=True),
        dict(name="Harvest Moon Farms",  entity_type=None,          is_active=False),
        dict(name="Ironclad Logistics",  entity_type=None,          is_active=True),
    ]

    client_objects = []
    for cd in clients_data:
        c = Client(
            firm_id=firm.id,
            name=cd["name"],
            entity_type=cd["entity_type"],
            is_active=cd["is_active"],
        )
        db.add(c)
        client_objects.append(c)
    db.flush()  # assigns all client ids

    acme = client_objects[0]

    # ── 3 ENGAGEMENTS (Acme Corp) ─────────────────────────────────────────────
    engagements_data = [
        dict(
            name="2024 Tax Return — Corporate",
            status="in_progress",
            engagement_type="tax_return",
            end_date=date(2025, 9, 15),
        ),
        dict(
            name="Q2 2024 Bookkeeping",
            status="awaiting_docs",
            engagement_type="bookkeeping",
            end_date=date(2025, 7, 31),
        ),
        dict(
            name="2023 Tax Return — Corporate",
            status="complete",
            engagement_type="tax_return",
            end_date=date(2024, 9, 15),
        ),
    ]

    engagement_objects = []
    for ed in engagements_data:
        e = Engagement(
            firm_id=firm.id,
            client_id=acme.id,
            name=ed["name"],
            status=ed["status"],
            engagement_type=ed["engagement_type"],
            end_date=ed["end_date"],
        )
        db.add(e)
        engagement_objects.append(e)
    db.flush()

    first_engagement = engagement_objects[0]

    # ── 3 TASKS (first engagement) ────────────────────────────────────────────
    tasks_data = [
        dict(title="Prepare depreciation schedule",          status="in_progress", due_date=date(2025, 8, 1)),
        dict(title="Request prior year returns from client", status="overdue",     due_date=date(2025, 7, 15)),
        dict(title="Review corporate structure",             status="not_started", due_date=date(2025, 8, 15)),
    ]

    for td in tasks_data:
        t = Task(
            firm_id=firm.id,
            client_id=acme.id,
            engagement_id=first_engagement.id,
            title=td["title"],
            status=td["status"],
            due_date=td["due_date"],
            assigned_to=owner.id,
        )
        db.add(t)
    db.flush()

    # ── 1 INVOICE (Acme Corp, first engagement) ───────────────────────────────
    invoice = Invoice(
        firm_id=firm.id,
        client_id=acme.id,
        engagement_id=first_engagement.id,
        invoice_number="INV-2024-001",
        subtotal=3500.00,
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=3500.00,
        status=InvoiceStatus.sent,
        due_date=date(2025, 7, 31),
        delivery_method=InvoiceDeliveryMethod.portal,
    )
    db.add(invoice)

    db.commit()

    print("Seed complete.")
    print("Login: admin@demofirm.com / password123")
    print("Firm: Demo Firm")
    print("Clients: 5")
    print("Engagements: 3 (Acme Corp)")
    print("Tasks: 3")
    print("Invoice: 1")

except Exception as exc:
    db.rollback()
    print(f"ERROR — seed failed: {exc}")
    sys.exit(1)
finally:
    db.close()
