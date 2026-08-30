# scripts/name_bookkeeping_line_items.py
"""
One-time idempotent data fix: add a period-specific "name" field to each
line item on the 5 Riverside bookkeeping invoices.

Before this fix each line item only had "description" (the category text).
After this fix:
  Bookkeeping line: name = "Monthly Bookkeeping - <Month Year>"
                    description = "General bookkeeping and transaction categorization"
  Reconciliation line: name = "Bank Reconciliation"
                       description = "Bank Reconciliation"

Idempotent: skips any invoice whose line items already carry the correct
name values.

Do NOT change total_amount, engagement_id, status, or amounts.
"""
import sys

sys.path.insert(0, "/home/corby/jamm-os")

from app.db.session import SessionLocal
from app.models.invoice import Invoice
from sqlalchemy.orm.attributes import flag_modified

INVOICE_IDS = [
    "9572fc6c-9886-40e4-b706-d6e78c9d3716",
    "6a2e230d-25dd-4f2f-8aa3-170ef37aa883",
    "7754011d-4d06-4576-bf1d-4ba82c651801",
    "5da7537e-1f55-4c9c-ba1e-3c2183318aae",
    "3ee008d4-1dda-4045-bcbe-65725fcd1415",
]

BOOKKEEPING_DESC = "General bookkeeping and transaction categorization"
RECONCILIATION_DESC = "Bank Reconciliation"


def expected_name(description, month_year):
    if description == BOOKKEEPING_DESC:
        return f"Monthly Bookkeeping - {month_year}"
    return description


def already_named(line_items, month_year):
    """Return True if all line items already have the correct name field."""
    if not line_items:
        return False
    for item in line_items:
        if "name" not in item:
            return False
        desc = item.get("description", "")
        if item["name"] != expected_name(desc, month_year):
            return False
    return True


def main():
    db = SessionLocal()
    try:
        print("=== Applying name fields to bookkeeping line items ===\n")
        for inv_id in INVOICE_IDS:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            if inv is None:
                print(f"  {inv_id} NOT FOUND -- skipping")
                continue

            sent_at = inv.sent_at
            if sent_at is None:
                print(f"  {inv_id} has no sent_at -- skipping")
                continue

            month_year = sent_at.strftime("%B %Y")

            if already_named(inv.line_items, month_year):
                print(f"  {inv_id} ({month_year}) already named -- skipping")
                continue

            updated_items = []
            for item in (inv.line_items or []):
                desc = item.get("description", "")
                new_item = dict(item)
                new_item["name"] = expected_name(desc, month_year)
                updated_items.append(new_item)
                print(f"  {inv_id} ({month_year}) | name: {new_item['name']!r} | desc: {desc!r}")

            inv.line_items = updated_items
            flag_modified(inv, "line_items")

        db.commit()
        print("\n=== Committed ===")

        print("\n=== Verification ===")
        for inv_id in INVOICE_IDS:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            if inv is None:
                continue
            month_year = inv.sent_at.strftime("%B %Y") if inv.sent_at else "?"
            print(f"\n  Invoice {inv_id} ({month_year})")
            for item in (inv.line_items or []):
                print(f"    name: {item.get('name')!r}")
                print(f"    description: {item.get('description')!r}")
                print(f"    amount (total): {item.get('total') or item.get('amount')}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()