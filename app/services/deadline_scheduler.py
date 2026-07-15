# app/services/deadline_scheduler.py
"""
Deadline check service for JAMM PX.

check_approaching_deadlines() queries all active engagements whose
effective deadline (extended_deadline if set, else filing_deadline)
falls within the next 30 days, and emits engagement.deadline_approaching
events for each one. The same sweep also detects deadlines that have
already passed with the engagement still not completed, and fires the
negative-space engagement.deadline_missed behavioral event once per
engagement per deadline track (original, extended).

This function is designed to be called:
  - As a FastAPI BackgroundTask (e.g. from a health/cron endpoint)
  - From a Celery beat task in future
  - Directly in tests

It creates its own DB session and never reuses a request session.
"""

from datetime import date, timedelta
from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.engagement import Engagement
from app.models.behavioral_event import BehavioralEvent
from app.services.event_bus import emit_event_sync
from app.services.behavioral_log import log_event
from app.core.enums import TriggerEvent


DEADLINE_WARNING_DAYS = 30


def check_approaching_deadlines() -> dict:
    """
    Scan active engagements for approaching IRS deadlines and for deadlines
    already missed. Emits engagement.deadline_approaching for each matching
    engagement and engagement.deadline_missed for each newly-detected miss.
    Returns a summary dict: {checked: N, alerts_emitted: N, misses_emitted: N}
    """
    db = SessionLocal()
    try:
        today = date.today()
        window_end = today + timedelta(days=DEADLINE_WARNING_DAYS)

        # Query active engagements that have a filing or extended deadline
        stmt = (
            select(Engagement)
            .where(
                Engagement.status.notin_(["completed", "archived"]),
                Engagement.is_active == True,
            )
        )

        engagements = db.execute(stmt).scalars().all()

        checked = 0
        alerts_emitted = 0
        misses_emitted = 0

        for eng in engagements:
            checked += 1

            # extended_deadline overrides filing_deadline if set
            effective_deadline = eng.extended_deadline or eng.filing_deadline
            if effective_deadline:
                days_remaining = (effective_deadline - today).days
                if 0 <= days_remaining <= DEADLINE_WARNING_DAYS:
                    emit_event_sync(
                        event=TriggerEvent.engagement_deadline_approaching,
                        payload={
                            "firm_id": str(eng.firm_id),
                            "engagement_id": str(eng.id),
                            "client_id": str(eng.client_id),
                            "engagement_type": eng.engagement_type,
                            "effective_deadline": effective_deadline.isoformat(),
                            "days_remaining": days_remaining,
                            "using_extended_deadline": eng.extended_deadline is not None,
                        },
                    )
                    alerts_emitted += 1

            misses_emitted += _detect_deadline_misses(db, eng, today)

        return {"checked": checked, "alerts_emitted": alerts_emitted, "misses_emitted": misses_emitted}

    finally:
        db.close()


def _deadline_miss_already_logged(db, engagement_id, deadline_type: str) -> bool:
    row = db.execute(
        select(BehavioralEvent.event_id)
        .where(
            BehavioralEvent.event_type == "engagement.deadline_missed",
            BehavioralEvent.entity_id == engagement_id,
            BehavioralEvent.extra_metadata["deadline_type"].astext == deadline_type,
        )
        .limit(1)
    ).first()
    return row is not None


def _detect_deadline_misses(db, eng: Engagement, today: date) -> int:
    """
    Gated on the operative deadline (extended if set, else original) actually
    being in the past -- an extension filed ahead of its own due date must
    not retroactively read as an original-deadline miss before that operative
    date has itself passed. Once gated open, every track whose own date has
    passed fires (idempotently) against that track specifically.
    """
    operative_deadline = eng.extended_deadline or eng.filing_deadline
    if operative_deadline is None or operative_deadline >= today:
        return 0

    fired = 0
    tracks = []
    if eng.filing_deadline is not None and eng.filing_deadline < today:
        tracks.append(("original", eng.filing_deadline))
    if eng.extended_deadline is not None and eng.extended_deadline < today:
        tracks.append(("extended", eng.extended_deadline))

    for deadline_type, deadline_date in tracks:
        if _deadline_miss_already_logged(db, eng.id, deadline_type):
            continue
        log_event(
            firm_id=eng.firm_id,
            event_type="engagement.deadline_missed",
            entity_type="engagement",
            entity_id=eng.id,
            actor_type="system",
            actor_id=None,
            metadata={
                "deadline_type": deadline_type,
                "deadline_date": deadline_date.isoformat(),
                "days_overdue": (today - deadline_date).days,
                "form_type": eng.engagement_type,
                "client_id": str(eng.client_id),
            },
        )
        fired += 1

    return fired
