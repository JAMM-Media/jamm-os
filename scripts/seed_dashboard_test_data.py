# scripts/seed_dashboard_test_data.py
"""
Seed realistic test data into the Riverside Tax & Advisory demo firm
so every section of the redesigned dashboard has content to display.

Creates:
  - 4 test clients (named "Seed Dashboard Client 1-4", clearly synthetic)
  - 6 invoices at varying ages and statuses for Revenue/AR trend calculations
  - 3 WIP engagements with unbilled time entries (including 1 aged 40+ days)
  - 3 engagements with filing_deadline dates within the next 14 days
  - Up to 7 new staff users with varying current-week time entries
  - 2 signature envelopes with status=sent at different ages

Idempotency: checks for the marker client "Seed Dashboard Client 1" before
creating. If already found, prints current counts and exits cleanly without
creating duplicates. This means the script is safe to re-run as a read-only
status check once it has been seeded once.

Usage:
    cd /home/corby/jamm-os
    python scripts/seed_dashboard_test_data.py

Never run against production. The guard below enforces this.
"""

import argparse
import os
import sys
import urllib.parse

# --- Environment guard (fail closed) ----------------------------------------
# This is the first executable statement after the four stdlib imports it needs
# (argparse, os, sys, urllib.parse). No other import may precede it.
# Copied verbatim from scripts/seed_additions.py.
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
            print(
                "ABORT: DATABASE_URL resolves to different hosts in the shell "
                "environment vs a dotenv file. Refusing to guess which one the "
                "application will actually use."
            )
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

from sqlalchemy import select, func
from app.db.session import SessionLocal
from app.models.firm import Firm
from app.models.user import User
from app.models.client import Client
from app.models.engagement import Engagement
from app.models.time_entry import TimeEntry
from app.models.invoice import Invoice
from app.models.signature_envelope import SignatureEnvelope
from app.core.security import get_password_hash
from app.core.enums import InvoiceStatus, InvoiceDeliveryMethod, UserRole, EngagementType

MARKER_CLIENT_NAME = "Seed Dashboard Client 1"
FIRM_NAME = "Riverside Tax & Advisory"


def _print_counts(db, firm_id: uuid.UUID, today: date) -> None:
    """Print current dashboard-relevant counts for the firm."""
    inv_paid = db.execute(
        select(func.count(Invoice.id)).where(
            Invoice.firm_id == firm_id,
            Invoice.status == InvoiceStatus.paid,
        )
    ).scalar()
    inv_unpaid = db.execute(
        select(func.count(Invoice.id)).where(
            Invoice.firm_id == firm_id,
            Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.overdue]),
        )
    ).scalar()
    te_unbilled = db.execute(
        select(func.count(TimeEntry.id)).where(
            TimeEntry.firm_id == firm_id,
            TimeEntry.is_billed == False,  # noqa: E712
            TimeEntry.is_billable == True,  # noqa: E712
        )
    ).scalar()
    staff_count = db.execute(
        select(func.count(User.id)).where(
            User.firm_id == firm_id,
            User.is_active == True,  # noqa: E712
            User.role != UserRole.client_portal_user,
        )
    ).scalar()
    cutoff = today + timedelta(days=14)
    effective_deadline = func.coalesce(Engagement.extended_deadline, Engagement.filing_deadline)
    upcoming = db.execute(
        select(func.count(Engagement.id)).where(
            Engagement.firm_id == firm_id,
            Engagement.status.notin_(["completed", "archived"]),
            effective_deadline.isnot(None),
            effective_deadline >= today,
            effective_deadline <= cutoff,
        )
    ).scalar()
    envelopes = db.execute(
        select(func.count(SignatureEnvelope.id)).where(
            SignatureEnvelope.firm_id == firm_id,
            SignatureEnvelope.status == "sent",
        )
    ).scalar()
    print()
    print("=== Dashboard data counts for Riverside Tax & Advisory ===")
    print(f"  Invoices paid:              {inv_paid}")
    print(f"  Invoices unpaid (AR):       {inv_unpaid}")
    print(f"  Unbilled time entries (WIP): {te_unbilled}")
    print(f"  Active staff:               {staff_count}")
    print(f"  Upcoming deadlines (14d):   {upcoming}")
    print(f"  Signature envelopes (sent): {envelopes}")


