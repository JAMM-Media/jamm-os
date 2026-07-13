# app/services/tax_organizer_service.py
"""
Tax organizer service — seeding and business logic.

Seven default templates are seeded on firm creation:
- Individual (1040) — personal income, dependents, deductions, life events
- Business (1120/1065/1120S) — business income, expenses, payroll, assets
- Rental Property — rental income, expenses, property details
- Estate & Trust (1041) — fiduciary info, income, deductions, distributions
- Non-Profit (990) — governance, revenue, expenses, program services
- Payroll & Bookkeeping — payroll details, bookkeeping, reporting needs
- New Client Intake — personal info, filing history, income sources

NOTE: Templates 4-7 are seeded for new firms only. Existing firms that
already have the original three templates will not receive these automatically.
"""

import logging
from urllib.parse import quote
from uuid import UUID, uuid4
from datetime import datetime, timezone

from fastapi import BackgroundTasks, HTTPException
from sqlalchemy.orm import Session

from app.crud import tax_organizer as crud_organizer
from app.core.enums import TriggerEvent
from app.models.tax_organizer import TaxOrganizerTemplate
from app.services.audit_service import write_audit_log
from app.services.behavioral_log import log_event
from app.services.email_service import EmailService
from app.services.event_bus import emit_event

logger = logging.getLogger(__name__)


async def send_organizer(
    *,
    db: Session,
    payload,  # TaxOrganizerSendRequest
    client,
    engagement,
    firm,
    current_user_id,
    background_tasks: BackgroundTasks,
):
    organizer = crud_organizer.create_organizer(
        db=db,
        request=payload,
        firm_id=firm.id,
    )

    log_event(
        firm_id=firm.id,
        event_type="tax_organizer.sent",
        entity_type="tax_organizer",
        entity_id=organizer.id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "client_id": str(payload.client_id),
            "engagement_id": str(payload.engagement_id),
            "template_id": str(payload.template_id),
            "tax_year": organizer.tax_year,
        }
    )

    write_audit_log(
        db=db,
        firm_id=firm.id,
        actor_id=current_user_id,
        action="tax_organizer.sent",
        entity_type="tax_organizer",
        entity_id=organizer.id,
    )

    await emit_event(
        event=TriggerEvent.doc_request_created,  # reuse closest event
        payload={
            "firm_id": str(firm.id),
            "engagement_id": str(engagement.id),
            "client_id": str(client.id),
            "organizer_id": str(organizer.id),
            "tax_year": organizer.tax_year,
        },
        background_tasks=background_tasks,
    )

    try:
        if client.email:
            from app.services import portal_magic_link
            from app.core.config import get_settings
            settings = get_settings()

            _, raw_token = portal_magic_link.generate_magic_link(
                client_id=client.id,
                firm_id=firm.id,
                expiry_hours=72,
                db=db,
            )
            redirect_path = f"/portal?tab=organizer&organizer_id={organizer.id}"
            magic_url = (
                f"{settings.FRONTEND_URL}/portal/auth"
                f"?token={raw_token}"
                f"&redirect={quote(redirect_path, safe='')}"
            )
            firm_name = firm.name
            email_settings = EmailService.get_firm_email_settings(firm)
            html_body = (
                f"<p>Hi {client.name},</p>"
                f"<p>{firm_name} has sent you a tax organizer to fill out. "
                f"Click the link below to open it and get started. No login or password required "
                f"-- the link is your access.</p>"
                f"<p><a href='{magic_url}' style='display:inline-block;"
                f"padding:10px 20px;background:#1F3148;color:#ffffff;"
                f"text-decoration:none;border-radius:6px;font-weight:600;"
                f"font-size:14px;'>Open My Tax Organizer</a></p>"
                f"<p style='color:#6B7280;font-size:12px;'>This link expires "
                f"in 72 hours and can only be used once. If you need a new link, "
                f"contact {firm_name}.</p>"
            )
            EmailService._send_raw(
                client.email,
                f"Your {organizer.tax_year} tax organizer from {firm.name}",
                html_body,
                firm.name,
                reply_to=email_settings.get("reply_to"),
                display_name=email_settings.get("display_name"),
                sending_domain=email_settings.get("sending_domain"),
            )
    except Exception as e:
        logger.error(
            "Auto magic link email failed on organizer creation: organizer_id=%s error=%s",
            organizer.id, str(e)
        )

    return organizer


