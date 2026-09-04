# scripts/seed_additions.py

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
from datetime import date, datetime, timezone, timedelta, time as time_type
from decimal import Decimal

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.engagement import Engagement
from app.models.time_entry import TimeEntry
from app.models.engagement_letter_template import EngagementLetterTemplate
from app.core.security import get_password_hash
from app.core.enums import UserRole


def main():
    db = SessionLocal()
    try:
        # Find firm
        firm = db.execute(
            select(Firm).where(Firm.name == "Riverside Tax & Advisory")
        ).scalars().first()
        if not firm:
            print("ERROR: Riverside Tax & Advisory not found. Run seed_riverside_demo.py first.")
            return

        firm_id = firm.id
        today = date.today()
        now = datetime.now(timezone.utc)

        # Load users by current demofirm emails
        alex = db.execute(select(User).where(User.email == "admin@demofirm.com")).scalars().first()
        jordan = db.execute(select(User).where(User.email == "jordan@demofirm.com")).scalars().first()
        taylor = db.execute(select(User).where(User.email == "taylor@demofirm.com")).scalars().first()
        casey = db.execute(select(User).where(User.email == "casey@demofirm.com")).scalars().first()

        if not alex:
            print("ERROR: Could not find staff users. Check that seed_riverside_demo.py ran successfully.")
            return

        print(f"Found firm: {firm.name} ({firm_id})")

        # STEP 1 - Update staff emails to real login emails
        alex.email = "andrew@jammpx.com"
        alex.hashed_password = get_password_hash("Demo2026!")
        jordan.email = "ben@jammpx.com"
        jordan.hashed_password = get_password_hash("Demo2026!")
        taylor.email = "ben@mail.jammpx.com"
        taylor.hashed_password = get_password_hash("Demo2026!")
        if casey:
            casey.hashed_password = get_password_hash("Demo2026!")

        db.commit()
        # Refresh so we have current IDs for later steps
        db.refresh(alex)
        db.refresh(jordan)
        db.refresh(taylor)
        if casey:
            db.refresh(casey)
        print("Updated staff email logins.")

        # STEP 2: RETIRED August 15 2026. Fee schedule seeding removed.
        #
        # This wrote a 16 key fee_schedule object into firm.settings, and it was
        # the only code anywhere that populated that key with real content. The
        # key is now retired and all three writer endpoints refuse it with a 422,
        # so this step could no longer run through them even if it were kept.
        #
        # Fee data seeding moves to the pricing tables: the system owned
        # complexity catalog (flags, dimensions, unit menus, vocabularies) plus
        # the firm scoped pricing tables (service catalog entries, dimension
        # configs, tiers, option prices). Those rows are authored in the catalog
        # content session, which produces data and never migrations.
        #
        # Nothing later in this script depended on this step. STEP 3's letter
        # template uses {{fee_amount}}, which is a merge field filled in at send
        # time, not a value read from this blob.

        # STEP 3 - Add fourth engagement letter template (bookkeeping/recurring)
        existing_names = [
            t.name for t in db.execute(
                select(EngagementLetterTemplate).where(
                    EngagementLetterTemplate.firm_id == firm_id
                )
            ).scalars().all()
        ]

        if "Bookkeeping & Recurring Services Engagement Letter" not in existing_names:
            letter4 = EngagementLetterTemplate(
                firm_id=firm_id,
                name="Bookkeeping & Recurring Services Engagement Letter",
                engagement_type="bookkeeping_monthly",
                variable_fields=["client_name", "firm_name", "firm_owner_name", "fee_amount", "engagement_date"],
                body_html="""<p>Dear {{client_name}},</p>
<p>Thank you for engaging {{firm_name}} to provide ongoing bookkeeping and accounting services. This letter confirms the nature and terms of our recurring engagement, effective {{engagement_date}}.</p>
<h3>Scope of Services</h3>
<p>We will provide monthly bookkeeping services including transaction categorization, bank and credit card reconciliation, accounts receivable and payable tracking, payroll entry posting, and preparation of monthly financial statements (profit & loss and balance sheet). Services outside this scope, including tax preparation, audit representation, or financial projections, will be covered under a separate engagement.</p>
<h3>Your Responsibilities</h3>
<p>You agree to provide complete bank statements, credit card statements, and supporting documentation by the 10th of each month for the prior month's activity. Delays in providing records may result in delays in deliverables and may incur additional fees. You are responsible for the accuracy of all source documents provided.</p>
<h3>Monthly Fee</h3>
<p>Our monthly fee for bookkeeping services is {{fee_amount}}, billed on the first of each month. This fee covers the standard scope described above. Additional services will be billed at our standard hourly rate.</p>
<h3>Term and Termination</h3>
<p>This engagement continues on a month-to-month basis. Either party may terminate with 30 days written notice. Upon termination, all work product through the final month will be delivered and any outstanding fees will be due.</p>
<p>Please sign below to confirm your agreement to these terms.</p>
<p>Sincerely,<br>{{firm_owner_name}}<br>{{firm_name}}</p>""",
                is_active=True,
            )
            db.add(letter4)
            db.commit()
            print("Added bookkeeping engagement letter template.")
        else:
            print("Bookkeeping letter template already exists - skipped.")

        # STEP 4 - Add historical time entries so all timesheet tabs show data
        # Load active engagements
        engagements = db.execute(
            select(Engagement).where(
                Engagement.firm_id == firm_id,
                Engagement.is_active == True,
            )
        ).scalars().all()

        sarah_1040 = next((e for e in engagements if "Individual" in e.name and "Sarah" not in e.name or "1040" in e.name), engagements[0])
        # More reliable: find by engagement_type
        eng_1040s = [e for e in engagements if e.engagement_type == "tax_return_1040"]
        eng_1120 = next((e for e in engagements if e.engagement_type == "tax_return_1120"), engagements[0])
        eng_1120s = next((e for e in engagements if e.engagement_type == "tax_return_1120s"), engagements[0])
        eng_1041 = next((e for e in engagements if e.engagement_type == "tax_return_1041"), engagements[0])
        eng_book = next((e for e in engagements if e.engagement_type == "bookkeeping_monthly"), engagements[0])
        eng_adv = next((e for e in engagements if e.engagement_type == "tax_planning_advisory"), engagements[0])

        e1 = eng_1040s[0] if eng_1040s else engagements[0]
        e2 = eng_1040s[1] if len(eng_1040s) > 1 else e1

        def hist(engagement, user, description, activity, hours, days_ago, rate):
            entry_date = today - timedelta(days=days_ago)
            te = TimeEntry(
                firm_id=firm_id,
                engagement_id=engagement.id,
                user_id=user.id,
                description=description,
                hours=Decimal(str(hours)),
                hourly_rate=Decimal(str(rate)),
                is_billable=True,
                is_billed=True,
                date=entry_date,
                activity_type=activity,
                is_submitted=True,
                submitted_at=datetime.combine(entry_date, time_type(8, 0), tzinfo=timezone.utc),
                is_approved=True,
                approved_at=datetime.combine(entry_date, time_type(8, 0), tzinfo=timezone.utc) + timedelta(hours=16),
                approved_by_id=alex.id,
            )
            return te

        historical = []

        # 2 months ago (days 45-75)
        historical += [
            hist(e1, alex, "Prior year return analysis", "Tax Preparation", 2.0, 65, 200),
            hist(eng_1120, taylor, "Q3 bookkeeping catch-up", "Document Review", 3.0, 68, 150),
            hist(eng_1120s, alex, "S-Corp mid-year planning", "Research", 1.5, 70, 200),
            hist(eng_1041, jordan, "Trust document review", "Document Review", 2.0, 62, 175),
            hist(e2, jordan, "Client intake call", "Client Meeting", 1.0, 55, 175),
            hist(eng_book, casey, "April bookkeeping close", "Tax Preparation", 2.0, 58, 125),
            hist(e1, taylor, "Document collection follow-up", "Admin", 1.0, 63, 150),
            hist(eng_1120s, casey, "Payroll reconciliation", "Document Review", 1.5, 60, 125),
        ]

        # 3 months ago (days 76-105)
        historical += [
            hist(e1, alex, "2023 tax planning session", "Tax Preparation", 2.5, 95, 200),
            hist(eng_1120, taylor, "Depreciation schedule analysis", "Research", 2.0, 90, 150),
            hist(eng_1041, jordan, "Trust beneficiary distribution analysis", "Tax Preparation", 3.0, 85, 175),
            hist(e2, jordan, "Document request follow-up", "Client Communication", 0.5, 92, 175),
            hist(eng_1120s, alex, "Officer compensation review", "Research", 1.0, 88, 200),
            hist(eng_1120, casey, "Bank statement reconciliation", "Document Review", 2.0, 80, 125),
            hist(e1, taylor, "Prior year comparison prep", "Tax Preparation", 1.5, 97, 150),
            hist(eng_book, casey, "March bookkeeping close", "Admin", 1.0, 83, 125),
        ]

        # 4 months ago (days 106-135)
        historical += [
            hist(e1, alex, "Q2 advisory call", "Client Meeting", 1.0, 120, 200),
            hist(eng_1120, taylor, "Corporate structure review", "Research", 2.5, 115, 150),
            hist(eng_1120s, jordan, "Shareholder meeting preparation", "Client Communication", 1.5, 110, 175),
            hist(eng_1041, jordan, "Estate planning coordination call", "Research", 2.0, 125, 175),
            hist(e2, taylor, "New client onboarding tasks", "Admin", 1.0, 118, 150),
            hist(eng_book, casey, "February bookkeeping close", "Tax Preparation", 2.0, 112, 125),
            hist(e1, alex, "Rental property income analysis", "Tax Preparation", 1.5, 130, 200),
            hist(eng_adv, alex, "Roth conversion modeling", "Research", 2.0, 122, 200),
        ]

        # 5 months ago (days 136-165)
        historical += [
            hist(eng_1120, taylor, "Year-end close preparation", "Tax Preparation", 3.0, 150, 150),
            hist(e1, alex, "Year-end advisory session", "Tax Preparation", 2.0, 145, 200),
            hist(eng_1041, jordan, "Trust year-end tax planning", "Research", 2.5, 155, 175),
            hist(eng_1120s, alex, "S-Corp year-end review and planning", "Review & Sign-off", 2.0, 142, 200),
            hist(e2, jordan, "Account setup and intake review", "Admin", 1.0, 160, 175),
            hist(eng_book, casey, "January bookkeeping close", "Tax Preparation", 2.0, 148, 125),
            hist(e1, taylor, "Document preparation and filing", "Document Review", 1.5, 158, 150),
            hist(eng_1041, casey, "Trust records organization", "Admin", 1.0, 152, 125),
        ]

        db.add_all(historical)
        db.commit()
        print(f"Added {len(historical)} historical time entries.")

        # Final summary
        print()
        print("=== Seed Additions Complete ===")
        print("Staff logins:")
        print("  andrew@jammpx.com / Demo2026!  (firm_owner - Alex Mercer)")
        print("  ben@jammpx.com / Demo2026!  (manager - Jordan Reeves)")
        print("  ben@mail.jammpx.com / Demo2026!  (staff - Taylor Kim)")
        print("  casey@demofirm.com / Demo2026!  (staff - Casey O'Brien)")
        print("Portal: corby0917@gmail.com / PortalDemo2026!  (Sarah Chen)")
        print()
        print("Fee schedule seeding retired: pricing lives in the pricing tables now.")
        print("4th letter template: Bookkeeping & Recurring Services.")
        print("40 historical time entries - all timesheet tabs now covered.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
