# scripts/seed_portal_document_folders.py
"""
One-time idempotent script: assigns real documents to their correct folders
for the Riverside demo client (bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47).

All four documents were seeded with folder_id=None, causing the Bank Statements
and Tax Documents folders to appear empty in the portal. This script assigns:
  Q1_2024_BankStatement.pdf  -> Bank Statements folder
  2024_W2_MainEmployer.pdf   -> Tax Documents folder

The other two documents (SignedEngagementLetter_2024.pdf and
BusinessExpenseReceipts_Q1_2024.pdf) remain at the root level since
no folder clearly matches them.

Idempotent: skips any document that already has the correct folder_id.
Run from /home/corby/jamm-os with the venv active.
"""
import sys
sys.path.insert(0, '/home/corby/jamm-os')

import uuid
from app.db.session import SessionLocal
from app.models.document import Document

CLIENT_ID = uuid.UUID('bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47')
FIRM_ID = uuid.UUID('185314c9-e702-4eab-8600-249848022206')

# Real folder IDs confirmed from the database
FOLDER_BANK_STATEMENTS = uuid.UUID('2b0906e1-6a53-4bbc-90e9-09e3150c8b06')
FOLDER_TAX_DOCUMENTS = uuid.UUID('0c864883-5489-4f42-b7e6-44291e83ae54')

# Real document IDs confirmed from the database
DOC_BANK_STATEMENT = uuid.UUID('b5c27895-2c67-491f-b8f7-89426361c55f')  # Q1_2024_BankStatement.pdf
DOC_W2 = uuid.UUID('9e3a3cb8-9564-43a9-8f4d-2f9225c9ef9e')              # 2024_W2_MainEmployer.pdf

ASSIGNMENTS = [
    (DOC_BANK_STATEMENT, FOLDER_BANK_STATEMENTS, 'Q1_2024_BankStatement.pdf'),
    (DOC_W2, FOLDER_TAX_DOCUMENTS, '2024_W2_MainEmployer.pdf'),
]


def main() -> None:
    db = SessionLocal()
    try:
        updated = 0
        skipped = 0
        for doc_id, folder_id, filename in ASSIGNMENTS:
            doc = (
                db.query(Document)
                .filter(
                    Document.id == doc_id,
                    Document.client_id == CLIENT_ID,
                    Document.firm_id == FIRM_ID,
                )
                .first()
            )
            if not doc:
                print(f'  ERROR: document {doc_id} ({filename}) not found')
                continue
            if doc.folder_id == folder_id:
                print(f'  SKIP (already assigned): {filename}')
                skipped += 1
                continue
            doc.folder_id = folder_id
            print(f'  ASSIGN: {filename} -> folder {folder_id}')
            updated += 1
        db.commit()
        print(f'Done. Assigned {updated}, skipped {skipped}.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