def send_organizer_magic_link(
    *,
    db: Session,
    organizer,
    organizer_id,
    client,
    firm,
    current_user_id,
):
    from app.services import portal_magic_link
    from app.core.config import get_settings
    settings = get_settings()

    _, raw_token = portal_magic_link.generate_magic_link(
        client_id=client.id,
        firm_id=firm.id,
        expiry_hours=72,
        db=db,
    )

    redirect_path = f"/portal?tab=organizer&organizer_id={organizer_id}"
    magic_url = (
        f"{settings.FRONTEND_URL}/portal/auth"
        f"?token={raw_token}"
        f"&redirect={quote(redirect_path, safe='')}"
    )

    firm_name = firm.name
    email_settings = EmailService.get_firm_email_settings(firm)

    html_body = (
        f"<p>Hi {client.name},</p>"
        f"<p>{firm_name} has sent you a tax organizer to complete. "
        f"Click the link below to open it. No login or password required "
        f"-- the link is your access.</p>"
        f"<p><a href='{magic_url}' style='display:inline-block;"
        f"padding:10px 20px;background:#1F3148;color:#ffffff;"
        f"text-decoration:none;border-radius:6px;font-weight:600;"
        f"font-size:14px;'>Open My Tax Organizer</a></p>"
        f"<p style='color:#6B7280;font-size:12px;'>This link expires "
        f"in 72 hours and can only be used once. If you need a new link, "
        f"contact {firm_name}.</p>"
    )

    try:
        EmailService._send_raw(
            to=client.email,
            subject=f"Your tax organizer from {firm_name}",
            html_body=html_body,
            firm_name=firm_name,
            reply_to=email_settings.get("reply_to"),
            display_name=email_settings.get("display_name"),
            sending_domain=email_settings.get("sending_domain"),
        )
    except Exception as e:
        logger.error(
            "Organizer magic link email failed: organizer_id=%s error=%s",
            organizer_id, str(e)
        )
        raise HTTPException(
            status_code=500,
            detail="Failed to send email. Please try again."
        )

    log_event(
        firm_id=firm.id,
        event_type="tax_organizer.link_sent",
        entity_type="tax_organizer",
        entity_id=organizer_id,
        actor_type="staff",
        actor_id=current_user_id,
        metadata={
            "client_id": str(client.id),
            "delivery_method": "magic_link_email",
        }
    )

    return {"sent": True, "expires_hours": 72}


def seed_firm_organizer_templates(firm_id: UUID, db: Session) -> int:
    """
    Seed the three default tax organizer templates for a new firm.
    Called from firms.py during firm creation, alongside seed_firm_presets.
    Returns the number of templates created.
    """
    templates = _get_default_templates(firm_id)
    for t in templates:
        db.add(TaxOrganizerTemplate(**t))
    db.commit()
    return len(templates)


