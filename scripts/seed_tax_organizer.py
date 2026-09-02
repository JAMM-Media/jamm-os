# scripts/seed_tax_organizer.py
"""
Creates one realistic TaxOrganizer instance for the demo portal client so the
rebuilt Tax Organizer page can be reviewed with real section data.

  CLIENT_ID = bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47
  FIRM_ID   = 185314c9-e702-4eab-8600-249848022206

Section completion mix:
  Personal Information -- Complete (all required questions answered)
  Income               -- In progress (w2_wages answered, has_self_employment not)
  Deductions           -- Not started
  Tax Payments         -- Not started
  Investments          -- Not started

Progress bar will show 1 of 5 sections complete (20%).

Responses are seeded in the real nested format: responses[section_id][question_id].
  This matches what the backend save endpoint (save_organizer_responses) stores and what
  the fixed PortalOrganizer.tsx getSectionStatus function reads.

Run from the project root:
    python scripts/seed_tax_organizer.py

Idempotent: skips if a 2024 organizer already exists for this client.
No server restart needed -- just refresh the browser after running.
"""

import sys
import os
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.tax_organizer import TaxOrganizer, TaxOrganizerTemplate

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
TAX_YEAR = 2024

SECTIONS = [
    {
        "id": "personal_info",
        "title": "Personal Information",
        "description": "Details about you and your family.",
        "questions": [
            {
                "id": "full_name",
                "label": "Full legal name",
                "type": "text",
                "required": True,
            },
            {
                "id": "ssn_last4",
                "label": "Last 4 digits of Social Security Number",
                "type": "text",
                "required": True,
            },
            {
                "id": "dob",
                "label": "Date of birth",
                "type": "text",
                "required": True,
            },
            {
                "id": "filing_status",
                "label": "Filing status",
                "type": "select",
                "required": True,
                "options": [
                    "Single",
                    "Married Filing Jointly",
                    "Married Filing Separately",
                    "Head of Household",
                ],
            },
            {
                "id": "address",
                "label": "Current home address",
                "type": "text",
                "required": False,
            },
        ],
    },
    {
        "id": "income",
        "title": "Income",
        "description": "Wages, salaries, tips, and other income.",
        "questions": [
            {
                "id": "w2_wages",
                "label": "Total W-2 wages (all employers combined)",
                "type": "number",
                "required": True,
            },
            {
                "id": "has_self_employment",
                "label": "Did you have any self-employment or freelance income?",
                "type": "boolean",
                "required": True,
            },
            {
                "id": "freelance_income",
                "label": "Freelance or self-employment income (if yes above)",
                "type": "number",
                "required": False,
            },
            {
                "id": "other_income_notes",
                "label": "Any other income to report? (rental, alimony, gambling, etc.)",
                "type": "textarea",
                "required": False,
            },
        ],
    },
    {
        "id": "deductions",
        "title": "Deductions",
        "description": "Tax deductions and adjustments.",
        "questions": [
            {
                "id": "mortgage_interest",
                "label": "Mortgage interest paid (from Form 1098)",
                "type": "number",
                "required": False,
            },
            {
                "id": "charitable_donations",
                "label": "Total charitable donations",
                "type": "number",
                "required": False,
            },
            {
                "id": "student_loan_interest",
                "label": "Student loan interest paid",
                "type": "number",
                "required": False,
            },
            {
                "id": "medical_expenses",
                "label": "Unreimbursed medical expenses",
                "type": "number",
                "required": False,
            },
        ],
    },
    {
        "id": "tax_payments",
        "title": "Tax Payments",
        "description": "Estimated tax payments and withholding.",
        "questions": [
            {
                "id": "federal_withheld",
                "label": "Federal income tax withheld (total from all W-2s and 1099s)",
                "type": "number",
                "required": True,
            },
            {
                "id": "state_withheld",
                "label": "State income tax withheld",
                "type": "number",
                "required": False,
            },
            {
                "id": "estimated_payments",
                "label": "Quarterly estimated tax payments made in 2024",
                "type": "number",
                "required": False,
            },
        ],
    },
    {
        "id": "investments",
        "title": "Investments",
        "description": "Interest, dividends, and investment income.",
        "questions": [
            {
                "id": "has_investments",
                "label": "Did you have any investment activity in 2024?",
                "type": "boolean",
                "required": True,
            },
            {
                "id": "capital_gains",
                "label": "Net capital gains or losses (approximate)",
                "type": "number",
                "required": False,
            },
            {
                "id": "dividend_income",
                "label": "Total dividend income",
                "type": "number",
                "required": False,
            },
            {
                "id": "interest_income",
                "label": "Total interest income",
                "type": "number",
                "required": False,
            },
        ],
    },
]

