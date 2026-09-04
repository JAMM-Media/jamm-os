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

import argparse
import os
import sys
import urllib.parse

# --- Environment guard (fail closed) ----------------------------------------
# This is the first executable statement in the file after the four stdlib
# imports it needs (argparse, os, sys, urllib.parse). Nothing else -- no
# other stdlib import, no third-party import, no app.* import -- may precede
# it. Reading the raw dotenv sources directly, before any app.* import
# happens, is what lets a missing DATABASE_URL be handled by this guard
# instead of by an unhandled ValidationError from pydantic.
#
# Written as "refuse unless positively proven non-production", not "refuse if
# production": the allowlist below is the only way to proceed normally. Every
# other case -- unrecognized host, missing DATABASE_URL, unparseable
# DATABASE_URL -- is treated as production and needs both --allow-production
# and a typed confirmation. Nothing here reads an ENVIRONMENT/env variable.
ALLOWLISTED_DB_HOSTS = {"localhost", "127.0.0.1"}


def _resolve_database_host(database_url: str | None) -> str:
    """Return a printable host token. Missing or unparseable input resolves to
    an explicit sentinel string rather than None, so the guard always has a
    concrete token to print and to require back as the typed confirmation."""
    if not database_url:
        return "(DATABASE_URL not set)"
    try:
        hostname = urllib.parse.urlparse(database_url).hostname
    except Exception:
        hostname = None
    if not hostname:
        return "(DATABASE_URL unparseable)"
    return hostname


def _database_url_from_dotenv_files() -> tuple[str | None, str | None]:
    """Reproduces Settings.model_config's env_file=('.env.local', '.env')
    resolution exactly: pydantic-settings loads .env.local first, then loads
    .env, and a key defined in .env overrides the same key from .env.local
    (confirmed empirically -- later files in the tuple win on conflict, not
    earlier ones). Both files are read relative to the current working
    directory, exactly like pydantic-settings itself -- there is no
    module-relative resolution here or in Settings.

    Returns (value, source_label), where source_label is exactly '.env' or
    '.env.local' -- whichever file the value actually came from -- so the
    guard can report it. Uses python-dotenv directly, which is already a
    project dependency (see tests/conftest.py), so this never has to import
    app.* just to see what host the app is about to connect to."""
    from dotenv import dotenv_values

    env_values = dotenv_values(".env")
    if env_values.get("DATABASE_URL"):
        return env_values["DATABASE_URL"], ".env"

    local_values = dotenv_values(".env.local")
    if local_values.get("DATABASE_URL"):
        return local_values["DATABASE_URL"], ".env.local"

    return None, None


def _resolve_effective_database_url() -> tuple[str | None, str | None, str | None]:
    """Returns (env_var_value, dotenv_value, dotenv_source_label) separately,
    unmerged, so the guard can detect disagreement between the shell
    environment and a dotenv file instead of silently trusting whichever
    pydantic-settings would pick, and can report exactly which dotenv file a
    value came from."""
    dotenv_value, dotenv_source = _database_url_from_dotenv_files()
    return os.environ.get("DATABASE_URL"), dotenv_value, dotenv_source


def _enforce_environment_guard(allow_production_flag: bool) -> None:
    env_var_url, dotenv_url, dotenv_source = _resolve_effective_database_url()
    cwd = os.getcwd()

    # Compare resolved HOSTS, not raw URLs: a dev .env and a shell-injected
    # DATABASE_URL routinely differ in port, database name, or credentials
    # while pointing at the same safe host. A host mismatch is the actual
    # danger: it means this guard cannot be sure which database traffic will
    # really hit. This check is unconditional.
    if env_var_url and dotenv_url:
        env_var_host = _resolve_database_host(env_var_url)
        dotenv_host = _resolve_database_host(dotenv_url)
        if env_var_host != dotenv_host:
            print(
                "ABORT: DATABASE_URL resolves to different hosts in the shell "
                "environment vs a dotenv file. Refusing to guess which one the "
                "application will actually use."
            )
            print(f"  shell environment host: {env_var_host}")
            print(f"  {dotenv_source} host:   {dotenv_host}")
            print(f"  working directory: {cwd}")
            sys.exit(1)

    # Real process env vars take priority over both dotenv files in
    # pydantic-settings (confirmed empirically), so this is the same value
    # Settings().DATABASE_URL will actually resolve to.
    if env_var_url:
        database_url, source_label = env_var_url, "shell environment"
    elif dotenv_url:
        database_url, source_label = dotenv_url, dotenv_source
    else:
        database_url, source_label = None, None

    host = _resolve_database_host(database_url)
    if source_label:
        print(f"Target database host: {host} (source: {source_label})")
    else:
        print(f"Target database host: {host}")
    print(f"Working directory: {cwd}")

    if host in ALLOWLISTED_DB_HOSTS:
        return

    if not sys.stdin.isatty():
        print(
            f"ABORT: host '{host}' is not on the local allowlist "
            f"({sorted(ALLOWLISTED_DB_HOSTS)}) and stdin is not a TTY, so there is "
            "no operator available to type a confirmation. Refusing to proceed."
        )
        sys.exit(1)

    if not allow_production_flag:
        print(
            f"ABORT: host '{host}' is not on the local allowlist "
            f"({sorted(ALLOWLISTED_DB_HOSTS)}). Re-run with --allow-production and "
            "be ready to type the host back exactly to proceed."
        )
        sys.exit(1)

    print(f"This run targets '{host}', which is not a recognized local database.")
    typed = input(f"Type the host exactly to confirm ({host}): ")
    if typed != host:
        print("ABORT: typed confirmation did not match the target host.")
        sys.exit(1)

    print(f"Confirmed. Proceeding against '{host}'.")

if __name__ == "__main__":
    _arg_parser = argparse.ArgumentParser()
    _arg_parser.add_argument(
        "--allow-production",
        action="store_true",
        help=(
            "Required, together with a typed host confirmation, to run against any "
            "database host not on the local allowlist (localhost, 127.0.0.1)."
        ),
    )
    ARGS = _arg_parser.parse_args()
    _enforce_environment_guard(ARGS.allow_production)

# Everything below this line is safe to import: when run as a script, the
# guard above has already either aborted the process or positively confirmed
# the target host.

import uuid

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

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
