# scripts/fix_orphan_bookkeeping_invoices.py
"""
One-time idempotent data fix: link 5 orphan bookkeeping invoices for Riverside
Tax & Advisory to real year-specific engagements, and add TimeEntry rows so
Total hours this year reflects real, non-zero data.

Two engagements are created:
  2025 Bookkeeping Services  -- invoices from 2025 (Jun, Oct)
  2026 Bookkeeping Services  -- invoices from 2026 (Jun, Jul, Aug)

The script is idempotent: it checks before creating engagements, before
re-linking invoices, and before adding TimeEntry rows.

Safe to re-run if seed data is reset.
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
from datetime import date

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.db.session import SessionLocal
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry

CLIENT_ID  = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID    = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
USER_ID    = uuid.UUID("93ab6936-de16-4baa-b1f0-55a9934e367f")

INVOICES_2025 = [
    uuid.UUID("9572fc6c-9886-40e4-b706-d6e78c9d3716"),  # sent Jun 2025, $1200
    uuid.UUID("6a2e230d-25dd-4f2f-8aa3-170ef37aa883"),  # sent Oct 2025, $750
]

INVOICES_2026 = [
    uuid.UUID("7754011d-4d06-4576-bf1d-4ba82c651801"),  # sent Jun 2026, $1200
    uuid.UUID("5da7537e-1f55-4c9c-ba1e-3c2183318aae"),  # sent Jul 2026, $1200
    uuid.UUID("3ee008d4-1dda-4045-bcbe-65725fcd1415"),  # sent Aug 2026, $950
]

# TimeEntry rows to add: invoice_id -> list of (description, hours, entry_date)
TIME_ENTRIES = {
    uuid.UUID("9572fc6c-9886-40e4-b706-d6e78c9d3716"): [
        ("General bookkeeping and transaction categorization", 8.00, date(2025, 6, 5)),
        ("Bank reconciliation", 0.50, date(2025, 6, 6)),
    ],
    uuid.UUID("6a2e230d-25dd-4f2f-8aa3-170ef37aa883"): [
        ("General bookkeeping and transaction categorization", 6.00, date(2025, 10, 14)),
        ("Accounts payable review", 0.50, date(2025, 10, 15)),
    ],
    uuid.UUID("7754011d-4d06-4576-bf1d-4ba82c651801"): [
        ("General bookkeeping and transaction categorization", 8.00, date(2026, 6, 12)),
        ("Bank reconciliation", 0.50, date(2026, 6, 13)),
    ],
    uuid.UUID("5da7537e-1f55-4c9c-ba1e-3c2183318aae"): [
        ("General bookkeeping and transaction categorization", 8.00, date(2026, 7, 14)),
        ("Credit card reconciliation", 0.50, date(2026, 7, 15)),
    ],
    uuid.UUID("3ee008d4-1dda-4045-bcbe-65725fcd1415"): [
        ("General bookkeeping and transaction categorization", 7.50, date(2026, 8, 22)),
    ],
}


def get_or_create_engagement(db, name):
    existing = db.query(Engagement).filter(
        Engagement.firm_id == FIRM_ID,
        Engagement.client_id == CLIENT_ID,
        Engagement.name == name,
    ).first()
    if existing:
        print(f"  Engagement already exists: {existing.name} ({existing.id})")
        return existing, False
    eng = Engagement(
        firm_id=FIRM_ID,
        client_id=CLIENT_ID,
        name=name,
        status="active",
    )
    db.add(eng)
    db.flush()
    print(f"  Created engagement: {eng.name} ({eng.id})")
    return eng, True


def link_invoices(db, invoice_ids, engagement):
    for inv_id in invoice_ids:
        inv = db.query(Invoice).filter(
            Invoice.id == inv_id,
            Invoice.firm_id == FIRM_ID,
            Invoice.client_id == CLIENT_ID,
        ).first()
        if inv is None:
            print(f"  WARNING: invoice {inv_id} not found -- skipping")
            continue
        if inv.engagement_id == engagement.id:
            print(f"  Invoice {inv_id} already linked to this engagement -- skipping")
            continue
        inv.engagement_id = engagement.id
        print(f"  Linked invoice {inv_id} (${float(inv.total_amount):.2f}) to {engagement.name}")


def add_time_entries(db, engagement_id):
    for inv_id, entries in TIME_ENTRIES.items():
        existing_count = db.query(TimeEntry).filter(
            TimeEntry.invoice_id == inv_id,
            TimeEntry.firm_id == FIRM_ID,
        ).count()
        if existing_count > 0:
            print(f"  TimeEntry rows already exist for invoice {inv_id} ({existing_count} row(s)) -- skipping")
            continue
        for description, hours, entry_date in entries:
            te = TimeEntry(
                firm_id=FIRM_ID,
                engagement_id=engagement_id,
                invoice_id=inv_id,
                user_id=USER_ID,
                description=description,
                hours=hours,
                hourly_rate=150.00,
                is_billable=True,
                is_billed=True,
                date=entry_date,
            )
            db.add(te)
            print(f"  Added TimeEntry: {description[:40]} | {hours} hrs | {entry_date} | invoice {inv_id}")


def main():
    db = SessionLocal()
    try:
        print("=== Step 1-2: Create engagements and link invoices ===")

        print("\n[2025 Bookkeeping Services]")
        eng_2025, _ = get_or_create_engagement(db, "2025 Bookkeeping Services")
        link_invoices(db, INVOICES_2025, eng_2025)

        print("\n[2026 Bookkeeping Services]")
        eng_2026, _ = get_or_create_engagement(db, "2026 Bookkeeping Services")
        link_invoices(db, INVOICES_2026, eng_2026)

        print("\n=== Step 3: Add TimeEntry rows ===")
        print("\n[2025 invoices]")
        for inv_id in INVOICES_2025:
            entries = TIME_ENTRIES.get(inv_id, [])
            if not entries:
                continue
            existing = db.query(TimeEntry).filter(
                TimeEntry.invoice_id == inv_id,
                TimeEntry.firm_id == FIRM_ID,
            ).count()
            if existing > 0:
                print(f"  TimeEntry rows already exist for {inv_id} ({existing} row(s)) -- skipping")
                continue
            for description, hours, entry_date in entries:
                te = TimeEntry(
                    firm_id=FIRM_ID,
                    engagement_id=eng_2025.id,
                    invoice_id=inv_id,
                    user_id=USER_ID,
                    description=description,
                    hours=hours,
                    hourly_rate=150.00,
                    is_billable=True,
                    is_billed=True,
                    date=entry_date,
                )
                db.add(te)
                print(f"  Added: {description[:50]} | {hours} hrs | {entry_date}")

        print("\n[2026 invoices]")
        for inv_id in INVOICES_2026:
            entries = TIME_ENTRIES.get(inv_id, [])
            if not entries:
                continue
            existing = db.query(TimeEntry).filter(
                TimeEntry.invoice_id == inv_id,
                TimeEntry.firm_id == FIRM_ID,
            ).count()
            if existing > 0:
                print(f"  TimeEntry rows already exist for {inv_id} ({existing} row(s)) -- skipping")
                continue
            for description, hours, entry_date in entries:
                te = TimeEntry(
                    firm_id=FIRM_ID,
                    engagement_id=eng_2026.id,
                    invoice_id=inv_id,
                    user_id=USER_ID,
                    description=description,
                    hours=hours,
                    hourly_rate=150.00,
                    is_billable=True,
                    is_billed=True,
                    date=entry_date,
                )
                db.add(te)
                print(f"  Added: {description[:50]} | {hours} hrs | {entry_date}")

        db.commit()
        print("\n=== Committed ===")

        print("\n=== Verification ===")
        for inv_id in INVOICES_2025 + INVOICES_2026:
            inv = db.query(Invoice).filter(Invoice.id == inv_id).first()
            te_count = db.query(TimeEntry).filter(TimeEntry.invoice_id == inv_id).count()
            print(f"  Invoice {inv_id} | engagement_id: {inv.engagement_id} | time_entries: {te_count}")

        total_te = db.query(TimeEntry).count()
        print(f"\n  Total TimeEntry rows in database: {total_te}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()