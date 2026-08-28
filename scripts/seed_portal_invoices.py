# scripts/seed_portal_invoices.py
"""
Seeds 5 realistic invoices for the demo portal client so the rebuilt Invoices
page can be reviewed with real content: stat cards, table rows, status badges,
Pay Now button, and Download PDF.

  CLIENT_ID = bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47
  FIRM_ID   = 185314c9-e702-4eab-8600-249848022206

Invoice mix (matching the reference mock):
  INV-1001  paid      Q1 2023 Bookkeeping Services    $1,200
  INV-1002  paid      2023 Tax Return Preparation       $750
  INV-1003  paid      Q2 2024 Bookkeeping Services    $1,200
  INV-1004  overdue   Q3 2024 Bookkeeping Services    $1,200  (past due, not paid)
  INV-1005  sent      2024 Tax Return Preparation       $950  (due in ~2 weeks)

Run from the project root:
    python scripts/seed_portal_invoices.py

Idempotent: skips any invoice number that already exists for this firm.
No server restart needed -- just refresh the browser after running.
"""

import sys
import os
import uuid
from datetime import date, datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.invoice import Invoice
from app.core.enums import InvoiceStatus, InvoiceDeliveryMethod

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")

TODAY = date.today()
NOW = datetime.now(timezone.utc)


def _line_item(description: str, amount: float) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "description": description,
        "quantity": 1,
        "unit_price": amount,
        "total": amount,
    }


INVOICES = [
    {
        "invoice_number": "INV-1001",
        "status": InvoiceStatus.paid,
        "line_items": [_line_item("Q1 2023 Bookkeeping Services", 1200.00)],
        "subtotal": 1200.00,
        "total_amount": 1200.00,
        "due_date": date(2023, 3, 31),
        "paid_at": NOW - timedelta(days=430),
        "sent_at": NOW - timedelta(days=445),
    },
    {
        "invoice_number": "INV-1002",
        "status": InvoiceStatus.paid,
        "line_items": [_line_item("2023 Tax Return Preparation", 750.00)],
        "subtotal": 750.00,
        "total_amount": 750.00,
        "due_date": date(2023, 9, 15),
        "paid_at": NOW - timedelta(days=300),
        "sent_at": NOW - timedelta(days=315),
    },
    {
        "invoice_number": "INV-1003",
        "status": InvoiceStatus.paid,
        "line_items": [_line_item("Q2 2024 Bookkeeping Services", 1200.00)],
        "subtotal": 1200.00,
        "total_amount": 1200.00,
        "due_date": date(2024, 6, 30),
        "paid_at": NOW - timedelta(days=58),
        "sent_at": NOW - timedelta(days=73),
    },
    {
        "invoice_number": "INV-1004",
        "status": InvoiceStatus.overdue,
        "line_items": [_line_item("Q3 2024 Bookkeeping Services", 1200.00)],
        "subtotal": 1200.00,
        "total_amount": 1200.00,
        "due_date": TODAY - timedelta(days=28),
        "paid_at": None,
        "sent_at": NOW - timedelta(days=42),
    },
    {
        "invoice_number": "INV-1005",
        "status": InvoiceStatus.sent,
        "line_items": [_line_item("2024 Tax Return Preparation", 950.00)],
        "subtotal": 950.00,
        "total_amount": 950.00,
        "due_date": TODAY + timedelta(days=14),
        "paid_at": None,
        "sent_at": NOW - timedelta(days=3),
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        client = db.get(Client, CLIENT_ID)
        if not client:
            print(f"ERROR: Client {CLIENT_ID} not found. Run seed_portal_client.py first.")
            return

        created = 0
        skipped = 0

        for inv_def in INVOICES:
            existing = db.execute(
                select(Invoice).where(
                    Invoice.firm_id == FIRM_ID,
                    Invoice.invoice_number == inv_def["invoice_number"],
                )
            ).scalars().first()

            if existing:
                print(f"  skip (exists): {inv_def['invoice_number']} [{existing.status.value}]")
                skipped += 1
                continue

            inv = Invoice(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                invoice_number=inv_def["invoice_number"],
                line_items=inv_def["line_items"],
                subtotal=inv_def["subtotal"],
                tax_rate=0.0,
                tax_amount=0.0,
                total_amount=inv_def["total_amount"],
                status=inv_def["status"],
                due_date=inv_def["due_date"],
                paid_at=inv_def["paid_at"],
                sent_at=inv_def["sent_at"],
                delivery_method=InvoiceDeliveryMethod.portal,
                is_deleted=False,
            )
            db.add(inv)
            db.flush()
            print(
                f"  created [{inv_def['status'].value:8s}]: "
                f"{inv_def['invoice_number']}  "
                f"${inv_def['total_amount']:,.2f}  "
                f"due {inv_def['due_date']}  (id: {inv.id})"
            )
            created += 1

        db.commit()

        print()
        print(f"Done. Created {created} invoice(s), skipped {skipped} (already existed).")
        print()

        # Summary query
        invoices = db.execute(
            select(Invoice).where(
                Invoice.client_id == CLIENT_ID,
                Invoice.firm_id == FIRM_ID,
                Invoice.is_deleted == False,
            ).order_by(Invoice.invoice_number)
        ).scalars().all()

        print("Current invoices for demo client:")
        for inv in invoices:
            print(
                f"  {inv.invoice_number}  [{inv.status.value:8s}]  "
                f"${float(inv.total_amount):,.2f}  "
                f"due {inv.due_date}"
            )

        print()
        print("Refresh the portal browser tab -- no server restart needed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
