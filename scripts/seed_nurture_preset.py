# scripts/seed_nurture_preset.py
"""
Backfill the acquisition nurture preset tree for existing firms that predate
the per-firm seeding hook added to create_firm.

Run from the project root:
    python scripts/seed_nurture_preset.py

Idempotent: checks for an existing Sequence with preset_lineage_key=
acquisition_nurture_v1 before seeding, so re-running is safe.
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

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from app.db.session import SessionLocal
from app.models.firm import Firm
from app.models.sequence import Sequence, SequenceVersion
from app.services.nurture_preset import PRESET_LINEAGE_KEY, seed_firm_nurture_preset


def main():
    db = SessionLocal()
    try:
        firms = db.query(Firm).order_by(Firm.created_at).all()
        if not firms:
            print("No firms found.")
            return

        seeded = 0
        skipped = 0
        for firm in firms:
            existing = (
                db.query(SequenceVersion)
                .join(Sequence, SequenceVersion.sequence_id == Sequence.id)
                .filter(
                    Sequence.firm_id == firm.id,
                    SequenceVersion.preset_lineage_key == PRESET_LINEAGE_KEY,
                )
                .first()
            )
            if existing:
                print(f"  Skipping (already seeded): {firm.name} ({firm.id})")
                skipped += 1
                continue

            try:
                n = seed_firm_nurture_preset(firm_id=firm.id, db=db)
                print(f"  Seeded {n} steps for: {firm.name} ({firm.id})")
                seeded += 1
            except Exception as exc:
                print(f"  ERROR for {firm.name} ({firm.id}): {exc}")

        print(f"\nDone. {seeded} firm(s) seeded, {skipped} skipped (already had preset).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
