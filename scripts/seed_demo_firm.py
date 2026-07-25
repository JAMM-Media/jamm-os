# scripts/seed_demo_firm.py
"""
Demo firm seed for JAMM PX - Cedar and Vance Advisors (DEMO).

Generates twelve trailing months of realistic operational history for a
single is_demo=True firm, exclusively by calling real service-layer
functions under freezegun so log_event fires organically. Never writes
BehavioralEvent rows directly and never inserts via raw SQL.

Usage:
    python scripts/seed_demo_firm.py                # full 12-month seed
    python scripts/seed_demo_firm.py --months 1      # smaller real run, trailing 1
                                                      # month only (roughly 1/12th the
                                                      # volume). NOT a dry run: it
                                                      # writes real rows and triggers
                                                      # every real side effect the full
                                                      # run does.
    python scripts/seed_demo_firm.py --teardown      # wipe the demo firm and exit
"""

import argparse
import os
import sys
import urllib.parse

# --- Environment guard (fail closed) ----------------------------------------
# This is the first executable statement in the file after the four stdlib
# imports it needs (argparse, os, sys, urllib.parse). Nothing else -- no
# other stdlib import, no third-party import, no app.* import -- may precede
# it. A production run once died on `from freezegun import freeze_time`
# before any "Target database host" line ever printed, because at that time
# an import capable of failing sat above the guard. The fix is structural,
# not "be more careful": every remaining stdlib import this script needs
# (asyncio, io, random, time, traceback, uuid, datetime), the JAMM_TESTING
# env default, the sys.path repo-root fix, and all third-party/app imports
# now live below the guard block, after it has already either aborted the
# process or positively confirmed the target host.
#
# This also runs before any app.* import for a second reason: app.db.session
# builds a real SQLAlchemy engine from Settings().DATABASE_URL at import
# time, and Settings.DATABASE_URL has no default -- if it were missing,
# pydantic would raise and crash the process before any guard placed later
# (e.g. inside main()) ever ran. Reading the raw sources directly here, before
# that import happens, is what lets a missing DATABASE_URL be handled by this
# guard instead of by an unhandled ValidationError.
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
    # DATABASE_URL (e.g. from .env.test, loaded by the test runner) routinely
    # differ in port, database name, or credentials while pointing at the
    # exact same, safe host -- that's expected, not a safety-relevant
    # disagreement, and would otherwise abort every test run with a false
    # positive. A host mismatch is the actual danger: it means this guard
    # can't be sure which database traffic will really hit. This check is
    # unconditional -- it runs, and can abort, regardless of --allow-production.
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


# The argv parse and the guard invocation itself only run when this file is
# executed as a script, not when it (or its helper functions above) is
# imported by a test module -- argparse.parse_args() with no explicit args
# reads real sys.argv, which under a test runner is the test runner's own
# argv, not this script's. main() (defined below) reads ARGS as a global and
# is itself only ever invoked from the __main__ block at the bottom of this
# file, so ARGS is guaranteed to exist by the time it is read.
if __name__ == "__main__":
    _arg_parser = argparse.ArgumentParser()
    _arg_parser.add_argument(
        "--months",
        type=int,
        default=12,
        help=(
            "Trailing N months to seed. This is a smaller REAL run, not a dry run -- "
            "it writes real rows and triggers every real side effect (minus outbound "
            "email/webhook, which this script always suppresses) that a full run does, "
            "just at roughly N/12th the volume."
        ),
    )
    _arg_parser.add_argument("--teardown", action="store_true", help="Wipe the demo firm and exit.")
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

import asyncio
import io
import random
import time as _time_module
import traceback
import uuid
from datetime import date, datetime, time, timedelta, timezone

os.environ.setdefault("JAMM_TESTING", "1")  # log_event writes synchronously

# Allow `python scripts/seed_demo_firm.py` to be run directly from anywhere:
# sys.path[0] is the scripts/ directory itself, not the repo root, so `app.*`
# and `scripts.*` absolute imports need the repo root added explicitly.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from fastapi import BackgroundTasks
from fastapi.datastructures import UploadFile
from freezegun import freeze_time
from sqlalchemy import select

import app.models  # noqa: F401 - registers all ORM models with Base.metadata
from app.db.base_class import Base
from app.db.session import SessionLocal
from app.core.enums import UserRole
from app.crud import user as crud_user
from app.models.firm import Firm
from app.models.client import Client
from app.models.user import User
from app.models.engagement import Engagement
from app.models.task import Task
from app.models.document_request import DocumentRequest
from app.models.invoice import Invoice
from app.models.automation_rule import AutomationRule
from app.models.firm_chat import Channel

from app.schemas.firm import FirmCreate
from app.schemas.user import UserCreate
from app.schemas.client import ClientCreate
from app.schemas.engagement import EngagementCreate, EngagementUpdate
from app.schemas.task import TaskCreate, TaskUpdate
from app.schemas.document_request import DocumentRequestCreate, DocumentRequestUpdate, ChecklistItem
from app.schemas.invoice import InvoiceCreate, LineItemSchema
from app.schemas.time_entry import TimeEntryCreate
from app.schemas.extension import ExtensionCreate
from app.schemas.totp import LoginRequest
from app.schemas.note import NoteCreate
from app.schemas.firm_chat import FirmMessageCreate, ChannelCreate

from app.services import firm_service, client_service, engagement_service, task_service
from app.services import document_request_service, document_service
from app.services import invoice_service, time_entry_service
from app.services import extension_service, firm_chat_service, note_service, auth_service
from app.services import deadline_scheduler
from app.services import automation_presets, automation_rule_service
from app.services import portal_magic_link
from app.services.behavioral_log import log_event

from scripts.seed_demo_firm_config import (
    FIRM, DEMO_PASSWORD, STAFF_PERSONAS, HERO_CLIENTS, POPULATION,
    CHOREOGRAPHY, WARMUP_EVENT_TYPE,
)

# psycopg/connection.py does `from time import monotonic` - a locally-cached
# reference, which freezegun's `ignore` mechanism DOES correctly protect
# (unlike botocore's plain `import time`, see below). Without this, psycopg's
# connect_timeout deadline math runs on freezegun's fake_monotonic(), which
# returns values on the scale of the frozen wall-clock epoch (~1.7 billion)
# instead of a real monotonic clock's scale (~a few hundred thousand seconds
# of uptime) - any deadline computed against that scale is nonsensical and
# fails instantly. This only bites when a *new* physical connection actually
# needs establishing (most log_event calls reuse an already-pooled
# connection and never hit this code path at all, which is why thousands of
# other calls succeeded while this one - hit during the less frequently
# exercised weekly overdue-sweep path - failed). Confirmed empirically:
# ignore=["psycopg"] alone fixes it, and the written row still carries the
# correct frozen timestamp (only psycopg's own deadline math is exempted).
PSYCOPG_FREEZE_IGNORE = ["psycopg"]


def frozen(dt):
    return freeze_time(dt, ignore=PSYCOPG_FREEZE_IGNORE)


