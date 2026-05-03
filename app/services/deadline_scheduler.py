# app/services/deadline_scheduler.py
"""
Deadline check service for JAMM PX.

check_approaching_deadlines() queries all active engagements whose
effective deadline (extended_deadline if set, else filing_deadline)
falls within the next 30 days, and emits engagement.deadline_approaching
events for each one.

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
from app.services.event_bus import emit_event_sync
from app.core.enums import TriggerEvent


DEADLINE_WARNING_DAYS = 30


def check_approaching_deadlines() -> dict:
    """
    Scan active engagements for approaching IRS deadlines.
    Emits engagement.deadline_approaching for each matching engagement.
    Returns a summary dict: {checked: N, alerts_emitted: N}
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

        for eng in engagements:
            checked += 1

            # extended_deadline overrides filing_deadline if set
            effective_deadline = eng.extended_deadline or eng.filing_deadline
            if not effective_deadline:
                continue

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

        return {"checked": checked, "alerts_emitted": alerts_emitted}

    finally:
        db.close()
