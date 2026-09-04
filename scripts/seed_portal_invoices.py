# scripts/seed_portal_invoices.py
"""
Seeds 5 realistic invoices for the demo portal client so the rebuilt Invoices
page can be reviewed with real content: stat cards, table rows, status badges,
Pay Now button, and Download PDF.

  CLIENT_ID = bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47
  FIRM_ID   = 185314c9-e702-4eab-8600-249848022206

Invoice mix (matching the reference mock):
  INV-1001  paid      Q1 2023 Bookkeeping Services    $1,200
  INV-1002  paid      2023 Tax Return Preparation       $750
  INV-1003  paid      Q2 2024 Bookkeeping Services    $1,200
  INV-1004  overdue   Q3 2024 Bookkeeping Services    $1,200  (past due, not paid)
  INV-1005  sent      2024 Tax Return Preparation       $950  (due in ~2 weeks)

Run from the project root:
    python scripts/seed_portal_invoices.py

Idempotent: skips any invoice number that already exists for this firm.
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
from datetime import date, datetime, timezone, timedelta

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.invoice import Invoice
from app.core.enums import InvoiceStatus, InvoiceDeliveryMethod

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")

TODAY = date.today()
NOW = datetime.now(timezone.utc)


def _line_item(description: str, amount: float) -> dict:
    return {
        "id": str(uuid.uuid4()),
        "description": description,
        "quantity": 1,
        "unit_price": amount,
        "total": amount,
    }


INVOICES = [
    {
        "invoice_number": "INV-1001",
        "status": InvoiceStatus.paid,
        "line_items": [_line_item("Q1 2023 Bookkeeping Services", 1200.00)],
        "subtotal": 1200.00,
        "total_amount": 1200.00,
        "due_date": date(2023, 3, 31),
        "paid_at": NOW - timedelta(days=430),
        "sent_at": NOW - timedelta(days=445),
    },
    {
        "invoice_number": "INV-1002",
        "status": InvoiceStatus.paid,
        "line_items": [_line_item("2023 Tax Return Preparation", 750.00)],
        "subtotal": 750.00,
        "total_amount": 750.00,
        "due_date": date(2023, 9, 15),
        "paid_at": NOW - timedelta(days=300),
        "sent_at": NOW - timedelta(days=315),
    },
    {
        "invoice_number": "INV-1003",
        "status": InvoiceStatus.paid,
        "line_items": [_line_item("Q2 2024 Bookkeeping Services", 1200.00)],
        "subtotal": 1200.00,
        "total_amount": 1200.00,
        "due_date": date(2024, 6, 30),
        "paid_at": NOW - timedelta(days=58),
        "sent_at": NOW - timedelta(days=73),
    },
    {
        "invoice_number": "INV-1004",
        "status": InvoiceStatus.overdue,
        "line_items": [_line_item("Q3 2024 Bookkeeping Services", 1200.00)],
        "subtotal": 1200.00,
        "total_amount": 1200.00,
        "due_date": TODAY - timedelta(days=28),
        "paid_at": None,
        "sent_at": NOW - timedelta(days=42),
    },
    {
        "invoice_number": "INV-1005",
        "status": InvoiceStatus.sent,
        "line_items": [_line_item("2024 Tax Return Preparation", 950.00)],
        "subtotal": 950.00,
        "total_amount": 950.00,
        "due_date": TODAY + timedelta(days=14),
        "paid_at": None,
        "sent_at": NOW - timedelta(days=3),
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        client = db.get(Client, CLIENT_ID)
        if not client:
            print(f"ERROR: Client {CLIENT_ID} not found. Run seed_portal_client.py first.")
            return

        created = 0
        skipped = 0

        for inv_def in INVOICES:
            existing = db.execute(
                select(Invoice).where(
                    Invoice.firm_id == FIRM_ID,
                    Invoice.invoice_number == inv_def["invoice_number"],
                )
            ).scalars().first()

            if existing:
                print(f"  skip (exists): {inv_def['invoice_number']} [{existing.status.value}]")
                skipped += 1
                continue

            inv = Invoice(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                invoice_number=inv_def["invoice_number"],
                line_items=inv_def["line_items"],
                subtotal=inv_def["subtotal"],
                tax_rate=0.0,
                tax_amount=0.0,
                total_amount=inv_def["total_amount"],
                status=inv_def["status"],
                due_date=inv_def["due_date"],
                paid_at=inv_def["paid_at"],
                sent_at=inv_def["sent_at"],
                delivery_method=InvoiceDeliveryMethod.portal,
                is_deleted=False,
            )
            db.add(inv)
            db.flush()
            print(
                f"  created [{inv_def['status'].value:8s}]: "
                f"{inv_def['invoice_number']}  "
                f"${inv_def['total_amount']:,.2f}  "
                f"due {inv_def['due_date']}  (id: {inv.id})"
            )
            created += 1

        db.commit()

        print()
        print(f"Done. Created {created} invoice(s), skipped {skipped} (already existed).")
        print()

        # Summary query
        invoices = db.execute(
            select(Invoice).where(
                Invoice.client_id == CLIENT_ID,
                Invoice.firm_id == FIRM_ID,
                Invoice.is_deleted == False,
            ).order_by(Invoice.invoice_number)
        ).scalars().all()

        print("Current invoices for demo client:")
        for inv in invoices:
            print(
                f"  {inv.invoice_number}  [{inv.status.value:8s}]  "
                f"${float(inv.total_amount):,.2f}  "
                f"due {inv.due_date}"
            )

        print()
        print("Refresh the portal browser tab -- no server restart needed.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
