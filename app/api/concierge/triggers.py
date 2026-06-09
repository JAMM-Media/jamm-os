# app/api/concierge/triggers.py

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.concierge.context import get_firm_context
from app.models.behavioral_event import BehavioralEvent

logger = logging.getLogger(__name__)


def _oldest_event_age_hours(firm_id: UUID, event_type: str, db: Session) -> float | None:
    oldest = db.execute(
        select(func.min(BehavioralEvent.occurred_at)).where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == event_type,
        )
    ).scalar()
    if oldest is None:
        return None
    now = datetime.now(timezone.utc)
    if oldest.tzinfo is None:
        oldest = oldest.replace(tzinfo=timezone.utc)
    return (now - oldest).total_seconds() / 3600


def is_tax_season() -> bool:
    """Returns True between January 15 and April 20 (inclusive), UTC."""
    from datetime import date
    today = date.today()
    start = date(today.year, 1, 15)
    end = date(today.year, 4, 20)
    return start <= today <= end


def evaluate_triggers(firm_id: UUID, db: Session) -> list[dict]:
    ctx = get_firm_context(firm_id, db)

    client_count = ctx.get("client_count", 0)
    clients_missing_email = ctx.get("clients_missing_email", 0)
    engagement_total = ctx.get("engagement_summary", {}).get("total", 0)
    portal_logged_in = ctx.get("portal_adoption", {}).get("logged_in", 0)
    staff_pending = ctx.get("staff_summary", {}).get("pending", 0)
    irs_with_auth = ctx.get("irs_coverage", {}).get("with_auth", 0)
    onboarding_completed = ctx.get("onboarding_steps", {}).get("completed", [])

    results: list[dict] = []
    _tax_season = is_tax_season()

    # Trigger 1 -- no_engagement_after_import
    if engagement_total == 0 and client_count > 0:
        age = _oldest_event_age_hours(firm_id, "client.created", db)
        if age is not None and age > 24:
            results.append({
                "trigger_type": "no_engagement_after_import",
                "message": (
                    f"You have {client_count} clients in JAMM PX but no engagements set up yet. "
                    "Want me to walk you through creating your first one?"
                ),
            })

    # Trigger 2 -- no_portal_invite_sent (suppressed during tax season)
    if not _tax_season and portal_logged_in == 0 and client_count > 0:
        age = _oldest_event_age_hours(firm_id, "client.created", db)
        if age is not None and age > 48:
            results.append({
                "trigger_type": "no_portal_invite_sent",
                "message": (
                    "None of your clients have been invited to the portal yet. "
                    "Sending a magic-link takes one click per client. "
                    "Want to start with your most active engagement?"
                ),
            })

    # Trigger 3 -- staff_invite_pending (suppressed during tax season)
    if not _tax_season and staff_pending > 0:
        results.append({
            "trigger_type": "staff_invite_pending",
            "message": (
                f"{staff_pending} team member(s) haven't accepted their invite yet. "
                "Want me to draft a follow-up message you can send directly?"
            ),
        })

    # Trigger 4 -- missing_email_clients (suppressed during tax season)
    if not _tax_season and clients_missing_email > 0:
        results.append({
            "trigger_type": "missing_email_clients",
            "message": (
                f"{clients_missing_email} client(s) are missing email addresses. "
                "They won't receive portal invitations or document requests until this is fixed. "
                "Want a list of who they are?"
            ),
        })

    # Trigger 5 -- no_automation_enabled (suppressed during tax season)
    if not _tax_season and "automation_enabled" not in onboarding_completed and client_count > 0:
        age = _oldest_event_age_hours(firm_id, "client.created", db)
        if age is not None and age > 72:
            results.append({
                "trigger_type": "no_automation_enabled",
                "message": (
                    "Your automation rules are all off. "
                    "Firms that enable presets in the first week save an average of 3 hours on follow-up per month. "
                    "Want me to walk you through the recommended ones?"
                ),
            })

    # Trigger 6 -- irs_auth_gap (suppressed during tax season)
    if not _tax_season and irs_with_auth == 0 and client_count > 0:
        results.append({
            "trigger_type": "irs_auth_gap",
            "message": (
                "None of your clients have IRS authorization records. "
                "If you handle any federal tax work, this is the gap most likely to create a problem. "
                "Want to add one now?"
            ),
        })

    return results
