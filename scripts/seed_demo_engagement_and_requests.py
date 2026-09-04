# scripts/seed_demo_engagement_and_requests.py
"""
Creates one real Engagement and five DocumentRequest rows for the demo portal
client so the To-do page stat cards and Open tasks list show genuine data.

  CLIENT_ID = bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47
  FIRM_ID   = 185314c9-e702-4eab-8600-249848022206

Spread of requests:
  - 2 x pending (one overdue, one due within 7 days)
  - 1 x pending (due later)
  - 1 x partial (overdue -- so "partial" also appears correctly in pending list)
  - 1 x complete (so the Completed stat card shows a non-zero count)

Run from the project root:
    python scripts/seed_demo_engagement_and_requests.py

Idempotent: skips if an engagement already exists for this client.
Backend needs restarting after this runs so the new endpoint logic takes effect.
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
from app.models.engagement import Engagement
from app.models.document_request import DocumentRequest

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")

TODAY = date.today()

REQUESTS = [
    {
        "title": "2024 W-2 Forms",
        "due_date": TODAY - timedelta(days=6),
        "status": "pending",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "W-2 from primary employer",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "Q1 2024 Bank Statements",
        "due_date": TODAY + timedelta(days=4),
        "status": "pending",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "January statement",
                "is_required": True,
                "status": "pending",
            },
            {
                "id": str(uuid.uuid4()),
                "label": "February statement",
                "is_required": True,
                "status": "pending",
            },
            {
                "id": str(uuid.uuid4()),
                "label": "March statement",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "Business Expense Receipts",
        "due_date": TODAY + timedelta(days=20),
        "status": "pending",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "Q1 receipts",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "Signed Engagement Letter",
        "due_date": TODAY - timedelta(days=10),
        "status": "partial",
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "Signed engagement letter",
                "is_required": True,
                "status": "uploaded",
            },
            {
                "id": str(uuid.uuid4()),
                "label": "Authorization form",
                "is_required": True,
                "status": "pending",
            },
        ],
    },
    {
        "title": "2023 Prior Year Tax Return",
        "due_date": TODAY - timedelta(days=45),
        "status": "complete",
        # completed_at set to a few days ago so the recency filter (current month) picks it up
        "completed_at": datetime.now(timezone.utc) - timedelta(days=3),
        "checklist_items": [
            {
                "id": str(uuid.uuid4()),
                "label": "2023 Form 1040",
                "is_required": True,
                "status": "uploaded",
            },
        ],
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        # Verify client
        client = db.get(Client, CLIENT_ID)
        if not client:
            print(f"ERROR: Client {CLIENT_ID} not found. Run seed_portal_client.py first.")
            return

        # Find or create engagement
        existing_eng = db.execute(
            select(Engagement).where(
                Engagement.client_id == CLIENT_ID,
                Engagement.firm_id == FIRM_ID,
            )
        ).scalars().first()

        if existing_eng:
            engagement_id = existing_eng.id
            print(f"Using existing engagement: {existing_eng.name} (id: {engagement_id})")
        else:
            engagement = Engagement(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                name="2024 Individual Tax Return",
                status="active",
            )
            db.add(engagement)
            db.flush()
            engagement_id = engagement.id
            print(f"Created engagement: {engagement.name} (id: {engagement_id})")

        created = 0
        skipped = 0

        for req_def in REQUESTS:
            existing_req = db.execute(
                select(DocumentRequest).where(
                    DocumentRequest.client_id == CLIENT_ID,
                    DocumentRequest.firm_id == FIRM_ID,
                    DocumentRequest.title == req_def["title"],
                )
            ).scalars().first()

            if existing_req:
                print(f"  skip (exists): {req_def['title']}")
                skipped += 1
                continue

            dr = DocumentRequest(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                engagement_id=engagement_id,
                title=req_def["title"],
                due_date=req_def["due_date"],
                status=req_def["status"],
                checklist_items=req_def["checklist_items"],
                completed_at=req_def.get("completed_at"),
            )
            db.add(dr)
            db.flush()
            print(f"  created [{req_def['status']}]: {req_def['title']} (id: {dr.id})")
            created += 1

        db.commit()
        print()
        print(f"Done. Created {created} document request(s), skipped {skipped}.")
        print()

        status_summary = {}
        for r in REQUESTS:
            status_summary[r["status"]] = status_summary.get(r["status"], 0) + 1
        for s, n in sorted(status_summary.items()):
            print(f"  {s}: {n}")

        print()
        print("Next steps:")
        print("  1. Restart the backend server (endpoint logic changed).")
        print("  2. Refresh the portal browser tab.")
        print("  The To-do stat cards should now show real counts.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
