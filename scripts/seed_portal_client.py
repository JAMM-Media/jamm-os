# scripts/seed_portal_client.py
"""
Creates one client with portal access enabled under Riverside Tax & Advisory
(firm_id 185314c9-e702-4eab-8600-249848022206) for UI design / screenshot work.

The client has referral_source=None so the attribution survey notification
fires when the portal dashboard loads.

Login:
  Email:    portal-demo@jammpx.com
  Password: Portal2026!

Run from the project root:
    python scripts/seed_portal_client.py

Idempotent: if a client with this email already exists, prints its portal
access state and exits without writing.
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.firm import Firm
from app.services.portal_auth import hash_portal_password

FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
PORTAL_EMAIL = "portal-demo@jammpx.com"
PORTAL_PASSWORD = "Portal2026!"


def main() -> None:
    db = SessionLocal()
    try:
        firm = db.execute(select(Firm).where(Firm.id == FIRM_ID)).scalars().first()
        if not firm:
            print(f"ERROR: Firm {FIRM_ID} not found. Run seed.py first.")
            return

        existing = db.execute(
            select(Client).where(Client.email == PORTAL_EMAIL)
        ).scalars().first()
        if existing:
            print(f"Client already exists: {existing.email}")
            print(f"  portal_access_enabled: {existing.portal_access_enabled}")
            print(f"  referral_source:       {existing.referral_source}")
            return

        client = Client(
            firm_id=FIRM_ID,
            name="Demo Portal Client",
            email=PORTAL_EMAIL,
            referral_source=None,
            portal_password_hash=hash_portal_password(PORTAL_PASSWORD),
            portal_access_enabled=True,
        )
        db.add(client)
        db.commit()
        db.refresh(client)

        print(f"Created client: {client.email} (id: {client.id})")
        print(f"  firm:                  {firm.name}")
        print(f"  portal_access_enabled: {client.portal_access_enabled}")
        print(f"  referral_source:       {client.referral_source}")
        print()
        print("Portal login credentials:")
        print(f"  Email:    {PORTAL_EMAIL}")
        print(f"  Password: {PORTAL_PASSWORD}")
        print()
        print("Start both dev servers (backend + frontend), then navigate to /portal/login")
    finally:
        db.close()


if __name__ == "__main__":
    main()
