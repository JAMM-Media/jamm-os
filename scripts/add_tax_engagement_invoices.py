# scripts/add_tax_engagement_invoices.py
"""
One-time idempotent data fix: add 2 invoices under the existing
"2024 Individual Tax Return" engagement for the Riverside demo client,
with real tax-specific line items that contrast with the bookkeeping
invoices already present.

Invoice 1: Individual tax return (March 2025), $800.00
  - Individual Tax Return Preparation: $650.00
  - Schedule A - Itemized Deductions:  $150.00

Invoice 2: Tax planning + state return (April 2025), $450.00
  - Tax Planning Consultation:         $250.00
  - State Tax Return Preparation:      $200.00

Both invoices are status=paid, sent_at in 2025, so they appear in
billing history without affecting the 2026 "this year" stat totals.

Idempotent: if any invoice already exists under this engagement,
skip creation and report what is already there.
"""
import sys
import uuid
from datetime import datetime, timezone

sys.path.insert(0, "/home/corby/jamm-os")

from app.db.session import SessionLocal
from app.models.invoice import Invoice
from app.core.enums import InvoiceStatus, InvoiceDeliveryMethod

CLIENT_ID    = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID      = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
TAX_ENG_ID   = uuid.UUID("8ab12dfa-058b-43d7-8084-df90e60f37cc")

INVOICES = [
    {
        "invoice_number": "TAX-2025-001",
        "sent_at": datetime(2025, 3, 28, 12, 0, 0, tzinfo=timezone.utc),
        "total_amount": 800.00,
        "subtotal": 800.00,
        "line_items": [
            {
                "id": str(uuid.uuid4()),
                "name": "Individual Tax Return - 2024",
                "description": "Individual Tax Return Preparation",
                "quantity": 1,
                "unit_price": 650.00,
                "total": 650.00,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Schedule A - 2024",
                "description": "Schedule A - Itemized Deductions",
                "quantity": 1,
                "unit_price": 150.00,
                "total": 150.00,
            },
        ],
    },
    {
        "invoice_number": "TAX-2025-002",
        "sent_at": datetime(2025, 4, 15, 12, 0, 0, tzinfo=timezone.utc),
        "total_amount": 450.00,
        "subtotal": 450.00,
        "line_items": [
            {
                "id": str(uuid.uuid4()),
                "name": "Tax Planning - 2025",
                "description": "Tax Planning Consultation",
                "quantity": 1,
                "unit_price": 250.00,
                "total": 250.00,
            },
            {
                "id": str(uuid.uuid4()),
                "name": "State Return - 2024",
                "description": "State Tax Return Preparation",
                "quantity": 1,
                "unit_price": 200.00,
                "total": 200.00,
            },
        ],
    },
]


def main():
    db = SessionLocal()
    try:
        # Idempotency: check if any invoice already exists under this engagement
        existing = db.query(Invoice).filter(
            Invoice.engagement_id == TAX_ENG_ID,
            Invoice.firm_id == FIRM_ID,
            Invoice.client_id == CLIENT_ID,
            Invoice.is_deleted == False,
        ).all()

        if existing:
            print(f"Invoices already exist under the tax engagement -- skipping creation.")
            for inv in existing:
                print(f"  {inv.id} | {inv.invoice_number} | ${float(inv.total_amount):.2f} | {inv.sent_at}")
            print("\nRun a second time after deletion if a reset is needed.")
            return

        print("=== Sum checks before insert ===")
        for inv_data in INVOICES:
            item_sum = round(sum(float(it["total"]) for it in inv_data["line_items"]), 2)
            total = round(inv_data["total_amount"], 2)
            match = "OK" if item_sum == total else "MISMATCH"
            print(f"  {inv_data['invoice_number']}: line items sum ${item_sum:.2f}, total_amount ${total:.2f} [{match}]")
            assert item_sum == total, f"Sum mismatch for {inv_data['invoice_number']}"

        print("\n=== Creating invoices ===")
        created = []
        for inv_data in INVOICES:
            inv = Invoice(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                engagement_id=TAX_ENG_ID,
                invoice_number=inv_data["invoice_number"],
                line_items=inv_data["line_items"],
                subtotal=inv_data["subtotal"],
                tax_rate=0.0,
                tax_amount=0.0,
                total_amount=inv_data["total_amount"],
                status=InvoiceStatus.paid,
                delivery_method=InvoiceDeliveryMethod.portal,
                sent_at=inv_data["sent_at"],
                is_deleted=False,
            )
            db.add(inv)
            db.flush()
            created.append(inv)
            print(f"  Created {inv.invoice_number} ({inv.id}) | ${float(inv.total_amount):.2f} | sent_at {inv.sent_at.date()}")

        db.commit()
        print("\n=== Committed ===")

        print("\n=== Verification ===")
        for inv in created:
            db.refresh(inv)
            print(f"\n  Invoice {inv.id}")
            print(f"    invoice_number: {inv.invoice_number}")
            print(f"    engagement_id:  {inv.engagement_id}")
            print(f"    total_amount:   ${float(inv.total_amount):.2f}")
            print(f"    status:         {inv.status}")
            print(f"    sent_at:        {inv.sent_at}")
            item_sum = 0.0
            for it in (inv.line_items or []):
                amt = float(it.get("total", it.get("amount", 0)))
                item_sum += amt
                print(f"    line: {it.get('name')!r} | {it.get('description')!r} | ${amt:.2f}")
            print(f"    line sum: ${item_sum:.2f} vs total_amount ${float(inv.total_amount):.2f} [{'OK' if round(item_sum, 2) == round(float(inv.total_amount), 2) else 'MISMATCH'}]")

        # Total invoice count for this client
        total_count = db.query(Invoice).filter(
            Invoice.client_id == CLIENT_ID,
            Invoice.firm_id == FIRM_ID,
            Invoice.is_deleted == False,
        ).count()
        print(f"\n  Total invoices for this client: {total_count}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()