# scripts/seed_messages_demo.py
"""
Seed a realistic message thread between Riverside Tax & Advisory and their
demo portal client (bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47) for Messages
page demonstration.

Idempotent: if messages already exist for this client, skips and reports.
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

from datetime import datetime, timezone, timedelta

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.db.session import SessionLocal
from app.models.message import ClientMessage
import uuid

CLIENT_ID = uuid.UUID("bb8cf7af-d819-4cc2-b61f-4e5cb75a5a47")
FIRM_ID   = uuid.UUID("185314c9-e702-4eab-8600-249848022206")
USER_ID   = uuid.UUID("fc28f112-d5e4-43fc-b9a9-cb99c36f15f8")  # Sarah Chen, firm owner

def ts(days_ago: int, hour: int = 10, minute: int = 0) -> datetime:
    base = datetime(2026, 8, 28, hour, minute, 0, tzinfo=timezone.utc)
    return base - timedelta(days=days_ago)

MESSAGES = [
    {
        "sender_role": "staff",
        "sender_id": USER_ID,
        "body": (
            "Hi!\n\n"
            "Just a quick update on your Q3 bookkeeping. We have completed all account "
            "reconciliations through September 30, 2026.\n\n"
            "Your financials are on track, and we don't anticipate any issues with "
            "your year-end tax planning.\n\n"
            "Please let us know if you have any questions.\n\n"
            "Best regards,\nRiverside Tax & Advisory Team"
        ),
        "created_at": ts(days_ago=7, hour=11, minute=33),
    },
    {
        "sender_role": "client",
        "sender_id": None,
        "body": "Thanks for the update! Appreciate the quick turnaround.",
        "created_at": ts(days_ago=7, hour=11, minute=42),
    },
    {
        "sender_role": "staff",
        "sender_id": USER_ID,
        "body": "You're welcome! Let us know if there's anything else we can help with.",
        "created_at": ts(days_ago=7, hour=11, minute=45),
    },
    {
        "sender_role": "client",
        "sender_id": None,
        "body": "One question -- I noticed the August invoice. Is that the final amount for the month?",
        "created_at": ts(days_ago=2, hour=14, minute=5),
    },
    {
        "sender_role": "staff",
        "sender_id": USER_ID,
        "body": (
            "Yes, that's the final amount for August. It covers the standard monthly "
            "bookkeeping plus the credit card reconciliation we completed for you.\n\n"
            "Let us know if you'd like a detailed breakdown."
        ),
        "created_at": ts(days_ago=2, hour=14, minute=31),
    },
]

def main():
    db = SessionLocal()
    try:
        existing = db.query(ClientMessage).filter(
            ClientMessage.client_id == CLIENT_ID,
            ClientMessage.firm_id == FIRM_ID,
        ).count()

        if existing > 0:
            # Check if staff sender is the correct real user
            wrong = db.query(ClientMessage).filter(
                ClientMessage.client_id == CLIENT_ID,
                ClientMessage.firm_id == FIRM_ID,
                ClientMessage.sender_role == "staff",
                ClientMessage.sender_id != USER_ID,
            ).count()
            if wrong == 0:
                print(f"Messages already exist with correct sender ({existing} rows) -- skipping.")
                return
            print(f"Found {existing} messages with wrong staff sender -- deleting and recreating.")
            db.query(ClientMessage).filter(
                ClientMessage.client_id == CLIENT_ID,
                ClientMessage.firm_id == FIRM_ID,
            ).delete()
            db.flush()

        print("=== Seeding demo messages ===")
        for data in MESSAGES:
            msg = ClientMessage(
                firm_id=FIRM_ID,
                client_id=CLIENT_ID,
                sender_id=data["sender_id"],
                sender_role=data["sender_role"],
                body=data["body"],
                created_at=data["created_at"],
            )
            db.add(msg)
            db.flush()
            print(f"  {data['sender_role']:6s}  {str(data['created_at'])[:16]}  {data['body'][:60]}")

        db.commit()
        print(f"\n  Committed {len(MESSAGES)} messages.")
    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    main()