# --- Harness-only AWS clock-skew workaround --------------------------------
# AWS request signing (botocore.auth) stamps each request with time.time()/
# datetime.datetime.utcnow() read directly off the shared `time`/`datetime`
# module objects, which freezegun overwrites globally and unconditionally in
# _freeze_time.start() - freezegun's own `ignore` parameter only prevents
# propagation into OTHER modules that did `from datetime import datetime`
# (a separately-cached local reference); it cannot exempt botocore, which
# does plain `import time` / `import datetime` and always resolves through
# the same shared, patched module object. Confirmed empirically: even with
# ignore=["botocore", ...], botocore.auth.time.time() and
# botocore.auth.datetime.datetime.utcnow() both still returned frozen values.
#
# Workaround: monkey-patch app.services.s3.upload_fileobj, from this seed
# script only, to swap the shared time/datetime module attributes back to
# freezegun's own saved real_* references for just the duration of the
# actual boto3 call, then restore the frozen ones immediately after. DB rows
# and log_event calls made before/after this narrow window still see
# simulated time; only the signed AWS request itself sees real time. No
# production file is modified, and this creates no backdating capability -
# it does the opposite, forcing the real AWS call to see real time.
import datetime as _datetime_module
import app.services.s3 as _s3_service_module

_real_upload_fileobj = _s3_service_module.upload_fileobj


def _upload_fileobj_with_real_time_for_aws(*args, **kwargs):
    import freezegun.api as _fg_api

    saved = {
        "time": _time_module.time,
        "monotonic": _time_module.monotonic,
        "perf_counter": _time_module.perf_counter,
        "datetime": _datetime_module.datetime,
    }
    try:
        _time_module.time = _fg_api.real_time
        _time_module.monotonic = _fg_api.real_monotonic
        _time_module.perf_counter = _fg_api.real_perf_counter
        _datetime_module.datetime = _fg_api.real_datetime
        return _real_upload_fileobj(*args, **kwargs)
    finally:
        _time_module.time = saved["time"]
        _time_module.monotonic = saved["monotonic"]
        _time_module.perf_counter = saved["perf_counter"]
        _datetime_module.datetime = saved["datetime"]


_s3_service_module.upload_fileobj = _upload_fileobj_with_real_time_for_aws


# --- Harness-only outbound-network suppression ------------------------------
# Two real outbound HTTP paths are reachable from a seed run (see Phase 1
# inventory): Postmark email sends and automation webhook_post calls. Both
# must never leave this machine, regardless of which Postmark token or which
# firm webhook config .env happens to carry.
#
# Same technique as the S3 patch above: reassign the attribute on the real
# class/module object so every caller sees the patched version at call time,
# no matter how or when that caller imported it. This is scoped to this
# script only and must never appear in application code.
#
# EmailService._send is the lowest layer that touches the network (raw
# requests.post to Postmark) -- every send_* helper and _send_raw funnels
# through it, so patching here still exercises template rendering, recipient
# resolution, and behavioral event logging for real; only the actual POST is
# intercepted. It is a @staticmethod, so the replacement is wrapped in
# staticmethod() to preserve that semantics if ever invoked through an
# instance instead of the class. The real _send returns None on success and
# raises on failure (never returns a falsy-but-not-None value), and no caller
# anywhere branches on its return value -- every send_* wrapper ignores it and
# unconditionally returns True itself -- so _suppressed_send returning None
# (its implicit no-op return) already matches the real success contract
# exactly.
#
# automation_actions._handle_webhook_post is a real httpx.post to a
# firm-configured URL. No automation preset currently reaches it (confirmed
# by inventory of every preset's action type), but that is safety by
# inventory, not by guard -- patching it directly makes the guarantee hold
# regardless of future preset changes.
#
# Installation is wrapped in a function and called from main(), not executed
# at module import time: EmailService and automation_actions are shared,
# process-wide objects, so a module-scope assignment here would mutate them
# for the entire pytest process the instant any test file imports this
# module (as tests/test_seed_demo_firm_guard.py and
# tests/test_seed_demo_firm_suppression.py both do) -- long before, and
# regardless of whether, a seed ever actually runs. Attribute lookup happens
# at call time, so installing from inside main(), immediately before any
# seeding work begins, is exactly as effective as installing at import time.
SUPPRESSED_SEND_COUNTS = {"email": 0, "webhook": 0}


def _suppressed_send(
    to_email,
    subject,
    html_body,
    from_name,
    reply_to=None,
    display_name=None,
    sending_domain=None,
) -> None:
    SUPPRESSED_SEND_COUNTS["email"] += 1


def _suppressed_handle_webhook_post(config, payload, db) -> str:
    SUPPRESSED_SEND_COUNTS["webhook"] += 1
    url = config.get("url")
    return f"webhook_post suppressed (seed run): would have posted to {url}"


def _install_network_suppression() -> None:
    SUPPRESSED_SEND_COUNTS["email"] = 0
    SUPPRESSED_SEND_COUNTS["webhook"] = 0

    from app.services.email_service import EmailService
    import app.services.automation_actions as automation_actions_module

    EmailService._send = staticmethod(_suppressed_send)
    automation_actions_module._handle_webhook_post = _suppressed_handle_webhook_post


FORM_TYPE_BY_ENGAGEMENT_TYPE = {
    "tax_return_1040": "4868",
    "tax_return_1120": "7004",
    "tax_return_1120s": "7004",
    "tax_return_1065": "7004",
    "tax_return_1041": "7004",
}

BUSINESS_ENGAGEMENT_TYPES = ("tax_return_1120", "tax_return_1120s", "tax_return_1065")


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def run_async(coro_func, **kwargs):
    """Call an async service function, then drain its BackgroundTasks queue
    synchronously (mirrors what FastAPI does at the end of a request), so
    automation dispatch actually executes instead of sitting unexecuted."""
    bg = BackgroundTasks()
    kwargs["background_tasks"] = bg

    async def _run():
        result = await coro_func(**kwargs)
        await bg()
        return result

    return asyncio.run(_run())


def make_upload_file(filename: str, content: bytes = b"demo document content") -> UploadFile:
    return UploadFile(filename=filename, file=io.BytesIO(content))


def window_bounds(months: int, today: date) -> tuple[date, date]:
    """Trailing N full months ending at today. Never hardcodes calendar years."""
    end = today
    year = end.year
    month = end.month - months
    while month <= 0:
        month += 12
        year -= 1
    start = date(year, month, 1)
    return start, end


def month_iter(start: date, end: date):
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        yield y, m
        m += 1
        if m > 12:
            m = 1
            y += 1


def days_in_month(y: int, m: int) -> int:
    if m == 12:
        nxt = date(y + 1, 1, 1)
    else:
        nxt = date(y, m + 1, 1)
    return (nxt - date(y, m, 1)).days


def month_progress_label(y: int, m: int) -> str:
    return f"{y}-{m:02d}"


BUSINESS_RETURN_TYPES = ("tax_return_1120", "tax_return_1120s", "tax_return_1065")
INDIVIDUAL_RETURN_TYPES = ("tax_return_1040", "amended_return_1040x")


