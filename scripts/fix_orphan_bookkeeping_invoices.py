# scripts/fix_orphan_bookkeeping_invoices.py
"""
One-time idempotent data fix: link 5 orphan bookkeeping invoices for Riverside
Tax & Advisory to real year-specific engagements, and add TimeEntry rows so
Total hours this year reflects real, non-zero data.

Two engagements are created:
  2025 Bookkeeping Services  -- invoices from 2025 (Jun, Oct)
  2026 Bookkeeping Services  -- invoices from 2026 (Jun, Jul, Aug)

The script is idempotent: it checks before creating engagements, before
re-linking invoices, and before adding TimeEntry rows.

Safe to re-run if seed data is reset.
"""
import sys
import uuid
from datetime import date

sys.path.insert(0, "/home/corby/jamm-os")

from app.db.session import SessionLocal
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry

CLIENT_ID  = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID    = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
USER_ID    = uuid.UUID("93ab6936-de16-4baa-b1f0-55a9934e367f")

INVOICES_2025 = [
    uuid.UUID("9572fc6c-9886-40e4-b706-d6e78c9d3716"),  # sent Jun 2025, $1200
    uuid.UUID("6a2e230d-25dd-4f2f-8aa3-170ef37aa883"),  # sent Oct 2025, $750
]

INVOICES_2026 = [
    uuid.UUID("7754011d-4d06-4576-bf1d-4ba82c651801"),  # sent Jun 2026, $1200
    uuid.UUID("5da7537e-1f55-4c9c-ba1e-3c2183318aae"),  # sent Jul 2026, $1200
    uuid.UUID("3ee008d4-1dda-4045-bcbe-65725fcd1415"),  # sent Aug 2026, $950
]

# TimeEntry rows to add: invoice_id -> list of (description, hours, entry_date)
TIME_ENTRIES = {
    uuid.UUID("9572fc6c-9886-40e4-b706-d6e78c9d3716"): [
        ("General bookkeeping and transaction categorization", 8.00, date(2025, 6, 5)),
        ("Bank reconciliation", 0.50, date(2025, 6, 6)),
    ],
    uuid.UUID("6a2e230d-25dd-4f2f-8aa3-170ef37aa883"): [
        ("General bookkeeping and transaction categorization", 6.00, date(2025, 10, 14)),
        ("Accounts payable review", 0.50, date(2025, 10, 15)),
    ],
    uuid.UUID("7754011d-4d06-4576-bf1d-4ba82c651801"): [
        ("General bookkeeping and transaction categorization", 8.00, date(2026, 6, 12)),
        ("Bank reconciliation", 0.50, date(2026, 6, 13)),
    ],
    uuid.UUID("5da7537e-1f55-4c9c-ba1e-3c2183318aae"): [
        ("General bookkeeping and transaction categorization", 8.00, date(2026, 7, 14)),
        ("Credit card reconciliation", 0.50, date(2026, 7, 15)),
    ],
    uuid.UUID("3ee008d4-1dda-4045-bcbe-65725fcd1415"): [
        ("General bookkeeping and transaction categorization", 7.50, date(2026, 8, 22)),
    ],
}


def get_or_create_engagement(db, name):
    existing = db.query(Engagement).filter(
        Engagement.firm_id == FIRM_ID,
        Engagement.client_id == CLIENT_ID,
        Engagement.name == name,
    ).first()
    if existing:
        print(f"  Engagement already exists: {existing.name} ({existing.id})")
        return existing, False
    eng = Engagement(
        firm_id=FIRM_ID,
        client_id=CLIENT_ID,
        name=name,
        status="active",
    )
    db.add(eng)
    db.flush()
    print(f"  Created engagement: {eng.name} ({eng.id})")
    return eng, True


def link_invoices(db, invoice_ids, engagement):
    for inv_id in invoice_ids:
        inv = db.query(Invoice).filter(
            Invoice.id == inv_id,
            Invoice.firm_id == FIRM_ID,
            Invoice.client_id == CLIENT_ID,
        ).first()
        if inv is None:
            print(f"  WARNING: invoice {inv_id} not found -- skipping")
            continue
        if inv.engagement_id == engagement.id:
            print(f"  Invoice {inv_id} already linked to this engagement -- skipping")
            continue
        inv.engagement_id = engagement.id
        print(f"  Linked invoice {inv_id} (${float(inv.total_amount):.2f}) to {engagement.name}")


