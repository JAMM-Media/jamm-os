# scripts/repair_line_item_none.py
"""
Finds invoices whose line_items JSON contains the literal string "None" in
any field (caused by a prior bug that ran str(v) over every value, including
None, before writing line_items). Replaces those "None" strings with real
null values.

Dry run by default -- prints a per-invoice summary and writes nothing.
Pass --apply to persist the fixes.

Run from the project root:
    python scripts/repair_line_item_none.py            # dry run
    python scripts/repair_line_item_none.py --apply    # writes changes
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.invoice import Invoice


def _repair_line_items(line_items):
    """Returns (fixed_line_items, changed_fields) where changed_fields is a
    list of "index.field" strings for every value that was "None" and got
    replaced with null."""
    changed_fields = []
    fixed = []
    for idx, item in enumerate(line_items):
        new_item = {}
        for field, value in item.items():
            if value == "None":
                changed_fields.append(f"{idx}.{field}")
                new_item[field] = None
            else:
                new_item[field] = value
        fixed.append(new_item)
    return fixed, changed_fields


def run(apply: bool) -> int:
    db = SessionLocal()
    try:
        invoices = db.query(Invoice).filter(Invoice.line_items.isnot(None)).all()

        affected_count = 0
        for invoice in invoices:
            if not invoice.line_items:
                continue
            fixed, changed_fields = _repair_line_items(invoice.line_items)
            if not changed_fields:
                continue

            affected_count += 1
            print(
                f"invoice_id={invoice.id} firm_id={invoice.firm_id} "
                f"invoice_number={invoice.invoice_number} fields={changed_fields}"
            )

            if apply:
                invoice.line_items = fixed

        if apply and affected_count:
            db.commit()

        mode = "APPLIED" if apply else "DRY RUN"
        print(f"{mode}: {affected_count} invoice(s) with corrupted line_items")
        return affected_count
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the fixes. Without this flag the script only prints what it would change.",
    )
    args = parser.parse_args()
    run(apply=args.apply)