def _get_default_templates(firm_id: UUID) -> list[dict]:
    now = datetime.now(timezone.utc)
    return [
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Individual Tax Organizer (1040)",
            "organizer_type": "individual",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
            "sections": [
                {
                    "id": "personal_info",
                    "title": "Personal Information",
                    "description": "Please confirm or update your personal details.",
                    "questions": [
                        {"id": "filing_status", "label": "Filing status", "type": "select",
                         "required": True, "options": ["Single", "Married Filing Jointly",
                         "Married Filing Separately", "Head of Household", "Qualifying Widow(er)"]},
                        {"id": "address_changed", "label": "Did your address change this year?",
                         "type": "boolean", "required": True},
                        {"id": "new_address", "label": "If yes, new address",
                         "type": "text", "required": False},
                        {"id": "phone", "label": "Best phone number",
                         "type": "text", "required": False},
                    ]
                },
                {
                    "id": "dependents",
                    "title": "Dependents",
                    "description": "List anyone you supported financially this year.",
                    "questions": [
                        {"id": "has_dependents", "label": "Do you have any dependents?",
                         "type": "boolean", "required": True},
                        {"id": "dependents_list",
                         "label": "List each dependent (name, relationship, date of birth)",
                         "type": "textarea", "required": False},
                        {"id": "dependent_changes",
                         "label": "Any changes to dependents from last year?",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "income",
                    "title": "Income",
                    "description": "Tell us about your income sources this year.",
                    "questions": [
                        {"id": "w2_employers",
                         "label": "List all W-2 employers (name and approximate wages)",
                         "type": "textarea", "required": False},
                        {"id": "self_employment",
                         "label": "Did you have any self-employment or freelance income?",
                         "type": "boolean", "required": True},
                        {"id": "self_employment_detail",
                         "label": "If yes, describe the business and approximate net income",
                         "type": "textarea", "required": False},
                        {"id": "investment_income",
                         "label": "Did you receive interest, dividends, or sell investments?",
                         "type": "boolean", "required": True},
                        {"id": "retirement_distributions",
                         "label": "Did you take any retirement account distributions (IRA, 401k)?",
                         "type": "boolean", "required": True},
                        {"id": "rental_income",
                         "label": "Did you receive any rental income?",
                         "type": "boolean", "required": True},
                        {"id": "other_income",
                         "label": "Any other income not listed above?",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "deductions",
                    "title": "Deductions & Credits",
                    "description": "Help us identify deductions you may qualify for.",
                    "questions": [
                        {"id": "home_ownership",
                         "label": "Did you pay mortgage interest or property taxes?",
                         "type": "boolean", "required": True},
                        {"id": "charitable_contributions",
                         "label": "Did you make any charitable donations?",
                         "type": "boolean", "required": True},
                        {"id": "charitable_amount",
                         "label": "If yes, approximate total amount donated",
                         "type": "number", "required": False},
                        {"id": "medical_expenses",
                         "label": "Did you have significant unreimbursed medical expenses?",
                         "type": "boolean", "required": True},
                        {"id": "student_loan_interest",
                         "label": "Did you pay student loan interest?",
                         "type": "boolean", "required": True},
                        {"id": "childcare_expenses",
                         "label": "Did you pay for childcare or dependent care?",
                         "type": "boolean", "required": True},
                        {"id": "education_expenses",
                         "label": "Did you pay tuition or education expenses?",
                         "type": "boolean", "required": True},
                    ]
                },
                {
                    "id": "life_events",
                    "title": "Life Events",
                    "description": "Major life events often affect your taxes.",
                    "questions": [
                        {"id": "married_divorced",
                         "label": "Did you get married or divorced this year?",
                         "type": "boolean", "required": True},
                        {"id": "new_child",
                         "label": "Did you have or adopt a child?",
                         "type": "boolean", "required": True},
                        {"id": "bought_sold_home",
                         "label": "Did you buy or sell a home?",
                         "type": "boolean", "required": True},
                        {"id": "started_business",
                         "label": "Did you start or close a business?",
                         "type": "boolean", "required": True},
                        {"id": "other_life_events",
                         "label": "Any other significant life events we should know about?",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "additional_info",
                    "title": "Additional Information",
                    "description": "Anything else that might be relevant.",
                    "questions": [
                        {"id": "foreign_accounts",
                         "label": "Did you have any foreign bank accounts or assets?",
                         "type": "boolean", "required": True},
                        {"id": "irs_notices",
                         "label": "Did you receive any IRS or state tax notices this year?",
                         "type": "boolean", "required": True},
                        {"id": "additional_notes",
                         "label": "Anything else you'd like us to know?",
                         "type": "textarea", "required": False},
                    ]
                },
            ]
        },
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Business Tax Organizer (1120 / 1065 / 1120S)",
            "organizer_type": "business",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
            "sections": [
                {
                    "id": "business_info",
                    "title": "Business Information",
                    "description": "Confirm your business details for this tax year.",
                    "questions": [
                        {"id": "legal_name", "label": "Legal business name",
                         "type": "text", "required": True},
                        {"id": "ein", "label": "Employer Identification Number (EIN)",
                         "type": "text", "required": True},
                        {"id": "entity_type",
                         "label": "Entity type",
                         "type": "select", "required": True,
                         "options": ["S-Corp (1120S)", "C-Corp (1120)",
                                     "Partnership (1065)", "LLC (multi-member)"]},
                        {"id": "fiscal_year_end",
                         "label": "Fiscal year end date",
                         "type": "text", "required": True},
                        {"id": "business_address_changed",
                         "label": "Did your business address change?",
                         "type": "boolean", "required": True},
                    ]
                },
                {
                    "id": "income_revenue",
                    "title": "Income & Revenue",
                    "questions": [
                        {"id": "gross_revenue",
                         "label": "Approximate gross revenue for the year",
                         "type": "number", "required": True},
                        {"id": "revenue_sources",
                         "label": "Primary revenue sources (describe briefly)",
                         "type": "textarea", "required": False},
                        {"id": "other_income",
                         "label": "Any other income (interest, gains, etc.)?",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "expenses",
                    "title": "Expenses",
                    "questions": [
                        {"id": "payroll_total",
                         "label": "Total payroll / compensation paid to employees",
                         "type": "number", "required": False},
                        {"id": "contractor_payments",
                         "label": "Total payments to contractors (1099 recipients)",
                         "type": "number", "required": False},
                        {"id": "rent_or_lease",
                         "label": "Did you pay rent or lease for office/equipment?",
                         "type": "boolean", "required": True},
                        {"id": "vehicle_use",
                         "label": "Did you use any vehicles for business purposes?",
                         "type": "boolean", "required": True},
                        {"id": "home_office",
                         "label": "Did any owners work from a home office?",
                         "type": "boolean", "required": True},
                        {"id": "major_purchases",
                         "label": "Any major asset purchases (equipment, computers, etc.)?",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "ownership_changes",
                    "title": "Ownership & Structure",
                    "questions": [
                        {"id": "ownership_changed",
                         "label": "Did ownership percentages change this year?",
                         "type": "boolean", "required": True},
                        {"id": "new_owners",
                         "label": "Were any new owners added or existing owners removed?",
                         "type": "boolean", "required": True},
                        {"id": "distributions",
                         "label": "Were any distributions made to owners?",
                         "type": "boolean", "required": True},
                        {"id": "distributions_amount",
                         "label": "If yes, total amount distributed",
                         "type": "number", "required": False},
                    ]
                },
                {
                    "id": "additional_info",
                    "title": "Additional Information",
                    "questions": [
                        {"id": "irs_notices",
                         "label": "Did the business receive any IRS or state notices?",
                         "type": "boolean", "required": True},
                        {"id": "bank_accounts_changed",
                         "label": "Did business bank accounts change?",
                         "type": "boolean", "required": True},
                        {"id": "additional_notes",
                         "label": "Anything else we should know?",
                         "type": "textarea", "required": False},
                    ]
                },
            ]
        },
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Rental Property Organizer",
            "organizer_type": "rental",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
            "sections": [
                {
                    "id": "property_info",
                    "title": "Property Information",
                    "questions": [
                        {"id": "property_address",
                         "label": "Property address",
                         "type": "text", "required": True},
                        {"id": "ownership_percentage",
                         "label": "Your ownership percentage",
                         "type": "number", "required": True},
                        {"id": "property_type",
                         "label": "Property type",
                         "type": "select", "required": True,
                         "options": ["Single family", "Multi-family", "Condo/Coop",
                                     "Commercial", "Vacation/short-term rental"]},
                        {"id": "days_rented",
                         "label": "Number of days rented this year",
                         "type": "number", "required": True},
                        {"id": "days_personal_use",
                         "label": "Number of days used personally",
                         "type": "number", "required": True},
                    ]
                },
                {
                    "id": "rental_income",
                    "title": "Rental Income",
                    "questions": [
                        {"id": "gross_rents",
                         "label": "Total gross rents collected",
                         "type": "number", "required": True},
                        {"id": "security_deposits_kept",
                         "label": "Any security deposits kept (counted as income)?",
                         "type": "number", "required": False},
                    ]
                },
                {
                    "id": "rental_expenses",
                    "title": "Rental Expenses",
                    "questions": [
                        {"id": "mortgage_interest",
                         "label": "Mortgage interest paid",
                         "type": "number", "required": False},
                        {"id": "property_taxes",
                         "label": "Property taxes paid",
                         "type": "number", "required": False},
                        {"id": "insurance",
                         "label": "Insurance premiums paid",
                         "type": "number", "required": False},
                        {"id": "repairs_maintenance",
                         "label": "Repairs and maintenance costs",
                         "type": "number", "required": False},
                        {"id": "property_management",
                         "label": "Property management fees",
                         "type": "number", "required": False},
                        {"id": "utilities_paid",
                         "label": "Utilities paid by you (not tenant)",
                         "type": "number", "required": False},
                        {"id": "other_expenses",
                         "label": "Other rental expenses",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "property_changes",
                    "title": "Property Changes",
                    "questions": [
                        {"id": "improvements",
                         "label": "Any capital improvements made (not repairs)?",
                         "type": "textarea", "required": False},
                        {"id": "purchased_this_year",
                         "label": "Was this property purchased this year?",
                         "type": "boolean", "required": True},
                        {"id": "sold_this_year",
                         "label": "Was this property sold this year?",
                         "type": "boolean", "required": True},
                        {"id": "sale_price",
                         "label": "If sold, sale price",
                         "type": "number", "required": False},
                    ]
                },
            ]
        },
        # ── Template 4 — Estate & Trust (1041) ────────────────────────────────
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Estate & Trust Return (1041)",
            "organizer_type": "custom",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
            "sections": [
                {
                    "id": "estate_trust_info",
                    "title": "Estate / Trust Information",
                    "questions": [
                        {"id": "legal_name_estate",
                         "label": "Legal name of estate or trust",
                         "type": "text", "required": True},
                        {"id": "ein_estate",
                         "label": "EIN of estate or trust",
                         "type": "text", "required": True},
                        {"id": "death_or_creation_date",
                         "label": "Date of death or trust creation",
                         "type": "text", "required": True},
                        {"id": "estate_or_trust_type",
                         "label": "Type: Estate or Trust",
                         "type": "select", "required": True,
                         "options": ["Estate", "Trust"]},
                        {"id": "fiscal_year_end_estate",
                         "label": "Fiscal year end",
                         "type": "text", "required": False},
                    ]
                },
                {
                    "id": "fiduciary_info",
                    "title": "Fiduciary Information",
                    "questions": [
                        {"id": "fiduciary_name",
                         "label": "Fiduciary name",
                         "type": "text", "required": True},
                        {"id": "fiduciary_address",
                         "label": "Fiduciary address",
                         "type": "text", "required": False},
                        {"id": "fiduciary_phone",
                         "label": "Fiduciary phone",
                         "type": "text", "required": False},
                        {"id": "fiduciary_is_executor",
                         "label": "Is fiduciary also the executor?",
                         "type": "boolean", "required": False},
                    ]
                },
                {
                    "id": "estate_income",
                    "title": "Income",
                    "questions": [
                        {"id": "interest_income",
                         "label": "Interest income",
                         "type": "number", "required": False},
                        {"id": "dividend_income",
                         "label": "Dividend income",
                         "type": "number", "required": False},
                        {"id": "business_income",
                         "label": "Business income",
                         "type": "number", "required": False},
                        {"id": "capital_gains_losses",
                         "label": "Capital gains or losses",
                         "type": "boolean", "required": False},
                        {"id": "rental_income_estate",
                         "label": "Rental income",
                         "type": "number", "required": False},
                        {"id": "other_income_description",
                         "label": "Other income description",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "estate_deductions",
                    "title": "Deductions",
                    "questions": [
                        {"id": "fiduciary_fees",
                         "label": "Fiduciary fees paid",
                         "type": "number", "required": False},
                        {"id": "attorney_accounting_fees",
                         "label": "Attorney and accounting fees",
                         "type": "number", "required": False},
                        {"id": "charitable_contributions_estate",
                         "label": "Charitable contributions",
                         "type": "boolean", "required": False},
                        {"id": "other_deductions",
                         "label": "Other deductions",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "distributions",
                    "title": "Distributions",
                    "questions": [
                        {"id": "distributions_made",
                         "label": "Were distributions made to beneficiaries?",
                         "type": "boolean", "required": True},
                        {"id": "total_distributions",
                         "label": "Total distributions made",
                         "type": "number", "required": False},
                        {"id": "beneficiary_count",
                         "label": "Number of beneficiaries",
                         "type": "number", "required": False},
                    ]
                },
            ]
        },
        # ── Template 5 — Non-Profit (990) ─────────────────────────────────────
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Non-Profit Return (990)",
            "organizer_type": "custom",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
            "sections": [
                {
                    "id": "org_info",
                    "title": "Organization Information",
                    "questions": [
                        {"id": "org_legal_name",
                         "label": "Legal name of organization",
                         "type": "text", "required": True},
                        {"id": "org_ein",
                         "label": "EIN",
                         "type": "text", "required": True},
                        {"id": "form_990_type",
                         "label": "Type of 990: 990, 990-EZ, or 990-N",
                         "type": "select", "required": True,
                         "options": ["990", "990-EZ", "990-N"]},
                        {"id": "mission_statement",
                         "label": "Mission statement",
                         "type": "textarea", "required": True},
                        {"id": "website",
                         "label": "Website",
                         "type": "text", "required": False},
                    ]
                },
                {
                    "id": "governance",
                    "title": "Governance",
                    "questions": [
                        {"id": "voting_board_members",
                         "label": "Number of voting board members",
                         "type": "number", "required": True},
                        {"id": "independent_board_members",
                         "label": "Number of independent board members",
                         "type": "number", "required": False},
                        {"id": "conflict_of_interest_policy",
                         "label": "Did the organization have a conflict of interest policy?",
                         "type": "boolean", "required": False},
                        {"id": "board_meeting_minutes",
                         "label": "Were board meeting minutes documented?",
                         "type": "boolean", "required": False},
                    ]
                },
                {
                    "id": "org_revenue",
                    "title": "Revenue",
                    "questions": [
                        {"id": "total_contributions_grants",
                         "label": "Total contributions and grants",
                         "type": "number", "required": True},
                        {"id": "program_service_revenue",
                         "label": "Program service revenue",
                         "type": "number", "required": False},
                        {"id": "investment_income_org",
                         "label": "Investment income",
                         "type": "number", "required": False},
                        {"id": "other_revenue",
                         "label": "Other revenue",
                         "type": "number", "required": False},
                    ]
                },
                {
                    "id": "org_expenses",
                    "title": "Expenses",
                    "questions": [
                        {"id": "program_service_expenses",
                         "label": "Total program service expenses",
                         "type": "number", "required": True},
                        {"id": "management_general_expenses",
                         "label": "Management and general expenses",
                         "type": "number", "required": False},
                        {"id": "fundraising_expenses",
                         "label": "Fundraising expenses",
                         "type": "number", "required": False},
                    ]
                },
                {
                    "id": "program_services",
                    "title": "Program Services",
                    "questions": [
                        {"id": "largest_program_services",
                         "label": "Describe your three largest program services",
                         "type": "textarea", "required": True},
                        {"id": "total_volunteers",
                         "label": "Total number of volunteers",
                         "type": "number", "required": False},
                        {"id": "total_employees",
                         "label": "Total number of employees",
                         "type": "number", "required": False},
                    ]
                },
            ]
        },
        # ── Template 6 — Payroll & Bookkeeping ────────────────────────────────
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "Payroll & Bookkeeping Engagement",
            "organizer_type": "custom",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
            "sections": [
                {
                    "id": "pb_business_info",
                    "title": "Business Information",
                    "questions": [
                        {"id": "business_legal_name",
                         "label": "Business legal name",
                         "type": "text", "required": True},
                        {"id": "business_ein",
                         "label": "EIN",
                         "type": "text", "required": True},
                        {"id": "state_of_incorporation",
                         "label": "State of incorporation",
                         "type": "text", "required": False},
                        {"id": "employee_count",
                         "label": "Number of employees",
                         "type": "number", "required": True},
                        {"id": "pay_frequency",
                         "label": "Pay frequency",
                         "type": "select", "required": True,
                         "options": ["Weekly", "Biweekly", "Semi-monthly", "Monthly"]},
                    ]
                },
                {
                    "id": "payroll_details",
                    "title": "Payroll Details",
                    "questions": [
                        {"id": "has_hourly_employees",
                         "label": "Do you have hourly employees?",
                         "type": "boolean", "required": False},
                        {"id": "has_salaried_employees",
                         "label": "Do you have salaried employees?",
                         "type": "boolean", "required": False},
                        {"id": "offers_health_insurance",
                         "label": "Do you offer health insurance?",
                         "type": "boolean", "required": False},
                        {"id": "offers_retirement_benefits",
                         "label": "Do you offer retirement benefits?",
                         "type": "boolean", "required": False},
                        {"id": "multi_state_employees",
                         "label": "Do you have employees in multiple states?",
                         "type": "boolean", "required": False},
                    ]
                },
                {
                    "id": "bookkeeping_details",
                    "title": "Bookkeeping Details",
                    "questions": [
                        {"id": "accounting_software",
                         "label": "Accounting software currently used",
                         "type": "text", "required": False},
                        {"id": "bank_accounts_count",
                         "label": "Bank accounts to reconcile",
                         "type": "number", "required": False},
                        {"id": "credit_card_accounts",
                         "label": "Credit card accounts to reconcile",
                         "type": "number", "required": False},
                        {"id": "monthly_transactions",
                         "label": "Approximate monthly transactions",
                         "type": "number", "required": False},
                        {"id": "needs_sales_tax_filing",
                         "label": "Do you need sales tax filing?",
                         "type": "boolean", "required": False},
                    ]
                },
                {
                    "id": "reporting_needs",
                    "title": "Reporting Needs",
                    "questions": [
                        {"id": "financial_statements_frequency",
                         "label": "How often do you need financial statements?",
                         "type": "select", "required": False,
                         "options": ["Monthly", "Quarterly", "Annually"]},
                        {"id": "needs_cash_flow_reports",
                         "label": "Do you need cash flow reports?",
                         "type": "boolean", "required": False},
                        {"id": "needs_budget_reports",
                         "label": "Do you need budget vs actual reports?",
                         "type": "boolean", "required": False},
                        {"id": "other_reporting_needs",
                         "label": "Any other reporting needs",
                         "type": "textarea", "required": False},
                    ]
                },
            ]
        },
        # ── Template 7 — New Client Intake ────────────────────────────────────
        {
            "id": uuid4(),
            "firm_id": firm_id,
            "name": "New Client Intake",
            "organizer_type": "custom",
            "is_default": True,
            "created_at": now,
            "updated_at": now,
            "sections": [
                {
                    "id": "personal_info",
                    "title": "Personal Information",
                    "questions": [
                        {"id": "full_legal_name",
                         "label": "Full legal name",
                         "type": "text", "required": True},
                        {"id": "date_of_birth",
                         "label": "Date of birth",
                         "type": "text", "required": True},
                        {"id": "ssn_last4",
                         "label": "Social Security Number last 4 digits",
                         "type": "text", "required": False},
                        {"id": "current_address",
                         "label": "Current address",
                         "type": "text", "required": True},
                        {"id": "phone_number",
                         "label": "Phone number",
                         "type": "text", "required": True},
                        {"id": "email_address",
                         "label": "Email address",
                         "type": "text", "required": True},
                        {"id": "preferred_contact_method",
                         "label": "Preferred contact method",
                         "type": "select", "required": False,
                         "options": ["Email", "Phone", "Text"]},
                    ]
                },
                {
                    "id": "filing_info",
                    "title": "Filing Information",
                    "questions": [
                        {"id": "filing_status",
                         "label": "Filing status",
                         "type": "select", "required": True,
                         "options": ["Single", "Married Filing Jointly",
                                     "Married Filing Separately",
                                     "Head of Household", "Qualifying Widow(er)"]},
                        {"id": "has_dependents",
                         "label": "Do you have dependents?",
                         "type": "boolean", "required": False},
                        {"id": "dependents_ssn_list",
                         "label": "If yes, list dependents and their SSN last 4",
                         "type": "textarea", "required": False},
                        {"id": "filing_status_changed",
                         "label": "Did your filing status change this year?",
                         "type": "boolean", "required": False},
                    ]
                },
                {
                    "id": "prior_tax_history",
                    "title": "Prior Tax History",
                    "questions": [
                        {"id": "filed_last_year",
                         "label": "Did you file a tax return last year?",
                         "type": "boolean", "required": True},
                        {"id": "prior_preparer",
                         "label": "Who prepared your last return?",
                         "type": "text", "required": False},
                        {"id": "has_prior_return_copy",
                         "label": "Do you have a copy of your prior year return?",
                         "type": "boolean", "required": False},
                        {"id": "owes_back_taxes",
                         "label": "Do you owe any back taxes?",
                         "type": "boolean", "required": False},
                        {"id": "ever_audited",
                         "label": "Have you ever been audited?",
                         "type": "boolean", "required": False},
                    ]
                },
                {
                    "id": "income_sources",
                    "title": "Income Sources",
                    "questions": [
                        {"id": "has_w2_income",
                         "label": "W-2 employment income?",
                         "type": "boolean", "required": False},
                        {"id": "has_self_employment_income",
                         "label": "Self-employment income?",
                         "type": "boolean", "required": False},
                        {"id": "has_investment_income",
                         "label": "Investment income?",
                         "type": "boolean", "required": False},
                        {"id": "has_rental_income",
                         "label": "Rental income?",
                         "type": "boolean", "required": False},
                        {"id": "has_retirement_distributions",
                         "label": "Retirement distributions?",
                         "type": "boolean", "required": False},
                        {"id": "has_social_security_income",
                         "label": "Social Security income?",
                         "type": "boolean", "required": False},
                        {"id": "other_income_sources",
                         "label": "Any other income sources?",
                         "type": "textarea", "required": False},
                    ]
                },
                {
                    "id": "how_did_you_find_us",
                    "title": "How Did You Find Us",
                    "questions": [
                        {"id": "referral_source",
                         "label": "How did you hear about our firm?",
                         "type": "select", "required": False,
                         "options": ["Referral", "Google Search", "Social Media",
                                     "Walking By", "Other"]},
                        {"id": "referral_name",
                         "label": "If referral, who referred you?",
                         "type": "text", "required": False},
                        {"id": "what_can_we_help",
                         "label": "What are you hoping we can help you with?",
                         "type": "textarea", "required": False},
                    ]
                },
            ]
        },
    ]
