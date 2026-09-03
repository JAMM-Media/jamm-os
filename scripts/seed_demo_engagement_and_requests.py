# scripts/seed_demo_engagement_and_requests.py
"""
Creates one real Engagement and five DocumentRequest rows for the demo portal
client so the To-do page stat cards and Open tasks list show genuine data.

  CLIENT_ID = bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47
  FIRM_ID   = 185314c9-e702-4eab-8600-249848022206

Spread of requests:
  - 2 x pending (one overdue, one due within 7 days)
  - 1 x pending (due later)
  - 1 x partial (overdue -- so "partial" also appears correctly in pending list)
  - 1 x complete (so the Completed stat card shows a non-zero count)

Run from the project root:
    python scripts/seed_demo_engagement_and_requests.py

Idempotent: skips if an engagement already exists for this client.
Backend needs restarting after this runs so the new endpoint logic takes effect.
"""

import sys
import os
import uuid
from datetime import date, datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.document_request import DocumentRequest

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")

TODAY = date.today()

REQUESTS = [
    {
        "title": "2024 W-2 Forms",
        "due_date": TODAY - timedelta(days=6),
        "status": "pending",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "W-2 from primary employer",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "Q1 2024 Bank Statements",
        "due_date": TODAY + timedelta(days=4),
        "status": "pending",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "January statement",
                "is_required": True,
                "status": "pending",
            },
            {
                "id": str(uuid.uuid4()),
                "label": "February statement",
                "is_required": True,
                "status": "pending",
            },
            {
                "id": str(uuid.uuid4()),
                "label": "March statement",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "Business Expense Receipts",
        "due_date": TODAY + timedelta(days=20),
        "status": "pending",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "Q1 receipts",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "Signed Engagement Letter",
        "due_date": TODAY - timedelta(days=10),
        "status": "partial",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "Signed engagement letter",
                "is_required": True,
                "status": "uploaded",
            },
            {
                "id": str(uuid.uuid4()),
                "label": "Authorization form",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "2023 Prior Year Tax Return",
        "due_date": TODAY - timedelta(days=45),
        "status": "complete",
        # completed_at set to a few days ago so the recency filter (current month) picks it up
        "completed_at": datetime.now(timezone.utc) - timedelta(days=3),
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "2023 Form 1040",
                "is_required": True,
                "status": "uploaded",
            },
        ],
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        # Verify client
        client = db.get(Client, CLIENT_ID)
        if not client:
            print(f"ERROR: Client {CLIENT_ID} not found. Run seed_portal_client.py first.")
            return

        # Find or create engagement
        existing_eng = db.execute(
            select(Engagement).where(
                Engagement.client_id == CLIENT_ID,
                Engagement.firm_id == FIRM_ID,
            )
        ).scalars().first()

        if existing_eng:
            engagement_id = existing_eng.id
            print(f"Using existing engagement: {existing_eng.name} (id: {engagement_id})")
        else:
            engagement = Engagement(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                name="2024 Individual Tax Return",
                status="active",
            )
            db.add(engagement)
            db.flush()
            engagement_id = engagement.id
            print(f"Created engagement: {engagement.name} (id: {engagement_id})")

        created = 0
        skipped = 0

        for req_def in REQUESTS:
            existing_req = db.execute(
                select(DocumentRequest).where(
                    DocumentRequest.client_id == CLIENT_ID,
                    DocumentRequest.firm_id == FIRM_ID,
                    DocumentRequest.title == req_def["title"],
                )
            ).scalars().first()

            if existing_req:
                print(f"  skip (exists): {req_def['title']}")
                skipped += 1
                continue

            dr = DocumentRequest(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                engagement_id=engagement_id,
                title=req_def["title"],
                due_date=req_def["due_date"],
                status=req_def["status"],
                checklist_items=req_def["checklist_items"],
                completed_at=req_def.get("completed_at"),
            )
            db.add(dr)
            db.flush()
            print(f"  created [{req_def['status']}]: {req_def['title']} (id: {dr.id})")
            created += 1

        db.commit()
        print()
        print(f"Done. Created {created} document request(s), skipped {skipped}.")
        print()

        status_summary = {}
        for r in REQUESTS:
            status_summary[r["status"]] = status_summary.get(r["status"], 0) + 1
        for s, n in sorted(status_summary.items()):
            print(f"  {s}: {n}")

        print()
        print("Next steps:")
        print("  1. Restart the backend server (endpoint logic changed).")
        print("  2. Refresh the portal browser tab.")
        print("  The To-do stat cards should now show real counts.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