def add_time_entries(db, engagement_id):
    for inv_id, entries in TIME_ENTRIES.items():
        existing_count = db.query(TimeEntry).filter(
            TimeEntry.invoice_id == inv_id,
            TimeEntry.firm_id == FIRM_ID,
        ).count()
        if existing_count > 0:
            print(f"  TimeEntry rows already exist for invoice {inv_id} ({existing_count} row(s)) -- skipping")
            continue
        for description, hours, entry_date in entries:
            te = TimeEntry(
                firm_id=FIRM_ID,
                engagement_id=engagement_id,
                invoice_id=inv_id,
                user_id=USER_ID,
                description=description,
                hours=hours,
                hourly_rate=150.00,
                is_billable=True,
                is_billed=True,
                date=entry_date,
            )
            db.add(te)
            print(f"  Added TimeEntry: {description[:40]} | {hours} hrs | {entry_date} | invoice {inv_id}")


def main():
    db = SessionLocal()
    try:
        print("=== Step 1-2: Create engagements and link invoices ===")

        print("\n[2025 Bookkeeping Services]")
        eng_2025, _ = get_or_create_engagement(db, "2025 Bookkeeping Services")
        link_invoices(db, INVOICES_2025, eng_2025)

        print("\n[2026 Bookkeeping Services]")
        eng_2026, _ = get_or_create_engagement(db, "2026 Bookkeeping Services")
        link_invoices(db, INVOICES_2026, eng_2026)

        print("\n=== Step 3: Add TimeEntry rows ===")
        print("\n[2025 invoices]")
        for inv_id in INVOICES_2025:
            entries = TIME_ENTRIES.get(inv_id, [])
            if not entries:
                continue
            existing = db.query(TimeEntry).filter(
                TimeEntry.invoice_id == inv_id,
                TimeEntry.firm_id == FIRM_ID,
            ).count()
            if existing > 0:
                print(f"  TimeEntry rows already exist for {inv_id} ({existing} row(s)) -- skipping")
                continue
            for description, hours, entry_date in entries:
                te = TimeEntry(
                    firm_id=FIRM_ID,
                    engagement_id=eng_2025.id,
                    invoice_id=inv_id,
                    user_id=USER_ID,
                    description=description,
                    hours=hours,
                    hourly_rate=150.00,
                    is_billable=True,
                    is_billed=True,
                    date=entry_date,
                )
                db.add(te)
                print(f"  Added: {description[:50]} | {hours} hrs | {entry_date}")

        print("\n[2026 invoices]")
        for inv_id in INVOICES_2026:
            entries = TIME_ENTRIES.get(inv_id, [])
            if not entries:
                continue
            existing = db.query(TimeEntry).filter(
                TimeEntry.invoice_id == inv_id,
                TimeEntry.firm_id == FIRM_ID,
            ).count()
            if existing > 0:
                print(f"  TimeEntry rows already exist for {inv_id} ({existing} row(s)) -- skipping")
                continue
            for description, hours, entry_date in entries:
                te = TimeEntry(
                    firm_id=FIRM_ID,
                    engagement_id=eng_2026.id,
                    invoice_id=inv_id,
                    user_id=USER_ID,
                    description=description,
                    hours=hours,
                    hourly_rate=150.00,
                    is_billable=True,
                    is_billed=True,
                    date=entry_date,
                )
                db.add(te)
                print(f"  Added: {description[:50]} | {hours} hrs | {entry_date}")

        db.commit()
        print("\n=== Committed ===")

        print("\n=== Verification ===")
        for inv_id in INVOICES_2025 + INVOICES_2026:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            te_count = db.query(TimeEntry).filter(TimeEntry.invoice_id == inv_id).count()
            print(f"  Invoice {inv_id} | engagement_id: {inv.engagement_id} | time_entries: {te_count}")

        total_te = db.query(TimeEntry).count()
        print(f"\n  Total TimeEntry rows in database: {total_te}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()