# app/api/concierge/triggers.py

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.api.concierge.context import get_firm_context
from app.api.concierge.functions import (
    get_stalled_engagements,
    get_unbilled_completed_work,
    get_overdue_invoices,
    get_staff_capacity,
    get_client_communication_gap,
    get_pipeline_bottleneck,
)
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


def _is_monday() -> bool:
    from datetime import date
    return date.today().weekday() == 0  # 0 = Monday


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

    # ------------------------------------------------------------------
    # OPERATIONAL TRIGGERS (fire weekly on Monday, not suppressed by tax season)
    # These monitor ongoing firm health, not onboarding state.
    # ------------------------------------------------------------------
    _monday = _is_monday()

    # Trigger 7 -- stalled_work
    # Fires Monday when 3+ engagements have not been updated in 14+ days.
    if _monday:
        stalled = get_stalled_engagements(firm_id, db, days=14)
        if stalled["stalled_count"] >= 3:
            names = ", ".join(
                f"{e['client_name']} ({e['engagement_name']})"
                for e in stalled["engagements"][:3]
            )
            more = stalled["stalled_count"] - 3
            suffix = f" and {more} more" if more > 0 else ""
            results.append({
                "trigger_type": "stalled_work",
                "message": (
                    f"{stalled['stalled_count']} engagements have not been updated in over 14 days: "
                    f"{names}{suffix}. Want to review what is blocking them?"
                ),
                "metadata": {"stalled_count": stalled["stalled_count"], "engagements": stalled["engagements"][:5]},
            })

    # Trigger 8 -- unbilled_work
    # Fires Monday when there is unbilled completed work worth $500+.
    if _monday:
        unbilled = get_unbilled_completed_work(firm_id, db)
        if unbilled["total_unbilled_value"] >= 500:
            results.append({
                "trigger_type": "unbilled_work",
                "message": (
                    f"You have ${unbilled['total_unbilled_value']:,.0f} in completed work that has not been invoiced this month "
                    f"across {unbilled['unbilled_count']} engagement(s). Want me to draft the invoices now?"
                ),
                "metadata": {"total_value": unbilled["total_unbilled_value"], "count": unbilled["unbilled_count"], "engagements": unbilled["engagements"][:5]},
            })

    # Trigger 9 -- overdue_invoices_alert
    # Fires Monday when 5+ invoices are more than 30 days overdue,
    # OR total overdue balance exceeds $2,000.
    if _monday:
        overdue_inv = get_overdue_invoices(firm_id, db)
        long_overdue = [i for i in overdue_inv["invoices"] if (i["days_overdue"] or 0) >= 30]
        if len(long_overdue) >= 5 or overdue_inv["total_overdue_amount"] >= 2000:
            results.append({
                "trigger_type": "overdue_invoices_alert",
                "message": (
                    f"{overdue_inv['overdue_count']} invoice(s) are overdue totaling "
                    f"${overdue_inv['total_overdue_amount']:,.0f}. "
                    "Want me to draft follow-up emails for each one?"
                ),
                "metadata": {"overdue_count": overdue_inv["overdue_count"], "total_amount": overdue_inv["total_overdue_amount"], "invoices": overdue_inv["invoices"][:5]},
            })

    # Trigger 10 -- staff_overload
    # Fires Monday when any staff member is at 100%+ utilization.
    if _monday:
        capacity = get_staff_capacity(firm_id, db)
        overloaded = [s for s in capacity["staff"] if s["status"] == "overloaded"]
        if overloaded:
            names = ", ".join(s["name"] for s in overloaded[:3])
            results.append({
                "trigger_type": "staff_overload",
                "message": (
                    f"{names} {'is' if len(overloaded) == 1 else 'are'} at or above full capacity this week. "
                    "Want to review their task assignments and redistribute?"
                ),
                "metadata": {"overloaded_staff": overloaded},
            })

    # Trigger 11 -- client_comm_gap
    # Fires Monday when 3+ clients with active engagements have had
    # no outbound contact in 21+ days.
    if _monday:
        comm_gap = get_client_communication_gap(firm_id, db, days=21)
        if comm_gap["gap_count"] >= 3:
            names = ", ".join(
                c["client_name"] for c in comm_gap["clients"][:3]
            )
            more = comm_gap["gap_count"] - 3
            suffix = f" and {more} more" if more > 0 else ""
            results.append({
                "trigger_type": "client_comm_gap",
                "message": (
                    f"You have not sent anything to {comm_gap['gap_count']} clients with active work in over 21 days: "
                    f"{names}{suffix}. Should I draft status update messages for them?"
                ),
                "metadata": {"gap_count": comm_gap["gap_count"], "clients": comm_gap["clients"][:5]},
            })

    # Trigger 12 -- pipeline_bottleneck
    # Fires Monday when any single status holds 3x average volume.
    if _monday:
        bottleneck = get_pipeline_bottleneck(firm_id, db)
        if bottleneck["bottlenecks"]:
            top = bottleneck["bottlenecks"][0]
            results.append({
                "trigger_type": "pipeline_bottleneck_alert",
                "message": (
                    f"{top['count']} engagements are sitting at {top['status']} status, "
                    f"which is {top['ratio_vs_average']}x your usual volume for that stage. "
                    "What is the blocker? I can help identify patterns."
                ),
                "metadata": {"bottlenecks": bottleneck["bottlenecks"], "status_counts": bottleneck["status_counts"]},
            })

    # Trigger 13 -- ar_alert
    # Fires Monday when total overdue AR exceeds the firm's average monthly billing.
    # Uses 30-day rolling invoice total as the average monthly billing proxy.
    if _monday:
        from datetime import date as _date
        from sqlalchemy import select as _select
        from app.models.invoice import Invoice as _Invoice
        _thirty_days_ago = _date.today().replace(day=1)
        _monthly_total = db.execute(
            _select(func.sum(_Invoice.total_amount)).where(
                _Invoice.firm_id == firm_id,
                _Invoice.sent_at >= datetime.combine(_thirty_days_ago, datetime.min.time()).replace(tzinfo=timezone.utc),
            )
        ).scalar() or 0
        overdue_ar = get_overdue_invoices(firm_id, db)
        if _monthly_total > 0 and overdue_ar["total_overdue_amount"] >= float(_monthly_total):
            results.append({
                "trigger_type": "ar_alert",
                "message": (
                    f"Your overdue AR (${overdue_ar['total_overdue_amount']:,.0f}) has reached or exceeded "
                    f"your billing from last month (${float(_monthly_total):,.0f}). "
                    "Want help drafting collection follow-ups?"
                ),
                "metadata": {"overdue_amount": overdue_ar["total_overdue_amount"], "monthly_billing": float(_monthly_total)},
            })

    return results