def compute_deadline(engagement_type: str, creation_date: date):
    """
    Anchor the deadline to the engagement type and the actual creation month,
    instead of always jumping to "next April 15" regardless of when the
    engagement was created (that bug concentrated nearly every individual
    return's completion into the same 10-day window every year, since a
    return created in, say, October always got deadline = next April 15).

    - bookkeeping_monthly: closes within the creation month.
    - business returns (1120/1120s/1065): Mar 15 if created on/before that
      date this year, else the Sep 15 extension-window deadline if still
      within it, else a near-term interim deadline (not idling to next Mar 15).
    - individual returns (1040/1040x): Apr 15 if created on/before that date
      this year, else the Oct 15 extension-window deadline if still within
      it, else a near-term interim deadline (not idling to next Apr 15).
    - anything else: a near-term interim deadline.
    """
    if engagement_type == "bookkeeping_monthly":
        return date(creation_date.year, creation_date.month,
                     days_in_month(creation_date.year, creation_date.month))

    if engagement_type in INDIVIDUAL_RETURN_TYPES:
        original = date(creation_date.year, 4, 15)
        extended = date(creation_date.year, 10, 15)
    elif engagement_type in BUSINESS_RETURN_TYPES:
        original = date(creation_date.year, 3, 15)
        extended = date(creation_date.year, 9, 15)
    else:
        return creation_date + timedelta(days=random.randint(30, 45))

    if creation_date <= original:
        return original
    elif creation_date <= extended:
        return extended
    else:
        return creation_date + timedelta(days=random.randint(45, 60))


class Stats:
    def __init__(self):
        self.events_by_type = {}
        self.entities_created = {}
        self.failures = []

    def note_entity(self, name: str, n: int = 1):
        self.entities_created[name] = self.entities_created.get(name, 0) + n


STATS = Stats()

# Set from main() once the per-run random seed is applied, so the miss rate
# itself is reproducible along with everything else. 3-8% per the spec.
MISS_RATE = 0.05

# Miss engagements are NOT completed inline - completion is deferred until
# after the full month loop (and all its organic weekly deadline_scheduler
# sweeps) has run, so the real scheduler detects each miss as a genuinely
# past-deadline, still-open engagement rather than the seed script simply
# announcing a fact it already knows. See finalize_deferred_misses().
DEFERRED_MISSES = []


# ---------------------------------------------------------------------------
# Teardown
# ---------------------------------------------------------------------------

GRANDCHILD_TABLES = {
    # table_name: (model_import_path, model_class, fk_column, parent_model_import_path, parent_class, parent_fk_col)
    "channel_members": ("app.models.firm_chat", "ChannelMember", "channel_id", "app.models.firm_chat", "Channel", "firm_id"),
    "client_message_reads": ("app.models.message", "ClientMessageRead", "message_id", "app.models.message", "ClientMessage", "firm_id"),
    "firm_message_reads": ("app.models.firm_chat", "FirmMessageRead", "message_id", "app.models.firm_chat", "FirmMessage", "firm_id"),
    "note_reads": ("app.models.note_read", "NoteRead", "note_id", "app.models.note", "Note", "firm_id"),
}


def _import_class(module_path: str, class_name: str):
    import importlib
    return getattr(importlib.import_module(module_path), class_name)


def _dependency_ordered_firm_tables():
    """Introspect Base.metadata for every table with a firm_id column, plus
    the known grandchild join tables, and return a deletion order where
    children are deleted before the parents they reference."""
    by_name = {t.name: t for t in Base.metadata.sorted_tables}
    firm_scoped = [t.name for t in Base.metadata.sorted_tables if "firm_id" in t.columns.keys()]
    target = set(firm_scoped) | set(GRANDCHILD_TABLES.keys()) | {"firms"}

    dependents = {n: set() for n in target}
    for name in target:
        if name in GRANDCHILD_TABLES or name == "firms":
            continue
        t = by_name[name]
        for fk in t.foreign_keys:
            ref = fk.column.table.name
            if ref in target and ref != name:
                dependents[ref].add(name)
    # grandchildren always precede their direct parent table
    for gname, (_, _, _, _, parent_cls_name, _) in GRANDCHILD_TABLES.items():
        parent_table = parent_cls_name  # placeholder, replaced below
    for gname, spec in GRANDCHILD_TABLES.items():
        parent_module, parent_cls = spec[3], spec[4]
        parent_table_name = _import_class(parent_module, parent_cls).__tablename__
        dependents[parent_table_name].add(gname)

    remaining = {k: set(v) for k, v in dependents.items()}
    order = []
    while remaining:
        leaves = [n for n, deps in remaining.items() if not deps]
        if not leaves:
            raise RuntimeError(f"Cycle detected in teardown dependency graph: {remaining}")
        for n in sorted(leaves):
            order.append(n)
            del remaining[n]
        for deps in remaining.values():
            deps.difference_update(leaves)
    return order


def teardown(db):
    firm = db.execute(select(Firm).where(Firm.slug == FIRM["slug"])).scalar_one_or_none()
    if firm is None:
        print(f"No firm found with slug={FIRM['slug']!r}. Nothing to tear down.")
        return
    if firm.is_demo is not True:
        raise SystemExit(
            f"ABORT: firm {firm.id} ({firm.slug}) has is_demo={firm.is_demo!r}, "
            f"not True. Refusing to delete a non-demo firm. Delete nothing."
        )

    firm_id = firm.id
    print(f"Confirmed demo firm: {firm_id} {firm.name!r} is_demo={firm.is_demo}")

    order = _dependency_ordered_firm_tables()
    from sqlalchemy import text
    deleted = {}
    for name in order:
        if name == "firms":
            continue
        if name in GRANDCHILD_TABLES:
            model_module, model_cls, fk_col, parent_module, parent_cls, parent_fk = GRANDCHILD_TABLES[name]
            Model = _import_class(model_module, model_cls)
            Parent = _import_class(parent_module, parent_cls)
            parent_ids = db.query(Parent.id).filter(getattr(Parent, parent_fk) == firm_id).subquery()
            n = db.query(Model).filter(getattr(Model, fk_col).in_(select(parent_ids.c.id))).delete(synchronize_session=False)
        else:
            n = db.execute(text(f'DELETE FROM "{name}" WHERE firm_id = :fid'), {"fid": str(firm_id)}).rowcount
        if n:
            deleted[name] = n

    firm_deleted = db.query(Firm).filter(Firm.id == firm_id).delete(synchronize_session=False)
    deleted["firms"] = firm_deleted
    db.commit()

    print("Teardown committed. Deleted row counts (nonzero only):")
    total = 0
    for name, n in deleted.items():
        print(f"  {name}: {n}")
        total += n
    print(f"TOTAL rows deleted: {total}")


# ---------------------------------------------------------------------------
# Setup: firm, staff, clients
# ---------------------------------------------------------------------------

def setup_firm(db) -> Firm:
    existing = db.execute(select(Firm).where(Firm.slug == FIRM["slug"])).scalar_one_or_none()
    if existing is not None:
        raise SystemExit(
            f"ABORT: a firm with slug={FIRM['slug']!r} already exists (id={existing.id}). "
            f"Run --teardown first if you intend to reseed."
        )

    firm = firm_service.create_firm(
        db,
        FirmCreate(name=FIRM["name"], slug=FIRM["slug"], subscription_tier=FIRM["subscription_tier"]),
        current_user_id=uuid.uuid4(),  # no staff exist yet; setup-time pseudo-actor
    )
    firm.is_demo = True
    db.commit()
    db.refresh(firm)
    STATS.note_entity("firms")

    n_presets = automation_presets.seed_firm_presets(firm.id, db)
    STATS.note_entity("automation_rules", n_presets)

    doc_reminder_rule = db.execute(
        select(AutomationRule).where(
            AutomationRule.firm_id == firm.id,
            AutomationRule.preset_key == "doc_request_reminder_3day",
        )
    ).scalar_one_or_none()
    if doc_reminder_rule is not None:
        automation_rule_service.toggle_automation_rule(db, doc_reminder_rule, True, firm_id=firm.id)

    return firm


