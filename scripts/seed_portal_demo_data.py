# scripts/seed_portal_demo_data.py
"""
Seeds realistic demo documents for the portal-demo@jammpx.com test client
so the To-do page's "Recent documents" section shows real rows.

IMPORTANT LIMITATION -- read before running:

  pending_document_requests (stat cards + Open tasks list): the portal dashboard
  endpoint currently hardcodes pending_document_requests = [] with an explicit
  TODO comment ("populate when Phase 4 DocumentRequest model is built"). Creating
  DocumentRequest rows in the DB will NOT populate the stat cards or task list --
  the backend query that would surface them is not yet written. Additionally,
  DocumentRequest requires engagement_id NOT NULL, and the demo client has no
  engagements. This script therefore does NOT seed DocumentRequest rows.

  pending_signatures (Open tasks list): SignatureEnvelope creation requires
  external provider IDs and multiple document FKs. Creating a syntactically
  valid but semantically broken envelope is not done here per the task's
  explicit skip instruction for non-trivial relationship seeding.

What this script DOES:
  Creates 4 Document rows scoped to the demo client with visibility=client_visible,
  so the "Recent documents" table in the portal To-do page populates with real data.

Run from the project root:
    python scripts/seed_portal_demo_data.py

Idempotent: checks for existing rows by s3_key before creating.
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
from datetime import datetime, timedelta, timezone

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.client import Client
from app.models.document import Document

CLIENT_EMAIL = "portal-demo@jammpx.com"
FIRM_ID = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")

now = datetime.now(timezone.utc)

DEMO_DOCUMENTS = [
    {
        "filename": "2024_W2_MainEmployer.pdf",
        "content_type": "application/pdf",
        "size_bytes": 184320,
        "category": "tax_document",
        "created_at": now - timedelta(days=3),
    },
    {
        "filename": "Q1_2024_BankStatement.pdf",
        "content_type": "application/pdf",
        "size_bytes": 512000,
        "category": "bank_statement",
        "created_at": now - timedelta(days=8),
    },
    {
        "filename": "SignedEngagementLetter_2024.pdf",
        "content_type": "application/pdf",
        "size_bytes": 95232,
        "category": "engagement_letter",
        "created_at": now - timedelta(days=14),
    },
    {
        "filename": "BusinessExpenseReceipts_Q1_2024.pdf",
        "content_type": "application/pdf",
        "size_bytes": 2097152,
        "category": "other",
        "created_at": now - timedelta(days=21),
    },
]


def main() -> None:
    db = SessionLocal()
    try:
        # Verify the demo client exists
        client = db.execute(
            select(Client).where(Client.email == CLIENT_EMAIL)
        ).scalars().first()
        if not client:
            print(f"ERROR: Client {CLIENT_EMAIL} not found. Run scripts/seed_portal_client.py first.")
            return

        actual_client_id = client.id
        actual_firm_id = client.firm_id

        created = 0
        skipped = 0

        for doc_def in DEMO_DOCUMENTS:
            doc_id = uuid.uuid4()
            s3_key = (
                f"{actual_firm_id}/{actual_client_id}/none"
                f"/{doc_id}/{doc_def['filename']}"
            )

            existing = db.execute(
                select(Document).where(
                    Document.client_id == actual_client_id,
                    Document.filename == doc_def["filename"],
                )
            ).scalars().first()

            if existing:
                print(f"  skip (exists): {doc_def['filename']}")
                skipped += 1
                continue

            doc = Document(
                id=doc_id,
                firm_id=actual_firm_id,
                client_id=actual_client_id,
                engagement_id=None,
                uploaded_by=None,
                filename=doc_def["filename"],
                s3_key=s3_key,
                content_type=doc_def["content_type"],
                size_bytes=doc_def["size_bytes"],
                category=doc_def["category"],
                visibility="client_visible",
                is_superseded=False,
                created_at=doc_def["created_at"],
                updated_at=doc_def["created_at"],
            )
            db.add(doc)
            db.flush()
            print(f"  created: {doc_def['filename']} (id: {doc_id})")
            created += 1

        db.commit()
        print()
        print(f"Done. Created {created} document(s), skipped {skipped} (already existed).")
        print()
        print("Limitation note:")
        print("  Stat cards (Open tasks / Overdue / Due this week / Completed) and the")
        print("  'Open tasks' list will still show zeros. The portal dashboard endpoint")
        print("  hardcodes pending_document_requests = [] -- the backend query is not")
        print("  yet implemented (TODO in app/api/portal.py line ~525). These stat cards")
        print("  cannot be populated by seeding until that endpoint is updated.")
        print()
        print("  Only 'Recent documents' will now show real rows. No server restart")
        print("  needed -- just refresh the browser.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
