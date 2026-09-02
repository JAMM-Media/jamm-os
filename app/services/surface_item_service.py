# app/services/surface_item_service.py

"""
Request-time behavior for the two curated surfaces.

The governing rule in this module, and the easiest thing to get wrong: THE ROW
GOVERNS AND THE LOG ECHOES. Every owner action writes the surface row first, as
operational truth, inside the request transaction. Only once that has committed
does the behavioral event fire, fire and forget. If the event write fails the
action still succeeded, because the action was the row.

Nothing here reads behavioral_events to decide anything.
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.enums import DismissalReason, SurfaceKind
from app.core.surface_constants import (
    BRIEFING_ACTIVE_CAP,
    BRIEFING_SUPPRESSION_DAYS,
    OBSERVATORY_SUPPRESSION_DAYS,
)
from app.models.surface_item import SurfaceItem
from app.services.behavioral_log import log_event
from app.services.surface_daily_job import (
    RankShim,
    is_active,
    is_permanently_dismissed,
)
from app.services.surface_generators import CLEAR_CONDITIONS, rank_candidates

logger = logging.getLogger(__name__)

# Reasons that start a suppression window rather than ending the item.
SUPPRESSING_REASONS = (DismissalReason.already_handling,)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def suppression_days_for(kind: SurfaceKind) -> int:
    """7 days on the Briefing, 14 in the Observatory, counted from the click."""
    return (
        OBSERVATORY_SUPPRESSION_DAYS
        if kind == SurfaceKind.observatory
        else BRIEFING_SUPPRESSION_DAYS
    )


def get_item_for_firm(db: Session, item_id: UUID, firm_id: UUID) -> Optional[SurfaceItem]:
    """
    Absent or another firm's reads the same from here: None, which the router
    turns into a 404. A cross-firm probe learns nothing about what exists.
    """
    return db.execute(
        select(SurfaceItem).where(
            SurfaceItem.id == item_id,
            SurfaceItem.firm_id == firm_id,
        )
    ).scalars().first()


def _fire(event_type: str, row: SurfaceItem, metadata: dict, actor_id) -> None:
    """
    The recorder. Called only after the row write has committed, and never
    allowed to affect the outcome of the action it is recording.
    """
    try:
        log_event(
            firm_id=row.firm_id,
            event_type=event_type,
            entity_type="surface_item",
            entity_id=row.id,
            actor_type="staff",
            actor_id=actor_id,
            metadata=metadata,
        )
    except Exception as exc:  # pragma: no cover - recorder must never raise
        logger.warning("%s recorder failed for %s: %s", event_type, row.id, exc)


def _measured_now(row: SurfaceItem) -> dict:
    return (row.payload or {}).get("measured") or {}


# ---------------------------------------------------------------------------
# Serving
# ---------------------------------------------------------------------------

def get_briefing(db: Session, firm_id: UUID, actor_id=None) -> dict:
    """
    Serve today's Briefing.

    Re-checks the clear condition of ONLY the rows being served, so a row that
    cleared since this morning is shown resolved in place, keeping its slot for
    the rest of the day rather than reshuffling the list under the reader. A
    dismissed or implemented row is already unslotted and simply is not here.

    appearance_count counts times served, not calendar days, and last_served_on
    makes that increment idempotent within a day.
    """
    now = _now()
    today = now.date()

    rows = list(db.execute(
        select(SurfaceItem).where(
            SurfaceItem.firm_id == firm_id,
            SurfaceItem.kind == SurfaceKind.briefing,
            SurfaceItem.slotted_at.isnot(None),
        ).order_by(SurfaceItem.rank)
    ).scalars().all())

    resolved_in_place = 0
    for row in rows:
        if row.resolved_at is not None:
            continue
        clear_condition = CLEAR_CONDITIONS.get(row.item_type)
        if clear_condition is None:
            continue
        try:
            result = clear_condition(db, firm_id, row.dedup_key)
        except (ValueError, AttributeError, TypeError):
            continue
        if result.cleared:
            row.resolved_at = now
            if result.outcome:
                payload = dict(row.payload or {})
                payload["resolved_outcome"] = result.outcome
                row.payload = payload
            resolved_in_place += 1

    for row in rows:
        if row.last_served_on != today:
            row.appearance_count = (row.appearance_count or 0) + 1
            row.last_served_on = today

    db.commit()

    for row in rows:
        db.refresh(row)

    # Recorder, after every row write has committed. The entity is the firm,
    # because a view is about the surface rather than any one item on it.
    try:
        log_event(
            firm_id=firm_id,
            event_type="briefing.viewed",
            entity_type="firm",
            entity_id=firm_id,
            actor_type="staff",
            actor_id=actor_id,
            metadata={
                "served_item_ids": [str(row.id) for row in rows],
                "count": len(rows),
                "resolved_in_place": resolved_in_place,
            },
        )
    except Exception as exc:  # pragma: no cover - recorder must never raise
        logger.warning("briefing.viewed recorder failed for firm %s: %s", firm_id, exc)

    return {
        "items": rows,
        "count": len(rows),
        "resolved_in_place": resolved_in_place,
        # Honest state: nothing has cleared the intelligence bar yet, because no
        # technique exists to clear it. The frontend renders this as
        # "collecting", never as an empty result that implies all is well.
        "intelligence_pending": True,
    }


def get_observatory(db: Session, firm_id: UUID) -> dict:
    """
    Active material signals. Empty on day one by construction: nothing can be
    promoted while the promotion registry is empty.

    The response says emptiness unambiguously with an explicit count and an
    explicit flag, so the frontend never has to infer it from a bare list.
    """
    now = _now()
    rows = [
        row for row in db.execute(
            select(SurfaceItem).where(
                SurfaceItem.firm_id == firm_id,
                SurfaceItem.kind == SurfaceKind.observatory,
                SurfaceItem.resolved_at.is_(None),
            ).order_by(SurfaceItem.rank)
        ).scalars().all()
        if is_active(row, now)
    ]

    return {
        "items": rows,
        "count": len(rows),
        "is_empty": len(rows) == 0,
        "intelligence_pending": True,
    }


# ---------------------------------------------------------------------------
# Owner actions
# ---------------------------------------------------------------------------

def dismiss_item(
    db: Session,
    item: SurfaceItem,
    reason: DismissalReason,
    actor_id=None,
) -> SurfaceItem:
    """
    Record a dismissal. The row is the truth; the event is the echo.

    already_handling starts a suppression window and the item comes back at
    expiry with delta copy. not_relevant and was_wrong never resurface, and
    was_wrong additionally flags the row for later human review. v1 records and
    does nothing automatic: no threshold anywhere responds to this yet.
    """
    now = _now()

    item.dismissed_at = now
    item.dismissal_reason = reason
    item.value_at_action = _measured_now(item)
    item.slotted_at = None

    if reason in SUPPRESSING_REASONS:
        item.suppressed_until = now + timedelta(days=suppression_days_for(item.kind))
    else:
        item.suppressed_until = None

    if reason == DismissalReason.was_wrong:
        item.flagged_for_review = True

    db.commit()
    db.refresh(item)

    _fire("surface_item.dismissed", item, {
        "item_type": item.item_type,
        "kind": str(item.kind.value),
        "reason": reason.value,
        "value_at_action": item.value_at_action,
        "appearance_count": item.appearance_count,
    }, actor_id)

    return item


def implement_item(db: Session, item: SurfaceItem, actor_id=None) -> SurfaceItem:
    """
    Record that the owner has dealt with the item.

    A separate action from dismissal, with its own event. The frontend labels it
    Done on the Briefing and Addressed in the Observatory; the backend serves
    the kind and never the label.
    """
    now = _now()

    item.implemented_at = now
    item.value_at_action = _measured_now(item)
    item.suppressed_until = now + timedelta(days=suppression_days_for(item.kind))
    item.slotted_at = None

    db.commit()
    db.refresh(item)

    _fire("surface_item.implemented", item, {
        "item_type": item.item_type,
        "kind": str(item.kind.value),
        "value_at_action": item.value_at_action,
        "appearance_count": item.appearance_count,
    }, actor_id)

    return item


def promote_next_briefing_item(db: Session, firm_id: UUID) -> Optional[SurfaceItem]:
    """
    Slot the single next-ranked active unslotted briefing row.

    Slots never auto-fill. When one opens because the owner dismissed or
    implemented something, it stays open until they explicitly ask for another,
    which is this endpoint. Returns None when there is nothing left to promote,
    which the router reports honestly rather than as an error.
    """
    now = _now()

    slotted_count = len([
        row for row in db.execute(
            select(SurfaceItem).where(
                SurfaceItem.firm_id == firm_id,
                SurfaceItem.kind == SurfaceKind.briefing,
                SurfaceItem.slotted_at.isnot(None),
                SurfaceItem.resolved_at.is_(None),
            )
        ).scalars().all()
    ])
    if slotted_count >= BRIEFING_ACTIVE_CAP:
        return None

    candidates = [
        row for row in db.execute(
            select(SurfaceItem).where(
                SurfaceItem.firm_id == firm_id,
                SurfaceItem.kind == SurfaceKind.briefing,
                SurfaceItem.slotted_at.is_(None),
                SurfaceItem.resolved_at.is_(None),
            )
        ).scalars().all()
        if is_active(row, now) and not is_permanently_dismissed(row)
    ]
    if not candidates:
        return None

    ordered = rank_candidates([RankShim(row) for row in candidates])
    winner = ordered[0].row
    winner.slotted_at = now
    db.commit()
    db.refresh(winner)
    return winner
