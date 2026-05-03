# scripts/seed_demo_firm.py
"""
Demo firm seed script for JAMM PX.
Creates a realistic demo account for Riverside Tax & Advisory.

Usage:
    python scripts/seed_demo_firm.py           # Create if not exists
    python scripts/seed_demo_firm.py --reset   # Delete and recreate
"""

import sys
import argparse
from datetime import datetime, timezone, date

from app.db.session import SessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.invoice import Invoice
from app.core.enums import (
    UserRole,
    EngagementType,
    EngagementStatus,
    TaskStatus,
    InvoiceStatus,
)
from app.core.security import get_password_hash


DEMO_SLUG = "riverside-demo"
DEMO_PASSWORD = "Demo2026!"


def current_year_date(month: int, day: int) -> date:
    return date(datetime.now(timezone.utc).year, month, day)


def next_year_date(month: int, day: int) -> date:
    return date(datetime.now(timezone.utc).year + 1, month, day)


def now() -> datetime:
    return datetime.now(timezone.utc)


def delete_demo_firm(db):
    firm = db.query(Firm).filter_by(slug=DEMO_SLUG).first()
    if not firm:
        return
    firm_id = firm.id

    db.query(Task).filter_by(firm_id=firm_id).delete(synchronize_session=False)
    db.query(Invoice).filter_by(firm_id=firm_id).delete(synchronize_session=False)
    db.query(Engagement).filter_by(firm_id=firm_id).delete(synchronize_session=False)
    db.query(Client).filter_by(firm_id=firm_id).delete(synchronize_session=False)
    db.query(User).filter_by(firm_id=firm_id).delete(synchronize_session=False)
    db.query(Firm).filter_by(id=firm_id).delete(synchronize_session=False)
    db.commit()
    print("Deleted existing demo firm.")


