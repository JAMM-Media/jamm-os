# scripts/fix_document_attribution.py
"""
Verifies and corrects uploaded_by attribution on the four demo portal documents.

The portal list endpoint derives attribution from Document.uploaded_by:
  NULL -> "client" (portal client uploaded it, no staff user involved)
  non-NULL UUID -> "firm" (a specific staff user uploaded it)

These four documents are all client-sourced uploads (W-2, bank statement,
signed engagement letter, business expense receipts). Their uploaded_by
should be NULL so the portal correctly places them under "Uploaded by you".

Idempotent: checks current state and prints what was found. Only updates
rows that have a non-NULL uploaded_by when they should not.

Run from the project root:
    python scripts/fix_document_attribution.py
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.document import Document

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")

# Filenames that are client-sourced uploads and must have uploaded_by = NULL.
CLIENT_UPLOADED_FILENAMES = {
    "2024_W2_MainEmployer.pdf",
    "Q1_2024_BankStatement.pdf",
    "SignedEngagementLetter_2024.pdf",
    "BusinessExpenseReceipts_Q1_2024.pdf",
}


def main() -> None:
    db = SessionLocal()
    try:
        docs = db.execute(
            select(Document).where(
                Document.client_id == CLIENT_ID,
                Document.firm_id == FIRM_ID,
            )
        ).scalars().all()

        if not docs:
            print("ERROR: No documents found for demo client. Run seed_portal_demo_data.py first.")
            return

        corrected = 0
        already_correct = 0

        for doc in docs:
            if doc.filename not in CLIENT_UPLOADED_FILENAMES:
                print(f"  skip (not a client-upload target): {doc.filename}")
                continue

            if doc.uploaded_by is None:
                print(f"  ok (uploaded_by already NULL): {doc.filename}")
                already_correct += 1
            else:
                print(f"  fix (clearing uploaded_by {doc.uploaded_by}): {doc.filename}")
                doc.uploaded_by = None
                corrected += 1

        if corrected > 0:
            db.commit()

        print()
        print(f"Done. {already_correct} already correct, {corrected} corrected.")
        print()
        print("Attribution rule: uploaded_by IS NULL -> portal shows 'Uploaded by you'")
        print("                  uploaded_by non-NULL -> portal shows 'Shared with you'")
    finally:
        db.close()


if __name__ == "__main__":
    main()
