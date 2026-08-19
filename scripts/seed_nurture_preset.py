# scripts/seed_nurture_preset.py
"""
Backfill the acquisition nurture preset tree for existing firms that predate
the per-firm seeding hook added to create_firm.

Run from the project root:
    python scripts/seed_nurture_preset.py

Idempotent: checks for an existing Sequence with preset_lineage_key=
acquisition_nurture_v1 before seeding, so re-running is safe.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.session import SessionLocal
from app.models.firm import Firm
from app.models.sequence import Sequence, SequenceVersion
from app.services.nurture_preset import PRESET_LINEAGE_KEY, seed_firm_nurture_preset


def main():
    db = SessionLocal()
    try:
        firms = db.query(Firm).order_by(Firm.created_at).all()
        if not firms:
            print("No firms found.")
            return

        seeded = 0
        skipped = 0
        for firm in firms:
            existing = (
                db.query(SequenceVersion)
                .join(Sequence, SequenceVersion.sequence_id == Sequence.id)
                .filter(
                    Sequence.firm_id == firm.id,
                    SequenceVersion.preset_lineage_key == PRESET_LINEAGE_KEY,
                )
                .first()
            )
            if existing:
                print(f"  Skipping (already seeded): {firm.name} ({firm.id})")
                skipped += 1
                continue

            try:
                n = seed_firm_nurture_preset(firm_id=firm.id, db=db)
                print(f"  Seeded {n} steps for: {firm.name} ({firm.id})")
                seeded += 1
            except Exception as exc:
                print(f"  ERROR for {firm.name} ({firm.id}): {exc}")

        print(f"\nDone. {seeded} firm(s) seeded, {skipped} skipped (already had preset).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