# Nested responses keyed by section_id -> question_id, matching the real backend format.
# Personal Information: all required answered -> Complete
# Income: w2_wages answered but has_self_employment missing -> In progress
# Deductions, Tax Payments, Investments: no answers -> Not started
RESPONSES = {
    "personal_info": {
        "full_name": "Jordan Demo",
        "ssn_last4": "1234",
        "dob": "1985-03-15",
        "filing_status": "Single",
        "address": "123 Main St, Springfield, MA 01101",
    },
    "income": {
        "w2_wages": "95000",
    },
}


def _get_section_state(section: dict, responses: dict) -> str:
    """Mirrors the getSectionStatus logic in PortalOrganizer.tsx."""
    section_responses = responses.get(section["id"], {})
    questions = section["questions"]
    answered = [q for q in questions if section_responses.get(q["id"], "").strip()]
    if not answered:
        return "Not started"
    required = [q for q in questions if q.get("required")]
    # Mirror the JS fix: when no questions are required, all must be answered.
    completion_set = required if required else questions
    if all(section_responses.get(q["id"], "").strip() for q in completion_set):
        return "Complete"
    return "In progress"


def _print_summary(organizer: TaxOrganizer, sections: list, responses: dict) -> None:
    print()
    print(f"Organizer id:  {organizer.id}")
    print(f"Tax year:      {organizer.tax_year}")
    print(f"Status:        {organizer.status}")
    print()
    print("Section states (as the portal page will render them):")
    for section in sections:
        state = _get_section_state(section, responses)
        print(f"  {section['title']:25s}  {state}")
    print()
    complete_count = sum(
        1 for s in sections if _get_section_state(s, responses) == "Complete"
    )
    pct = round(complete_count / len(sections) * 100) if sections else 0
    print(f"Progress bar:  {complete_count} of {len(sections)} complete ({pct}%)")


def main() -> None:
    db = SessionLocal()
    try:
        client = db.get(Client, CLIENT_ID)
        if not client:
            print(f"ERROR: Client {CLIENT_ID} not found. Run seed_portal_client.py first.")
            return

        # Reuse existing engagement or create a new one
        engagement = db.execute(
            select(Engagement).where(
                Engagement.client_id == CLIENT_ID,
                Engagement.firm_id == FIRM_ID,
            )
        ).scalars().first()

        if engagement:
            print(f"Using existing engagement: {engagement.name} (id: {engagement.id})")
        else:
            engagement = Engagement(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                name="2024 Individual Tax Return",
                status="active",
            )
            db.add(engagement)
            db.flush()
            print(f"Created engagement: {engagement.name} (id: {engagement.id})")

        # Idempotency check
        existing = db.execute(
            select(TaxOrganizer).where(
                TaxOrganizer.client_id == CLIENT_ID,
                TaxOrganizer.firm_id == FIRM_ID,
                TaxOrganizer.tax_year == TAX_YEAR,
            )
        ).scalars().first()

        if existing:
            print(f"Organizer for {TAX_YEAR} already exists -- skipping creation.")
            _print_summary(existing, SECTIONS, existing.responses or {})
            return

        # Create template
        template = TaxOrganizerTemplate(
            firm_id=FIRM_ID,
            name=f"{TAX_YEAR} Individual Tax Organizer",
            organizer_type="individual",
            sections=SECTIONS,
            is_default=False,
            is_active=True,
        )
        db.add(template)
        db.flush()
        print(f"Created template: {template.name} (id: {template.id})")

        # Create organizer with pre-seeded responses
        organizer = TaxOrganizer(
            firm_id=FIRM_ID,
            client_id=CLIENT_ID,
            engagement_id=engagement.id,
            template_id=template.id,
            tax_year=TAX_YEAR,
            status="in_progress",
            responses=RESPONSES,
            client_message=(
                "Your 2024 tax organizer is ready. Please complete all sections "
                "so we can prepare your return."
            ),
        )
        db.add(organizer)
        db.flush()
        print(f"Created organizer: tax year {TAX_YEAR} (id: {organizer.id})")

        db.commit()

        _print_summary(organizer, SECTIONS, RESPONSES)
        print("Done. Refresh the portal browser tab -- no server restart needed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
