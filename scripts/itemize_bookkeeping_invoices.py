# scripts/itemize_bookkeeping_invoices.py
"""
One-time idempotent data fix: replace the single generic line item on 5
Riverside demo invoices with two properly-themed bookkeeping line items.

Target structure for each invoice:
  Line 1: "General bookkeeping and transaction categorization"
           amount = total_amount - 50.00
  Line 2: "Bank Reconciliation"
           amount = 50.00
  Sum = total_amount (unchanged)

Idempotent: skips any invoice whose line_items already has the two-line
structure with these exact descriptions.

Do NOT change total_amount, engagement_id, status, or any other field.
"""
import sys
import uuid

sys.path.insert(0, "/home/corby/jamm-os")

from app.db.session import SessionLocal
from app.models.invoice import Invoice

INVOICE_IDS = [
    "9572fc6c-9886-40e4-b706-d6e78c9d3716",
    "6a2e230d-25dd-4f2f-8aa3-170ef37aa883",
    "7754011d-4d06-4576-bf1d-4ba82c651801",
    "5da7537e-1f55-4c9c-ba1e-3c2183318aae",
    "3ee008d4-1dda-4045-bcbe-65725fcd1415",
]

LINE1_DESC = "General bookkeeping and transaction categorization"
LINE2_DESC = "Bank Reconciliation"
LINE2_AMOUNT = 50.00

TARGET_DESCRIPTIONS = {LINE1_DESC, LINE2_DESC}


def already_itemized(line_items):
    """Return True if line_items already has exactly the two target lines."""
    if not line_items or len(line_items) != 2:
        return False
    descs = {item.get("description", "") for item in line_items}
    return descs == TARGET_DESCRIPTIONS


def build_line_items(total_amount):
    line1_amount = round(float(total_amount) - LINE2_AMOUNT, 2)
    return [
        {
            "id": str(uuid.uuid4()),
            "description": LINE1_DESC,
            "quantity": 1,
            "unit_price": line1_amount,
            "total": line1_amount,
        },
        {
            "id": str(uuid.uuid4()),
            "description": LINE2_DESC,
            "quantity": 1,
            "unit_price": LINE2_AMOUNT,
            "total": LINE2_AMOUNT,
        },
    ]


def main():
    db = SessionLocal()
    try:
        print("=== Before state ===")
        for inv_id in INVOICE_IDS:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            if inv is None:
                print(f"  {inv_id} NOT FOUND")
                continue
            print(f"  {inv.id} | total: ${float(inv.total_amount):.2f} | items: {inv.line_items}")

        print("\n=== Applying itemization ===")
        for inv_id in INVOICE_IDS:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            if inv is None:
                print(f"  {inv_id} NOT FOUND -- skipping")
                continue

            if already_itemized(inv.line_items):
                print(f"  {inv.id} already has two-line structure -- skipping")
                continue

            total = float(inv.total_amount)
            new_items = build_line_items(total)
            line1_amt = new_items[0]["total"]
            line2_amt = new_items[1]["total"]
            check_sum = round(line1_amt + line2_amt, 2)

            assert check_sum == round(total, 2), (
                f"Sum check failed for {inv_id}: {line1_amt} + {line2_amt} = {check_sum} != {total}"
            )

            inv.line_items = new_items
            from sqlalchemy.orm.attributes import flag_modified
            flag_modified(inv, "line_items")

            print(f"  {inv.id} | ${line1_amt:.2f} + ${line2_amt:.2f} = ${check_sum:.2f} (total_amount ${total:.2f}) -- updated")

        db.commit()
        print("\n=== Committed ===")

        print("\n=== After state ===")
        for inv_id in INVOICE_IDS:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            if inv is None:
                continue
            items = inv.line_items or []
            total = float(inv.total_amount)
            item_sum = round(sum(float(it.get("total", it.get("amount", 0))) for it in items), 2)
            match = "OK" if item_sum == round(total, 2) else "MISMATCH"
            print(f"\n  Invoice {inv.id}")
            print(f"    total_amount: ${total:.2f} | engagement_id: {inv.engagement_id} | status: {inv.status}")
            for it in items:
                print(f"    line: {it['description']} | ${float(it.get('total', it.get('amount', 0))):.2f}")
            print(f"    sum of lines: ${item_sum:.2f} vs total_amount ${total:.2f} [{match}]")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()