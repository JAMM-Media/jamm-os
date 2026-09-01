# scripts/seed_portal_notifications_demo.py
"""
One-time idempotent script: seeds 5 real PortalNotification rows for the
Riverside demo client (bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47).

Each row references a genuinely existing database record confirmed
before this script was written. Run from /home/corby/jamm-os with
the venv active.

Idempotent: checks (notification_type, related_entity_id) before
inserting. Re-running is safe.
"""
import sys
sys.path.insert(0, '/home/corby/jamm-os')

import uuid
from datetime import datetime
from zoneinfo import ZoneInfo

from app.db.session import SessionLocal
from app.models.portal_notification import PortalNotification

FIRM_ID = uuid.UUID('185314c9-e702-4eab-8600-249848022206')
CLIENT_ID = uuid.UUID('bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47')
ET = ZoneInfo('America/New_York')


def et(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=ET)


NOTIFICATIONS = [
    # 1. message
    # References real staff message sent 2026-08-26 10:31 ET
    # (client_messages id f3da9bb0-7882-4c58-bec9-97bec388522e)
    # Body: "Yes, that's the final amount for August. It covers the standard
    # monthly bookkeeping plus the credit card reconciliation..."
    {
        'title': 'New message from your team',
        'body': '"Yes, that\'s the final amount for August." Re: your August invoice question.',
        'notification_type': 'message',
        'is_read': False,
        'is_pinned': False,
        'related_entity_type': 'client_message',
        'related_entity_id': uuid.UUID('f3da9bb0-7882-4c58-bec9-97bec388522e'),
        'created_at': et(2026, 8, 26, 10, 31),
    },
    # 2. document_request
    # References real document_request id 739a8851: "Q1 2024 Bank Statements"
    # Status: pending, due 2026-08-25 (now overdue as of today 2026-09-01)
    {
        'title': 'Document request: Q1 2024 Bank Statements',
        'body': 'This request was due Aug 25. Please upload the documents when ready.',
        'notification_type': 'document_request',
        'is_read': False,
        'is_pinned': False,
        'related_entity_type': 'document_request',
        'related_entity_id': uuid.UUID('739a8851-c5b6-4f44-969a-78f275557410'),
        'created_at': et(2026, 8, 24, 9, 0),
    },
    # 3. payment_due
    # References real invoice id 5da7537e: INV-1004, $1,200.00, status overdue,
    # due_date 2026-07-30
    {
        'title': 'Invoice INV-1004 is overdue',
        'body': '$1,200.00 was due July 30. Please review your Invoices page.',
        'notification_type': 'payment_due',
        'is_read': False,
        'is_pinned': False,
        'related_entity_type': 'invoice',
        'related_entity_id': uuid.UUID('5da7537e-1f55-4c9c-ba1e-3c2183318aae'),
        'created_at': et(2026, 8, 15, 9, 0),
    },
    # 4. engagement_update
    # References real engagement id 8ab12dfa: "2024 Individual Tax Return", active
    {
        'title': '2024 Individual Tax Return in progress',
        'body': 'Your engagement is active. Check the To-do tab for any open items.',
        'notification_type': 'engagement_update',
        'is_read': True,
        'is_pinned': False,
        'related_entity_type': 'engagement',
        'related_entity_id': uuid.UUID('8ab12dfa-058b-43d7-8084-df90e60f37cc'),
        'created_at': et(2026, 8, 7, 10, 0),
    },
    # 5. system
    # No specific entity reference -- honest system notification marking
    # when the portal account was set up (documents first appeared 2026-07-31)
    {
        'title': 'Your client portal is ready',
        'body': 'You can now view invoices, documents, and messages from Riverside Tax & Advisory.',
        'notification_type': 'system',
        'is_read': True,
        'is_pinned': False,
        'related_entity_type': None,
        'related_entity_id': None,
        'created_at': et(2026, 7, 31, 10, 0),
    },
]


def main():
    db = SessionLocal()
    try:
        existing = (
            db.query(PortalNotification)
            .filter(PortalNotification.client_id == CLIENT_ID)
            .all()
        )
        existing_keys = {
            (str(n.notification_type), str(n.related_entity_id) if n.related_entity_id else None)
            for n in existing
        }

        inserted = 0
        skipped = 0
        for spec in NOTIFICATIONS:
            key = (
                spec['notification_type'],
                str(spec['related_entity_id']) if spec['related_entity_id'] else None,
            )
            if key in existing_keys:
                print(f'  SKIP (already exists): {spec["title"]}')
                skipped += 1
                continue

            n = PortalNotification(
                id=uuid.uuid4(),
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                title=spec['title'],
                body=spec['body'],
                notification_type=spec['notification_type'],
                is_read=spec['is_read'],
                is_pinned=spec['is_pinned'],
                related_entity_type=spec.get('related_entity_type'),
                related_entity_id=spec.get('related_entity_id'),
                created_at=spec['created_at'],
            )
            db.add(n)
            inserted += 1
            print(f'  INSERT: {spec["title"]}')

        db.commit()
        print(f'Done. Inserted {inserted}, skipped {skipped}.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
