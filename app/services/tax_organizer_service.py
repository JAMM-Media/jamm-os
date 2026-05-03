# app/services/tax_organizer_service.py
"""
Tax organizer service — seeding and business logic.

Three default templates are seeded on firm creation:
- Individual (1040) — personal income, dependents, deductions, life events
- Business (1120/1065/1120S) — business income, expenses, payroll, assets
- Rental Property — rental income, expenses, property details
"""

from uuid import UUID, uuid4
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.tax_organizer import TaxOrganizerTemplate
from app.services.audit_service import write_audit_log


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
    ]
