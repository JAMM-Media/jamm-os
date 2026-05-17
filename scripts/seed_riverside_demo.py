# scripts/seed_riverside_demo.py
"""
JAMM PX — Full Demo Seed Script
Firm: Riverside Tax & Advisory

Run with:  python -m scripts.seed_riverside_demo

Emails:
  andrew@jammpx.com   → firm_owner
  ben@jammpx.com      → manager
  ben@mail.jammpx.com → staff
  corby0917@gmail.com → portal (Sarah Chen)
"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import uuid
from datetime import datetime, date, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.services.portal_auth import hash_portal_password_bcrypt
from app.services.automation_presets import seed_firm_presets
from app.services.tax_organizer_service import seed_firm_organizer_templates

from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.document_request import DocumentRequest
from app.models.invoice import Invoice
from app.models.irs_authorization import IrsAuthorization
from app.models.extension import Extension
from app.models.message import ClientMessage
from app.models.note import Note
from app.models.firm_chat import Channel, FirmMessage
from app.models.time_entry import TimeEntry
from app.models.signature_envelope import SignatureEnvelope
from app.core.enums import (
    UserRole, InvoiceStatus, InvoiceDeliveryMethod
)

NOW = datetime.now(timezone.utc)
TODAY = date.today()

def d(days_offset: int) -> date:
    return TODAY + timedelta(days=days_offset)

def dt(days_offset: int) -> datetime:
    return NOW + timedelta(days=days_offset)


def run():
    db: Session = SessionLocal()
    try:
        existing = db.query(User).filter_by(email="andrew@jammpx.com").first()
        if existing:
            print("Demo firm already exists. Delete firm 'Riverside Tax & Advisory' to re-seed.")
            return

        print("Creating Riverside Tax & Advisory demo firm...")

        firm = Firm(
            id=uuid.uuid4(),
            name="Riverside Tax & Advisory",
        )
        db.add(firm)
        db.flush()
        fid = firm.id
        print(f"  Firm ID: {fid}")

        owner = User(
            id=uuid.uuid4(),
            firm_id=fid,
            email="andrew@jammpx.com",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Andrew Corby",
            role=UserRole.firm_owner,
            is_active=True,
        )
        manager = User(
            id=uuid.uuid4(),
            firm_id=fid,
            email="ben@jammpx.com",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Ben Carter",
            role=UserRole.manager,
            is_active=True,
        )
        staff = User(
            id=uuid.uuid4(),
            firm_id=fid,
            email="ben@mail.jammpx.com",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Ben Carter (Staff)",
            role=UserRole.staff,
            is_active=True,
        )
        db.add_all([owner, manager, staff])
        db.flush()
        print(f"  Users: owner={owner.id}, manager={manager.id}, staff={staff.id}")

        seed_firm_presets(firm_id=fid, db=db)
        seed_firm_organizer_templates(firm_id=fid, db=db)
        print("  Automation presets and organizer templates seeded")

        ch_general = Channel(id=uuid.uuid4(), firm_id=fid, name="general", created_by=owner.id)
        ch_tax = Channel(id=uuid.uuid4(), firm_id=fid, name="tax-season-2025", created_by=owner.id)
        ch_ops = Channel(id=uuid.uuid4(), firm_id=fid, name="operations", created_by=owner.id)
        db.add_all([ch_general, ch_tax, ch_ops])
        db.flush()

        chat_msgs = [
            FirmMessage(id=uuid.uuid4(), firm_id=fid, channel_id=ch_general.id,
                sender_id=owner.id, body="Good morning team — big week ahead. Chen return is filed, let's get Martinez caught up.",
                created_at=dt(-3)),
            FirmMessage(id=uuid.uuid4(), firm_id=fid, channel_id=ch_general.id,
                sender_id=manager.id, body="On it. I'll reach out to Martinez today about the missing bank statements.",
                created_at=dt(-3) + timedelta(minutes=8)),
            FirmMessage(id=uuid.uuid4(), firm_id=fid, channel_id=ch_tax.id,
                sender_id=staff.id, body="Kowalski extension is filed and confirmed. Updated the engagement deadline in JAMM.",
                created_at=dt(-5)),
            FirmMessage(id=uuid.uuid4(), firm_id=fid, channel_id=ch_tax.id,
                sender_id=owner.id, body="Good. Okonkwo 8821 is expiring in 12 days — @Ben please send them the renewal request today.",
                created_at=dt(-5) + timedelta(minutes=15)),
            FirmMessage(id=uuid.uuid4(), firm_id=fid, channel_id=ch_ops.id,
                sender_id=manager.id, body="Hammond Estate is flagged at risk. IRS auth expired, no portal activity. Should we reach out directly?",
                created_at=dt(-1)),
            FirmMessage(id=uuid.uuid4(), firm_id=fid, channel_id=ch_ops.id,
                sender_id=owner.id, body="Yes — I'll call them. Their 706 deadline is approaching and we can't pull transcripts without the 2848 renewed.",
                created_at=dt(-1) + timedelta(minutes=4)),
        ]
        db.add_all(chat_msgs)

        # ── CLIENT 1: Sarah Chen ─────────────────────────────────────────────
        chen = Client(
            id=uuid.uuid4(), firm_id=fid,
            name="Sarah Chen", email="corby0917@gmail.com",
            phone="(512) 555-0841",
            entity_type="individual",
            address_line1="412 Maple Street", city="Austin", state="TX", postal_code="78701",
            tags="individual,priority",
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password_bcrypt("PortalDemo2026!"),
            portal_last_login_at=dt(-2),
        )
        db.add(chen)
        db.flush()

        eng_chen = Engagement(
            id=uuid.uuid4(), firm_id=fid, client_id=chen.id,
            name="2024 Individual Tax Return — Form 1040",
            engagement_type="tax_return_1040",
            status="completed",
            filing_deadline=date(2025, 4, 15),
            start_date=d(-90), end_date=d(-36),
            notes="Straightforward W-2 income. Single filer. Refund of $2,841 confirmed.",
        )
        db.add(eng_chen)
        db.flush()

        chen_tasks = [
            Task(id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
                title="Collect W-2 and prior year return", status="done", is_completed=True,
                assigned_to=staff.id, due_date=d(-75)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
                title="Prepare Form 1040", status="done", is_completed=True,
                assigned_to=staff.id, due_date=d(-50)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
                title="Partner review", status="done", is_completed=True,
                assigned_to=owner.id, due_date=d(-40)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
                title="E-file and confirm acceptance", status="done", is_completed=True,
                assigned_to=staff.id, due_date=d(-36)),
        ]
        db.add_all(chen_tasks)

        db.add(DocumentRequest(
            id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
            title="2024 Tax Documents — Sarah Chen",
            status="complete", due_date=d(-70), completed_at=dt(-72),
            checklist_items=[
                {"id": str(uuid.uuid4()), "label": "2024 W-2 (Meridian Financial Group)", "description": "Your W-2 from your primary employer.", "is_required": True, "status": "approved"},
                {"id": str(uuid.uuid4()), "label": "Prior year tax return (2023)", "description": "Page 1 of your 2023 Form 1040.", "is_required": True, "status": "approved"},
                {"id": str(uuid.uuid4()), "label": "Bank interest statements (1099-INT)", "description": "Any 1099-INT from your bank accounts.", "is_required": False, "status": "approved"},
            ]
        ))

        db.add(IrsAuthorization(
            id=uuid.uuid4(), firm_id=fid, client_id=chen.id,
            form_type="8821", status="active",
            tax_years=[2022, 2023, 2024],
            valid_from=date(2024, 1, 15), valid_until=d(548),
            expiry_notification_sent=False,
        ))

        db.add(Invoice(
            id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
            invoice_number="RTA-2025-001",
            line_items=[{"description": "2024 Form 1040 Preparation", "quantity": 1, "unit_price": 1200.00, "amount": 1200.00}],
            subtotal=1200.00, tax_rate=0.0, tax_amount=0.0, total_amount=1200.00,
            status=InvoiceStatus.paid, due_date=d(-30), sent_at=dt(-38), paid_at=dt(-35),
            delivery_method=InvoiceDeliveryMethod.portal, created_by=owner.id,
        ))

        db.add(Invoice(
            id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
            invoice_number="RTA-2025-008",
            line_items=[
                {"description": "2024 Tax Planning Advisory — Q2", "quantity": 1, "unit_price": 450.00, "amount": 450.00},
                {"description": "IRS Correspondence Assistance", "quantity": 1, "unit_price": 200.00, "amount": 200.00},
            ],
            subtotal=650.00, tax_rate=0.0, tax_amount=0.0, total_amount=650.00,
            status=InvoiceStatus.sent, due_date=d(14), sent_at=dt(-3),
            delivery_method=InvoiceDeliveryMethod.portal, created_by=owner.id,
            notes_client_visible="Thank you for your continued business, Sarah. Please pay at your convenience by the due date.",
        ))

        db.add_all([
            TimeEntry(id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
                user_id=staff.id, hours=3.5, hourly_rate=150.0, is_billable=True, is_billed=True,
                description="Document review and data entry", date=d(-80)),
            TimeEntry(id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
                user_id=staff.id, hours=4.0, hourly_rate=150.0, is_billable=True, is_billed=True,
                description="Return preparation", date=d(-60)),
            TimeEntry(id=uuid.uuid4(), firm_id=fid, client_id=chen.id, engagement_id=eng_chen.id,
                user_id=owner.id, hours=1.0, hourly_rate=250.0, is_billable=True, is_billed=True,
                description="Partner review and sign-off", date=d(-40)),
        ])

        db.add_all([
            ClientMessage(id=uuid.uuid4(), firm_id=fid, client_id=chen.id,
                sender_type="staff", sender_id=owner.id,
                body="Hi Sarah — your 2024 return is complete and has been e-filed. You should see a refund of approximately $2,841 within 21 days. Please let us know if you have any questions!",
                created_at=dt(-36)),
            ClientMessage(id=uuid.uuid4(), firm_id=fid, client_id=chen.id,
                sender_type="client",
                body="Thank you so much! That's great news. Will do.",
                created_at=dt(-35)),
        ])

        db.add(Note(
            id=uuid.uuid4(), firm_id=fid, client_id=chen.id, author_id=owner.id,
            body="Sarah is a great client — always responsive and documents come in on time. Potential for advisory work Q3.",
            is_private=False, created_at=dt(-30),
        ))

        # ── CLIENT 2: Martinez Consulting LLC ───────────────────────────────
        martinez = Client(
            id=uuid.uuid4(), firm_id=fid,
            name="Martinez Consulting LLC", email="martinez.taxdemo@gmail.com",
            phone="(512) 555-0374",
            entity_type="business", company_name="Martinez Consulting LLC",
            address_line1="7710 Rialto Blvd, Suite 120", city="Austin", state="TX", postal_code="78735",
            tags="business,overdue,needs-attention",
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password_bcrypt("PortalDemo2026!"),
            portal_last_login_at=None,
        )
        db.add(martinez)
        db.flush()

        eng_martinez = Engagement(
            id=uuid.uuid4(), firm_id=fid, client_id=martinez.id,
            name="2024 S-Corporation Return — Form 1120-S",
            engagement_type="tax_return_1120s",
            status="active",
            filing_deadline=date(2025, 3, 15),
            start_date=d(-120),
            notes="Missing bank statements and receipts. Carlos has been slow to respond. Follow up urgently.",
        )
        db.add(eng_martinez)
        db.flush()

        db.add_all([
            Task(id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, engagement_id=eng_martinez.id,
                title="Send document request — bank statements", status="done", is_completed=True,
                assigned_to=staff.id, due_date=d(-100)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, engagement_id=eng_martinez.id,
                title="Follow up on missing Q4 receipts", status="in_progress", is_completed=False,
                assigned_to=manager.id, due_date=d(-10)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, engagement_id=eng_martinez.id,
                title="Prepare 1120-S once all documents received", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(7)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, engagement_id=eng_martinez.id,
                title="URGENT: Call Carlos — 45 days past deadline", status="todo", is_completed=False,
                assigned_to=owner.id, due_date=d(-5)),
        ])

        db.add_all([
            DocumentRequest(
                id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, engagement_id=eng_martinez.id,
                title="2024 Business Documents — Bank Statements",
                status="partial", due_date=d(-60), reminder_count=3, last_reminder_sent_at=dt(-7),
                checklist_items=[
                    {"id": str(uuid.uuid4()), "label": "January 2024 business bank statement", "description": "Full statement for your primary business checking account.", "is_required": True, "status": "uploaded"},
                    {"id": str(uuid.uuid4()), "label": "February 2024 business bank statement", "description": "Full statement for your primary business checking account.", "is_required": True, "status": "pending"},
                    {"id": str(uuid.uuid4()), "label": "March 2024 business bank statement", "description": "Full statement for your primary business checking account.", "is_required": True, "status": "pending"},
                    {"id": str(uuid.uuid4()), "label": "Q1 payroll summary", "description": "Payroll summary for Jan–Mar 2024.", "is_required": True, "status": "pending"},
                ]
            ),
            DocumentRequest(
                id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, engagement_id=eng_martinez.id,
                title="2024 Business Expenses — Receipts & Records",
                status="pending", due_date=d(-45), reminder_count=2, last_reminder_sent_at=dt(-14),
                checklist_items=[
                    {"id": str(uuid.uuid4()), "label": "Vehicle mileage log 2024", "description": "Full year mileage log or odometer records.", "is_required": True, "status": "pending"},
                    {"id": str(uuid.uuid4()), "label": "Home office documentation", "description": "Square footage records and utility bills if claiming home office.", "is_required": False, "status": "pending"},
                    {"id": str(uuid.uuid4()), "label": "Equipment purchases over $2,500", "description": "Receipts for any equipment or asset purchases.", "is_required": True, "status": "pending"},
                ]
            ),
        ])

        db.add(Invoice(
            id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, engagement_id=eng_martinez.id,
            invoice_number="RTA-2025-002",
            line_items=[{"description": "2024 Form 1120-S Preparation (retainer)", "quantity": 1, "unit_price": 1400.00, "amount": 1400.00}],
            subtotal=1400.00, tax_rate=0.0, tax_amount=0.0, total_amount=1400.00,
            status=InvoiceStatus.overdue, due_date=d(-45), sent_at=dt(-52),
            delivery_method=InvoiceDeliveryMethod.portal, created_by=owner.id,
        ))

        db.add_all([
            Note(id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, author_id=manager.id,
                body="Left voicemail 3x this week. Carlos mentioned he's traveling. Expected documents by end of next week.",
                is_private=False, created_at=dt(-7)),
            Note(id=uuid.uuid4(), firm_id=fid, client_id=martinez.id, author_id=owner.id,
                body="PRIVATE: Consider whether we continue engagement if invoice not paid by June 1.",
                is_private=True, created_at=dt(-3)),
        ])

        # ── CLIENT 3: Kowalski Family Trust ─────────────────────────────────
        kowalski = Client(
            id=uuid.uuid4(), firm_id=fid,
            name="Kowalski Family Trust", email="kowalski.taxdemo@gmail.com",
            phone="(512) 555-0529",
            entity_type="trust", company_name="Kowalski Family Trust",
            address_line1="5501 Balcones Dr", city="Austin", state="TX", postal_code="78731",
            tags="trust,extension-filed",
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password_bcrypt("PortalDemo2026!"),
            portal_last_login_at=dt(-14),
        )
        db.add(kowalski)
        db.flush()

        eng_kowalski = Engagement(
            id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id,
            name="2024 Trust Income Tax Return — Form 1041",
            engagement_type="tax_return_1041",
            status="active",
            filing_deadline=date(2025, 4, 15),
            extended_deadline=date(2025, 9, 30),
            start_date=d(-100),
            notes="Extension filed April 12. Trustee is Margaret Kowalski. Waiting on K-1s from three partnership interests.",
        )
        db.add(eng_kowalski)
        db.flush()

        db.add_all([
            Task(id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id, engagement_id=eng_kowalski.id,
                title="File Form 8868 extension", status="done", is_completed=True,
                assigned_to=manager.id, due_date=d(-33)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id, engagement_id=eng_kowalski.id,
                title="Collect K-1s from Kowalski partnership interests", status="in_progress", is_completed=False,
                assigned_to=staff.id, due_date=d(30)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id, engagement_id=eng_kowalski.id,
                title="Prepare Form 1041 once K-1s received", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(60)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id, engagement_id=eng_kowalski.id,
                title="Partner review and e-file", status="todo", is_completed=False,
                assigned_to=owner.id, due_date=d(100)),
        ])

        db.add(Extension(
            id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id, engagement_id=eng_kowalski.id,
            form_type="8868", filed_at=d(-33),
            extended_deadline=date(2025, 9, 30), status="filed",
            notes="Extension accepted. Waiting on K-1s from three pass-through entities.",
        ))

        db.add(DocumentRequest(
            id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id, engagement_id=eng_kowalski.id,
            title="2024 Trust Documents — K-1s and Investment Statements",
            status="pending", due_date=d(20),
            checklist_items=[
                {"id": str(uuid.uuid4()), "label": "K-1 — Cedar Creek Partners LP", "description": "Schedule K-1 from Cedar Creek Partners LP.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "K-1 — Barton Springs Holdings LLC", "description": "Schedule K-1 from Barton Springs Holdings LLC.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "1099-DIV — Fidelity trust account", "description": "Dividend and distribution statements.", "is_required": True, "status": "uploaded"},
                {"id": str(uuid.uuid4()), "label": "Trust agreement (if amended in 2024)", "description": "Only needed if trust was modified during the year.", "is_required": False, "status": "pending"},
            ]
        ))

        db.add(Invoice(
            id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id, engagement_id=eng_kowalski.id,
            invoice_number="RTA-2025-003",
            line_items=[{"description": "2024 Form 1041 Preparation (retainer — 50%)", "quantity": 1, "unit_price": 1100.00, "amount": 1100.00}],
            subtotal=1100.00, tax_rate=0.0, tax_amount=0.0, total_amount=1100.00,
            status=InvoiceStatus.paid, due_date=d(-20), sent_at=dt(-28), paid_at=dt(-21),
            delivery_method=InvoiceDeliveryMethod.portal, created_by=owner.id,
        ))

        db.add(IrsAuthorization(
            id=uuid.uuid4(), firm_id=fid, client_id=kowalski.id,
            form_type="8821", status="active",
            tax_years=[2023, 2024],
            valid_from=date(2024, 3, 1), valid_until=d(400),
        ))

        # ── CLIENT 4: Okonkwo & Associates ──────────────────────────────────
        okonkwo = Client(
            id=uuid.uuid4(), firm_id=fid,
            name="Okonkwo & Associates LLC", email="okonkwo.taxdemo@gmail.com",
            phone="(512) 555-0618",
            entity_type="business", company_name="Okonkwo & Associates LLC",
            address_line1="2200 E 6th St, Suite 315", city="Austin", state="TX", postal_code="78702",
            tags="business,irs-auth-expiring",
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password_bcrypt("PortalDemo2026!"),
            portal_last_login_at=dt(-7),
        )
        db.add(okonkwo)
        db.flush()

        eng_okonkwo = Engagement(
            id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id,
            name="2024 S-Corporation Return — Form 1120-S",
            engagement_type="tax_return_1120s",
            status="in_review",
            filing_deadline=date(2025, 3, 15),
            extended_deadline=date(2025, 9, 15),
            start_date=d(-90),
            notes="Return nearly complete. IRS auth must be renewed before we can pull final transcripts.",
        )
        db.add(eng_okonkwo)
        db.flush()

        db.add(Extension(
            id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id, engagement_id=eng_okonkwo.id,
            form_type="7004", filed_at=d(-58),
            extended_deadline=date(2025, 9, 15), status="filed",
        ))

        db.add(IrsAuthorization(
            id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id,
            form_type="8821", status="active",
            tax_years=[2022, 2023, 2024],
            valid_from=date(2024, 5, 20), valid_until=d(12),
            expiry_notification_sent=True,
        ))

        db.add_all([
            Task(id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id, engagement_id=eng_okonkwo.id,
                title="URGENT: Renew Form 8821 before expiry (12 days)", status="in_progress", is_completed=False,
                assigned_to=manager.id, due_date=d(10)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id, engagement_id=eng_okonkwo.id,
                title="Pull IRS transcripts once auth renewed", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(20)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id, engagement_id=eng_okonkwo.id,
                title="Final review and e-file 1120-S", status="todo", is_completed=False,
                assigned_to=owner.id, due_date=d(40)),
        ])

        db.add(DocumentRequest(
            id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id, engagement_id=eng_okonkwo.id,
            title="2024 S-Corp Documents — Completed",
            status="complete", due_date=d(-50), completed_at=dt(-55),
            checklist_items=[
                {"id": str(uuid.uuid4()), "label": "2024 profit & loss statement", "description": "Full year P&L.", "is_required": True, "status": "approved"},
                {"id": str(uuid.uuid4()), "label": "2024 balance sheet", "description": "Year-end balance sheet.", "is_required": True, "status": "approved"},
                {"id": str(uuid.uuid4()), "label": "Officer W-2s", "description": "W-2 for all officers.", "is_required": True, "status": "approved"},
            ]
        ))

        db.add(Invoice(
            id=uuid.uuid4(), firm_id=fid, client_id=okonkwo.id, engagement_id=eng_okonkwo.id,
            invoice_number="RTA-2025-004",
            line_items=[{"description": "2024 Form 1120-S Preparation", "quantity": 1, "unit_price": 2400.00, "amount": 2400.00}],
            subtotal=2400.00, tax_rate=0.0, tax_amount=0.0, total_amount=2400.00,
            status=InvoiceStatus.sent, due_date=d(7), sent_at=dt(-5),
            delivery_method=InvoiceDeliveryMethod.portal, created_by=owner.id,
        ))

        # ── CLIENT 5: Patel Family ───────────────────────────────────────────
        patel = Client(
            id=uuid.uuid4(), firm_id=fid,
            name="Patel Family", email="patel.taxdemo@gmail.com",
            phone="(512) 555-0783",
            entity_type="individual",
            address_line1="229 Barton Springs Rd", city="Austin", state="TX", postal_code="78704",
            tags="individual,new-client",
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password_bcrypt("PortalDemo2026!"),
            portal_last_login_at=dt(-1),
        )
        db.add(patel)
        db.flush()

        eng_patel = Engagement(
            id=uuid.uuid4(), firm_id=fid, client_id=patel.id,
            name="2024 Individual Tax Return — Form 1040",
            engagement_type="tax_return_1040",
            status="active",
            filing_deadline=date(2025, 10, 15),
            extended_deadline=date(2025, 10, 15),
            start_date=d(-14),
            notes="New client referral from Sarah Chen. Self-employed consultant plus W-2 spouse. First year with us.",
        )
        db.add(eng_patel)
        db.flush()

        db.add_all([
            Task(id=uuid.uuid4(), firm_id=fid, client_id=patel.id, engagement_id=eng_patel.id,
                title="Send tax organizer and document request", status="done", is_completed=True,
                assigned_to=staff.id, due_date=d(-10)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=patel.id, engagement_id=eng_patel.id,
                title="Send engagement letter for signature", status="done", is_completed=True,
                assigned_to=staff.id, due_date=d(-10)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=patel.id, engagement_id=eng_patel.id,
                title="Review documents once received", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(30)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=patel.id, engagement_id=eng_patel.id,
                title="Prepare 1040 — self-employment schedule + W-2", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(90)),
        ])

        db.add(DocumentRequest(
            id=uuid.uuid4(), firm_id=fid, client_id=patel.id, engagement_id=eng_patel.id,
            title="2024 Tax Documents — Patel Family",
            status="pending", due_date=d(21), reminder_count=1, last_reminder_sent_at=dt(-2),
            checklist_items=[
                {"id": str(uuid.uuid4()), "label": "2024 W-2 (Raj — Lakeside Technology)", "description": "W-2 from your employer.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "1099-NEC — consulting income", "description": "1099-NEC from any consulting clients.", "is_required": True, "status": "uploaded"},
                {"id": str(uuid.uuid4()), "label": "Spouse W-2 (Priya — Austin ISD)", "description": "Your spouse's W-2.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "Schedule C expense records", "description": "Business expenses for consulting activity.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "Prior year return (2023)", "description": "Copy of 2023 Form 1040.", "is_required": True, "status": "pending"},
            ]
        ))

        db.add(IrsAuthorization(
            id=uuid.uuid4(), firm_id=fid, client_id=patel.id,
            form_type="8821", status="pending_signature",
            tax_years=[2024], valid_from=None, valid_until=None,
        ))

        db.add(ClientMessage(
            id=uuid.uuid4(), firm_id=fid, client_id=patel.id,
            sender_type="staff", sender_id=staff.id,
            body="Hi Raj and Priya! Welcome to Riverside Tax & Advisory. I've sent over your tax organizer and document checklist through the portal. Please upload your documents when you have a chance — we'll be in touch once we've had a chance to review everything.",
            created_at=dt(-14),
        ))

        # ── CLIENT 6: Rivera Consulting Group ───────────────────────────────
        rivera = Client(
            id=uuid.uuid4(), firm_id=fid,
            name="Rivera Consulting Group LLC", email="rivera.taxdemo@gmail.com",
            phone="(512) 555-0447",
            entity_type="business", company_name="Rivera Consulting Group LLC",
            address_line1="7710 Rialto Blvd, Suite 120", city="Austin", state="TX", postal_code="78735",
            tags="business,esign-pending",
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password_bcrypt("PortalDemo2026!"),
            portal_last_login_at=dt(-4),
        )
        db.add(rivera)
        db.flush()

        eng_rivera = Engagement(
            id=uuid.uuid4(), firm_id=fid, client_id=rivera.id,
            name="2024 Partnership Return — Form 1065",
            engagement_type="tax_return_1065",
            status="active",
            filing_deadline=date(2025, 9, 15),
            extended_deadline=date(2025, 9, 15),
            start_date=d(-21),
            notes="Engagement letter sent. Waiting on signature. Three partners — K-1s needed for all.",
        )
        db.add(eng_rivera)
        db.flush()

        db.add(SignatureEnvelope(
            id=uuid.uuid4(), firm_id=fid, client_id=rivera.id, engagement_id=eng_rivera.id,
            provider="dropbox_sign",
            provider_envelope_id="ds-env-2025-rivera-001",
            status="sent",
            subject="Engagement Letter — Rivera Consulting Group 2024 Form 1065",
            message="Please review and sign the attached engagement letter to authorize us to prepare your 2024 partnership return.",
            signers=[{"name": "Carlos Rivera", "email": "rivera.taxdemo@gmail.com", "status": "pending", "signed_at": None}],
            sent_at=dt(-7), expires_at=dt(21),
            reminder_count=1, last_reminder_sent_at=dt(-3),
        ))

        db.add_all([
            Task(id=uuid.uuid4(), firm_id=fid, client_id=rivera.id, engagement_id=eng_rivera.id,
                title="Send engagement letter for signature", status="done", is_completed=True,
                assigned_to=staff.id, due_date=d(-14)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=rivera.id, engagement_id=eng_rivera.id,
                title="Follow up on unsigned engagement letter", status="in_progress", is_completed=False,
                assigned_to=manager.id, due_date=d(3)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=rivera.id, engagement_id=eng_rivera.id,
                title="Send document request once letter signed", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(10)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=rivera.id, engagement_id=eng_rivera.id,
                title="Prepare Form 1065 and three K-1s", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(75)),
        ])

        db.add(Invoice(
            id=uuid.uuid4(), firm_id=fid, client_id=rivera.id, engagement_id=eng_rivera.id,
            invoice_number="RTA-2025-005",
            line_items=[{"description": "2024 Form 1065 Preparation — 50% retainer", "quantity": 1, "unit_price": 1400.00, "amount": 1400.00}],
            subtotal=1400.00, tax_rate=0.0, tax_amount=0.0, total_amount=1400.00,
            status=InvoiceStatus.sent, due_date=d(7), sent_at=dt(-7),
            delivery_method=InvoiceDeliveryMethod.portal, created_by=owner.id,
        ))

        db.add(IrsAuthorization(
            id=uuid.uuid4(), firm_id=fid, client_id=rivera.id,
            form_type="2848", status="active",
            tax_years=[2023, 2024],
            valid_from=date(2024, 6, 1), valid_until=d(365),
        ))

        # ── CLIENT 7: Hammond Family Estate ─────────────────────────────────
        hammond = Client(
            id=uuid.uuid4(), firm_id=fid,
            name="Hammond Family Estate", email="hammond.taxdemo@gmail.com",
            phone="(512) 555-0921",
            entity_type="estate", company_name="Hammond Family Estate",
            address_line1="109 West 38th St", city="Austin", state="TX", postal_code="78705",
            tags="estate,at-risk,irs-auth-expired",
            portal_access_enabled=True,
            portal_password_hash=hash_portal_password_bcrypt("PortalDemo2026!"),
            portal_last_login_at=None,
        )
        db.add(hammond)
        db.flush()

        eng_hammond = Engagement(
            id=uuid.uuid4(), firm_id=fid, client_id=hammond.id,
            name="Estate Tax Return — Form 706",
            engagement_type="tax_return_706",
            status="active",
            filing_deadline=date(2025, 1, 15),
            start_date=d(-180),
            notes="Estate of Robert Hammond. Date of death April 2022. 706 is overdue. IRS auth expired. Executor is Margaret Hammond.",
        )
        db.add(eng_hammond)
        db.flush()

        db.add_all([
            Task(id=uuid.uuid4(), firm_id=fid, client_id=hammond.id, engagement_id=eng_hammond.id,
                title="Renew Form 2848 — Power of Attorney (EXPIRED)", status="todo", is_completed=False,
                assigned_to=manager.id, due_date=d(-30)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=hammond.id, engagement_id=eng_hammond.id,
                title="Contact executor — Margaret Hammond — re: overdue 706", status="in_progress", is_completed=False,
                assigned_to=owner.id, due_date=d(-20)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=hammond.id, engagement_id=eng_hammond.id,
                title="Collect estate inventory and asset valuations", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(30)),
            Task(id=uuid.uuid4(), firm_id=fid, client_id=hammond.id, engagement_id=eng_hammond.id,
                title="Prepare Form 706", status="todo", is_completed=False,
                assigned_to=staff.id, due_date=d(60)),
        ])

        db.add(IrsAuthorization(
            id=uuid.uuid4(), firm_id=fid, client_id=hammond.id,
            form_type="2848", status="expired",
            tax_years=[2022],
            valid_from=date(2023, 3, 15), valid_until=date(2025, 3, 15),
            expiry_notification_sent=True,
        ))

        db.add(DocumentRequest(
            id=uuid.uuid4(), firm_id=fid, client_id=hammond.id, engagement_id=eng_hammond.id,
            title="Estate Documents — Asset Inventory and Valuations",
            status="pending", due_date=d(-60), reminder_count=4, last_reminder_sent_at=dt(-21),
            checklist_items=[
                {"id": str(uuid.uuid4()), "label": "Real property appraisals", "description": "Appraisals for all real estate in the estate.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "Investment account statements (date of death)", "description": "All brokerage and retirement account statements as of date of death.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "Business interest valuations", "description": "Professional valuation of any business interests held.", "is_required": True, "status": "pending"},
                {"id": str(uuid.uuid4()), "label": "Life insurance policies", "description": "All life insurance policies naming the estate as beneficiary.", "is_required": True, "status": "pending"},
            ]
        ))

        db.add(Invoice(
            id=uuid.uuid4(), firm_id=fid, client_id=hammond.id, engagement_id=eng_hammond.id,
            invoice_number="RTA-2025-006",
            line_items=[{"description": "Form 706 Estate Tax Return — retainer", "quantity": 1, "unit_price": 2800.00, "amount": 2800.00}],
            subtotal=2800.00, tax_rate=0.0, tax_amount=0.0, total_amount=2800.00,
            status=InvoiceStatus.overdue, due_date=d(-90), sent_at=dt(-100),
            delivery_method=InvoiceDeliveryMethod.portal, created_by=owner.id,
        ))

        db.add(Note(
            id=uuid.uuid4(), firm_id=fid, client_id=hammond.id, author_id=owner.id,
            body="PRIVATE: Relationship at serious risk. Two overdue invoices, expired auth, zero portal engagement. Consider sending formal notice.",
            is_private=True, created_at=dt(-7),
        ))

        db.commit()
        print("")
        print("=" * 60)
        print("SEED COMPLETE — Riverside Tax & Advisory")
        print("=" * 60)
        print("")
        print("STAFF LOGINS:")
        print("  Firm Owner : andrew@jammpx.com   / Demo2026!")
        print("  Manager    : ben@jammpx.com       / Demo2026!")
        print("  Staff      : ben@mail.jammpx.com  / Demo2026!")
        print("")
        print("CLIENT PORTAL:")
        print("  Sarah Chen : corby0917@gmail.com  / PortalDemo2026!")
        print("  All others : *@gmail.com           / PortalDemo2026!")
        print("")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run()
