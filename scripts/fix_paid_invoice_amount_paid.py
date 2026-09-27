# scripts/fix_paid_invoice_amount_paid.py
"""
One-time data fix: set amount_paid = total_amount for invoices where
status=paid AND paid_at IS NOT NULL AND amount_paid=0.

These invoices were created by seed scripts that set status=paid and paid_at
but never populated amount_paid, causing the Morning Briefing's balance
calculation (total_amount - amount_paid) to treat them as having a full
outstanding balance even though they are paid.

In the dev database this matches INV-1001, INV-1002, INV-1003 only.
A fourth category (status=paid AND amount_paid=0 AND paid_at IS NULL)
also exists (INV-003, TAX-2025-001, TAX-2025-002) but is NOT touched here
because the absence of paid_at suggests a different seed-data intent.

Usage:
    cd /home/corby/jamm-os
    python scripts/fix_paid_invoice_amount_paid.py
"""

import argparse
import os
import sys
import urllib.parse

# --- Environment guard (fail closed) ----------------------------------------
ALLOWLISTED_DB_HOSTS = {"localhost", "127.0.0.1"}


def _resolve_database_host(database_url: str | None) -> str:
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
    from dotenv import dotenv_values
    env_values = dotenv_values(".env")
    if env_values.get("DATABASE_URL"):
        return env_values["DATABASE_URL"], ".env"
    local_values = dotenv_values(".env.local")
    if local_values.get("DATABASE_URL"):
        return local_values["DATABASE_URL"], ".env.local"
    return None, None


def _resolve_effective_database_url() -> tuple[str | None, str | None, str | None]:
    dotenv_value, dotenv_source = _database_url_from_dotenv_files()
    return os.environ.get("DATABASE_URL"), dotenv_value, dotenv_source


def _enforce_environment_guard(allow_production_flag: bool) -> None:
    env_var_url, dotenv_url, dotenv_source = _resolve_effective_database_url()
    cwd = os.getcwd()

    if env_var_url and dotenv_url:
        env_var_host = _resolve_database_host(env_var_url)
        dotenv_host = _resolve_database_host(dotenv_url)
        if env_var_host != dotenv_host:
            print("ABORT: DATABASE_URL resolves to different hosts in the shell environment vs a dotenv file.")
            print(f"  shell environment host: {env_var_host}")
            print(f"  {dotenv_source} host:   {dotenv_host}")
            print(f"  working directory: {cwd}")
            sys.exit(1)

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
            f"({sorted(ALLOWLISTED_DB_HOSTS)}) and stdin is not a TTY."
        )
        sys.exit(1)

    if not allow_production_flag:
        print(
            f"ABORT: host '{host}' is not on the local allowlist "
            f"({sorted(ALLOWLISTED_DB_HOSTS)}). Re-run with --allow-production."
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
        help="Required with typed confirmation to run against non-local hosts.",
    )
    _arg_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print which invoices would be updated without writing anything.",
    )
    ARGS = _arg_parser.parse_args()
    _enforce_environment_guard(ARGS.allow_production)

# Safe to import app.* below: guard has already confirmed the target host.

import os as _os
_REPO_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import select
from app.db.session import SessionLocal
from app.models.invoice import Invoice
from app.core.enums import InvoiceStatus


def main(dry_run: bool = False) -> None:
    db = SessionLocal()
    try:
        # Narrow filter: status=paid AND paid_at IS NOT NULL AND amount_paid=0
        # This targets exactly the invoices where a real payment was recorded
        # (paid_at set) but amount_paid was never populated by the seed script.
        # Invoices with paid_at=None are excluded deliberately -- they represent
        # a different seed-data pattern and should not be touched here.
        rows = db.execute(
            select(Invoice).where(
                Invoice.status == InvoiceStatus.paid,
                Invoice.paid_at.isnot(None),
                Invoice.amount_paid == 0,
            )
        ).scalars().all()

        if not rows:
            print("No invoices match the fix criteria. Nothing to do.")
            return

        print(f"Found {len(rows)} invoice(s) to fix:")
        for inv in rows:
            print(
                f"  {inv.invoice_number}: total_amount={inv.total_amount}, "
                f"amount_paid={inv.amount_paid} -> {inv.total_amount}, "
                f"paid_at={inv.paid_at}"
            )

        if dry_run:
            print("Dry run -- no changes written.")
            return

        for inv in rows:
            inv.amount_paid = inv.total_amount

        db.commit()
        print(f"Fixed {len(rows)} invoice(s). amount_paid set to total_amount for each.")

    except Exception as e:
        db.rollback()
        print(f"Error: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main(dry_run=ARGS.dry_run)
