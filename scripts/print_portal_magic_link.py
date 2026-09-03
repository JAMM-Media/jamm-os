# scripts/print_portal_magic_link.py
"""
Generates a real portal magic link for the demo client and prints the raw URL,
so it can be opened directly in a browser without needing real email delivery.

Side effects when run:
  - Writes or updates a PortalSession row for the demo client (stores the token hash).
  - Fires a client.portal_invited behavioral log event in the database.
  - Attempts a Postmark email send -- this will fail silently in dev (exception is
    caught and logged inside generate_magic_link; the token is still valid).

The backend dev server does NOT need to be running; this script goes directly through
the service layer and database. The frontend dev server DOES need to be running
for the printed URL to be usable in a browser.

Run from the project root:
    python scripts/print_portal_magic_link.py
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.client import Client
from app.services.portal_magic_link import generate_magic_link

PORTAL_EMAIL = "portal-demo@jammpx.com"
EXPIRY_HOURS = 24


def main() -> None:
    settings = get_settings()
    db = SessionLocal()
    try:
        client = db.execute(
            select(Client).where(Client.email == PORTAL_EMAIL)
        ).scalars().first()
        if client is None:
            print(f"ERROR: Client {PORTAL_EMAIL} not found. Run scripts/seed_portal_client.py first.")
            return

        _, raw_token = generate_magic_link(
            client_id=client.id,
            firm_id=client.firm_id,
            expiry_hours=EXPIRY_HOURS,
            db=db,
        )

        url = f"{settings.FRONTEND_URL}/portal/auth?token={raw_token}"
        print(f"Magic link (expires in {EXPIRY_HOURS} hours):")
        print(url)
    finally:
        db.close()


if __name__ == "__main__":
    main()
