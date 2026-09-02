# app/services/engagement_completion.py

"""
The single place an engagement's completion timestamp is stamped.

completed_at exists because completion previously survived only as a status
string plus a behavioral event, and operational control flow is never allowed
to read the behavioral log. work_unbilled reads this column.

Every path that moves an engagement into completed status calls
stamp_completion_transition. There are three today (the single-engagement
update, the bulk status update, and the automation action), and this module is
the obvious place for a fourth to join rather than quietly not stamping.

It lives in its own module, importing nothing but the model, so any caller can
use it without dragging in the event bus or the audit service and without
risking an import cycle.
"""

from datetime import datetime, timezone

from app.models.engagement import Engagement

COMPLETED_STATUS = "completed"


def stamp_completion_transition(
    engagement: Engagement,
    old_status: str | None,
    new_status: str | None,
) -> bool:
    """
    Stamp completed_at when an engagement moves INTO completed status.

    Returns True when a stamp was written, so callers can decide whether they
    need to commit. Does not commit: the caller owns the transaction, and the
    stamp must land in the same one as the status change.

    Only the transition stamps. Re-saving an already-completed engagement does
    not move the timestamp, so completed_at keeps meaning "when this was first
    completed".

    Reopening does NOT clear it, by ruling. Readers pair completed_at with a
    current status check rather than trusting it alone.

    No backfill exists: engagements completed before the column landed stay
    NULL, so work_unbilled only ever fires for completions recorded after it.
    """
    if new_status != COMPLETED_STATUS:
        return False
    if old_status == COMPLETED_STATUS:
        return False

    engagement.completed_at = datetime.now(timezone.utc)
    return True
