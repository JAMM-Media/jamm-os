# scripts/seed_portal_notifications_demo.py
"""
One-time idempotent script: seeds 5 real PortalNotification rows for the
Riverside demo client (bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47).

Each row references a genuinely existing database record confirmed
before this script was written. Run from /home/corby/jamm-os with
the venv active.

Idempotent: checks (notification_type, related_entity_id) before
inserting. Re-running is safe.
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
from datetime import datetime
from zoneinfo import ZoneInfo

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.db.session import SessionLocal
from app.models.portal_notification import PortalNotification

FIRM_ID = uuid.UUID('185314c9-e702-4eab-8600-249848022206')
CLIENT_ID = uuid.UUID('bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47')
ET = ZoneInfo('America/New_York')


def et(year, month, day, hour, minute):
    return datetime(year, month, day, hour, minute, tzinfo=ET)


NOTIFICATIONS = [
    # 1. message
    # References real staff message sent 2026-08-26 10:31 ET
    # (client_messages id f3da9bb0-7882-4c58-bec9-97bec388522e)
    # Body: "Yes, that's the final amount for August. It covers the standard
    # monthly bookkeeping plus the credit card reconciliation..."
    {
        'title': 'New message from your team',
        'body': '"Yes, that\'s the final amount for August." Re: your August invoice question.',
        'notification_type': 'message',
        'is_read': False,
        'is_pinned': False,
        'related_entity_type': 'client_message',
        'related_entity_id': uuid.UUID('f3da9bb0-7882-4c58-bec9-97bec388522e'),
        'created_at': et(2026, 8, 26, 10, 31),
    },
    # 2. document_request
    # References real document_request id 739a8851: "Q1 2024 Bank Statements"
    # Status: pending, due 2026-08-25 (now overdue as of today 2026-09-01)
    {
        'title': 'Document request: Q1 2024 Bank Statements',
        'body': 'This request was due Aug 25. Please upload the documents when ready.',
        'notification_type': 'document_request',
        'is_read': False,
        'is_pinned': False,
        'related_entity_type': 'document_request',
        'related_entity_id': uuid.UUID('739a8851-c5b6-4f44-969a-78f275557410'),
        'created_at': et(2026, 8, 24, 9, 0),
    },
    # 3. payment_due
    # References real invoice id 5da7537e: INV-1004, $1,200.00, status overdue,
    # due_date 2026-07-30
    {
        'title': 'Invoice INV-1004 is overdue',
        'body': '$1,200.00 was due July 30. Please review your Invoices page.',
        'notification_type': 'payment_due',
        'is_read': False,
        'is_pinned': False,
        'related_entity_type': 'invoice',
        'related_entity_id': uuid.UUID('5da7537e-1f55-4c9c-ba1e-3c2183318aae'),
        'created_at': et(2026, 8, 15, 9, 0),
    },
    # 4. engagement_update
    # References real engagement id 8ab12dfa: "2024 Individual Tax Return", active
    {
        'title': '2024 Individual Tax Return in progress',
        'body': 'Your engagement is active. Check the To-do tab for any open items.',
        'notification_type': 'engagement_update',
        'is_read': True,
        'is_pinned': False,
        'related_entity_type': 'engagement',
        'related_entity_id': uuid.UUID('8ab12dfa-058b-43d7-8084-df90e60f37cc'),
        'created_at': et(2026, 8, 7, 10, 0),
    },
    # 5. system
    # No specific entity reference -- honest system notification marking
    # when the portal account was set up (documents first appeared 2026-07-31)
    {
        'title': 'Your client portal is ready',
        'body': 'You can now view invoices, documents, and messages from Riverside Tax & Advisory.',
        'notification_type': 'system',
        'is_read': True,
        'is_pinned': False,
        'related_entity_type': None,
        'related_entity_id': None,
        'created_at': et(2026, 7, 31, 10, 0),
    },
]


def main():
    db = SessionLocal()
    try:
        existing = (
            db.query(PortalNotification)
            .filter(PortalNotification.client_id == CLIENT_ID)
            .all()
        )
        existing_keys = {
            (str(n.notification_type), str(n.related_entity_id) if n.related_entity_id else None)
            for n in existing
        }

        inserted = 0
        skipped = 0
        for spec in NOTIFICATIONS:
            key = (
                spec['notification_type'],
                str(spec['related_entity_id']) if spec['related_entity_id'] else None,
            )
            if key in existing_keys:
                print(f'  SKIP (already exists): {spec["title"]}')
                skipped += 1
                continue

            n = PortalNotification(
                id=uuid.uuid4(),
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                title=spec['title'],
                body=spec['body'],
                notification_type=spec['notification_type'],
                is_read=spec['is_read'],
                is_pinned=spec['is_pinned'],
                related_entity_type=spec.get('related_entity_type'),
                related_entity_id=spec.get('related_entity_id'),
                created_at=spec['created_at'],
            )
            db.add(n)
            inserted += 1
            print(f'  INSERT: {spec["title"]}')

        db.commit()
        print(f'Done. Inserted {inserted}, skipped {skipped}.')
    finally:
        db.close()


if __name__ == '__main__':
    main()
