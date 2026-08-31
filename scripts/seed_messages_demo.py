# scripts/seed_messages_demo.py
"""
Seed a realistic message thread between Riverside Tax & Advisory and their
demo portal client (bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47) for Messages
page demonstration.

Idempotent: if messages already exist for this client, skips and reports.
"""
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, "/home/corby/jamm-os")

from app.db.session import SessionLocal
from app.models.message import ClientMessage
import uuid

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID   = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
USER_ID   = uuid.UUID("fc28f112-d5e4-43fc-b9a9-cb99c36f15f8")  # Sarah Chen, firm owner

def ts(days_ago: int, hour: int = 10, minute: int = 0) -> datetime:
    base = datetime(2026, 8, 28, hour, minute, 0, tzinfo=timezone.utc)
    return base - timedelta(days=days_ago)

MESSAGES = [
    {
        "sender_role": "staff",
        "sender_id": USER_ID,
        "body": (
            "Hi!\n\n"
            "Just a quick update on your Q3 bookkeeping. We have completed all account "
            "reconciliations through September 30, 2026.\n\n"
            "Your financials are on track, and we don't anticipate any issues with "
            "your year-end tax planning.\n\n"
            "Please let us know if you have any questions.\n\n"
            "Best regards,\nRiverside Tax & Advisory Team"
        ),
        "created_at": ts(days_ago=7, hour=11, minute=33),
    },
    {
        "sender_role": "client",
        "sender_id": None,
        "body": "Thanks for the update! Appreciate the quick turnaround.",
        "created_at": ts(days_ago=7, hour=11, minute=42),
    },
    {
        "sender_role": "staff",
        "sender_id": USER_ID,
        "body": "You're welcome! Let us know if there's anything else we can help with.",
        "created_at": ts(days_ago=7, hour=11, minute=45),
    },
    {
        "sender_role": "client",
        "sender_id": None,
        "body": "One question -- I noticed the August invoice. Is that the final amount for the month?",
        "created_at": ts(days_ago=2, hour=14, minute=5),
    },
    {
        "sender_role": "staff",
        "sender_id": USER_ID,
        "body": (
            "Yes, that's the final amount for August. It covers the standard monthly "
            "bookkeeping plus the credit card reconciliation we completed for you.\n\n"
            "Let us know if you'd like a detailed breakdown."
        ),
        "created_at": ts(days_ago=2, hour=14, minute=31),
    },
]

def main():
    db = SessionLocal()
    try:
        existing = db.query(ClientMessage).filter(
            ClientMessage.client_id == CLIENT_ID,
            ClientMessage.firm_id == FIRM_ID,
        ).count()

        if existing > 0:
            # Check if staff sender is the correct real user
            wrong = db.query(ClientMessage).filter(
                ClientMessage.client_id == CLIENT_ID,
                ClientMessage.firm_id == FIRM_ID,
                ClientMessage.sender_role == "staff",
                ClientMessage.sender_id != USER_ID,
            ).count()
            if wrong == 0:
                print(f"Messages already exist with correct sender ({existing} rows) -- skipping.")
                return
            print(f"Found {existing} messages with wrong staff sender -- deleting and recreating.")
            db.query(ClientMessage).filter(
                ClientMessage.client_id == CLIENT_ID,
                ClientMessage.firm_id == FIRM_ID,
            ).delete()
            db.flush()

        print("=== Seeding demo messages ===")
        for data in MESSAGES:
            msg = ClientMessage(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                sender_id=data["sender_id"],
                sender_role=data["sender_role"],
                body=data["body"],
                created_at=data["created_at"],
            )
            db.add(msg)
            db.flush()
            print(f"  {data['sender_role']:6s}  {str(data['created_at'])[:16]}  {data['body'][:60]}")

        db.commit()
        print(f"\n  Committed {len(MESSAGES)} messages.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()