def create_demo_firm(db):
    firm = Firm(
        name="Riverside Tax & Advisory",
        slug=DEMO_SLUG,
        subscription_tier="professional",
        plan_override=True,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(firm)
    db.flush()

    # --- Users ---
    owner = User(
        firm_id=firm.id,
        email="owner@riverside-demo.com",
        full_name="Sarah Chen",
        role=UserRole.firm_owner,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        totp_enabled=False,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    james = User(
        firm_id=firm.id,
        email="james@riverside-demo.com",
        full_name="James Okafor",
        role=UserRole.manager,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        totp_enabled=False,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    priya = User(
        firm_id=firm.id,
        email="priya@riverside-demo.com",
        full_name="Priya Mehta",
        role=UserRole.staff,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        totp_enabled=False,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    tom = User(
        firm_id=firm.id,
        email="tom@riverside-demo.com",
        full_name="Tom Reyes",
        role=UserRole.staff,
        hashed_password=get_password_hash(DEMO_PASSWORD),
        totp_enabled=False,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add_all([owner, james, priya, tom])
    db.flush()

    # --- Clients, Engagements, Tasks, Invoices ---
    task_count = 0
    invoice_count = 0

    # 1. Marcus & Diana Webb
    webb = Client(
        firm_id=firm.id,
        name="Marcus & Diana Webb",
        email="webb@example.com",
        entity_type="individual",
        portal_access_enabled=True,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(webb)
    db.flush()

    webb_eng = Engagement(
        firm_id=firm.id,
        client_id=webb.id,
        name="2025 Individual Tax Return",
        engagement_type=EngagementType.tax_return_1040.value,
        status=EngagementStatus.active.value,
        filing_deadline=current_year_date(4, 15),
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(webb_eng)
    db.flush()

    for title, status_val, completed in [
        ("Collect W-2 from employer", TaskStatus.done.value, True),
        ("Review prior year return", TaskStatus.done.value, True),
        ("Prepare return", TaskStatus.in_progress.value, False),
    ]:
        db.add(Task(
            firm_id=firm.id,
            client_id=webb.id,
            engagement_id=webb_eng.id,
            title=title,
            status=status_val,
            is_completed=completed,
            assigned_to=priya.id,
            created_at=now(),
            updated_at=now(),
        ))
        task_count += 1

    db.add(Invoice(
        firm_id=firm.id,
        client_id=webb.id,
        engagement_id=webb_eng.id,
        invoice_number="INV-001",
        subtotal=850.00,
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=850.00,
        status=InvoiceStatus.sent,
        created_by=owner.id,
        created_at=now(),
        updated_at=now(),
    ))
    invoice_count += 1

    # 2. Acme Consulting LLC
    acme = Client(
        firm_id=firm.id,
        name="Acme Consulting LLC",
        email="finance@acme-example.com",
        entity_type="business",
        portal_access_enabled=False,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(acme)
    db.flush()

    acme_eng = Engagement(
        firm_id=firm.id,
        client_id=acme.id,
        name="2025 S-Corp Tax Return",
        engagement_type=EngagementType.tax_return_1120s.value,
        status=EngagementStatus.active.value,
        filing_deadline=current_year_date(3, 15),
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(acme_eng)
    db.flush()

    for title in ["Request prior year K-1s", "Confirm officer compensation"]:
        db.add(Task(
            firm_id=firm.id,
            client_id=acme.id,
            engagement_id=acme_eng.id,
            title=title,
            status=TaskStatus.todo.value,
            is_completed=False,
            assigned_to=james.id,
            created_at=now(),
            updated_at=now(),
        ))
        task_count += 1

    db.add(Invoice(
        firm_id=firm.id,
        client_id=acme.id,
        engagement_id=acme_eng.id,
        invoice_number="INV-002",
        subtotal=2400.00,
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=2400.00,
        status=InvoiceStatus.overdue,
        created_by=owner.id,
        created_at=now(),
        updated_at=now(),
    ))
    invoice_count += 1

    # 3. Patricia Nguyen
    patricia = Client(
        firm_id=firm.id,
        name="Patricia Nguyen",
        email="pnguyen@example.com",
        entity_type="individual",
        portal_access_enabled=True,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(patricia)
    db.flush()

    patricia_eng = Engagement(
        firm_id=firm.id,
        client_id=patricia.id,
        name="2025 Individual Tax Return",
        engagement_type=EngagementType.tax_return_1040.value,
        status=EngagementStatus.completed.value,
        filing_deadline=current_year_date(4, 15),
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(patricia_eng)
    db.flush()

    for title in ["Prepare return", "Client review", "File return"]:
        db.add(Task(
            firm_id=firm.id,
            client_id=patricia.id,
            engagement_id=patricia_eng.id,
            title=title,
            status=TaskStatus.done.value,
            is_completed=True,
            created_at=now(),
            updated_at=now(),
        ))
        task_count += 1

    db.add(Invoice(
        firm_id=firm.id,
        client_id=patricia.id,
        engagement_id=patricia_eng.id,
        invoice_number="INV-003",
        subtotal=750.00,
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=750.00,
        status=InvoiceStatus.paid,
        created_by=owner.id,
        created_at=now(),
        updated_at=now(),
    ))
    invoice_count += 1

    # 4. Brightline Properties LLC
    brightline = Client(
        firm_id=firm.id,
        name="Brightline Properties LLC",
        email="accounts@brightline-example.com",
        entity_type="business",
        portal_access_enabled=False,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(brightline)
    db.flush()

    brightline_eng = Engagement(
        firm_id=firm.id,
        client_id=brightline.id,
        name="Monthly Bookkeeping",
        engagement_type=EngagementType.bookkeeping_monthly.value,
        status=EngagementStatus.active.value,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(brightline_eng)
    db.flush()

    for title, status_val, completed in [
        ("Reconcile bank accounts", TaskStatus.done.value, True),
        ("Review AP/AR", TaskStatus.in_progress.value, False),
        ("Monthly close", TaskStatus.todo.value, False),
    ]:
        db.add(Task(
            firm_id=firm.id,
            client_id=brightline.id,
            engagement_id=brightline_eng.id,
            title=title,
            status=status_val,
            is_completed=completed,
            assigned_to=james.id,
            created_at=now(),
            updated_at=now(),
        ))
        task_count += 1

    db.add(Invoice(
        firm_id=firm.id,
        client_id=brightline.id,
        engagement_id=brightline_eng.id,
        invoice_number="INV-004",
        subtotal=400.00,
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=400.00,
        status=InvoiceStatus.sent,
        created_by=owner.id,
        created_at=now(),
        updated_at=now(),
    ))
    invoice_count += 1

    # 5. Robert & Carol Tanner
    tanner = Client(
        firm_id=firm.id,
        name="Robert & Carol Tanner",
        email="rtanner@example.com",
        entity_type="individual",
        portal_access_enabled=True,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(tanner)
    db.flush()

    tanner_eng = Engagement(
        firm_id=firm.id,
        client_id=tanner.id,
        name="2026 Individual Tax Return",
        engagement_type=EngagementType.tax_return_1040.value,
        status=EngagementStatus.draft.value,
        filing_deadline=next_year_date(4, 15),
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(tanner_eng)
    db.flush()

    # 6. Goldstein Family Trust
    goldstein = Client(
        firm_id=firm.id,
        name="Goldstein Family Trust",
        email="trustee@goldstein-example.com",
        entity_type="trust",
        portal_access_enabled=False,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(goldstein)
    db.flush()

    goldstein_eng = Engagement(
        firm_id=firm.id,
        client_id=goldstein.id,
        name="2025 Trust Tax Return",
        engagement_type=EngagementType.tax_return_1041.value,
        status=EngagementStatus.active.value,
        is_active=True,
        created_at=now(),
        updated_at=now(),
    )
    db.add(goldstein_eng)
    db.flush()

    for title, status_val, completed in [
        ("Gather trust documents", TaskStatus.done.value, True),
        ("Prepare return", TaskStatus.in_progress.value, False),
    ]:
        db.add(Task(
            firm_id=firm.id,
            client_id=goldstein.id,
            engagement_id=goldstein_eng.id,
            title=title,
            status=status_val,
            is_completed=completed,
            created_at=now(),
            updated_at=now(),
        ))
        task_count += 1

    db.add(Invoice(
        firm_id=firm.id,
        client_id=goldstein.id,
        engagement_id=goldstein_eng.id,
        invoice_number="INV-005",
        subtotal=1100.00,
        tax_rate=0.0,
        tax_amount=0.0,
        total_amount=1100.00,
        status=InvoiceStatus.sent,
        created_by=owner.id,
        created_at=now(),
        updated_at=now(),
    ))
    invoice_count += 1

    db.commit()

    print("=" * 60)
    print("JAMM PX — Demo Firm Ready")
    print("=" * 60)
    print(f"Firm:     Riverside Tax & Advisory")
    print(f"Slug:     riverside-demo")
    print()
    print(f"Credentials (password for all: {DEMO_PASSWORD})")
    print(f"  Owner:   owner@riverside-demo.com   (Sarah Chen)")
    print(f"  Manager: james@riverside-demo.com   (James Okafor)")
    print(f"  Staff:   priya@riverside-demo.com   (Priya Mehta)")
    print(f"           tom@riverside-demo.com     (Tom Reyes)")
    print()
    print(f"Data created:")
    print(f"  Clients:     6")
    print(f"  Engagements: 6")
    print(f"  Tasks:       {task_count}")
    print(f"  Invoices:    {invoice_count}")
    print()
    print(f"Plan override: ACTIVE — no Stripe required")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description="Seed JAMM PX demo firm")
    parser.add_argument("--reset", action="store_true", help="Delete and recreate demo firm")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        existing = db.query(Firm).filter_by(slug=DEMO_SLUG).first()
        if existing and not args.reset:
            print("Demo firm already exists. Use --reset to recreate.")
            sys.exit(0)

        if args.reset:
            delete_demo_firm(db)

        create_demo_firm(db)
    except Exception as e:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
