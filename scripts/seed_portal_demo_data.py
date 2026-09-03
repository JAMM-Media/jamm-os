# scripts/seed_portal_demo_data.py
"""
Seeds realistic demo documents for the portal-demo@jammpx.com test client
so the To-do page's "Recent documents" section shows real rows.

IMPORTANT LIMITATION -- read before running:

  pending_document_requests (stat cards + Open tasks list): the portal dashboard
  endpoint currently hardcodes pending_document_requests = [] with an explicit
  TODO comment ("populate when Phase 4 DocumentRequest model is built"). Creating
  DocumentRequest rows in the DB will NOT populate the stat cards or task list --
  the backend query that would surface them is not yet written. Additionally,
  DocumentRequest requires engagement_id NOT NULL, and the demo client has no
  engagements. This script therefore does NOT seed DocumentRequest rows.

  pending_signatures (Open tasks list): SignatureEnvelope creation requires
  external provider IDs and multiple document FKs. Creating a syntactically
  valid but semantically broken envelope is not done here per the task's
  explicit skip instruction for non-trivial relationship seeding.

What this script DOES:
  Creates 4 Document rows scoped to the demo client with visibility=client_visible,
  so the "Recent documents" table in the portal To-do page populates with real data.

Run from the project root:
    python scripts/seed_portal_demo_data.py

Idempotent: checks for existing rows by s3_key before creating.
"""

import sys
import os
import uuid
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.document import Document

CLIENT_EMAIL = "portal-demo@jammpx.com"
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")

now = datetime.now(timezone.utc)

DEMO_DOCUMENTS = [
    {
        "filename": "2024_W2_MainEmployer.pdf",
        "content_type": "application/pdf",
        "size_bytes": 184320,
        "category": "tax_document",
        "created_at": now - timedelta(days=3),
    },
    {
        "filename": "Q1_2024_BankStatement.pdf",
        "content_type": "application/pdf",
        "size_bytes": 512000,
        "category": "bank_statement",
        "created_at": now - timedelta(days=8),
    },
    {
        "filename": "SignedEngagementLetter_2024.pdf",
        "content_type": "application/pdf",
        "size_bytes": 95232,
        "category": "engagement_letter",
        "created_at": now - timedelta(days=14),
    },
    {
        "filename": "BusinessExpenseReceipts_Q1_2024.pdf",
        "content_type": "application/pdf",
        "size_bytes": 2097152,
        "category": "other",
        "created_at": now - timedelta(days=21),
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        # Verify the demo client exists
        client = db.execute(
            select(Client).where(Client.email == CLIENT_EMAIL)
        ).scalars().first()
        if not client:
            print(f"ERROR: Client {CLIENT_EMAIL} not found. Run scripts/seed_portal_client.py first.")
            return

        actual_client_id = client.id
        actual_firm_id = client.firm_id

        created = 0
        skipped = 0

        for doc_def in DEMO_DOCUMENTS:
            doc_id = uuid.uuid4()
            s3_key = (
                f"{actual_firm_id}/{actual_client_id}/none"
                f"/{doc_id}/{doc_def['filename']}"
            )

            existing = db.execute(
                select(Document).where(
                    Document.client_id == actual_client_id,
                    Document.filename == doc_def["filename"],
                )
            ).scalars().first()

            if existing:
                print(f"  skip (exists): {doc_def['filename']}")
                skipped += 1
                continue

            doc = Document(
                id=doc_id,
                firm_id=actual_firm_id,
                client_id=actual_client_id,
                engagement_id=None,
                uploaded_by=None,
                filename=doc_def["filename"],
                s3_key=s3_key,
                content_type=doc_def["content_type"],
                size_bytes=doc_def["size_bytes"],
                category=doc_def["category"],
                visibility="client_visible",
                is_superseded=False,
                created_at=doc_def["created_at"],
                updated_at=doc_def["created_at"],
            )
            db.add(doc)
            db.flush()
            print(f"  created: {doc_def['filename']} (id: {doc_id})")
            created += 1

        db.commit()
        print()
        print(f"Done. Created {created} document(s), skipped {skipped} (already existed).")
        print()
        print("Limitation note:")
        print("  Stat cards (Open tasks / Overdue / Due this week / Completed) and the")
        print("  'Open tasks' list will still show zeros. The portal dashboard endpoint")
        print("  hardcodes pending_document_requests = [] -- the backend query is not")
        print("  yet implemented (TODO in app/api/portal.py line ~525). These stat cards")
        print("  cannot be populated by seeding until that endpoint is updated.")
        print()
        print("  Only 'Recent documents' will now show real rows. No server restart")
        print("  needed -- just refresh the browser.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
