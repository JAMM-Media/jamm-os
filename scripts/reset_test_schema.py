# scripts/reset_test_schema.py
r"""
Guarded reset of the TEST database's public schema.

Why this exists: tests/conftest.py builds the test database with
Base.metadata.create_all(), which creates tables that are absent and never
alters tables that are present. A column added to an existing table is
therefore invisible to the test database forever, and the drop_all in
pytest_unconfigure can itself fail and leave the stale tables standing
(How_We_Work_Process_Rules.md, instance twelve). Dropping and recreating the
public schema is the reset that always works.

It leaves the schema empty on purpose. conftest's create_all rebuilds it at
the start of the next suite run.

Usage, from the repo root:

    python scripts\reset_test_schema.py

Guards, every one of which runs before any database connection is opened:

  1. No production marker anywhere in the target URL.
  2. The target host is on the local allowlist, identical to
     scripts/seed_demo_firm.py: localhost and 127.0.0.1 only.
  3. The target database name equals the name tests/conftest.py uses, read at
     run time out of .env.test rather than hardcoded here, so this script
     cannot drift away from the file conftest actually loads.
  4. The target is not the dev database: host, port and name are compared
     against the DATABASE_URL in .env and .env.local.

A refusal exits non-zero with one reason line. No refusal, and no other line
this script prints, ever contains the URL or its password.
"""

import os
import sys
import urllib.parse

# --- Environment guard (fail closed) ----------------------------------------
# Same structural rule as scripts/seed_demo_firm.py: only argparse, os, sys
# and urllib may be imported above the guard invocation, so nothing that can
# fail on import ever runs before the guard has confirmed the target. Every
# third-party import in this file lives below the guard block, and the two
# dotenv reads the guard itself needs are deferred into function bodies.
# tests/test_seed_demo_firm_guard_ordering.py enforces this.
ALLOWLISTED_DB_HOSTS = {"localhost", "127.0.0.1"}

# The two markers tests/conftest.py and app/services/behavioral_log.py
# already refuse on.
PRODUCTION_MARKERS = ("ondigitalocean.com", ":25060")

TEST_ENV_FILE = ".env.test"
DEV_ENV_FILES = (".env", ".env.local")

# Set by _enforce_environment_guard once the target has passed every guard.
# main() reads this and never re-resolves, so the URL that gets connected to
# is the exact string that was validated.
VALIDATED_URL: str | None = None


def _refuse(reason: str) -> None:
    """Print one reason line and exit non-zero. The reason never carries the
    URL, because the URL carries the password."""
    print(f"REFUSED: {reason}")
    sys.exit(1)


def _url_parts(database_url: str | None) -> tuple[str, int | None, str] | None:
    """(host, port, database name), or None when the URL cannot be parsed.

    Never raises. A guard whose own resolution step can crash would abort the
    process before it ever printed a refusal, which is the failure this file
    is shaped to avoid."""
    if not database_url:
        return None
    try:
        parsed = urllib.parse.urlparse(database_url)
        host = parsed.hostname
        port = parsed.port
    except Exception:
        return None
    if not host:
        return None
    name = parsed.path.lstrip("/").split("?")[0]
    return host, port, name


def _dotenv_url(filename: str) -> str | None:
    """DATABASE_URL out of one dotenv file, or None if the file is missing,
    unreadable, or does not set it. python-dotenv is already a project
    dependency (tests/conftest.py uses it), and it is imported here rather
    than at module level because an import that can fail must not precede the
    guard."""
    from dotenv import dotenv_values

    try:
        return dotenv_values(filename).get("DATABASE_URL") or None
    except Exception:
        return None


def _resolve_target_url() -> tuple[str | None, str]:
    """Shell environment first, then .env.test. This is pydantic-settings'
    precedence and scripts/seed_demo_firm.py's, and it is what makes an
    injected DATABASE_URL reach the guards instead of being silently
    outranked by a dotenv file (How_We_Work_Process_Rules.md, instance
    seventeen, where load_dotenv(override=True) defeated exactly that check).
    Whatever wins here is validated in full by the four guards below."""
    env_url = os.environ.get("DATABASE_URL")
    if env_url:
        return env_url, "shell environment"
    return _dotenv_url(TEST_ENV_FILE), TEST_ENV_FILE


def _enforce_environment_guard() -> None:
    global VALIDATED_URL

    target_url, source = _resolve_target_url()
    if not target_url:
        _refuse(
            f"no DATABASE_URL in the shell environment or {TEST_ENV_FILE}; "
            "nothing to check and nothing to reset"
        )

    for marker in PRODUCTION_MARKERS:
        if marker in target_url:
            _refuse(
                f"target URL (source: {source}) carries the production marker {marker!r}"
            )

    target = _url_parts(target_url)
    if target is None:
        _refuse(f"target DATABASE_URL (source: {source}) is unparseable")
    host, port, name = target

    if host not in ALLOWLISTED_DB_HOSTS:
        _refuse(
            f"target host {host!r} (source: {source}) is not on the local "
            f"allowlist {sorted(ALLOWLISTED_DB_HOSTS)}"
        )

    expected = _url_parts(_dotenv_url(TEST_ENV_FILE))
    if expected is None:
        _refuse(
            f"cannot read the test database name from {TEST_ENV_FILE}, so there is "
            "nothing to check the target against"
        )
    if name != expected[2]:
        _refuse(
            f"target database {name!r} (source: {source}) is not the test database "
            f"{expected[2]!r} that tests/conftest.py uses"
        )

    for dev_env_file in DEV_ENV_FILES:
        dev = _url_parts(_dotenv_url(dev_env_file))
        if dev is not None and (host, port, name) == dev:
            _refuse(
                f"target is the dev database named in {dev_env_file}; refusing to "
                "drop the schema a running app is using"
            )

    print(f"Target host: {host}")
    print(f"Target port: {port}")
    print(f"Target database: {name} (source: {source})")
    print(f"Working directory: {os.getcwd()}")
    VALIDATED_URL = target_url


if __name__ == "__main__":
    _enforce_environment_guard()

from sqlalchemy import create_engine, text


def main() -> None:
    """Drop and recreate the public schema of the validated target.

    AUTOCOMMIT because DROP SCHEMA ... CASCADE and CREATE SCHEMA are the whole
    job: there is nothing to roll back to, and a half-applied reset is more
    useful visible than hidden inside an aborted transaction.

    The table counts either side are read from information_schema and printed,
    because a reset that silently did nothing looks exactly like a reset that
    worked (How_We_Work_Process_Rules.md, section 1). After must be 0."""
    if VALIDATED_URL is None:
        _refuse("the environment guard did not run; refusing to connect")

    engine = create_engine(VALIDATED_URL, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            live = conn.execute(text("select current_database()")).scalar()
            before = conn.execute(
                text(
                    "select count(*) from information_schema.tables "
                    "where table_schema = 'public'"
                )
            ).scalar()
            print(f"Connected to: {live}")
            print(f"Public tables before: {before}")

            conn.execute(text("DROP SCHEMA public CASCADE"))
            conn.execute(text("CREATE SCHEMA public"))

            after = conn.execute(
                text(
                    "select count(*) from information_schema.tables "
                    "where table_schema = 'public'"
                )
            ).scalar()
            print(f"Public tables after: {after}")
    finally:
        engine.dispose()

    print("Reset complete. conftest's create_all rebuilds the schema on the next run.")


if __name__ == "__main__":
    main()