def main() -> None:
    db = SessionLocal()
    try:
        firm = db.execute(
            select(Firm).where(Firm.name == FIRM_NAME)
        ).scalar_one_or_none()
        if not firm:
            print(f"ERROR: '{FIRM_NAME}' not found. Run seed_riverside_demo.py first.")
            return

        firm_id = firm.id
        today = date.today()
        now = datetime.now(timezone.utc)

        # Idempotency check: if marker client already exists, report and exit.
        marker = db.execute(
            select(Client).where(
                Client.firm_id == firm_id,
                Client.name == MARKER_CLIENT_NAME,
            )
        ).scalar_one_or_none()

        if marker is not None:
            print(f"Marker client '{MARKER_CLIENT_NAME}' already exists -- seed already ran.")
            print("Printing current counts and exiting. Delete seed data manually to re-seed.")
            _print_counts(db, firm_id, today)
            return

        print(f"Seeding dashboard test data for: {firm.name} ({firm_id})")

        # -----------------------------------------------------------------------
        # 1. Clients
        # -----------------------------------------------------------------------
        clients = []
        for i in range(1, 5):
            c = Client(firm_id=firm_id, name=f"Seed Dashboard Client {i}")
            db.add(c)
            clients.append(c)
        db.flush()
        print(f"Created {len(clients)} test clients.")

        c1, c2, c3, c4 = clients

        # -----------------------------------------------------------------------
        # 2. Invoices -- for Revenue, Outstanding AR, and trend calculations
        # -----------------------------------------------------------------------
        start_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
        if today.month == 1:
            prior_start = datetime(today.year - 1, 12, 1, tzinfo=timezone.utc)
        else:
            prior_start = datetime(today.year, today.month - 1, 1, tzinfo=timezone.utc)

        invoices_data = [
            # (invoice_number, client, total, status, paid_at, sent_at, due_date)
            ("SEED-001", c1, 2500.0, InvoiceStatus.paid,
             now.replace(day=min(today.day, 28)),
             None, None),
            ("SEED-002", c2, 1800.0, InvoiceStatus.paid,
             now - timedelta(days=5),
             None, None),
            ("SEED-003", c3, 1500.0, InvoiceStatus.paid,
             prior_start + timedelta(days=10),
             None, None),
            ("SEED-004", c1, 3200.0, InvoiceStatus.sent,
             None,
             now - timedelta(days=45),
             today - timedelta(days=15)),
            ("SEED-005", c2, 2100.0, InvoiceStatus.sent,
             None,
             now - timedelta(days=50),
             today - timedelta(days=20)),
            ("SEED-006", c3, 900.0, InvoiceStatus.sent,
             None,
             now - timedelta(days=10),
             today + timedelta(days=20)),
        ]

        for (num, client, total, status, paid_at, sent_at, due_date) in invoices_data:
            inv = Invoice(
                firm_id=firm_id,
                client_id=client.id,
                invoice_number=num,
                subtotal=total,
                tax_rate=0.0,
                tax_amount=0.0,
                total_amount=total,
                status=status,
                paid_at=paid_at,
                sent_at=sent_at,
                due_date=due_date,
                amount_paid=total if status == InvoiceStatus.paid else 0.0,
                delivery_method=InvoiceDeliveryMethod.portal,
                is_deleted=False,
            )
            db.add(inv)

        db.flush()
        print("Created 6 invoices (2 paid this month, 1 paid last month, 3 unpaid).")

        # -----------------------------------------------------------------------
        # 3. WIP engagements and time entries
        # -----------------------------------------------------------------------
        # Use the firm owner for billable work attribution
        owner = db.execute(
            select(User).where(User.email == "andrew@jammpx.com")
        ).scalar_one_or_none()
        if owner is None:
            owner = db.execute(
                select(User).where(
                    User.firm_id == firm_id,
                    User.role == UserRole.firm_owner,
                )
            ).scalar_one_or_none()
        if owner is None:
            print("WARNING: could not find firm owner. Time entries may fail.")
            return

        wip_engagements = [
            Engagement(
                firm_id=firm_id, client_id=c1.id,
                name="Seed Q4 Bookkeeping",
                engagement_type=EngagementType.bookkeeping_cleanup,
                status="in_progress",
            ),
            Engagement(
                firm_id=firm_id, client_id=c2.id,
                name="Seed Individual Return 2025",
                engagement_type=EngagementType.tax_return_1040,
                status="in_progress",
            ),
            Engagement(
                firm_id=firm_id, client_id=c3.id,
                name="Seed S-Corp Return 2025",
                engagement_type=EngagementType.tax_return_1120s,
                status="in_progress",
            ),
        ]
        for e in wip_engagements:
            db.add(e)
        db.flush()

        # Unbilled time entries -- current (within last 30 days)
        wip_entries = [
            TimeEntry(firm_id=firm_id, engagement_id=wip_engagements[0].id,
                      user_id=owner.id, description="Seed: bookkeeping review",
                      hours=6.0, hourly_rate=125.0, is_billable=True, is_billed=False,
                      date=today - timedelta(days=3)),
            TimeEntry(firm_id=firm_id, engagement_id=wip_engagements[0].id,
                      user_id=owner.id, description="Seed: reconciliation work",
                      hours=4.0, hourly_rate=125.0, is_billable=True, is_billed=False,
                      date=today - timedelta(days=1)),
            TimeEntry(firm_id=firm_id, engagement_id=wip_engagements[1].id,
                      user_id=owner.id, description="Seed: return preparation",
                      hours=8.0, hourly_rate=200.0, is_billable=True, is_billed=False,
                      date=today - timedelta(days=5)),
            TimeEntry(firm_id=firm_id, engagement_id=wip_engagements[1].id,
                      user_id=owner.id, description="Seed: client data review",
                      hours=2.5, hourly_rate=200.0, is_billable=True, is_billed=False,
                      date=today - timedelta(days=2)),
            TimeEntry(firm_id=firm_id, engagement_id=wip_engagements[2].id,
                      user_id=owner.id, description="Seed: entity return work",
                      hours=5.0, hourly_rate=175.0, is_billable=True, is_billed=False,
                      date=today - timedelta(days=7)),
        ]

        # Aged unbilled entry -- created 40 days ago for historical WIP trend
        aged_entry = TimeEntry(
            firm_id=firm_id, engagement_id=wip_engagements[2].id,
            user_id=owner.id, description="Seed: prior period work (aged)",
            hours=3.0, hourly_rate=175.0, is_billable=True, is_billed=False,
            date=today - timedelta(days=40),
            created_at=datetime.now(timezone.utc) - timedelta(days=40),
        )
        wip_entries.append(aged_entry)

        for te in wip_entries:
            db.add(te)
        db.flush()
        print(f"Created {len(wip_entries)} unbilled time entries across 3 WIP engagements.")

        # -----------------------------------------------------------------------
        # 4. Upcoming deadlines -- 3 engagements with filing_deadline in 14 days
        # -----------------------------------------------------------------------
        deadline_engagements = [
            Engagement(
                firm_id=firm_id, client_id=c1.id,
                name="Seed Extension Due Soon",
                engagement_type=EngagementType.extension_4868,
                status="in_progress",
                filing_deadline=today + timedelta(days=2),
            ),
            Engagement(
                firm_id=firm_id, client_id=c2.id,
                name="Seed Partnership Return Due",
                engagement_type=EngagementType.tax_return_1065,
                status="planning",
                filing_deadline=today + timedelta(days=7),
            ),
            Engagement(
                firm_id=firm_id, client_id=c3.id,
                name="Seed S-Corp Deadline",
                engagement_type=EngagementType.tax_return_1120s,
                status="in_progress",
                filing_deadline=today + timedelta(days=13),
            ),
        ]
        for e in deadline_engagements:
            db.add(e)
        db.flush()
        print("Created 3 engagements with upcoming deadlines (2d, 7d, 13d).")

        # -----------------------------------------------------------------------
        # 5. Staff -- create enough to reach 7+ for the expand-preview behavior
        # -----------------------------------------------------------------------
        existing_staff_count = db.execute(
            select(func.count(User.id)).where(
                User.firm_id == firm_id,
                User.is_active == True,  # noqa: E712
                User.role != UserRole.client_portal_user,
            )
        ).scalar() or 0

        # We need at least 7 total. Create enough new staff to reach 8 (a comfortable buffer).
        target_total = 8
        to_create = max(0, target_total - existing_staff_count)

        seed_staff = []
        for i in range(1, to_create + 1):
            u = User(
                firm_id=firm_id,
                email=f"seed-staff-{i}@riverside-seed.invalid",
                hashed_password=get_password_hash("SeedStaff2026!"),
                full_name=f"Seed Staff {i}",
                role=UserRole.staff,
                is_active=True,
            )
            db.add(u)
            seed_staff.append(u)

        db.flush()
        if seed_staff:
            print(f"Created {len(seed_staff)} new staff users (existing: {existing_staff_count}, new total: {existing_staff_count + len(seed_staff)}).")
        else:
            print(f"Already have {existing_staff_count} staff -- no new staff created.")

        # Add current-week time entries to show varying staff utilization.
        # The dashboard computes utilization as (hours_this_week / 40) * 100.
        # Use newly created staff if any exist; otherwise fall back to up to 6
        # existing non-owner staff (creating new time entries is not modifying
        # existing records -- it is creating new ones).
        start_of_week = today - timedelta(days=today.weekday())
        utilization_hours = [40.0, 32.0, 24.0, 16.0, 8.0, 4.0, 2.0]

        utilization_targets = seed_staff
        if not utilization_targets:
            # Find up to 6 existing active staff who are not the firm owner
            existing_non_owner = db.execute(
                select(User).where(
                    User.firm_id == firm_id,
                    User.is_active == True,  # noqa: E712
                    User.role == UserRole.staff,
                ).limit(6)
            ).scalars().all()
            utilization_targets = existing_non_owner

        util_entry_count = 0
        for idx, staff_user in enumerate(utilization_targets):
            hours = utilization_hours[idx % len(utilization_hours)]
            if hours > 0:
                entry_date = max(start_of_week, today - timedelta(days=min(idx, 4)))
                te = TimeEntry(
                    firm_id=firm_id,
                    engagement_id=wip_engagements[idx % len(wip_engagements)].id,
                    user_id=staff_user.id,
                    description=f"Seed: utilization entry for {staff_user.full_name}",
                    hours=hours,
                    hourly_rate=100.0,
                    is_billable=True,
                    is_billed=False,
                    date=entry_date,
                )
                db.add(te)
                util_entry_count += 1

        db.flush()
        if util_entry_count:
            print(f"Created {util_entry_count} current-week time entries for varying staff utilization.")

        # -----------------------------------------------------------------------
        # 6. Signature envelopes -- 2 with status=sent at different ages
        # -----------------------------------------------------------------------
        envelopes = [
            SignatureEnvelope(
                firm_id=firm_id,
                client_id=c1.id,
                status="sent",
                subject="Seed Engagement Letter 2025",
                provider="dropbox_sign",
                sent_at=now - timedelta(days=3),
                signers=[{"name": "Seed Client 1", "email": "seed1@test.invalid", "status": "pending", "signed_at": None}],
                reminder_count=0,
            ),
            SignatureEnvelope(
                firm_id=firm_id,
                client_id=c2.id,
                status="sent",
                subject="Seed Tax Engagement Agreement",
                provider="dropbox_sign",
                sent_at=now - timedelta(days=12),
                signers=[{"name": "Seed Client 2", "email": "seed2@test.invalid", "status": "pending", "signed_at": None}],
                reminder_count=1,
                last_reminder_sent_at=now - timedelta(days=6),
            ),
        ]
        for env in envelopes:
            db.add(env)

        db.flush()
        db.commit()
        print("Created 2 signature envelopes (fresh: 3d old, aged: 12d old).")

        # Final counts
        _print_counts(db, firm_id, today)
        print()
        print("Seed complete. Reload /dashboard to verify all sections have content.")

    except Exception as e:
        db.rollback()
        print(f"Error during seed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