def setup_staff(db, firm: Firm) -> dict:
    staff = {}
    for persona in STAFF_PERSONAS:
        user = crud_user.create_user(
            db,
            UserCreate(
                email=persona["email"],
                full_name=persona["full_name"],
                role=UserRole(persona["role"]),
                password=DEMO_PASSWORD,
                firm_id=firm.id,
            ),
        )
        staff[persona["key"]] = user
        STATS.note_entity("users")
    return staff


def setup_clients(db, firm: Firm, actor_id) -> tuple[list, list]:
    hero_records = []
    for cfg in HERO_CLIENTS:
        client = client_service.create_client(
            db=db,
            payload=ClientCreate(
                name=cfg["name"],
                email=f"{cfg['key']}@democlient-cedarvance.com",
                is_active=True,
                entity_type="business" if cfg["engagement_type"] in BUSINESS_ENGAGEMENT_TYPES else "individual",
            ),
            firm_id=firm.id,
            current_user_id=actor_id,
        )
        hero_records.append({**cfg, "client": client})
        STATS.note_entity("clients")

    population_records = []
    pop = POPULATION
    bands = list(pop["individual_bands"].keys())
    band_weights = list(pop["individual_bands"].values())
    upload_styles = list(pop["upload_style_weights"].keys())
    upload_weights = list(pop["upload_style_weights"].values())
    invoice_tiers = list(pop["invoice_tier_weights"].keys())
    invoice_weights = list(pop["invoice_tier_weights"].values())
    portal_levels = list(pop["portal_activity_weights"].keys())
    portal_weights = list(pop["portal_activity_weights"].values())

    def _gen(n, name_prefix, engagement_type_choices):
        for i in range(1, n + 1):
            band = random.choices(bands, weights=band_weights)[0] if engagement_type_choices == "individual" else "n/a"
            engagement_type = (
                "tax_return_1040" if engagement_type_choices == "individual"
                else engagement_type_choices
            )
            client = client_service.create_client(
                db=db,
                payload=ClientCreate(
                    name=f"{name_prefix} {i}",
                    email=f"{name_prefix.lower().replace(' ', '')}{i}@democlient-cedarvance.com",
                    is_active=True,
                    entity_type="business" if engagement_type in BUSINESS_ENGAGEMENT_TYPES else "individual",
                ),
                firm_id=firm.id,
                current_user_id=actor_id,
            )
            STATS.note_entity("clients")
            population_records.append({
                "key": f"{name_prefix}_{i}",
                "client": client,
                "engagement_type": engagement_type,
                "band": band,
                "upload_style": random.choices(upload_styles, weights=upload_weights)[0],
                "invoice_tier": random.choices(invoice_tiers, weights=invoice_weights)[0],
                "portal_activity": random.choices(portal_levels, weights=portal_weights)[0],
            })

    _gen(pop["individual_count"], "Individual Client", "individual")
    _gen(pop["business_count"], "Business Client", random.choice(BUSINESS_ENGAGEMENT_TYPES))
    _gen(pop["bookkeeping_count"], "Bookkeeping Client", "bookkeeping_monthly")

    return hero_records, population_records


# ---------------------------------------------------------------------------
# Persona / choreography helpers
# ---------------------------------------------------------------------------

def is_march_or_april(y: int, m: int) -> bool:
    return m in (3, 4)


def persona_active_today(persona: dict, d: date) -> bool:
    if "active_window" in persona:
        (sm, sd), (em, ed) = persona["active_window"]
        start = date(d.year, sm, sd)
        end = date(d.year, em, ed)
        if not (start <= d <= end):
            return False
    weekday = d.weekday()  # 0=Mon .. 6=Sun
    if weekday < 5:
        return True
    if weekday == 5 and persona.get("weekend") and is_march_or_april(d.year, d.month):
        return True
    return False


def staff_login(db, user, persona, d: date):
    hour = random.randint(*persona["login_window"])
    minute_range = persona.get("login_minute_range", (0, 59))
    minute = random.randint(*minute_range)
    with frozen(datetime(d.year, d.month, d.day, hour, minute, tzinfo=timezone.utc)):
        try:
            auth_service.authenticate_staff(
                db=db,
                login_data=LoginRequest(username=user.email, password=DEMO_PASSWORD),
            )
            STATS.events_by_type["user.login"] = STATS.events_by_type.get("user.login", 0) + 1
        except Exception as e:
            STATS.failures.append(("staff_login", persona["key"], str(e)))

    if persona.get("after_hours_window") and is_march_or_april(d.year, d.month) and d.weekday() < 5:
        if random.random() < 0.35:
            ah_hour = random.randint(*persona["after_hours_window"])
            with frozen(datetime(d.year, d.month, d.day, ah_hour, random.randint(0, 59), tzinfo=timezone.utc)):
                try:
                    auth_service.authenticate_staff(
                        db=db,
                        login_data=LoginRequest(username=user.email, password=DEMO_PASSWORD),
                    )
                except Exception as e:
                    STATS.failures.append(("staff_login_after_hours", persona["key"], str(e)))


def pick_persona_for_engagement(is_hero: bool, staff: dict) -> str:
    if is_hero:
        weights = {k: p["touches_hero_share"] for k, p in ((per["key"], per) for per in STAFF_PERSONAS)}
        keys = list(weights.keys())
        w = list(weights.values())
        return random.choices(keys, weights=w)[0]
    non_seasonal = [p["key"] for p in STAFF_PERSONAS if p["key"] not in ("owner", "seasonal_preparer")]
    return random.choice(non_seasonal)


# ---------------------------------------------------------------------------
# Per-client engagement lifecycle (real service calls throughout)
# ---------------------------------------------------------------------------

