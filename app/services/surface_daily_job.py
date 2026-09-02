# app/services/surface_daily_job.py

"""
The daily job that maintains surface_items.

Runs once per firm per day at 5am in that firm's own local time. It is
registered as an hourly tick rather than a daily cron because "5am local" is a
different UTC moment for every firm, and Firm.timezone is the column that says
which. The tick is cheap: it reads the firm list, converts, and does nothing
for the firms whose local hour is not 5.

Order of work per firm, which matters:

  1. evaluate every generator and upsert the conditions that are true now
  2. evaluate clear conditions on every OPEN row, including suppressed ones and
     permanently dismissed ones
  3. expire suppression windows that have run their course, writing the delta
  4. recompute ranks across the active rows
  5. slot the top briefing rows and unslot yesterday's

Step 2 covers permanently dismissed rows deliberately. A row dismissed
not_relevant whose condition later clears gets resolved_at set, so the truth is
recorded and the dedup block releases, while the row still never resurfaced to
anybody. Recording that it ended is not the same as showing it again.

This module reads operational tables only. It never reads the behavioral log to
decide anything; it only writes to it afterwards, as a recorder.
"""

import logging
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Optional
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DismissalReason, SurfaceKind
from app.core.surface_constants import BRIEFING_ACTIVE_CAP
from app.db.session import SessionLocal
from app.models.firm import Firm
from app.models.surface_item import SurfaceItem
from app.services.behavioral_log import log_event
from app.services.surface_generators import (
    CLEAR_CONDITIONS,
    GENERATORS,
    compute_delta_shape,
    rank_candidates,
)

logger = logging.getLogger(__name__)

# The hour, in each firm's own local time, that the briefing is built.
FIRM_LOCAL_GENERATION_HOUR = 5

DEFAULT_TIMEZONE = "America/New_York"

# Dismissal reasons that end an item permanently. A row carrying one of these
# never resurfaces, but stays unresolved (and so keeps blocking duplicates)
# until its condition genuinely clears.
PERMANENT_DISMISSAL_REASONS = (
    DismissalReason.not_relevant,
    DismissalReason.was_wrong,
)


class RankShim:
    """
    Adapts a stored row to the shape rank_candidates compares.

    Rank inputs are persisted in payload["rank_inputs"] by the upsert, so a row
    that has no candidate this morning (a suppressed one, say) can still be
    ranked from the last thing that was measured about it rather than dropping
    to the bottom for lack of numbers.
    """

    __slots__ = ("row", "tier", "time_urgency", "magnitude")

    def __init__(self, row: SurfaceItem):
        self.row = row
        inputs = (row.payload or {}).get("rank_inputs") or {}
        self.tier = int(inputs.get("tier") or 2)
        self.time_urgency = int(inputs.get("time_urgency") or 0)
        self.magnitude = _decimal_or_none(inputs.get("magnitude"))


def _decimal_or_none(value) -> Optional[Decimal]:
    """
    None stays None. It is the absence of a magnitude, never a zero.

    Magnitudes round-trip through JSON as strings so a Decimal keeps its exact
    value, and an unparseable one degrades to None (no boost) rather than to
    zero (a penalty).
    """
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def is_permanently_dismissed(row: SurfaceItem) -> bool:
    return (
        row.dismissed_at is not None
        and row.dismissal_reason in PERMANENT_DISMISSAL_REASONS
    )


def is_suppressed(row: SurfaceItem, now: datetime) -> bool:
    return row.suppressed_until is not None and row.suppressed_until > now


def is_active(row: SurfaceItem, now: datetime) -> bool:
    """Eligible to be ranked and shown right now."""
    return (
        row.resolved_at is None
        and not is_permanently_dismissed(row)
        and not is_suppressed(row, now)
    )


def _open_rows(db: Session, firm_id: UUID) -> list[SurfaceItem]:
    """
    Every row still live for this firm.

    Open means unresolved, exactly as the partial unique index defines it, so
    this set is the same one the dedup rule is enforced against.
    """
    return list(db.execute(
        select(SurfaceItem).where(
            SurfaceItem.firm_id == firm_id,
            SurfaceItem.resolved_at.is_(None),
        )
    ).scalars().all())


def _fire(event_type: str, row: SurfaceItem, metadata: dict) -> None:
    """
    Recorder only, after the row is already written. Never blocks the job and
    never decides anything.
    """
    try:
        log_event(
            firm_id=row.firm_id,
            event_type=event_type,
            entity_type="surface_item",
            entity_id=row.id,
            actor_type="system",
            actor_id=None,
            metadata=metadata,
        )
    except Exception as exc:  # pragma: no cover - recorder must never raise
        logger.warning("%s recorder failed for %s: %s", event_type, row.id, exc)


