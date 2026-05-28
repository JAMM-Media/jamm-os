import uuid
import sys
import os
from datetime import date, datetime, timezone, timedelta, time as time_type
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.core.security import get_password_hash
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.contact import Contact
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.document_request import DocumentRequest
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.irs_authorization import IrsAuthorization
from app.models.note import Note
from app.models.notification import Notification
from app.models.qc_checklist import QcChecklistTemplate
from app.services.automation_presets import seed_firm_presets
from app.services.tax_organizer_service import seed_firm_organizer_templates
from app.core.enums import (
    UserRole, NotificationType, RecipientType, InvoiceStatus
)

try:
    from app.core.enums import InvoiceDeliveryMethod
    _DELIVERY_PORTAL = InvoiceDeliveryMethod.portal
except (ImportError, AttributeError):
    _DELIVERY_PORTAL = "portal"


def main():
    db = SessionLocal()

    try:
        # STEP 0 — Idempotency
        existing = db.execute(
            select(Firm).where(Firm.name == "Riverside Tax & Advisory")
        ).scalars().first()
        if existing:
            db.delete(existing)
            db.commit()
            print("Cleared existing Riverside Tax & Advisory data.")

        now = datetime.now(timezone.utc)
        today = date.today()

        # STEP 1 — Firm and Staff Users
        firm = Firm(
            name="Riverside Tax & Advisory",
            slug="riverside-tax-advisory",
        )
        db.add(firm)
        db.commit()
        db.refresh(firm)
        firm_id = firm.id

        alex = User(
            firm_id=firm_id,
            email="admin@demofirm.com",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Alex Mercer",
            role=UserRole.firm_owner,
            is_active=True,
        )
        jordan = User(
            firm_id=firm_id,
            email="jordan@demofirm.com",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Jordan Reeves",
            role=UserRole.manager,
            is_active=True,
        )
        taylor = User(
            firm_id=firm_id,
            email="taylor@demofirm.com",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Taylor Kim",
            role=UserRole.staff,
            is_active=True,
        )
        casey = User(
            firm_id=firm_id,
            email="casey@demofirm.com",
            hashed_password=get_password_hash("Demo2026!"),
            full_name="Casey O'Brien",
            role=UserRole.staff,
            is_active=True,
        )
        db.add_all([alex, jordan, taylor, casey])
        db.commit()
        db.refresh(alex)
        db.refresh(jordan)
        db.refresh(taylor)
        db.refresh(casey)

        seed_firm_presets(firm_id=firm_id, db=db)
        seed_firm_organizer_templates(firm_id=firm_id, db=db)
        print("Created firm and 4 staff users.")

        # STEP 2 — Clients
        portal_pw = get_password_hash("PortalDemo2026!")

        sarah_chen = Client(
            firm_id=firm_id,
            name="Sarah Chen",
            email="corby0917@gmail.com",
            entity_type="individual",
            phone="(617) 555-0142",
            tags="vip,long-term",
            is_active=True,
            portal_access_enabled=True,
            portal_password_hash=portal_pw,
            portal_last_login_at=now - timedelta(days=3),
            address_line1="142 Beacon St",
            city="Boston",
            state="MA",
            postal_code="02108",
        )
        marcus_rivera = Client(
            firm_id=firm_id,
            name="Marcus Rivera",
            email="marcus.rivera@demofirm.com",
            entity_type="individual",
            phone="(312) 555-0289",
            tags="new-client",
            is_active=True,
            portal_access_enabled=True,
            portal_password_hash=portal_pw,
            portal_last_login_at=now - timedelta(days=10),
            address_line1="289 N Michigan Ave",
            city="Chicago",
            state="IL",
            postal_code="60601",
        )
        blue_ridge = Client(
            firm_id=firm_id,
            name="Blue Ridge Contracting LLC",
            email="bluridge@demofirm.com",
            entity_type="business",
            company_name="Blue Ridge Contracting LLC",
            phone="(828) 555-0371",
            tags="construction",
            is_active=True,
            portal_access_enabled=True,
            portal_password_hash=portal_pw,
            portal_last_login_at=now - timedelta(days=1),
            address_line1="371 Blue Ridge Pkwy",
            city="Asheville",
            state="NC",
            postal_code="28801",
        )
        fernwood_trust = Client(
            firm_id=firm_id,
            name="Fernwood Family Trust",
            email="fernwood@demofirm.com",
            entity_type="trust",
            company_name="Fernwood Family Trust",
            phone="(415) 555-0483",
            tags="estate-planning",
            is_active=True,
            portal_access_enabled=True,
            portal_password_hash=portal_pw,
        )
        apex_staffing = Client(
            firm_id=firm_id,
            name="Apex Staffing Solutions",
            email="apex@demofirm.com",
            entity_type="business",
            company_name="Apex Staffing Solutions",
            phone="(212) 555-0517",
            tags="payroll,quarterly",
            is_active=True,
            portal_access_enabled=True,
            portal_password_hash=portal_pw,
        )
        robert_gallagher = Client(
            firm_id=firm_id,
            name="Robert Gallagher",
            email="robert.g@demofirm.com",
            entity_type="individual",
            phone="(617) 555-0621",
            is_active=True,
        )
        martinez_estate = Client(
            firm_id=firm_id,
            name="Martinez Family Estate",
            email="martinez@demofirm.com",
            entity_type="estate",
            company_name="Martinez Family Estate",
            phone="(305) 555-0734",
            is_active=True,
        )
        nguyen_consulting = Client(
            firm_id=firm_id,
            name="Nguyen Consulting Group",
            email="nguyen@demofirm.com",
            entity_type="business",
            company_name="Nguyen Consulting Group",
            phone="(408) 555-0856",
            is_active=False,
        )

        db.add_all([
            sarah_chen, marcus_rivera, blue_ridge, fernwood_trust,
            apex_staffing, robert_gallagher, martinez_estate, nguyen_consulting,
        ])
        db.commit()
        for c in [sarah_chen, marcus_rivera, blue_ridge, fernwood_trust,
                  apex_staffing, robert_gallagher, martinez_estate, nguyen_consulting]:
            db.refresh(c)
        print("Created 8 clients.")

        # STEP 3 — Contacts
        contact1 = Contact(
            firm_id=firm_id,
            client_id=sarah_chen.id,
            name="David Chen",
            email="david.chen@gmail.com",
            phone="(617) 555-0143",
        )
        contact2 = Contact(
            firm_id=firm_id,
            client_id=blue_ridge.id,
            name="Diana Krueger",
            email="diana@blueridgellc.com",
            phone="(828) 555-0372",
        )
        contact3 = Contact(
            firm_id=firm_id,
            client_id=fernwood_trust.id,
            name="Patricia Fernwood",
            email="patricia@fernwoodfamily.com",
            phone="(415) 555-0484",
        )
        db.add_all([contact1, contact2, contact3])
        db.commit()
        print("Created 3 contacts.")

        # STEP 4 — Engagements
        sarah_1040 = Engagement(
            firm_id=firm_id, client_id=sarah_chen.id,
            name="2024 Individual Tax Return",
            engagement_type="tax_return_1040",
            status="active",
            start_date=today - timedelta(days=60),
            filing_deadline=date(2025, 4, 15),
            notes="Client mentioned rental property income this year — need Schedule E. Also check K-1 from partnership interest.",
        )
        marcus_1040 = Engagement(
            firm_id=firm_id, client_id=marcus_rivera.id,
            name="2024 Individual Tax Return",
            engagement_type="tax_return_1040",
            status="in_review",
            start_date=today - timedelta(days=50),
            filing_deadline=date(2025, 4, 15),
            notes="Currently in review with Jordan. Waiting on brokerage statement from Fidelity.",
        )
        blue_ridge_1120 = Engagement(
            firm_id=firm_id, client_id=blue_ridge.id,
            name="2024 Corporate Tax Return",
            engagement_type="tax_return_1120",
            status="active",
            start_date=today - timedelta(days=55),
            filing_deadline=date(2025, 4, 15),
        )
        blue_ridge_payroll = Engagement(
            firm_id=firm_id, client_id=blue_ridge.id,
            name="2024 Payroll Tax — Q4",
            engagement_type="payroll_tax_941",
            status="completed",
            start_date=today - timedelta(days=90),
            filing_deadline=date(2025, 1, 31),
        )
        fernwood_1041 = Engagement(
            firm_id=firm_id, client_id=fernwood_trust.id,
            name="2024 Trust Tax Return",
            engagement_type="tax_return_1041",
            status="active",
            start_date=today - timedelta(days=45),
            filing_deadline=date(2025, 4, 15),
            extended_deadline=date(2025, 10, 15),
            notes="Extension filed automatically. Client trustee is Patricia — she responds same day via email.",
        )
        apex_scorp = Engagement(
            firm_id=firm_id, client_id=apex_staffing.id,
            name="2024 S-Corp Return",
            engagement_type="tax_return_1120s",
            status="in_review",
            start_date=today - timedelta(days=70),
            filing_deadline=date(2025, 3, 15),
        )
        apex_bookkeeping = Engagement(
            firm_id=firm_id, client_id=apex_staffing.id,
            name="Bookkeeping — March 2025",
            engagement_type="bookkeeping_monthly",
            status="active",
            start_date=today - timedelta(days=30),
        )
        robert_amended = Engagement(
            firm_id=firm_id, client_id=robert_gallagher.id,
            name="2023 Amended Return",
            engagement_type="amended_return_1040x",
            status="active",
            start_date=today - timedelta(days=25),
        )
        robert_advisory = Engagement(
            firm_id=firm_id, client_id=robert_gallagher.id,
            name="Tax Planning Advisory — 2025",
            engagement_type="tax_planning_advisory",
            status="active",
            start_date=today - timedelta(days=15),
        )
        martinez_706 = Engagement(
            firm_id=firm_id, client_id=martinez_estate.id,
            name="706 Estate Return",
            engagement_type="tax_return_706",
            status="active",
            start_date=today - timedelta(days=80),
            filing_deadline=date(2025, 10, 15),
        )
        sarah_extension = Engagement(
            firm_id=firm_id, client_id=sarah_chen.id,
            name="Extension Filing — 4868",
            engagement_type="extension_4868",
            status="completed",
            start_date=today - timedelta(days=20),
            filing_deadline=date(2025, 4, 15),
            extended_deadline=date(2025, 10, 15),
        )
        nguyen_1065 = Engagement(
            firm_id=firm_id, client_id=nguyen_consulting.id,
            name="2024 Partnership Return",
            engagement_type="tax_return_1065",
            status="archived",
            start_date=today - timedelta(days=120),
            filing_deadline=date(2025, 3, 15),
            is_active=False,
        )

        db.add_all([
            sarah_1040, marcus_1040, blue_ridge_1120, blue_ridge_payroll,
            fernwood_1041, apex_scorp, apex_bookkeeping, robert_amended,
            robert_advisory, martinez_706, sarah_extension, nguyen_1065,
        ])
        db.commit()
        for e in [sarah_1040, marcus_1040, blue_ridge_1120, blue_ridge_payroll,
                  fernwood_1041, apex_scorp, apex_bookkeeping, robert_amended,
                  robert_advisory, martinez_706, sarah_extension, nguyen_1065]:
            db.refresh(e)
        print("Created 12 engagements.")

        # STEP 5 — Tasks
        tasks = []

        # Sarah Chen 1040
        tasks += [
            Task(firm_id=firm_id, client_id=sarah_chen.id, engagement_id=sarah_1040.id,
                 title="Collect W-2 from employer", status="todo",
                 due_date=today + timedelta(days=3), assigned_to=taylor.id),
            Task(firm_id=firm_id, client_id=sarah_chen.id, engagement_id=sarah_1040.id,
                 title="Pull IRS transcript — 2023", status="in_progress",
                 due_date=today + timedelta(days=5), assigned_to=alex.id),
            Task(firm_id=firm_id, client_id=sarah_chen.id, engagement_id=sarah_1040.id,
                 title="Prepare Schedule E — rental income", status="todo",
                 due_date=today + timedelta(days=7), assigned_to=taylor.id),
            Task(firm_id=firm_id, client_id=sarah_chen.id, engagement_id=sarah_1040.id,
                 title="Partner review sign-off", status="todo",
                 due_date=today + timedelta(days=10), assigned_to=jordan.id),
        ]

        # Marcus Rivera 1040
        tasks += [
            Task(firm_id=firm_id, client_id=marcus_rivera.id, engagement_id=marcus_1040.id,
                 title="Final review of draft return", status="in_progress",
                 due_date=today + timedelta(days=2), assigned_to=jordan.id),
            Task(firm_id=firm_id, client_id=marcus_rivera.id, engagement_id=marcus_1040.id,
                 title="Confirm brokerage statement received", status="todo",
                 due_date=today + timedelta(days=1), assigned_to=casey.id),
            Task(firm_id=firm_id, client_id=marcus_rivera.id, engagement_id=marcus_1040.id,
                 title="Send draft to client for review", status="todo",
                 due_date=today + timedelta(days=4), assigned_to=jordan.id),
        ]

        # Blue Ridge 1120
        tasks += [
            Task(firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
                 title="Reconcile depreciation schedule", status="in_progress",
                 due_date=today + timedelta(days=5), assigned_to=taylor.id),
            Task(firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
                 title="Review officer compensation", status="todo",
                 due_date=today + timedelta(days=8), assigned_to=alex.id),
            Task(firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
                 title="Calculate QBI deduction", status="todo",
                 due_date=today + timedelta(days=6), assigned_to=taylor.id),
            Task(firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
                 title="Prepare state return — NC", status="todo",
                 due_date=today + timedelta(days=12), assigned_to=casey.id),
        ]

        # Fernwood Trust
        tasks += [
            Task(firm_id=firm_id, client_id=fernwood_trust.id, engagement_id=fernwood_1041.id,
                 title="Obtain all trust K-1s", status="in_progress",
                 due_date=today + timedelta(days=4), assigned_to=jordan.id),
            Task(firm_id=firm_id, client_id=fernwood_trust.id, engagement_id=fernwood_1041.id,
                 title="Calculate DNI and distribution deduction", status="todo",
                 due_date=today + timedelta(days=9), assigned_to=jordan.id),
        ]

        # Apex S-Corp
        tasks += [
            Task(firm_id=firm_id, client_id=apex_staffing.id, engagement_id=apex_scorp.id,
                 title="Final partner review", status="in_progress",
                 due_date=today + timedelta(days=1), assigned_to=alex.id),
            Task(firm_id=firm_id, client_id=apex_staffing.id, engagement_id=apex_scorp.id,
                 title="Confirm shareholder basis calculations", status="done",
                 due_date=today - timedelta(days=2), assigned_to=alex.id),
            Task(firm_id=firm_id, client_id=apex_staffing.id, engagement_id=apex_scorp.id,
                 title="File state return — NY", status="todo",
                 due_date=today + timedelta(days=3), assigned_to=casey.id),
        ]

        # Robert Gallagher Amended
        tasks += [
            Task(firm_id=firm_id, client_id=robert_gallagher.id, engagement_id=robert_amended.id,
                 title="Pull original 2023 return", status="done",
                 due_date=today - timedelta(days=5), assigned_to=taylor.id),
            Task(firm_id=firm_id, client_id=robert_gallagher.id, engagement_id=robert_amended.id,
                 title="Identify adjustment items", status="in_progress",
                 due_date=today + timedelta(days=2), assigned_to=taylor.id),
        ]

        # Robert Gallagher Advisory
        tasks += [
            Task(firm_id=firm_id, client_id=robert_gallagher.id, engagement_id=robert_advisory.id,
                 title="Run 2025 tax projection", status="todo",
                 due_date=today + timedelta(days=7), assigned_to=alex.id),
            Task(firm_id=firm_id, client_id=robert_gallagher.id, engagement_id=robert_advisory.id,
                 title="Prepare Roth conversion analysis", status="todo",
                 due_date=today + timedelta(days=14), assigned_to=alex.id),
        ]

        # Martinez Estate
        tasks += [
            Task(firm_id=firm_id, client_id=martinez_estate.id, engagement_id=martinez_706.id,
                 title="Obtain date-of-death valuations", status="in_progress",
                 due_date=today + timedelta(days=10), assigned_to=jordan.id),
            Task(firm_id=firm_id, client_id=martinez_estate.id, engagement_id=martinez_706.id,
                 title="Coordinate with estate attorney", status="todo",
                 due_date=today + timedelta(days=15), assigned_to=jordan.id),
            Task(firm_id=firm_id, client_id=martinez_estate.id, engagement_id=martinez_706.id,
                 title="Pull bank account records at death", status="todo",
                 due_date=today + timedelta(days=8), assigned_to=casey.id),
        ]

        # Overdue tasks
        tasks += [
            Task(firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
                 title="Send IRS correspondence response", status="todo",
                 due_date=today - timedelta(days=3), assigned_to=casey.id),
            Task(firm_id=firm_id, client_id=marcus_rivera.id, engagement_id=marcus_1040.id,
                 title="Upload signed engagement letter", status="todo",
                 due_date=today - timedelta(days=3), assigned_to=taylor.id),
        ]

        db.add_all(tasks)
        db.commit()
        for t in tasks:
            db.refresh(t)
        print("Created tasks.")

        # STEP 6 — Document Requests
        dr_sarah = DocumentRequest(
            firm_id=firm_id, client_id=sarah_chen.id, engagement_id=sarah_1040.id,
            title="2024 Tax Documents",
            status="partial", reminder_count=2, due_date=today + timedelta(days=5),
            checklist_items=[
                {"id": "item-1", "label": "W-2 from employer", "description": "All W-2 forms for 2024", "is_required": True, "status": "uploaded"},
                {"id": "item-2", "label": "1099-INT (bank interest)", "description": "Interest income statements", "is_required": True, "status": "uploaded"},
                {"id": "item-3", "label": "1099-DIV (dividends)", "description": "Dividend statements", "is_required": True, "status": "pending"},
                {"id": "item-4", "label": "Schedule K-1 (partnership)", "description": "K-1 from any partnerships", "is_required": False, "status": "pending"},
                {"id": "item-5", "label": "Rental property income/expense summary", "description": "Income and expenses for all rental properties", "is_required": True, "status": "pending"},
            ],
        )
        dr_marcus = DocumentRequest(
            firm_id=firm_id, client_id=marcus_rivera.id, engagement_id=marcus_1040.id,
            title="2024 Tax Documents",
            status="partial", reminder_count=1, due_date=today + timedelta(days=5),
            checklist_items=[
                {"id": "item-1", "label": "W-2 from employer", "description": "W-2 for tax year 2024", "is_required": True, "status": "uploaded"},
                {"id": "item-2", "label": "1099-B (brokerage statement)", "description": "Fidelity account statement", "is_required": True, "status": "pending"},
                {"id": "item-3", "label": "1099-INT", "description": "Bank interest statements", "is_required": False, "status": "uploaded"},
            ],
        )
        dr_blue_ridge = DocumentRequest(
            firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
            title="2024 Corporate Documents",
            status="partial", reminder_count=1, due_date=today + timedelta(days=5),
            checklist_items=[
                {"id": "item-1", "label": "Bank statements — all accounts", "description": "12 months of bank statements", "is_required": True, "status": "uploaded"},
                {"id": "item-2", "label": "Payroll summary / W-3", "description": "Annual payroll summary", "is_required": True, "status": "uploaded"},
                {"id": "item-3", "label": "Fixed asset additions list", "description": "New equipment or property purchased in 2024", "is_required": True, "status": "pending"},
                {"id": "item-4", "label": "Officer compensation detail", "description": "Breakdown of officer W-2s and distributions", "is_required": True, "status": "pending"},
            ],
        )
        dr_fernwood = DocumentRequest(
            firm_id=firm_id, client_id=fernwood_trust.id, engagement_id=fernwood_1041.id,
            title="Trust Tax Documents",
            status="pending", reminder_count=0, due_date=today + timedelta(days=5),
            checklist_items=[
                {"id": "item-1", "label": "Trust agreement / amendments", "description": "Current trust agreement and any amendments", "is_required": True, "status": "pending"},
                {"id": "item-2", "label": "K-1s from trust investments", "description": "All K-1 forms received by the trust", "is_required": True, "status": "pending"},
                {"id": "item-3", "label": "Distribution records", "description": "Record of all distributions made in 2024", "is_required": True, "status": "pending"},
            ],
        )
        dr_apex = DocumentRequest(
            firm_id=firm_id, client_id=apex_staffing.id, engagement_id=apex_scorp.id,
            title="2024 S-Corp Documents",
            status="complete", reminder_count=0, due_date=today - timedelta(days=5),
            checklist_items=[
                {"id": "item-1", "label": "Shareholder W-2s", "description": "W-2 for all shareholder-employees", "is_required": True, "status": "approved"},
                {"id": "item-2", "label": "Payroll records", "description": "Complete 2024 payroll detail", "is_required": True, "status": "approved"},
                {"id": "item-3", "label": "Loan agreements", "description": "Any shareholder loans", "is_required": False, "status": "approved"},
            ],
        )

        db.add_all([dr_sarah, dr_marcus, dr_blue_ridge, dr_fernwood, dr_apex])
        db.commit()
        for dr in [dr_sarah, dr_marcus, dr_blue_ridge, dr_fernwood, dr_apex]:
            db.refresh(dr)
        print("Created document requests.")

        # STEP 7 — Invoices
        inv1 = Invoice(
            firm_id=firm_id, client_id=sarah_chen.id, engagement_id=sarah_1040.id,
            invoice_number="INV-2025-001",
            line_items=[{"description": "1040 Individual Tax Return Preparation", "quantity": 1, "unit_price": 850.00, "amount": 850.00}],
            subtotal=Decimal("850.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("850.00"),
            status=InvoiceStatus.sent,
            sent_at=now - timedelta(days=7), due_date=today + timedelta(days=23),
            delivery_method=_DELIVERY_PORTAL,
        )
        inv2 = Invoice(
            firm_id=firm_id, client_id=marcus_rivera.id, engagement_id=marcus_1040.id,
            invoice_number="INV-2025-002",
            line_items=[{"description": "1040 Individual Tax Return Preparation", "quantity": 1, "unit_price": 750.00, "amount": 750.00}],
            subtotal=Decimal("750.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("750.00"),
            status=InvoiceStatus.sent,
            sent_at=now - timedelta(days=7), due_date=today + timedelta(days=23),
            delivery_method=_DELIVERY_PORTAL,
        )
        inv3 = Invoice(
            firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
            invoice_number="INV-2025-003",
            line_items=[{"description": "1120 Corporate Tax Return Preparation", "quantity": 1, "unit_price": 2400.00, "amount": 2400.00}],
            subtotal=Decimal("2400.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("2400.00"),
            status=InvoiceStatus.draft,
            delivery_method=_DELIVERY_PORTAL,
        )
        inv4 = Invoice(
            firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_payroll.id,
            invoice_number="INV-2025-004",
            line_items=[{"description": "941 Quarterly Payroll Tax Filing", "quantity": 1, "unit_price": 350.00, "amount": 350.00}],
            subtotal=Decimal("350.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("350.00"),
            status=InvoiceStatus.paid,
            paid_at=now - timedelta(days=15), sent_at=now - timedelta(days=20),
            delivery_method=_DELIVERY_PORTAL,
        )
        inv5 = Invoice(
            firm_id=firm_id, client_id=apex_staffing.id, engagement_id=apex_scorp.id,
            invoice_number="INV-2025-005",
            line_items=[{"description": "1120-S S-Corporation Tax Return", "quantity": 1, "unit_price": 1800.00, "amount": 1800.00}],
            subtotal=Decimal("1800.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("1800.00"),
            status=InvoiceStatus.paid,
            paid_at=now - timedelta(days=15), sent_at=now - timedelta(days=20),
            delivery_method=_DELIVERY_PORTAL,
        )
        inv6 = Invoice(
            firm_id=firm_id, client_id=robert_gallagher.id, engagement_id=robert_amended.id,
            invoice_number="INV-2025-006",
            line_items=[{"description": "1040-X Amended Return Preparation", "quantity": 1, "unit_price": 400.00, "amount": 400.00}],
            subtotal=Decimal("400.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("400.00"),
            status=InvoiceStatus.overdue,
            sent_at=now - timedelta(days=45), due_date=today - timedelta(days=15),
            delivery_method=_DELIVERY_PORTAL,
        )
        inv7 = Invoice(
            firm_id=firm_id, client_id=fernwood_trust.id, engagement_id=fernwood_1041.id,
            invoice_number="INV-2025-007",
            line_items=[{"description": "1041 Trust Tax Return Preparation", "quantity": 1, "unit_price": 1200.00, "amount": 1200.00}],
            subtotal=Decimal("1200.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("1200.00"),
            status=InvoiceStatus.draft,
            delivery_method=_DELIVERY_PORTAL,
        )
        inv8 = Invoice(
            firm_id=firm_id, client_id=apex_staffing.id, engagement_id=apex_bookkeeping.id,
            invoice_number="INV-2025-008",
            line_items=[{"description": "Monthly Bookkeeping Services — March 2025", "quantity": 1, "unit_price": 600.00, "amount": 600.00}],
            subtotal=Decimal("600.00"), tax_rate=Decimal("0.0"), tax_amount=Decimal("0.0"), total_amount=Decimal("600.00"),
            status=InvoiceStatus.sent,
            sent_at=now - timedelta(days=7), due_date=today + timedelta(days=23),
            delivery_method=_DELIVERY_PORTAL,
        )

        db.add_all([inv1, inv2, inv3, inv4, inv5, inv6, inv7, inv8])
        db.commit()
        for inv in [inv1, inv2, inv3, inv4, inv5, inv6, inv7, inv8]:
            db.refresh(inv)
        print("Created 8 invoices.")

        # STEP 8 — Time Entries
        def make_te(engagement, user, description, activity_type, hours, days_ago,
                    status="submitted_approved", is_billable=True, is_billed=False, hourly_rate=Decimal("0")):
            entry_date = today - timedelta(days=days_ago)
            te = TimeEntry(
                firm_id=firm_id,
                engagement_id=engagement.id,
                user_id=user.id,
                description=description,
                hours=Decimal(str(hours)),
                hourly_rate=hourly_rate,
                is_billable=is_billable,
                is_billed=is_billed,
                date=entry_date,
                activity_type=activity_type,
            )
            if status == "submitted_approved":
                te.is_submitted = True
                te.submitted_at = datetime.combine(entry_date, time_type(8, 0), tzinfo=timezone.utc)
                te.is_approved = True
                te.approved_at = datetime.combine(entry_date, time_type(8, 0), tzinfo=timezone.utc) + timedelta(hours=16)
                te.approved_by_id = alex.id
            elif status == "submitted_not_approved":
                te.is_submitted = True
                te.submitted_at = datetime.combine(entry_date, time_type(8, 0), tzinfo=timezone.utc)
                te.is_approved = False
            else:
                te.is_submitted = False
                te.is_approved = False
            return te

        time_entries = []

        # Alex (200.00/hr)
        ar = Decimal("200.00")
        time_entries += [
            make_te(sarah_1040, alex, "Initial review and prior year analysis", "Tax Preparation", 2.5, 21, "submitted_approved", hourly_rate=ar),
            make_te(sarah_1040, alex, "Client onboarding call", "Client Meeting", 1.0, 18, "submitted_approved", hourly_rate=ar),
            make_te(apex_scorp, alex, "Return review and sign-off", "Review & Sign-off", 3.0, 14, "submitted_approved", hourly_rate=ar),
            make_te(apex_scorp, alex, "Final preparation and e-file", "Tax Preparation", 2.0, 7, "submitted_approved", hourly_rate=ar),
            make_te(robert_advisory, alex, "Roth conversion research", "Research", 1.5, 5, "submitted_not_approved", hourly_rate=ar),
            make_te(robert_advisory, alex, "Client communication re: projections", "Client Communication", 0.5, 3, "not_submitted", hourly_rate=ar),
            make_te(sarah_1040, alex, "Schedule E preparation", "Tax Preparation", 2.0, 2, "submitted_approved", hourly_rate=ar),
        ]

        # Jordan (175.00/hr)
        jr = Decimal("175.00")
        time_entries += [
            make_te(marcus_1040, jordan, "Data entry and initial preparation", "Tax Preparation", 3.0, 20, "submitted_approved", hourly_rate=jr),
            make_te(marcus_1040, jordan, "Brokerage statement review", "Document Review", 1.5, 15, "submitted_approved", hourly_rate=jr),
            make_te(fernwood_1041, jordan, "Trust return preparation", "Tax Preparation", 2.5, 12, "submitted_approved", hourly_rate=jr),
            make_te(fernwood_1041, jordan, "DNI calculation research", "Research", 2.0, 8, "submitted_approved", hourly_rate=jr),
            make_te(martinez_706, jordan, "Estate attorney coordination call", "Client Communication", 1.0, 6, "submitted_approved", hourly_rate=jr),
            make_te(martinez_706, jordan, "Date-of-death valuation research", "Research", 2.0, 3, "submitted_not_approved", hourly_rate=jr),
            make_te(marcus_1040, jordan, "Final review", "Review & Sign-off", 1.0, 1, "not_submitted", hourly_rate=jr),
        ]

        # Taylor (150.00/hr)
        tr = Decimal("150.00")
        time_entries += [
            make_te(blue_ridge_1120, taylor, "Corporate return preparation — Part 1", "Tax Preparation", 4.0, 22, "submitted_approved", hourly_rate=tr),
            make_te(blue_ridge_1120, taylor, "Bank statement reconciliation", "Document Review", 2.0, 16, "submitted_approved", hourly_rate=tr),
            make_te(robert_amended, taylor, "Prior year return analysis", "Tax Preparation", 1.5, 11, "submitted_approved", hourly_rate=tr),
            make_te(blue_ridge_1120, taylor, "Depreciation schedule preparation", "Tax Preparation", 3.0, 9, "submitted_approved", hourly_rate=tr),
            make_te(sarah_1040, taylor, "W-2 and 1099 data entry", "Document Review", 1.0, 4, "submitted_approved", hourly_rate=tr),
            make_te(blue_ridge_1120, taylor, "NC state return research", "Research", 1.5, 2, "not_submitted", hourly_rate=tr),
            make_te(robert_amended, taylor, "Client call re: amended items", "Client Communication", 0.5, 1, "not_submitted", hourly_rate=tr),
        ]

        # Casey (125.00/hr)
        cr = Decimal("125.00")
        time_entries += [
            make_te(blue_ridge_payroll, casey, "941 preparation and filing", "Tax Preparation", 2.0, 25, "submitted_approved", is_billed=True, hourly_rate=cr),
            make_te(apex_bookkeeping, casey, "March bookkeeping entry", "Admin", 3.0, 18, "submitted_approved", hourly_rate=cr),
            make_te(apex_bookkeeping, casey, "Bank reconciliation review", "Document Review", 1.0, 14, "submitted_approved", hourly_rate=cr),
            make_te(blue_ridge_1120, casey, "Admin and file organization", "Admin", 1.5, 10, "submitted_approved", is_billable=False, hourly_rate=cr),
            make_te(apex_scorp, casey, "Payroll record processing", "Tax Preparation", 2.0, 7, "submitted_approved", is_billed=True, hourly_rate=cr),
            make_te(apex_bookkeeping, casey, "April bookkeeping setup", "Tax Preparation", 2.0, 4, "submitted_approved", hourly_rate=cr),
            make_te(martinez_706, casey, "Estate asset research", "Research", 1.0, 2, "not_submitted", hourly_rate=cr),
        ]

        db.add_all(time_entries)
        db.commit()
        print("Created 28 time entries.")

        # STEP 9 — IRS Authorizations
        irs_auths = [
            IrsAuthorization(firm_id=firm_id, client_id=sarah_chen.id, form_type="8821", status="active",
                             valid_from=today - timedelta(days=90), valid_until=today + timedelta(days=180)),
            IrsAuthorization(firm_id=firm_id, client_id=marcus_rivera.id, form_type="8821", status="active",
                             valid_from=today - timedelta(days=90), valid_until=today + timedelta(days=90)),
            IrsAuthorization(firm_id=firm_id, client_id=blue_ridge.id, form_type="2848", status="active",
                             valid_from=today - timedelta(days=90), valid_until=today + timedelta(days=365)),
            IrsAuthorization(firm_id=firm_id, client_id=blue_ridge.id, form_type="8821", status="active",
                             valid_from=today - timedelta(days=90), valid_until=today + timedelta(days=365)),
            IrsAuthorization(firm_id=firm_id, client_id=fernwood_trust.id, form_type="8821", status="active",
                             valid_from=today - timedelta(days=90), valid_until=today + timedelta(days=30)),
            IrsAuthorization(firm_id=firm_id, client_id=apex_staffing.id, form_type="2848",
                             status="pending_signature"),
            IrsAuthorization(firm_id=firm_id, client_id=robert_gallagher.id, form_type="8821", status="expired",
                             valid_from=today - timedelta(days=400), valid_until=today - timedelta(days=30)),
            IrsAuthorization(firm_id=firm_id, client_id=martinez_estate.id, form_type="2848", status="active",
                             valid_from=today - timedelta(days=90), valid_until=today + timedelta(days=200)),
        ]
        db.add_all(irs_auths)
        db.commit()
        print("Created IRS authorizations.")

        # STEP 10 — Notes
        notes = [
            Note(firm_id=firm_id, entity_type="client", entity_id=sarah_chen.id, author_id=alex.id,
                 body="Prefers communication via email. Vacation mid-July — plan filing accordingly.", is_private=False),
            Note(firm_id=firm_id, entity_type="client", entity_id=sarah_chen.id, author_id=jordan.id,
                 body="Note: David (spouse) will be present on review call.", is_private=False),
            Note(firm_id=firm_id, entity_type="client", entity_id=marcus_rivera.id, author_id=alex.id,
                 body="New client — referred by Sarah Chen. Very responsive.", is_private=False),
            Note(firm_id=firm_id, entity_type="client", entity_id=blue_ridge.id, author_id=taylor.id,
                 body="Owner is Diana Krueger. Always available Tue/Thu mornings.", is_private=False),
            Note(firm_id=firm_id, entity_type="client", entity_id=robert_gallagher.id, author_id=alex.id,
                 body="Gallagher was audited in 2022 — keep documentation thorough.", is_private=True),
            Note(firm_id=firm_id, entity_type="engagement", entity_id=sarah_1040.id, author_id=taylor.id,
                 body="Confirmed rental income from 142 Beacon St unit — $1,800/month. Need depreciation schedule.", is_private=False),
            Note(firm_id=firm_id, entity_type="engagement", entity_id=marcus_1040.id, author_id=jordan.id,
                 body="Fidelity account 7823 — client confirmed they will upload by Friday.", is_private=False),
            Note(firm_id=firm_id, entity_type="engagement", entity_id=fernwood_1041.id, author_id=jordan.id,
                 body="Trust was created 2019. Patricia is sole trustee. Annual distribution: $45,000 to two beneficiaries.", is_private=False),
            Note(firm_id=firm_id, entity_type="engagement", entity_id=apex_scorp.id, author_id=alex.id,
                 body="Please double check the shareholder basis worksheet before we file.", is_private=False),
            Note(firm_id=firm_id, entity_type="engagement", entity_id=martinez_706.id, author_id=jordan.id,
                 body="Date of death: October 12, 2024. Gross estate approximately $2.1M. Coordinating with Hendricks Law.", is_private=False),
        ]
        db.add_all(notes)
        db.commit()
        print("Created notes.")

        # STEP 11 — Firm Chat Channels and Messages
        from app.models.firm_chat import Channel, FirmMessage

        ch_general = Channel(firm_id=firm_id, name="general", created_by=alex.id)
        ch_tax = Channel(firm_id=firm_id, name="tax-season-2025", created_by=alex.id)
        ch_billing = Channel(firm_id=firm_id, name="billing", created_by=alex.id)
        db.add_all([ch_general, ch_tax, ch_billing])
        db.commit()
        db.refresh(ch_general)
        db.refresh(ch_tax)
        db.refresh(ch_billing)

        def make_msg(channel, sender, body, days_ago):
            return FirmMessage(
                firm_id=firm_id,
                channel_id=channel.id,
                sender_id=sender.id,
                body=body,
                mentions=None,
                created_at=datetime.combine(today - timedelta(days=days_ago), time_type(9, 0), tzinfo=timezone.utc),
            )

        messages = [
            make_msg(ch_general, alex, "Good morning team. Heavy week ahead — let's stay on top of the deadline board.", 14),
            make_msg(ch_general, taylor, "Heads up — Blue Ridge sent over their bank statements this morning. Starting on the reconciliation now.", 13),
            make_msg(ch_general, jordan, "Marcus Rivera's brokerage statement is still outstanding. I'll send a reminder this afternoon.", 12),
            make_msg(ch_general, casey, "Apex payroll filing went through — confirmed with the client.", 11),
            make_msg(ch_general, alex, "Great work everyone on getting through the first wave. Only 6 returns still open.", 10),
            make_msg(ch_general, taylor, "Quick question @Jordan — do you want me to start on the NC state return for Blue Ridge or wait until the federal is done?", 8),
            make_msg(ch_general, jordan, "Go ahead and start the state, we're close on federal. Will have it wrapped today.", 7),
            make_msg(ch_general, casey, "Robert Gallagher's amended return — pulled the original 2023. Ready to go when Taylor has bandwidth.", 5),
            make_msg(ch_general, alex, "Reminder: all time entries need to be submitted by Friday EOD for approval.", 3),
            make_msg(ch_general, taylor, "Done — all my entries are in.", 2),
            make_msg(ch_tax, alex, "Kicking off this channel for tax season coordination. Use this for deadline tracking and escalations.", 14),
            make_msg(ch_tax, jordan, "Fernwood Trust extension is filed and confirmed. Extended deadline is October 15.", 11),
            make_msg(ch_tax, alex, "Martinez Estate — this one will take time. Coordinating with the law firm on valuations.", 9),
            make_msg(ch_tax, casey, "Apex Staffing S-Corp is in review. Should be done by end of week.", 6),
            make_msg(ch_tax, jordan, "Marcus Rivera return is in final review. Just waiting on that Fidelity statement.", 4),
            make_msg(ch_tax, alex, "Good progress team. On track for the April 15 deadline across the board.", 1),
            make_msg(ch_billing, alex, "INV-2025-006 for Robert Gallagher is now 15 days overdue. Casey, can you reach out today?", 7),
            make_msg(ch_billing, casey, "On it — I'll send a follow-up email this morning.", 6),
            make_msg(ch_billing, jordan, "Sarah Chen invoice is sent. She mentioned she'll pay before end of the month.", 4),
            make_msg(ch_billing, alex, "Blue Ridge invoice is still in draft — Taylor, confirm all time entries are captured before we send.", 2),
        ]
        db.add_all(messages)
        db.commit()
        print("Created 3 channels and 20 messages.")

        # STEP 12 — Notifications
        notifications = [
            Notification(firm_id=firm_id, recipient_id=taylor.id, recipient_type=RecipientType.staff,
                         title="New task: Collect W-2 from employer",
                         body="Assigned to you on Sarah Chen's 1040 return. Due in 3 days.",
                         notification_type=NotificationType.task_assigned, is_read=False,
                         created_at=now - timedelta(days=1)),
            Notification(firm_id=firm_id, recipient_id=casey.id, recipient_type=RecipientType.staff,
                         title="New task: Confirm brokerage statement",
                         body="Assigned to you on Marcus Rivera's 1040 return.",
                         notification_type=NotificationType.task_assigned, is_read=True,
                         created_at=now - timedelta(days=8)),
            Notification(firm_id=firm_id, recipient_id=taylor.id, recipient_type=RecipientType.staff,
                         title="New task: Reconcile depreciation schedule",
                         body="Assigned to you on Blue Ridge Contracting's 1120 return.",
                         notification_type=NotificationType.task_assigned, is_read=True,
                         created_at=now - timedelta(days=7)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="Documents complete: Apex Staffing S-Corp",
                         body="All required documents uploaded and approved for Apex Staffing Solutions.",
                         notification_type=NotificationType.doc_request_ready, is_read=False,
                         created_at=now - timedelta(days=2)),
            Notification(firm_id=firm_id, recipient_id=jordan.id, recipient_type=RecipientType.staff,
                         title="Documents uploaded: Marcus Rivera 1040",
                         body="Marcus Rivera uploaded 1 new document to their tax folder.",
                         notification_type=NotificationType.doc_request_ready, is_read=True,
                         created_at=now - timedelta(days=9)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="Signature required: Apex Staffing 2848",
                         body="The Form 2848 for Apex Staffing Solutions is awaiting client signature.",
                         notification_type=NotificationType.esign_needed, is_read=False,
                         created_at=now - timedelta(days=2)),
            Notification(firm_id=firm_id, recipient_id=jordan.id, recipient_type=RecipientType.staff,
                         title="Engagement letter pending: Fernwood Trust",
                         body="The engagement letter sent to Fernwood Family Trust has not been signed.",
                         notification_type=NotificationType.esign_needed, is_read=True,
                         created_at=now - timedelta(days=10)),
            Notification(firm_id=firm_id, recipient_id=casey.id, recipient_type=RecipientType.staff,
                         title="Invoice overdue: Robert Gallagher — $400.00",
                         body="INV-2025-006 is 15 days past due.",
                         notification_type=NotificationType.payment_due, is_read=False,
                         created_at=now - timedelta(days=1)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="Invoice paid: Apex Staffing — $1,800.00",
                         body="INV-2025-005 has been paid in full.",
                         notification_type=NotificationType.payment_due, is_read=True,
                         created_at=now - timedelta(days=12)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="Deadline approaching: Marcus Rivera 1040",
                         body="April 15 is 14 days away. The return is currently in review.",
                         notification_type=NotificationType.deadline_alert, is_read=False,
                         created_at=now - timedelta(days=2)),
            Notification(firm_id=firm_id, recipient_id=jordan.id, recipient_type=RecipientType.staff,
                         title="Deadline approaching: Fernwood Trust 1041",
                         body="April 15 is 14 days away. Extension filed — new deadline October 15.",
                         notification_type=NotificationType.deadline_alert, is_read=True,
                         created_at=now - timedelta(days=11)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="IRS auth expiring: Fernwood Family Trust",
                         body="Form 8821 for Fernwood Family Trust expires in 30 days. Renewal required.",
                         notification_type=NotificationType.irs_auth_expiry, is_read=False,
                         created_at=now - timedelta(days=1)),
            Notification(firm_id=firm_id, recipient_id=jordan.id, recipient_type=RecipientType.staff,
                         title="IRS auth expiring: Marcus Rivera",
                         body="Form 8821 expires in 90 days. Plan renewal before next filing season.",
                         notification_type=NotificationType.irs_auth_expiry, is_read=True,
                         created_at=now - timedelta(days=9)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="IRS auth expired: Robert Gallagher",
                         body="Form 8821 for Robert Gallagher has expired. Cannot pull IRS transcripts without renewal.",
                         notification_type=NotificationType.irs_auth_missing, is_read=False,
                         created_at=now - timedelta(days=2)),
            Notification(firm_id=firm_id, recipient_id=taylor.id, recipient_type=RecipientType.staff,
                         title="Extension filed: Sarah Chen 1040",
                         body="Form 4868 filed for Sarah Chen. New deadline: October 15, 2025.",
                         notification_type=NotificationType.extension_deadline, is_read=True,
                         created_at=now - timedelta(days=6)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="Extension deadline: Fernwood Trust",
                         body="Extended deadline of October 15 is 6 months away — begin preparation.",
                         notification_type=NotificationType.extension_deadline, is_read=True,
                         created_at=now - timedelta(days=8)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="Client anniversary: Sarah Chen",
                         body="Sarah Chen has been a client for 3 years today. Consider sending a personal note.",
                         notification_type=NotificationType.client_anniversary, is_read=False,
                         created_at=now - timedelta(days=1)),
            Notification(firm_id=firm_id, recipient_id=jordan.id, recipient_type=RecipientType.staff,
                         title="Client anniversary: Marcus Rivera",
                         body="Marcus Rivera's 1-year client anniversary is today.",
                         notification_type=NotificationType.client_anniversary, is_read=True,
                         created_at=now - timedelta(days=5)),
            Notification(firm_id=firm_id, recipient_id=casey.id, recipient_type=RecipientType.staff,
                         title="Document expiring: Blue Ridge — Articles of Incorporation",
                         body="Uploaded Articles of Incorporation for Blue Ridge Contracting expires in 60 days.",
                         notification_type=NotificationType.document_expiry_alert, is_read=False,
                         created_at=now - timedelta(days=2)),
            Notification(firm_id=firm_id, recipient_id=taylor.id, recipient_type=RecipientType.staff,
                         title="Document expiry: Robert Gallagher — POA",
                         body="Uploaded Power of Attorney document expires in 14 days.",
                         notification_type=NotificationType.document_expiry_alert, is_read=True,
                         created_at=now - timedelta(days=7)),
            Notification(firm_id=firm_id, recipient_id=alex.id, recipient_type=RecipientType.staff,
                         title="Automation rules active",
                         body="8 automation rules are now active for your firm. Review them in Settings → Automations.",
                         notification_type=NotificationType.system, is_read=True,
                         created_at=now - timedelta(days=14)),
            Notification(firm_id=firm_id, recipient_id=casey.id, recipient_type=RecipientType.staff,
                         title="Timesheet reminder",
                         body="You have 3 unsubmitted time entries from last week. Submit by Friday for approval.",
                         notification_type=NotificationType.system, is_read=False,
                         created_at=now - timedelta(days=1)),
        ]
        db.add_all(notifications)
        db.commit()
        print("Created notifications.")

        # STEP 13 — QC Checklist Templates
        qc_templates = [
            QcChecklistTemplate(
                firm_id=firm_id,
                name="1040 Individual Return QC",
                engagement_type="tax_return_1040",
                is_active=True,
                items=[
                    "Confirm client identity and SSN matches prior year",
                    "Verify all W-2s received and entered correctly",
                    "Confirm all 1099 income captured (INT, DIV, B, R, SSA)",
                    "Review Schedule A — itemized deductions vs standard deduction comparison",
                    "Check Schedule B — interest and dividend income totals",
                    "Verify Schedule D — capital gains/losses and carryovers",
                    "Confirm Schedule E — rental income/loss and K-1 entries",
                    "Verify QBI deduction calculation (Schedule 1, Section 199A)",
                    "Check estimated tax payments match IRS records",
                    "Confirm prior year AGI used for e-file PIN",
                    "Verify banking information for refund or balance due",
                    "Review for AMT exposure",
                    "Confirm state return matches federal AGI",
                    "Partner/manager sign-off complete",
                    "E-file authorization (8879) signed by client",
                ],
            ),
            QcChecklistTemplate(
                firm_id=firm_id,
                name="S-Corp / Partnership Return QC",
                engagement_type="tax_return_1120s",
                is_active=True,
                items=[
                    "Confirm EIN and entity type are correct",
                    "Verify officer W-2s are included and reasonable",
                    "Review shareholder basis calculations — confirm no excess distributions",
                    "Check AAA account balance and reconciliation",
                    "Verify all K-1s prepared and match return totals",
                    "Confirm built-in gains tax exposure reviewed (S-Corps within 5-year window)",
                    "Check depreciation schedules — bonus depreciation and Section 179 elections",
                    "Verify payroll tax deposits reconcile to 941s",
                    "Review officer health insurance deduction treatment",
                    "Confirm state return(s) prepared for all nexus states",
                    "Check loan agreement documentation for shareholder loans",
                    "Partner/manager sign-off complete",
                    "E-file authorization signed",
                ],
            ),
            QcChecklistTemplate(
                firm_id=firm_id,
                name="Extension Filing QC",
                engagement_type="extension_4868",
                is_active=True,
                items=[
                    "Confirm correct extension form (4868 / 7004 / 8868)",
                    "Verify client name and EIN/SSN match return on file",
                    "Calculate estimated tax liability for the year",
                    "Confirm prior year tax as safe harbor baseline",
                    "Verify any balance due payment submitted with extension",
                    "Confirm extended deadline date is correct and noted in engagement",
                    "Notify client of new deadline in writing",
                    "Update engagement extended deadline field in JAMM PX",
                    "File confirmation saved to client file",
                ],
            ),
            QcChecklistTemplate(
                firm_id=firm_id,
                name="New Client Intake QC",
                engagement_type=None,
                is_active=True,
                items=[
                    "Engagement letter signed and filed",
                    "Form 8821 or 2848 executed and filed with IRS",
                    "Prior year returns collected (minimum 2 years)",
                    "Client contact information verified — email, phone, address",
                    "Entity type confirmed — individual / business / trust / estate",
                    "Portal invitation sent and client has logged in",
                    "Fee schedule discussed and engagement terms confirmed",
                    "QuickBooks or accounting software access established (if applicable)",
                    "Prior accountant records requested (if switching firms)",
                    "Client onboarding call completed and notes filed",
                ],
            ),
            QcChecklistTemplate(
                firm_id=firm_id,
                name="Trust and Estate Return QC",
                engagement_type="tax_return_1041",
                is_active=True,
                items=[
                    "Confirm trust type — simple, complex, grantor, or estate",
                    "Verify trustee information and EIN",
                    "Confirm all income sources captured — dividends, interest, rental, K-1s",
                    "Calculate distributable net income (DNI) correctly",
                    "Verify distribution deduction matches actual distributions made",
                    "Check Schedule K-1 (1041) prepared for each beneficiary",
                    "Review for alternative minimum tax (AMT) exposure",
                    "Confirm state fiduciary return prepared if required",
                    "Verify charitable deduction if applicable",
                    "Check depreciation and depletion allocations",
                    "Partner/manager sign-off complete",
                    "E-file authorization signed by trustee",
                ],
            ),
            QcChecklistTemplate(
                firm_id=firm_id,
                name="Monthly Bookkeeping Close QC",
                engagement_type="bookkeeping_monthly",
                is_active=True,
                items=[
                    "Bank accounts reconciled — all accounts match statements",
                    "Credit card statements reconciled",
                    "Accounts receivable aging reviewed",
                    "Accounts payable aging reviewed",
                    "Payroll entries posted and reconciled to payroll reports",
                    "Fixed asset additions and disposals recorded",
                    "Depreciation entries posted",
                    "Loan payments split correctly between principal and interest",
                    "Sales tax liability reviewed and payment scheduled",
                    "P&L reviewed for reasonableness vs prior month",
                    "Balance sheet reviewed — no unexplained balances",
                    "Client questions or issues documented and communicated",
                ],
            ),
        ]
        db.add_all(qc_templates)
        db.commit()
        print("Created 6 QC checklist templates.")

        # STEP 14 — Behavioral Events (best effort)
        try:
            from app.models.behavioral_event import BehavioralEvent

            done_tasks = [t for t in tasks if t.status == "done"]
            done_task_1 = done_tasks[0] if done_tasks else tasks[0]
            done_task_2 = done_tasks[1] if len(done_tasks) > 1 else tasks[0]

            behavioral_events = [
                BehavioralEvent(firm_id=firm_id, event_type="engagement.created",
                                entity_type="engagement", entity_id=sarah_1040.id,
                                actor_type="staff", actor_id=alex.id,
                                occurred_at=now - timedelta(days=29),
                                extra_metadata={"engagement_type": "tax_return_1040"}),
                BehavioralEvent(firm_id=firm_id, event_type="engagement.created",
                                entity_type="engagement", entity_id=blue_ridge_1120.id,
                                actor_type="staff", actor_id=taylor.id,
                                occurred_at=now - timedelta(days=25),
                                extra_metadata={"engagement_type": "tax_return_1120"}),
                BehavioralEvent(firm_id=firm_id, event_type="document_request.sent",
                                entity_type="document_request", entity_id=dr_sarah.id,
                                actor_type="staff", actor_id=alex.id,
                                occurred_at=now - timedelta(days=20),
                                extra_metadata={}),
                BehavioralEvent(firm_id=firm_id, event_type="invoice.paid",
                                entity_type="invoice", entity_id=inv5.id,
                                actor_type="staff", actor_id=alex.id,
                                occurred_at=now - timedelta(days=15),
                                extra_metadata={"amount": 1800.00}),
                BehavioralEvent(firm_id=firm_id, event_type="portal.first_login",
                                entity_type="client", entity_id=sarah_chen.id,
                                actor_type="staff", actor_id=alex.id,
                                occurred_at=now - timedelta(days=14),
                                extra_metadata={}),
                BehavioralEvent(firm_id=firm_id, event_type="task.completed",
                                entity_type="task", entity_id=done_task_1.id,
                                actor_type="staff", actor_id=alex.id,
                                occurred_at=now - timedelta(days=12),
                                extra_metadata={}),
                BehavioralEvent(firm_id=firm_id, event_type="firm.automation_enabled",
                                entity_type="automation_rule", entity_id=firm_id,
                                actor_type="staff", actor_id=alex.id,
                                occurred_at=now - timedelta(days=10),
                                extra_metadata={}),
                BehavioralEvent(firm_id=firm_id, event_type="invoice.paid",
                                entity_type="invoice", entity_id=inv4.id,
                                actor_type="staff", actor_id=casey.id,
                                occurred_at=now - timedelta(days=8),
                                extra_metadata={"amount": 350.00}),
                BehavioralEvent(firm_id=firm_id, event_type="task.completed",
                                entity_type="task", entity_id=done_task_2.id,
                                actor_type="staff", actor_id=taylor.id,
                                occurred_at=now - timedelta(days=5),
                                extra_metadata={}),
                BehavioralEvent(firm_id=firm_id, event_type="user.login",
                                entity_type="user", entity_id=alex.id,
                                actor_type="staff", actor_id=alex.id,
                                occurred_at=now - timedelta(days=1),
                                extra_metadata={"time_of_day": "morning"}),
            ]
            db.add_all(behavioral_events)
            db.commit()
            print("Created behavioral events.")
        except Exception as e:
            print(f"Warning: Could not create behavioral events: {e}")

        # STEP 16 — Signature Envelopes
        from app.models.signature_envelope import SignatureEnvelope

        env1 = SignatureEnvelope(
            firm_id=firm_id, client_id=sarah_chen.id, engagement_id=sarah_1040.id,
            provider="dropbox_sign", provider_envelope_id=None,
            status="sent",
            subject="Engagement Letter — 2024 Individual Tax Return",
            signers=[{"name": "Sarah Chen", "email": "corby0917@gmail.com", "role": "client"}],
            reminder_count=0, document_id=None, signed_document_id=None,
            sent_at=now - timedelta(days=5),
            created_at=now - timedelta(days=5),
        )
        env2 = SignatureEnvelope(
            firm_id=firm_id, client_id=marcus_rivera.id, engagement_id=marcus_1040.id,
            provider="dropbox_sign", provider_envelope_id=None,
            status="sent",
            subject="Engagement Letter — 2024 Individual Tax Return",
            signers=[{"name": "Marcus Rivera", "email": "marcus.rivera@demofirm.com", "role": "client"}],
            reminder_count=0, document_id=None, signed_document_id=None,
            sent_at=now - timedelta(days=3),
            created_at=now - timedelta(days=3),
        )
        env3 = SignatureEnvelope(
            firm_id=firm_id, client_id=apex_staffing.id, engagement_id=apex_scorp.id,
            provider="dropbox_sign", provider_envelope_id=None,
            status="viewed",
            subject="IRS Power of Attorney — Form 2848",
            signers=[{"name": "Apex Staffing Solutions", "email": "apex@demofirm.com", "role": "client"}],
            reminder_count=0, document_id=None, signed_document_id=None,
            sent_at=now - timedelta(days=7),
            created_at=now - timedelta(days=7),
        )
        env4 = SignatureEnvelope(
            firm_id=firm_id, client_id=blue_ridge.id, engagement_id=blue_ridge_1120.id,
            provider="dropbox_sign", provider_envelope_id=None,
            status="completed",
            subject="Engagement Letter — 2024 Corporate Tax Return",
            signers=[{"name": "Blue Ridge Contracting LLC", "email": "bluridge@demofirm.com", "role": "client"}],
            reminder_count=0, document_id=None, signed_document_id=None,
            sent_at=now - timedelta(days=20),
            completed_at=now - timedelta(days=18),
        )
        db.add_all([env1, env2, env3, env4])
        db.commit()
        print("Created 4 signature envelopes.")

        # STEP 17 — Documents
        from app.models.document import Document

        doc_spec = [
            (sarah_chen, sarah_1040, "Sarah_Chen_W2_2024.pdf", "tax_document", "internal", alex, 245760, 28),
            (sarah_chen, sarah_1040, "Sarah_Chen_1099_INT_2024.pdf", "tax_document", "internal", alex, 98304, 25),
            (marcus_rivera, marcus_1040, "Marcus_Rivera_W2_2024.pdf", "tax_document", "internal", jordan, 212992, 22),
            (blue_ridge, blue_ridge_1120, "BlueRidge_BankStatements_2024.pdf", "financial", "internal", taylor, 1048576, 20),
            (blue_ridge, blue_ridge_1120, "BlueRidge_Payroll_W3_2024.pdf", "tax_document", "internal", taylor, 331776, 17),
            (apex_staffing, apex_scorp, "ApexStaffing_1120S_2024_DRAFT.pdf", "return_draft", "internal", alex, 524288, 14),
            (fernwood_trust, fernwood_1041, "Fernwood_TrustAgreement.pdf", "legal", "internal", jordan, 786432, 10),
            (martinez_estate, martinez_706, "Martinez_EstateInventory.pdf", "legal", "internal", jordan, 655360, 7),
        ]

        documents = []
        for client_obj, eng_obj, filename, category, visibility, uploader, size, days_ago in doc_spec:
            doc_uuid = uuid.uuid4()
            doc = Document(
                firm_id=firm_id,
                client_id=client_obj.id,
                engagement_id=eng_obj.id,
                uploaded_by=uploader.id,
                filename=filename,
                s3_key=f"firms/{firm_id}/clients/{client_obj.id}/documents/{doc_uuid}.pdf",
                content_type="application/pdf",
                size_bytes=size,
                category=category,
                visibility=visibility,
                is_superseded=False,
                created_at=datetime.combine(today - timedelta(days=days_ago), time_type(9, 0), tzinfo=timezone.utc),
            )
            documents.append(doc)

        db.add_all(documents)
        db.commit()
        print("Created 8 documents.")

        # STEP 18 — Document Expiries
        from app.models.document_expiry import DocumentExpiry

        doc_expiries = [
            DocumentExpiry(
                firm_id=firm_id, client_id=blue_ridge.id, document_id=None,
                document_type="Articles of Incorporation",
                description="Annual renewal required by NC Secretary of State",
                expires_on=today + timedelta(days=60),
                status="active", expiry_notification_sent=False,
            ),
            DocumentExpiry(
                firm_id=firm_id, client_id=robert_gallagher.id, document_id=None,
                document_type="Power of Attorney",
                description="Client POA expires — renewal needed before representation",
                expires_on=today + timedelta(days=14),
                status="active", expiry_notification_sent=False,
            ),
            DocumentExpiry(
                firm_id=firm_id, client_id=sarah_chen.id, document_id=None,
                document_type="Government ID",
                description="ID verification on file for IRS authorization purposes",
                expires_on=today + timedelta(days=180),
                status="active", expiry_notification_sent=False,
            ),
        ]
        db.add_all(doc_expiries)
        db.commit()
        print("Created 3 document expiries.")

        # STEP 19 — Client Messages
        from app.models.message import ClientMessage

        client_messages = [
            ClientMessage(firm_id=firm_id, client_id=sarah_chen.id, sender_id=alex.id, sender_role="staff",
                          body="Hi Sarah, just a quick note that we received your W-2 and 1099-INT forms. We're still waiting on the 1099-DIV and the Schedule K-1 from your partnership. Could you upload those when you get a chance? We'd like to have everything by end of next week.",
                          created_at=now - timedelta(days=8)),
            ClientMessage(firm_id=firm_id, client_id=sarah_chen.id, sender_id=None, sender_role="client",
                          body="Hi Alex, thanks for the update. I'll reach out to my brokerage about the 1099-DIV — I think they may have mailed it. I don't think I received a K-1 this year, the partnership was dissolved in October. Does that change anything?",
                          created_at=now - timedelta(days=7)),
            ClientMessage(firm_id=firm_id, client_id=sarah_chen.id, sender_id=jordan.id, sender_role="staff",
                          body="Hi Sarah, good to know about the partnership. Yes, if the partnership was dissolved before year-end we'll need the final K-1 from the dissolution — the partnership is required to issue one. Please check with the other partners or their accountant. No rush, just let us know what you find.",
                          created_at=now - timedelta(days=6)),
            ClientMessage(firm_id=firm_id, client_id=sarah_chen.id, sender_id=None, sender_role="client",
                          body="Got it, I'll check with David. He handled most of the partnership paperwork. Should have an answer by Friday.",
                          created_at=now - timedelta(days=5)),
            ClientMessage(firm_id=firm_id, client_id=sarah_chen.id, sender_id=alex.id, sender_role="staff",
                          body="Perfect, thank you Sarah. Take your time — we have a few weeks before the April deadline. Everything else looks great on your return.",
                          created_at=now - timedelta(days=4)),
            ClientMessage(firm_id=firm_id, client_id=marcus_rivera.id, sender_id=jordan.id, sender_role="staff",
                          body="Hi Marcus, we're in the final review stage of your return. We're still waiting on the 1099-B from Fidelity showing your brokerage activity for 2024. Could you log into Fidelity and download it from their tax documents section? It should be available now.",
                          created_at=now - timedelta(days=5)),
            ClientMessage(firm_id=firm_id, client_id=marcus_rivera.id, sender_id=None, sender_role="client",
                          body="Hi Jordan, I'll grab that tonight. I just logged into the portal and see where to upload it. Will have it to you by tomorrow morning.",
                          created_at=now - timedelta(days=4)),
        ]
        db.add_all(client_messages)
        db.commit()
        print("Created client messages.")

        # STEP 20 — Portal Notifications (best effort)
        try:
            from app.models.portal_notification import PortalNotification

            portal_notifs = [
                PortalNotification(
                    firm_id=firm_id, client_id=sarah_chen.id,
                    title="New document request",
                    body="Riverside Tax & Advisory has sent you a 2024 tax document request. Please upload your W-2 and 1099 forms when you have a chance.",
                    notification_type="document_request", is_read=True,
                    created_at=now - timedelta(days=10),
                ),
                PortalNotification(
                    firm_id=firm_id, client_id=sarah_chen.id,
                    title="Invoice ready: INV-2025-001",
                    body="Your invoice for $850.00 is ready for payment. You can pay securely through your portal.",
                    notification_type="payment_due", is_read=False,
                    created_at=now - timedelta(days=7),
                ),
                PortalNotification(
                    firm_id=firm_id, client_id=sarah_chen.id,
                    title="Return status update",
                    body="Your 2024 Individual Tax Return is now in preparation. We'll notify you when it's ready for your review.",
                    notification_type="engagement_update", is_read=True,
                    created_at=now - timedelta(days=12),
                ),
                PortalNotification(
                    firm_id=firm_id, client_id=sarah_chen.id,
                    title="Welcome to your client portal",
                    body="Your secure portal is ready. Upload documents, view your return status, and pay invoices — all in one place.",
                    notification_type="system", is_read=True,
                    created_at=now - timedelta(days=20),
                ),
            ]
            db.add_all(portal_notifs)
            db.commit()
            print("Created 4 portal notifications.")
        except Exception as e:
            print(f"Warning: Could not create portal notifications: {e}")

        # STEP 21 — Engagement Letter Templates
        from app.models.engagement_letter_template import EngagementLetterTemplate

        letter_templates = [
            EngagementLetterTemplate(
                firm_id=firm_id,
                name="Standard Individual Engagement Letter",
                engagement_type="tax_return_1040",
                variable_fields=["client_name", "firm_name", "firm_owner_name", "engagement_name", "fee_amount", "engagement_date"],
                body_html="""<p>Dear {{client_name}},</p>
<p>Thank you for engaging {{firm_name}} to prepare your federal and state income tax returns for the current tax year. This letter confirms the terms of our engagement.</p>
<h3>Scope of Services</h3>
<p>We will prepare your federal Form 1040 and applicable state income tax return(s) based on information you provide. We will not audit or independently verify the information you provide, but we may ask for clarification where needed.</p>
<h3>Client Responsibilities</h3>
<p>You agree to provide complete and accurate information in a timely manner, review the completed returns before signing, and inform us of any changes in your tax situation.</p>
<h3>Fees</h3>
<p>Our fee for this engagement is {{fee_amount}}. Payment is due upon completion of your return.</p>
<p>Please sign below to confirm your acceptance of these terms.</p>
<p>Sincerely,<br>{{firm_owner_name}}<br>{{firm_name}}</p>""",
                is_active=True,
            ),
            EngagementLetterTemplate(
                firm_id=firm_id,
                name="Business Entity Engagement Letter",
                engagement_type="tax_return_1120s",
                variable_fields=["client_name", "firm_name", "firm_owner_name", "engagement_name", "fee_amount", "engagement_date"],
                body_html="""<p>Dear {{client_name}},</p>
<p>Thank you for selecting {{firm_name}} to prepare your business tax return. This letter outlines the scope and terms of our engagement.</p>
<h3>Scope of Services</h3>
<p>We will prepare your federal business income tax return and applicable state return(s) based on the financial information and records you provide.</p>
<h3>Your Responsibilities</h3>
<p>You are responsible for maintaining adequate records, ensuring the accuracy of all information provided, and making all management decisions. Our work does not constitute an audit or review of your financial statements.</p>
<h3>Fees</h3>
<p>Our estimated fee for this engagement is {{fee_amount}}, subject to adjustment based on the complexity of work required.</p>
<p>Sincerely,<br>{{firm_owner_name}}<br>{{firm_name}}</p>""",
                is_active=True,
            ),
            EngagementLetterTemplate(
                firm_id=firm_id,
                name="Tax Planning & Advisory Engagement Letter",
                engagement_type="tax_planning_advisory",
                variable_fields=["client_name", "firm_name", "firm_owner_name", "fee_amount", "engagement_date"],
                body_html="""<p>Dear {{client_name}},</p>
<p>We are pleased to provide tax planning and advisory services to you. This letter describes the nature and scope of the services we will provide.</p>
<h3>Services</h3>
<p>Our advisory services will include analysis of your current tax position, identification of planning opportunities, and recommendations to minimize your tax liability within the bounds of applicable law.</p>
<h3>Important Limitations</h3>
<p>Tax planning advice is based on current law, which is subject to change. Our advice represents our best professional judgment and does not guarantee specific tax outcomes.</p>
<h3>Fees</h3>
<p>Our fee for advisory services is {{fee_amount}} per engagement or as otherwise agreed in writing.</p>
<p>Sincerely,<br>{{firm_owner_name}}<br>{{firm_name}}</p>""",
                is_active=True,
            ),
        ]
        db.add_all(letter_templates)
        db.commit()
        print("Created 3 engagement letter templates.")

        # STEP 22 — Engagement Templates
        from app.models.engagement_template import EngagementTemplate

        eng_templates = [
            EngagementTemplate(
                firm_id=firm_id,
                name="1040 Individual — Standard",
                description="Standard workflow for individual tax return preparation",
                engagement_type="tax_return_1040",
                estimated_hours=Decimal("4.5"),
                task_templates=[
                    {"title": "Send document request to client", "order": 1},
                    {"title": "Enter income data (W-2, 1099s)", "order": 2},
                    {"title": "Prepare Schedule A / standard deduction comparison", "order": 3},
                    {"title": "Review for credits and deductions", "order": 4},
                    {"title": "Prepare state return(s)", "order": 5},
                    {"title": "Partner review", "order": 6},
                    {"title": "Send draft to client for review", "order": 7},
                    {"title": "Obtain signed 8879 e-file authorization", "order": 8},
                    {"title": "E-file and confirm acceptance", "order": 9},
                ],
                document_checklist=[
                    "W-2 from all employers",
                    "1099-INT (bank interest)",
                    "1099-DIV (dividends)",
                    "1099-B (brokerage)",
                    "Prior year return",
                    "Social security numbers for all dependents",
                ],
                is_active=True, use_count=0, is_recurring=False,
            ),
            EngagementTemplate(
                firm_id=firm_id,
                name="Monthly Bookkeeping Close",
                description="Standard monthly close workflow for bookkeeping clients",
                engagement_type="bookkeeping_monthly",
                estimated_hours=Decimal("3.0"),
                task_templates=[
                    {"title": "Download and categorize bank transactions", "order": 1},
                    {"title": "Reconcile all bank accounts", "order": 2},
                    {"title": "Reconcile credit card accounts", "order": 3},
                    {"title": "Post payroll entries", "order": 4},
                    {"title": "Review accounts receivable aging", "order": 5},
                    {"title": "Review P&L for anomalies", "order": 6},
                    {"title": "Send monthly report to client", "order": 7},
                ],
                document_checklist=[
                    "Bank statements — all accounts",
                    "Credit card statements",
                    "Payroll reports",
                    "Any vendor invoices over $500",
                ],
                is_active=True, use_count=0, is_recurring=True,
            ),
            EngagementTemplate(
                firm_id=firm_id,
                name="Extension Filing — Individual",
                description="Quick workflow for filing a personal extension",
                engagement_type="extension_4868",
                estimated_hours=Decimal("0.5"),
                task_templates=[
                    {"title": "Estimate tax liability for the year", "order": 1},
                    {"title": "Calculate balance due / safe harbor payment", "order": 2},
                    {"title": "File Form 4868 and submit any payment", "order": 3},
                    {"title": "Update engagement deadline to October 15", "order": 4},
                    {"title": "Notify client of extended deadline in writing", "order": 5},
                ],
                document_checklist=[
                    "Prior year tax return",
                    "Estimated income summary if available",
                ],
                is_active=True, use_count=0, is_recurring=False,
            ),
        ]
        db.add_all(eng_templates)
        db.commit()
        print("Created 3 engagement templates.")

        # FINAL SUMMARY
        print()
        print("=== Riverside Tax & Advisory — Seed Complete ===")
        print(f"Firm ID: {firm.id}")
        print("Staff logins:")
        print("  admin@demofirm.com / Demo2026!  (firm_owner — Alex Mercer)")
        print("  jordan@demofirm.com / Demo2026!  (manager — Jordan Reeves)")
        print("  taylor@demofirm.com / Demo2026!  (staff — Taylor Kim)")
        print("  casey@demofirm.com / Demo2026!  (staff — Casey O'Brien)")
        print("Portal demo: corby0917@gmail.com / PortalDemo2026!  (Sarah Chen)")
        print()
        print("Clients: 8  |  Engagements: 12  |  Tasks: 25+  |  Invoices: 8")
        print("Time entries: 28  |  Notifications: 22  |  Channels: 3  |  Messages: 20")
        print("QC Templates: 6  |  Engagement Templates: 3  |  Letter Templates: 3")
        print("Documents: 8  |  Signature Envelopes: 4  |  Client Messages: 7")
        print("Document Expiries: 3  |  Portal Notifications: 4  |  IRS Authorizations: 8")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