def run_client_lifecycle(db, firm, staff, record, creation_date: date, window_end: date):
    client = record["client"]
    engagement_type = record["engagement_type"]
    upload_style = record.get("upload_style", "batch")
    invoice_tier = record.get("invoice_tier", "middle")
    actor_key = pick_persona_for_engagement(record.get("tier") == "hero", staff)
    actor = staff[actor_key]

    create_hour = random.randint(*CHOREOGRAPHY["staff_login_cluster"])
    with frozen(datetime(creation_date.year, creation_date.month, creation_date.day, create_hour, random.randint(0, 59), tzinfo=timezone.utc)):
        deadline = compute_deadline(engagement_type, creation_date)

        engagement = run_async(
            engagement_service.create_engagement,
            db=db, payload=EngagementCreate(
                name=f"{client.name} - {engagement_type}",
                client_id=client.id,
                engagement_type=engagement_type,
                filing_deadline=deadline,
            ),
            firm_id=firm.id, current_user_id=actor.id,
        )
    STATS.note_entity("engagements")

    doc_request = None
    if engagement_type != "bookkeeping_monthly":
        req_date = creation_date + timedelta(days=random.randint(1, 3))
        with frozen(datetime(req_date.year, req_date.month, req_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
            checklist = [
                ChecklistItem(id=str(uuid.uuid4()), label=f"Document {i}", is_required=True, status="pending")
                for i in range(1, random.randint(2, 5))
            ]
            doc_request = document_request_service.create_document_request(
                db=db,
                payload=DocumentRequestCreate(
                    title=f"Documents needed - {client.name}",
                    due_date=req_date + timedelta(days=21),
                    checklist_items=checklist,
                    client_id=client.id,
                    engagement_id=engagement.id,
                ),
                firm_id=firm.id, current_user_id=actor.id,
            )
        STATS.note_entity("document_requests")

        reminders_needed = 1
        if upload_style == "chronic_slow":
            reminders_needed = record.get("reminders_min", 3)
        elif upload_style == "drip":
            reminders_needed = random.randint(1, 2)

        upload_day = req_date
        for r in range(reminders_needed):
            reminder_date = req_date + timedelta(days=3 + r * 7)
            if reminder_date > window_end:
                break
            with frozen(datetime(reminder_date.year, reminder_date.month, reminder_date.day, 10, 0, tzinfo=timezone.utc)):
                try:
                    document_request_service.send_document_request_reminder(
                        db=db, request_id=doc_request.id, firm_id=firm.id, current_user_id=actor.id,
                    )
                except Exception as e:
                    STATS.failures.append(("send_reminder", client.name, str(e)))
            if random.random() < CHOREOGRAPHY["reminder_to_upload_share"]:
                upload_day = reminder_date + timedelta(hours=random.randint(4, 47))
            else:
                upload_day = reminder_date + timedelta(days=random.randint(3, 10))

        n_items = len(checklist)
        upload_days = [upload_day]
        if upload_style == "drip":
            upload_days = [upload_day + timedelta(days=d) for d in sorted(random.sample(range(0, 21), min(n_items, 3)))]

        # NOTE: portal-side upload routing (portal_service.upload_document)
        # was tried and reverted - that function passes client.id into
        # Document.uploaded_by, which has a hard FK to users.id, so it fails
        # on every real client upload. Backlogged as PRE-LAUNCH CRITICAL, not
        # fixed this session (would require a schema change/migration).
        # portal_utilization_documents stays at 0.0 for a documented reason:
        # the portal upload path is broken in production, not a seed gap.
        for idx, item in enumerate(checklist):
            u_day = upload_days[idx % len(upload_days)]
            if u_day > window_end:
                continue
            with frozen(datetime(u_day.year, u_day.month, u_day.day, random.randint(19, 21), random.randint(0, 59), tzinfo=timezone.utc)):
                try:
                    f = make_upload_file(f"{item.label}.pdf")
                    document_service.upload_document(
                        db=db, file=f, client_id=client.id, engagement_id=engagement.id,
                        firm_id=firm.id, current_user_id=actor.id,
                    )
                    STATS.note_entity("documents")
                    document_request_service.update_checklist_item_status(
                        db=db, request_id=doc_request.id, item_id=item.id,
                        new_status="uploaded", firm_id=firm.id, current_user_id=actor.id,
                    )
                except Exception as e:
                    STATS.failures.append(("upload_document", client.name, str(e)))

        complete_date = upload_days[-1] + timedelta(days=1)
        if complete_date <= window_end:
            with frozen(datetime(complete_date.year, complete_date.month, complete_date.day, 11, 0, tzinfo=timezone.utc)):
                try:
                    document_request_service.update_document_request(
                        db=db, request_id=doc_request.id,
                        payload=DocumentRequestUpdate(status="complete"),
                        firm_id=firm.id, current_user_id=actor.id,
                    )
                except Exception as e:
                    STATS.failures.append(("complete_doc_request", client.name, str(e)))
        # else: last upload falls beyond window_end - request stays pending,
        # a realistic still-open document request as of demo day.

    task_date = creation_date + timedelta(days=random.randint(1, 4))
    with frozen(datetime(task_date.year, task_date.month, task_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
        task = task_service.create_task(
            db=db, payload=TaskCreate(
                title=f"Prepare {engagement_type} - {client.name}",
                client_id=client.id, engagement_id=engagement.id,
                assigned_to=actor.id,
            ),
            firm_id=firm.id, current_user_id=actor.id,
        )
    STATS.note_entity("tasks")

    hours = round(random.uniform(1.5, 6.0), 1)
    if record.get("scope_creep"):
        hours *= record.get("extra_hours_multiplier", 1.0)
    lag = STAFF_PERSONAS_BY_KEY[actor_key]["time_entry_lag"]
    entry_date = task_date
    if lag == "next_morning":
        entry_date = task_date + timedelta(days=1)
    elif lag == "catch_up_2_3_day":
        entry_date = task_date + timedelta(days=random.randint(2, 3))
    if entry_date <= window_end:
        with frozen(datetime(entry_date.year, entry_date.month, entry_date.day, random.randint(17, 20), random.randint(0, 59), tzinfo=timezone.utc)):
            try:
                time_entry_service.create_time_entry(
                    db=db, payload=TimeEntryCreate(
                        engagement_id=engagement.id, description=f"Work on {engagement_type}",
                        hours=hours, hourly_rate=185.0, date=entry_date,
                    ),
                    firm_id=firm.id, current_user=actor,
                )
                STATS.note_entity("time_entries")
            except Exception as e:
                STATS.failures.append(("time_entry", client.name, str(e)))
    # else: the lag would push logging past window_end - the persona simply
    # hasn't logged this time yet, a realistic in-flight state.

    extended = False
    if deadline and deadline.month in (3, 4) and engagement_type in FORM_TYPE_BY_ENGAGEMENT_TYPE:
        if random.random() < 0.2:
            file_date = deadline - timedelta(days=random.randint(3, 10))
            if task_date < file_date <= window_end:
                with frozen(datetime(file_date.year, file_date.month, file_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
                    try:
                        eng_row = db.get(Engagement, engagement.id)
                        run_async(
                            extension_service.file_extension,
                            db=db, payload=ExtensionCreate(
                                form_type=FORM_TYPE_BY_ENGAGEMENT_TYPE[engagement_type],
                                engagement_id=engagement.id, client_id=client.id,
                            ),
                            engagement=eng_row, firm_id=firm.id, actor_id=actor.id,
                        )
                        STATS.note_entity("extensions")
                        extended = True
                    except Exception as e:
                        STATS.failures.append(("file_extension", client.name, str(e)))

    if extended:
        eng_row = db.get(Engagement, engagement.id)
        deadline = eng_row.extended_deadline or deadline

    # A small share of March/April-crunch (non-extended) engagements
    # deliberately miss their deadline, so deadline adherence reads strong
    # but not a flat 100%. Detected organically by the real weekly
    # deadline_scheduler.check_approaching_deadlines() sweep (see run_month),
    # which fires engagement.deadline_missed once the deadline has passed
    # while the engagement is still not completed.
    is_march_april_deadline = deadline is not None and deadline.month in (3, 4) and not extended
    miss = is_march_april_deadline and random.random() < MISS_RATE

    # Mark the engagement actively in progress shortly after task creation -
    # a real WIP signal regardless of whether it naturally completes within
    # the window, so engagements left incomplete look mid-stream, not untouched.
    active_date = min(task_date + timedelta(days=1), window_end)
    with frozen(datetime(active_date.year, active_date.month, active_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
        try:
            run_async(
                engagement_service.update_engagement,
                db=db, engagement_id=engagement.id,
                payload=EngagementUpdate(status="active"),
                firm_id=firm.id, current_user_id=actor.id,
            )
        except Exception as e:
            STATS.failures.append(("activate_engagement", client.name, str(e)))

    if miss:
        # Do not complete inline - defer until after the full month loop's
        # organic weekly sweeps have had a genuine chance to detect this
        # engagement as past-deadline and still open. See
        # finalize_deferred_misses().
        complete_target = deadline + timedelta(days=random.randint(2, 12))
        complete_target = max(complete_target, task_date + timedelta(days=2))
        DEFERRED_MISSES.append({
            "engagement_id": engagement.id, "client": client, "actor": actor,
            "deadline": deadline, "complete_target": complete_target,
            "hours": hours, "invoice_tier": invoice_tier,
        })
        return

    complete_target = deadline - timedelta(days=random.randint(1, 10)) if deadline else task_date + timedelta(days=14)
    complete_target = max(complete_target, task_date + timedelta(days=2))

    if complete_target <= window_end:
        _complete_and_invoice(db, firm, actor, engagement.id, client, complete_target, hours, invoice_tier, window_end)
    # else: natural completion date falls beyond window_end - the engagement
    # stays "active" (open WIP) as of demo day, exactly as intended.


def _complete_and_invoice(db, firm, actor, engagement_id, client, complete_target, hours, invoice_tier, window_end):
    completed = False
    with frozen(datetime(complete_target.year, complete_target.month, complete_target.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
        try:
            run_async(
                engagement_service.update_engagement,
                db=db, engagement_id=engagement_id,
                payload=EngagementUpdate(status="completed"),
                firm_id=firm.id, current_user_id=actor.id,
            )
            STATS.note_entity("engagement_completions")
            completed = True
        except Exception as e:
            STATS.failures.append(("complete_engagement", client.name, str(e)))

    if not completed:
        return

    invoice_date = complete_target + timedelta(days=random.randint(0, 3))
    if invoice_date > window_end:
        return  # completed but the natural invoicing lag pushes past window_end

    invoice = None
    with frozen(datetime(invoice_date.year, invoice_date.month, invoice_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
        try:
            amount = round(hours * 185.0, 2)
            invoice = run_async(
                invoice_service.create_invoice,
                db=db, payload=InvoiceCreate(
                    invoice_number=f"INV-{uuid.uuid4().hex[:8].upper()}",
                    line_items=[LineItemSchema(description="Professional services", quantity=1, unit_price=amount, amount=amount, total=amount)],
                    subtotal=amount, total_amount=amount,
                    due_date=invoice_date + timedelta(days=14),
                    client_id=client.id, engagement_id=engagement_id,
                ),
                firm_id=firm.id, current_user_id=actor.id,
            )
            STATS.note_entity("invoices")
            run_async(
                invoice_service.send_invoice,
                db=db, invoice_id=invoice.id, firm_id=firm.id, current_user_id=actor.id,
            )
        except Exception as e:
            STATS.failures.append(("invoice", client.name, str(e)))
            invoice = None

    if invoice is not None:
        _run_invoice_payment(db, firm, invoice, invoice_date, invoice_tier, actor, window_end)


def finalize_deferred_misses(db, firm, window_end):
    """
    Runs once, after the entire month loop (and every organic weekly
    deadline_scheduler.check_approaching_deadlines() sweep within it) has
    already executed. Every deferred miss sat "active" with a passed
    deadline throughout that whole loop, so the real scheduler had genuine,
    repeated organic opportunity to detect it and fire
    engagement.deadline_missed - this pass never fires that event itself,
    it only resolves what happens next for each miss.

    Misses whose deadline falls in the final stretch of the window stay
    active/open permanently - real stragglers still outstanding on demo
    day. The rest complete late now, well after the detection window.
    """
    LATE_WINDOW_CUTOFF_DAYS = 60
    for miss in DEFERRED_MISSES:
        deadline = miss["deadline"]
        complete_target = miss["complete_target"]
        if (window_end - deadline).days < LATE_WINDOW_CUTOFF_DAYS or complete_target > window_end:
            continue  # stays active/open permanently
        _complete_and_invoice(
            db, firm, miss["actor"], miss["engagement_id"], miss["client"],
            complete_target, miss["hours"], miss["invoice_tier"], window_end,
        )


def _run_invoice_payment(db, firm, invoice, invoice_date, invoice_tier, actor, window_end):
    from app.services import portal_service

    client_row = db.get(Client, invoice.client_id)

    def _view_at(dt):
        if dt.date() > window_end:
            return
        with frozen(dt):
            try:
                portal_service.log_invoice_viewed(db=db, invoice=invoice, client=client_row)
                STATS.note_entity("invoice_views")
            except Exception as e:
                STATS.failures.append(("invoice_viewed", client_row.name if client_row else "?", str(e)))

    # Natural (uncapped) dates throughout - if the natural pay day falls
    # beyond window_end, the invoice stays outstanding/overdue as of demo
    # day rather than being force-paid at window_end.
    pay_dt = None
    if invoice_tier == "pay_on_view":
        # pay-on-view clients view then pay within minutes
        view_dt = datetime(invoice_date.year, invoice_date.month, invoice_date.day,
                            random.randint(18, 21), random.randint(0, 50), tzinfo=timezone.utc)
        _view_at(view_dt)
        pay_dt = view_dt + timedelta(minutes=random.randint(2, 15))
        pay_day = pay_dt.date()
    elif invoice_tier == "slow_tail":
        # slow-tail clients view 2 to 4 times spread across the delay before eventually paying
        days = random.randint(35, 60)
        pay_day = invoice_date + timedelta(days=days)
        n_views = random.randint(2, 4)
        for i in range(n_views):
            offset = round((i + 1) * days / (n_views + 1))
            view_day = invoice_date + timedelta(days=offset)
            _view_at(datetime(view_day.year, view_day.month, view_day.day,
                               random.randint(9, 21), random.randint(0, 59), tzinfo=timezone.utc))
    else:
        # middle tier views within 2 days, pays later per the existing window
        pay_day = invoice_date + timedelta(days=random.randint(7, 20))
        view_day = invoice_date + timedelta(days=random.randint(0, 2))
        _view_at(datetime(view_day.year, view_day.month, view_day.day,
                           random.randint(9, 21), random.randint(0, 59), tzinfo=timezone.utc))

    if pay_day > window_end:
        return  # stays sent/overdue as of demo day - not force-paid

    if pay_dt is not None and pay_dt.date() == pay_day:
        freeze_dt = pay_dt
    else:
        freeze_dt = datetime(pay_day.year, pay_day.month, pay_day.day, random.randint(19, 21), random.randint(0, 59), tzinfo=timezone.utc)

    with frozen(freeze_dt):
        try:
            invoice_service.mark_invoice_paid(db=db, invoice=invoice, firm_id=firm.id)
            from app.crud import invoice as crud_invoice
            crud_invoice.mark_invoice_paid(db, invoice, stripe_charge_id=None)
        except Exception as e:
            STATS.failures.append(("mark_paid", str(invoice.id), str(e)))


STAFF_PERSONAS_BY_KEY = {p["key"]: p for p in STAFF_PERSONAS}


def seed_prior_season_extensions(db, firm, staff, all_records, window_start, window_end):
    """
    Backfill a batch of engagements anchored to the tax season that already
    concluded BEFORE window_start (window_start.year's Apr 15 / Mar 15
    original deadlines, extended to that same year's Oct 15 / Sep 15) -
    unlike the current-season extensions produced during the normal monthly
    loop (which always resolve to a not-yet-arrived Sep/Oct of the *coming*
    season and so can never populate deadline_adherence_extended's "already
    resolved" condition), these extended deadlines are already in the past
    relative to any real run date, so the extended track gets real,
    resolvable sample size instead of reading empty on demo day.
    """
    individual_candidates = [r for r in all_records if r.get("engagement_type") in INDIVIDUAL_RETURN_TYPES]
    business_candidates = [r for r in all_records if r.get("engagement_type") in BUSINESS_RETURN_TYPES]
    n_individual = min(12, len(individual_candidates))
    n_business = min(12, len(business_candidates))
    chosen = (
        random.sample(individual_candidates, n_individual) +
        random.sample(business_candidates, n_business)
    )

    for record in chosen:
        client = record["client"]
        engagement_type = record["engagement_type"]
        is_individual = engagement_type in INDIVIDUAL_RETURN_TYPES
        original = date(window_start.year, 4, 15) if is_individual else date(window_start.year, 3, 15)
        extended = date(window_start.year, 10, 15) if is_individual else date(window_start.year, 9, 15)
        form_type = FORM_TYPE_BY_ENGAGEMENT_TYPE[engagement_type]

        create_date = window_start + timedelta(days=random.randint(0, 10))
        actor = staff[pick_persona_for_engagement(record.get("tier") == "hero", staff)]

        with frozen(datetime(create_date.year, create_date.month, create_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
            engagement = run_async(
                engagement_service.create_engagement,
                db=db, payload=EngagementCreate(
                    name=f"{client.name} - {engagement_type} (prior season)",
                    client_id=client.id, engagement_type=engagement_type,
                    filing_deadline=original,
                ),
                firm_id=firm.id, current_user_id=actor.id,
            )
        STATS.note_entity("engagements")

        file_date = create_date + timedelta(days=random.randint(2, 8))
        with frozen(datetime(file_date.year, file_date.month, file_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
            try:
                eng_row = db.get(Engagement, engagement.id)
                run_async(
                    extension_service.file_extension,
                    db=db, payload=ExtensionCreate(
                        form_type=form_type, engagement_id=engagement.id, client_id=client.id,
                        extended_deadline=extended,
                    ),
                    engagement=eng_row, firm_id=firm.id, actor_id=actor.id,
                )
                STATS.note_entity("extensions")
            except Exception as e:
                STATS.failures.append(("prior_season_extension", client.name, str(e)))
                continue

        complete_date = extended - timedelta(days=random.randint(2, 12))
        with frozen(datetime(complete_date.year, complete_date.month, complete_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
            try:
                run_async(
                    engagement_service.update_engagement,
                    db=db, engagement_id=engagement.id,
                    payload=EngagementUpdate(status="completed"),
                    firm_id=firm.id, current_user_id=actor.id,
                )
                STATS.note_entity("engagement_completions")
            except Exception as e:
                STATS.failures.append(("prior_season_complete", client.name, str(e)))


def seed_late_window_outstanding_invoices(db, firm, staff, all_records, window_end):
    """
    Reserve a small batch of clients whose engagement completes and gets
    invoiced in the final 30-45 days of the window, weighted toward the
    slow_tail invoice tier, so their natural pay date is guaranteed to
    exceed window_end - real, unforced outstanding/overdue invoices on
    demo day, rather than every invoice happening to resolve before the
    window closes (which is what the seasonal taper otherwise produces,
    since completions drop off sharply well before window_end).
    """
    n = min(15, len(all_records))
    chosen = random.sample(all_records, n)

    for record in chosen:
        client = record["client"]
        actor = staff[pick_persona_for_engagement(record.get("tier") == "hero", staff)]
        invoice_tier = random.choices(["slow_tail", "middle"], weights=[0.7, 0.3])[0]

        create_date = window_end - timedelta(days=random.randint(30, 40))
        with frozen(datetime(create_date.year, create_date.month, create_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
            engagement = run_async(
                engagement_service.create_engagement,
                db=db, payload=EngagementCreate(
                    name=f"{client.name} - bookkeeping_monthly (late window)",
                    client_id=client.id, engagement_type="bookkeeping_monthly",
                    filing_deadline=date(create_date.year, create_date.month,
                                          days_in_month(create_date.year, create_date.month)),
                ),
                firm_id=firm.id, current_user_id=actor.id,
            )
        STATS.note_entity("engagements")

        task_date = create_date + timedelta(days=random.randint(1, 3))
        with frozen(datetime(task_date.year, task_date.month, task_date.day, random.randint(9, 16), random.randint(0, 59), tzinfo=timezone.utc)):
            task_service.create_task(
                db=db, payload=TaskCreate(
                    title=f"Monthly close - {client.name}",
                    client_id=client.id, engagement_id=engagement.id, assigned_to=actor.id,
                ),
                firm_id=firm.id, current_user_id=actor.id,
            )
        STATS.note_entity("tasks")

        hours = round(random.uniform(1.5, 4.0), 1)
        complete_target = task_date + timedelta(days=random.randint(2, 5))
        if complete_target <= window_end:
            _complete_and_invoice(db, firm, actor, engagement.id, client, complete_target, hours, invoice_tier, window_end)


# ---------------------------------------------------------------------------
# Chat and notes
# ---------------------------------------------------------------------------

def setup_chat_channel(db, firm, staff):
    owner = staff["owner"]
    channel = firm_chat_service.create_channel(
        db, firm_id=firm.id, requesting_user=owner, data=ChannelCreate(name="general"),
    )
    STATS.note_entity("channels")
    return channel


def fire_chat_and_notes_for_day(db, firm, staff, channel, d: date, clients_touched):
    for persona in STAFF_PERSONAS:
        if not persona.get("chat_active"):
            continue
        if not persona_active_today(persona, d):
            continue
        if random.random() < 0.15:
            hour = random.randint(9, 17)
            with frozen(datetime(d.year, d.month, d.day, hour, random.randint(0, 59), tzinfo=timezone.utc)):
                try:
                    firm_chat_service.send_message(
                        db, firm_id=firm.id, channel_id=channel.id,
                        sender_user=staff[persona["key"]],
                        data=FirmMessageCreate(body="Status update on client work."),
                    )
                except Exception as e:
                    STATS.failures.append(("chat", persona["key"], str(e)))

    if clients_touched and random.random() < 0.1:
        client = random.choice(clients_touched)
        actor = random.choice([staff["owner"], staff["manager"], staff["preparer_a"]])
        hour = random.randint(9, 17)
        with frozen(datetime(d.year, d.month, d.day, hour, random.randint(0, 59), tzinfo=timezone.utc)):
            try:
                note_service.create_note(
                    db, firm_id=firm.id, author_id=actor.id,
                    data=NoteCreate(body="Follow-up needed next cycle.", entity_type="client", entity_id=client.id),
                )
                STATS.note_entity("notes")
            except Exception as e:
                STATS.failures.append(("note", client.name, str(e)))


# ---------------------------------------------------------------------------
# Portal activity
# ---------------------------------------------------------------------------

def portal_activity_for_client(db, firm, record, d: date, window_end: date):
    level = record.get("portal_activity", "medium")
    prob = {"low": 0.03, "medium": 0.08, "high": 0.18}.get(level, 0.08)
    if random.random() > prob:
        return
    hour_range = CHOREOGRAPHY["portal_evening_peak"] if d.weekday() < 5 else CHOREOGRAPHY["portal_sunday_afternoon"]
    hour = random.randint(*hour_range)
    with frozen(datetime(d.year, d.month, d.day, hour, random.randint(0, 59), tzinfo=timezone.utc)):
        try:
            client = record["client"]
            _, raw_token = portal_magic_link.generate_magic_link(
                client_id=client.id, firm_id=firm.id, expiry_hours=48, db=db,
            )
            STATS.note_entity("portal_invites")
            portal_magic_link.exchange_magic_link(token=raw_token, db=db)
            STATS.note_entity("portal_logins")
        except Exception as e:
            STATS.failures.append(("portal_login", record.get("key", "?"), str(e)))


# ---------------------------------------------------------------------------
# Main seasonal month loop
# ---------------------------------------------------------------------------

def run_month(db, firm, staff, channel, all_records, y, m, window_end):
    n_days = days_in_month(y, m)
    events_before = sum(STATS.events_by_type.values())
    entities_before = dict(STATS.entities_created)

    for day_num in range(1, n_days + 1):
        d = date(y, m, day_num)
        if d > window_end:
            break
        if (m, day_num) == (12, 24) or (m == 12 and day_num > 23) or (m == 1 and day_num == 1):
            continue  # near-silence Dec 23 - Jan 1

        for persona in STAFF_PERSONAS:
            if persona_active_today(persona, d):
                staff_login(db, staff[persona["key"]], persona, d)

    n_clients_this_month = max(1, len(all_records) // 12)
    month_clients = random.sample(all_records, min(n_clients_this_month, len(all_records)))
    touched_clients = []
    for record in month_clients:
        creation_day = random.randint(1, n_days)
        creation_date = date(y, m, creation_day)
        if creation_date > window_end:
            continue
        try:
            run_client_lifecycle(db, firm, staff, record, creation_date, window_end)
            touched_clients.append(record["client"])
        except Exception as e:
            STATS.failures.append(("client_lifecycle", record.get("key", "?"), f"{e}\n{traceback.format_exc(limit=3)}"))

    for day_num in range(1, n_days + 1):
        d = date(y, m, day_num)
        if d > window_end:
            continue
        if d.weekday() == 0:  # weekly cadence, mirrors the real nightly/weekly sweep job
            with frozen(datetime(d.year, d.month, d.day, 2, 0, tzinfo=timezone.utc)):
                try:
                    invoice_service.run_invoice_overdue_sweep()
                except Exception as e:
                    STATS.failures.append(("overdue_sweep", month_progress_label(y, m), str(e)))
                try:
                    deadline_scheduler.check_approaching_deadlines()
                except Exception as e:
                    STATS.failures.append(("deadline_sweep", month_progress_label(y, m), str(e)))

    for day_num in range(1, n_days + 1):
        d = date(y, m, day_num)
        if d > window_end:
            continue
        for record in random.sample(all_records, min(20, len(all_records))):
            portal_activity_for_client(db, firm, record, d, window_end)

    for day_num in range(1, n_days + 1):
        d = date(y, m, day_num)
        if d > window_end:
            continue
        fire_chat_and_notes_for_day(db, firm, staff, channel, d, touched_clients)

    db.commit()

    events_after = sum(STATS.events_by_type.values())
    print(f"[{month_progress_label(y, m)}] entities_created_delta="
          f"{ {k: v - entities_before.get(k, 0) for k, v in STATS.entities_created.items()} }")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    global MISS_RATE
    args = ARGS

    _install_network_suppression()

    seed = int.from_bytes(os.urandom(4), "little")
    random.seed(seed)
    print(f"Random seed for this run: {seed}")

    MISS_RATE = random.uniform(0.03, 0.08)
    print(f"March/April deadline miss rate for this run: {MISS_RATE:.3f}")

    db = SessionLocal()
    try:
        if args.teardown:
            teardown(db)
            return

        today = date.today()
        window_start, window_end = window_bounds(args.months, today)
        print(f"Simulated window: {window_start} .. {window_end}")

        # Firm creation happens under freeze_time at window_start so its own
        # created_at/firm.created event land at the start of the simulated
        # history, matching every other organic event in this run.
        with frozen(datetime(window_start.year, window_start.month, window_start.day, 9, 0, tzinfo=timezone.utc)):
            firm = setup_firm(db)

        # Unfrozen warmup event - pre-warms the log_event connection pool
        # before the timing-sensitive simulation loop begins. Fires at real
        # wall-clock time (not part of the simulated history), using the
        # now-real firm id since behavioral_events.firm_id has a hard FK
        # constraint - a placeholder id would violate it. Permanent, never deleted.
        log_event(
            event_type=WARMUP_EVENT_TYPE,
            firm_id=firm.id,
            metadata={"note": "seed warmup, connection pool pre-warm"},
        )

        with frozen(datetime(window_start.year, window_start.month, window_start.day, 9, 0, tzinfo=timezone.utc)):
            staff = setup_staff(db, firm)
            hero_records, population_records = setup_clients(db, firm, staff["owner"].id)
            channel = setup_chat_channel(db, firm, staff)

        all_records = hero_records + population_records

        seed_prior_season_extensions(db, firm, staff, all_records, window_start, window_end)

        start_time = _time_module.time()
        for y, m in month_iter(window_start, window_end):
            run_month(db, firm, staff, channel, all_records, y, m, window_end)

        # Every deferred miss has now sat "active" with a passed deadline
        # through the entire month loop's organic weekly sweeps - resolve
        # each one (late completion, or stays open permanently) only now.
        finalize_deferred_misses(db, firm, window_end)

        seed_late_window_outstanding_invoices(db, firm, staff, all_records, window_end)

        # One final sweep at window_end - exactly what the real nightly job
        # would do if run today - so the reserved late-window invoices (and
        # anything else still open) that have genuinely passed their due
        # date get organically flipped to overdue before demo day, instead
        # of sitting unpaid-but-never-checked just because no further sweep
        # was scheduled after this post-loop pass created them.
        with frozen(datetime(window_end.year, window_end.month, window_end.day, 2, 0, tzinfo=timezone.utc)):
            try:
                invoice_service.run_invoice_overdue_sweep()
            except Exception as e:
                STATS.failures.append(("final_overdue_sweep", "window_end", str(e)))
            try:
                deadline_scheduler.check_approaching_deadlines()
            except Exception as e:
                STATS.failures.append(("final_deadline_sweep", "window_end", str(e)))

        elapsed = _time_module.time() - start_time

        print()
        print("=== RUN SUMMARY ===")
        print(f"Wall-clock runtime: {elapsed:.1f}s")
        print(f"Entities created: {STATS.entities_created}")
        print(f"Failures: {len(STATS.failures)}")
        for f in STATS.failures[:20]:
            print("  FAILURE:", f)

        from app.models.behavioral_event import BehavioralEvent
        from sqlalchemy import func
        rows = db.execute(
            select(BehavioralEvent.event_type, func.count()).where(
                BehavioralEvent.firm_id == firm.id
            ).group_by(BehavioralEvent.event_type)
        ).all()
        print("Events fired by event_type:")
        total_events = 0
        for event_type, count in sorted(rows, key=lambda r: -r[1]):
            print(f"  {event_type}: {count}")
            total_events += count
        print(f"TOTAL events: {total_events}")

        print(f"Suppressed email sends: {SUPPRESSED_SEND_COUNTS['email']}")
        print(f"Suppressed webhook posts: {SUPPRESSED_SEND_COUNTS['webhook']}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