# ---------------------------------------------------------------------------
# Step 1: generate and upsert
# ---------------------------------------------------------------------------

def _upsert_candidates(db: Session, firm_id: UUID) -> dict:
    created = 0
    refreshed = 0

    existing = {
        (row.kind, row.item_type, row.dedup_key): row
        for row in _open_rows(db, firm_id)
    }

    for item_type, generator in GENERATORS.items():
        for candidate in generator(db, firm_id):
            rank_inputs = {
                "tier": candidate.tier,
                "time_urgency": candidate.time_urgency,
                # Serialised as a string so the Decimal survives the round trip
                # exactly. None stays null, and null is not zero.
                "magnitude": (
                    None if candidate.magnitude is None else str(candidate.magnitude)
                ),
            }
            payload = dict(candidate.payload)
            payload["rank_inputs"] = rank_inputs
            payload["measured"] = candidate.measured

            key = (candidate.kind, candidate.item_type, candidate.dedup_key)
            row = existing.get(key)

            if row is None:
                row = SurfaceItem(
                    firm_id=firm_id,
                    kind=candidate.kind,
                    item_type=candidate.item_type,
                    dedup_key=candidate.dedup_key,
                    headline=candidate.headline,
                    payload=payload,
                    rank=0,
                )
                db.add(row)
                existing[key] = row
                created += 1
                continue

            # An existing row is refreshed in place, whatever state it is in.
            # A suppressed or permanently dismissed row keeps its numbers
            # current without being shown: refreshing is not resurfacing.
            preserved_delta = (row.payload or {}).get("delta")
            row.headline = candidate.headline
            row.payload = (
                {**payload, "delta": preserved_delta} if preserved_delta else payload
            )
            refreshed += 1

    db.commit()
    return {"created": created, "refreshed": refreshed}


# ---------------------------------------------------------------------------
# Step 2: clear conditions
# ---------------------------------------------------------------------------

def _evaluate_clear_conditions(db: Session, firm_id: UUID) -> int:
    now = _now()
    just_resolved: list[SurfaceItem] = []

    for row in _open_rows(db, firm_id):
        clear_condition = CLEAR_CONDITIONS.get(row.item_type)
        if clear_condition is None:
            # A finding-backed row has no rule-based clear condition: its
            # resolution echoes the finding's own recheck cycle and is never
            # led from here.
            continue

        try:
            result = clear_condition(db, firm_id, row.dedup_key)
        except (ValueError, AttributeError, TypeError) as exc:
            logger.warning(
                "clear condition failed for %s %s: %s", row.item_type, row.id, exc
            )
            continue

        if not result.cleared:
            continue

        row.resolved_at = now
        if result.outcome:
            payload = dict(row.payload or {})
            payload["resolved_outcome"] = result.outcome
            row.payload = payload
        just_resolved.append(row)

    # Row first, recorder second. The rows are committed before a single event
    # fires, so a failing recorder cannot cost us the resolution.
    if just_resolved:
        db.commit()

    for row in just_resolved:
        _fire("surface_item.resolved", row, {
            "item_type": row.item_type,
            "outcome": (row.payload or {}).get("resolved_outcome"),
            "was_dismissed": row.dismissed_at is not None,
        })

    return len(just_resolved)


# ---------------------------------------------------------------------------
# Step 3: expire suppression windows
# ---------------------------------------------------------------------------

def _expire_suppression_windows(db: Session, firm_id: UUID) -> int:
    """
    A window that has run its course puts the item back, carrying delta copy
    computed against the snapshot taken at the click.

    The comparison is row against row: value_at_action versus what the
    generator measured this morning. History is never reconstructed from the
    behavioral log.
    """
    now = _now()
    resurfaced = 0

    rows = db.execute(
        select(SurfaceItem).where(
            SurfaceItem.firm_id == firm_id,
            SurfaceItem.resolved_at.is_(None),
            SurfaceItem.suppressed_until.isnot(None),
            SurfaceItem.suppressed_until <= now,
        )
    ).scalars().all()

    for row in rows:
        if is_permanently_dismissed(row):
            # Belt and braces: these never carry a window in the first place.
            continue

        measured_now = (row.payload or {}).get("measured") or {}
        shape = compute_delta_shape(row.item_type, row.value_at_action, measured_now)

        payload = dict(row.payload or {})
        payload["delta"] = {
            "shape": shape,
            "since": row.value_at_action,
            "now": measured_now,
        }
        row.payload = payload
        row.suppressed_until = None
        resurfaced += 1

    if resurfaced:
        db.commit()

    return resurfaced


# ---------------------------------------------------------------------------
# Steps 4 and 5: rank and slot
# ---------------------------------------------------------------------------

def _rank_and_slot(db: Session, firm_id: UUID) -> dict:
    now = _now()
    active = [row for row in _open_rows(db, firm_id) if is_active(row, now)]

    ordered = rank_candidates([RankShim(row) for row in active])
    for position, shim in enumerate(ordered):
        shim.row.rank = position

    briefing = [
        shim.row for shim in ordered if shim.row.kind == SurfaceKind.briefing
    ]
    keep = briefing[:BRIEFING_ACTIVE_CAP]
    keep_ids = {row.id for row in keep}

    for row in keep:
        if row.slotted_at is None:
            row.slotted_at = now

    # Yesterday's slots that did not make today's cut are released. Rows that
    # are no longer active (dismissed, implemented, suppressed, resolved) are
    # unslotted too, which is what makes a dismissed row leave the display
    # immediately rather than at the next generation.
    #
    # This deliberately reads EVERY slotted row and not just the open ones. A
    # row that resolved in place keeps its slot for the rest of that day, by
    # ruling, and this is the only thing that ever takes it back: resolved rows
    # are not open, so scoping this to open rows would leave yesterday's
    # resolved items pinned to the briefing forever.
    for row in db.execute(
        select(SurfaceItem).where(
            SurfaceItem.firm_id == firm_id,
            SurfaceItem.slotted_at.isnot(None),
        )
    ).scalars().all():
        if row.id not in keep_ids:
            row.slotted_at = None

    db.commit()
    return {"ranked": len(ordered), "slotted": len(keep)}


# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------

def run_surface_generation_for_firm(db: Session, firm_id: UUID) -> dict:
    """One firm's full daily pass. Safe to run more than once in a day."""
    upserted = _upsert_candidates(db, firm_id)
    resolved = _evaluate_clear_conditions(db, firm_id)
    resurfaced = _expire_suppression_windows(db, firm_id)
    slotting = _rank_and_slot(db, firm_id)

    return {
        "firm_id": str(firm_id),
        "created": upserted["created"],
        "refreshed": upserted["refreshed"],
        "resolved": resolved,
        "resurfaced": resurfaced,
        **slotting,
    }


def _firm_local_hour(firm: Firm, moment: datetime) -> Optional[int]:
    name = firm.timezone or DEFAULT_TIMEZONE
    try:
        return moment.astimezone(ZoneInfo(name)).hour
    except (ZoneInfoNotFoundError, ValueError):
        logger.warning("firm %s has unusable timezone %r", firm.id, name)
        return None


def run_surface_daily_job(firm_ids: Optional[list[UUID]] = None) -> dict:
    """
    Run the pass for the given firms, or for every firm when none are named.

    Creates its own SessionLocal in a try/finally, per the standing rule that a
    background task never borrows a request session.
    """
    db = SessionLocal()
    results: list[dict] = []
    try:
        stmt = select(Firm)
        if firm_ids is not None:
            stmt = stmt.where(Firm.id.in_(firm_ids))
        firms = db.execute(stmt).scalars().all()

        for firm in firms:
            try:
                results.append(run_surface_generation_for_firm(db, firm.id))
            except Exception as exc:
                db.rollback()
                logger.error(
                    "surface generation failed for firm %s: %s",
                    firm.id, exc, exc_info=True,
                )
    finally:
        db.close()

    return {"firms": len(results), "results": results}


def run_surface_hourly_tick() -> dict:
    """
    Scheduled hourly. Runs the daily pass for the firms whose local clock has
    just reached the generation hour.

    The scheduler trigger pins its timezone explicitly at registration, because
    BackgroundScheduler otherwise resolves the zone from the host through
    tzlocal and nothing in this repo pins the droplet's TZ.
    """
    moment = _now()
    db = SessionLocal()
    try:
        due = [
            firm.id
            for firm in db.execute(select(Firm)).scalars().all()
            if _firm_local_hour(firm, moment) == FIRM_LOCAL_GENERATION_HOUR
        ]
    finally:
        db.close()

    if not due:
        return {"firms": 0, "results": []}

    return run_surface_daily_job(firm_ids=due)
