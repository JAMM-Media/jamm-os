# app/api/concierge/functions.py
#
# Operational function library for the JAMM Concierge agent.
# Each function reads live firm data and returns a structured dict
# the agent can use to answer operational questions accurately.
#
# All functions follow the same signature:
#   get_X(firm_id: uuid.UUID, db: Session) -> dict

import uuid
from datetime import datetime, timezone, timedelta, date
from sqlalchemy import select, func, or_, and_
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.models.automation_rule import AutomationRule
from app.models.behavioral_event import BehavioralEvent
from app.models.document_request import DocumentRequest
from app.models.irs_authorization import IrsAuthorization
from app.models.task import Task
from app.models.qc_checklist import QcChecklistItem
from app.models.signature_envelope import SignatureEnvelope
from app.models.firm import Firm
from app.models.integration import Integration
from app.models.stripe_connection import StripeConnection


# ---------------------------------------------------------------------------
# Function 1: get_stalled_engagements
# Returns engagements with no status change or update in more than N days.
# ---------------------------------------------------------------------------
def get_stalled_engagements(firm_id: uuid.UUID, db: Session, days: int = 14) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = db.execute(
        select(
            Engagement.id,
            Engagement.name,
            Engagement.status,
            Engagement.updated_at,
            Client.name.label("client_name"),
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.updated_at < cutoff,
        )
        .order_by(Engagement.updated_at.asc())
        .limit(20)
    ).fetchall()

    stalled = [
        {
            "engagement_id": str(r.id),
            "engagement_name": r.name,
            "client_name": r.client_name,
            "status": str(r.status),
            "last_updated": r.updated_at.isoformat() if r.updated_at else None,
            "days_stalled": (datetime.now(timezone.utc) - r.updated_at).days
            if r.updated_at
            else None,
        }
        for r in rows
    ]

    return {
        "stalled_count": len(stalled),
        "threshold_days": days,
        "engagements": stalled,
    }


# ---------------------------------------------------------------------------
# Function 2: get_unbilled_completed_work
# Returns completed engagements with unbilled time entries this month.
# ---------------------------------------------------------------------------
def get_unbilled_completed_work(firm_id: uuid.UUID, db: Session) -> dict:
    today = date.today()
    month_start = today.replace(day=1)

    rows = db.execute(
        select(
            Engagement.id,
            Engagement.name,
            Client.name.label("client_name"),
            func.sum(TimeEntry.hours).label("total_hours"),
            func.sum(TimeEntry.hours * TimeEntry.hourly_rate).label("total_value"),
        )
        .join(Client, Engagement.client_id == Client.id)
        .join(TimeEntry, TimeEntry.engagement_id == Engagement.id)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.status == "completed",
            TimeEntry.is_billable == True,
            TimeEntry.is_billed == False,
            TimeEntry.date >= month_start,
        )
        .group_by(Engagement.id, Engagement.name, Client.name)
        .order_by(func.sum(TimeEntry.hours * TimeEntry.hourly_rate).desc())
        .limit(20)
    ).fetchall()

    items = [
        {
            "engagement_id": str(r.id),
            "engagement_name": r.name,
            "client_name": r.client_name,
            "unbilled_hours": float(r.total_hours or 0),
            "unbilled_value": float(r.total_value or 0),
        }
        for r in rows
    ]

    total_value = sum(i["unbilled_value"] for i in items)
    total_hours = sum(i["unbilled_hours"] for i in items)

    return {
        "unbilled_count": len(items),
        "total_unbilled_hours": total_hours,
        "total_unbilled_value": total_value,
        "since": month_start.isoformat(),
        "engagements": items,
    }


# ---------------------------------------------------------------------------
# Function 3: get_overdue_invoices
# Returns sent invoices past their due date.
# ---------------------------------------------------------------------------
def get_overdue_invoices(firm_id: uuid.UUID, db: Session) -> dict:
    today = date.today()

    rows = db.execute(
        select(
            Invoice.id,
            Invoice.invoice_number,
            Invoice.total_amount,
            Invoice.due_date,
            Invoice.sent_at,
            Client.name.label("client_name"),
        )
        .join(Client, Invoice.client_id == Client.id)
        .where(
            Invoice.firm_id == firm_id,
            or_(
                Invoice.status == "overdue",
                and_(
                    Invoice.status == "sent",
                    Invoice.due_date != None,
                    Invoice.due_date < today,
                ),
            ),
        )
        .order_by(Invoice.due_date.asc())
        .limit(20)
    ).fetchall()

    items = [
        {
            "invoice_id": str(r.id),
            "invoice_number": r.invoice_number,
            "client_name": r.client_name,
            "amount": float(r.total_amount or 0),
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "days_overdue": (today - r.due_date).days if r.due_date else None,
        }
        for r in rows
    ]

    total_overdue = sum(i["amount"] for i in items)

    return {
        "overdue_count": len(items),
        "total_overdue_amount": total_overdue,
        "invoices": items,
    }


# ---------------------------------------------------------------------------
# Function 4: get_staff_capacity
# Returns time logged this week per staff member and a utilization estimate.
# ---------------------------------------------------------------------------
def get_staff_capacity(firm_id: uuid.UUID, db: Session) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())

    staff_rows = db.execute(
        select(User.id, User.full_name, User.role)
        .where(User.firm_id == firm_id, User.is_active == True)
    ).fetchall()

    results = []
    for staff in staff_rows:
        hours_row = db.execute(
            select(func.sum(TimeEntry.hours))
            .where(
                TimeEntry.firm_id == firm_id,
                TimeEntry.user_id == staff.id,
                TimeEntry.date >= week_start,
            )
        ).scalar()

        hours_this_week = float(hours_row or 0)
        standard_week = 40.0
        utilization_pct = round((hours_this_week / standard_week) * 100, 1)

        results.append(
            {
                "user_id": str(staff.id),
                "name": staff.full_name,
                "role": str(staff.role),
                "hours_this_week": hours_this_week,
                "utilization_pct": utilization_pct,
                "status": "overloaded"
                if utilization_pct >= 100
                else "high"
                if utilization_pct >= 80
                else "normal",
            }
        )

    results.sort(key=lambda x: x["hours_this_week"], reverse=True)

    return {
        "week_start": week_start.isoformat(),
        "staff": results,
        "overloaded_count": sum(1 for s in results if s["status"] == "overloaded"),
    }


# ---------------------------------------------------------------------------
# Function 5: get_client_communication_gap
# Returns clients with active engagements but no outbound event in N days.
# ---------------------------------------------------------------------------
def get_client_communication_gap(
    firm_id: uuid.UUID, db: Session, days: int = 21
) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    active_client_ids = db.execute(
        select(func.distinct(Engagement.client_id)).where(
            Engagement.firm_id == firm_id,
            Engagement.status.in_(["active", "in_review"]),
        )
    ).scalars().all()

    OUTBOUND_EVENTS = [
        "document_request.sent",
        "invoice.sent",
        "message.sent",
        "portal.magic_link_sent",
        "engagement.created",
    ]

    gaps = []
    for client_id in active_client_ids:
        last_event = db.execute(
            select(func.max(BehavioralEvent.occurred_at)).where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == client_id,
                BehavioralEvent.event_type.in_(OUTBOUND_EVENTS),
            )
        ).scalar()

        if last_event is None or last_event < cutoff:
            client = db.execute(
                select(Client.name).where(Client.id == client_id)
            ).scalar()
            days_since = (
                (datetime.now(timezone.utc) - last_event).days
                if last_event
                else None
            )
            gaps.append(
                {
                    "client_id": str(client_id),
                    "client_name": client or "Unknown",
                    "last_outbound": last_event.isoformat() if last_event else None,
                    "days_since_contact": days_since,
                }
            )

    gaps.sort(
        key=lambda x: x["days_since_contact"] if x["days_since_contact"] else 9999,
        reverse=True,
    )

    return {
        "gap_count": len(gaps),
        "threshold_days": days,
        "clients": gaps[:15],
    }


# ---------------------------------------------------------------------------
# Function 6: get_pipeline_bottleneck
# Returns engagement status counts and flags any status with 3x normal volume.
# ---------------------------------------------------------------------------
def get_pipeline_bottleneck(firm_id: uuid.UUID, db: Session) -> dict:
    rows = db.execute(
        select(Engagement.status, func.count().label("count"))
        .where(
            Engagement.firm_id == firm_id,
            Engagement.status.notin_(["archived", "completed"]),
        )
        .group_by(Engagement.status)
    ).fetchall()

    status_counts = {str(r.status): r.count for r in rows}
    total = sum(status_counts.values())

    if total == 0:
        return {"total_active": 0, "status_counts": {}, "bottlenecks": []}

    avg = total / max(len(status_counts), 1)
    threshold = avg * 3

    bottlenecks = [
        {
            "status": status,
            "count": count,
            "ratio_vs_average": round(count / avg, 1),
        }
        for status, count in status_counts.items()
        if count >= threshold
    ]

    return {
        "total_active": total,
        "status_counts": status_counts,
        "average_per_status": round(avg, 1),
        "bottlenecks": bottlenecks,
    }


# ---------------------------------------------------------------------------
# Function 7: get_daily_brief
# Assembles a structured daily summary across all operational signals.
# ---------------------------------------------------------------------------
def get_daily_brief(firm_id: uuid.UUID, db: Session) -> dict:
    stalled = get_stalled_engagements(firm_id, db, days=14)
    unbilled = get_unbilled_completed_work(firm_id, db)
    overdue_inv = get_overdue_invoices(firm_id, db)
    capacity = get_staff_capacity(firm_id, db)
    bottleneck = get_pipeline_bottleneck(firm_id, db)

    today = date.today()
    in_14_days = today + timedelta(days=14)
    upcoming_rows = db.execute(
        select(
            Engagement.name,
            Client.name.label("client_name"),
            Engagement.filing_deadline,
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.filing_deadline >= today,
            Engagement.filing_deadline <= in_14_days,
        )
        .order_by(Engagement.filing_deadline.asc())
        .limit(10)
    ).fetchall()

    upcoming_deadlines = [
        {
            "engagement_name": r.name,
            "client_name": r.client_name,
            "due_date": r.filing_deadline.isoformat() if r.filing_deadline else None,
        }
        for r in upcoming_rows
    ]

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "stalled_engagements": stalled,
        "unbilled_completed_work": unbilled,
        "overdue_invoices": overdue_inv,
        "staff_capacity": capacity,
        "pipeline_bottleneck": bottleneck,
        "upcoming_deadlines_14_days": upcoming_deadlines,
    }


# ---------------------------------------------------------------------------
# Function: resolve_client_by_name
# Case-insensitive partial name search. Returns matching client ids and names
# so the model can resolve a name mentioned in conversation into a real UUID
# before calling any client-scoped tool.
# ---------------------------------------------------------------------------
def resolve_client_by_name(firm_id: uuid.UUID, db: Session, name_query: str) -> dict:
    rows = db.execute(
        select(Client.id, Client.name)
        .where(
            Client.firm_id == firm_id,
            or_(
                Client.name.ilike(f"%{name_query}%"),
                Client.business_description.ilike(f"%{name_query}%"),
            ),
            Client.is_active == True,
        )
        .order_by(Client.name.asc())
        .limit(10)
    ).fetchall()

    matches = [
        {"client_id": str(r.id), "client_name": r.name}
        for r in rows
    ]

    return {
        "match_count": len(matches),
        "matches": matches,
    }

# ---------------------------------------------------------------------------
# Function 8: get_client_full_snapshot
# Returns all key data points for a single client.
# ---------------------------------------------------------------------------
def get_client_full_snapshot(
    firm_id: uuid.UUID, client_id: uuid.UUID, db: Session
) -> dict:
    client = db.execute(
        select(Client).where(Client.id == client_id, Client.firm_id == firm_id)
    ).scalar_one_or_none()

    if not client:
        return {"error": "Client not found"}

    engagements = db.execute(
        select(Engagement.name, Engagement.status, Engagement.filing_deadline)
        .where(
            Engagement.client_id == client_id,
            Engagement.firm_id == firm_id,
        )
        .order_by(Engagement.updated_at.desc())
        .limit(10)
    ).fetchall()

    invoices = db.execute(
        select(
            Invoice.invoice_number,
            Invoice.total_amount,
            Invoice.status,
            Invoice.due_date,
        )
        .where(Invoice.client_id == client_id, Invoice.firm_id == firm_id)
        .order_by(Invoice.due_date.desc())
        .limit(5)
    ).fetchall()

    overdue_docs = db.execute(
        select(func.count())
        .select_from(DocumentRequest)
        .where(
            DocumentRequest.client_id == client_id,
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.status.in_(["pending", "partial"]),
        )
    ).scalar() or 0

    return {
        "client_id": str(client.id),
        "client_name": client.name,
        "email": client.email,
        "entity_type": str(client.entity_type) if client.entity_type else None,
        "portal_access": client.portal_access_enabled,
        "engagements": [
            {
                "name": r.name,
                "status": str(r.status),
                "deadline": r.filing_deadline.isoformat()
                if r.filing_deadline
                else None,
            }
            for r in engagements
        ],
        "invoices": [
            {
                "number": r.invoice_number,
                "amount": float(r.total_amount or 0),
                "status": str(r.status),
                "due": r.due_date.isoformat() if r.due_date else None,
            }
            for r in invoices
        ],
        "pending_document_requests": overdue_docs,
    }


# ---------------------------------------------------------------------------
# Function 9: get_weekly_summary
# Returns firm performance metrics for the past 7 days.
# ---------------------------------------------------------------------------
def get_weekly_summary(firm_id: uuid.UUID, db: Session) -> dict:
    today = date.today()
    week_ago = today - timedelta(days=7)

    engagements_completed = db.execute(
        select(func.count())
        .select_from(Engagement)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.status == "completed",
            Engagement.updated_at >= week_ago,
        )
    ).scalar() or 0

    invoices_sent = db.execute(
        select(func.count())
        .select_from(Invoice)
        .where(
            Invoice.firm_id == firm_id,
            Invoice.sent_at >= week_ago,
        )
    ).scalar() or 0

    invoices_paid_row = db.execute(
        select(func.count(), func.sum(Invoice.total_amount))
        .select_from(Invoice)
        .where(
            Invoice.firm_id == firm_id,
            Invoice.status == "paid",
            Invoice.updated_at >= week_ago,
        )
    ).fetchone()
    invoices_paid = invoices_paid_row[0] or 0
    revenue_collected = float(invoices_paid_row[1] or 0)

    doc_requests_completed = db.execute(
        select(func.count())
        .select_from(DocumentRequest)
        .where(
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.status == "completed",
            DocumentRequest.updated_at >= week_ago,
        )
    ).scalar() or 0

    automations_fired = db.execute(
        select(func.count())
        .select_from(BehavioralEvent)
        .where(
            BehavioralEvent.firm_id == firm_id,
            BehavioralEvent.event_type == "automation.fired",
            BehavioralEvent.occurred_at >= week_ago,
        )
    ).scalar() or 0

    return {
        "period": "last_7_days",
        "week_start": week_ago.isoformat(),
        "engagements_completed": engagements_completed,
        "invoices_sent": invoices_sent,
        "invoices_paid": invoices_paid,
        "revenue_collected": revenue_collected,
        "document_requests_completed": doc_requests_completed,
        "automations_fired": automations_fired,
    }


# ---------------------------------------------------------------------------
# Function 10: get_deadline_calendar
# Returns upcoming engagement deadlines within N days.
# ---------------------------------------------------------------------------
def get_deadline_calendar(firm_id: uuid.UUID, db: Session, days_ahead: int = 14) -> dict:
    today = date.today()
    cutoff = today + timedelta(days=days_ahead)

    rows = db.execute(
        select(
            Engagement.id,
            Engagement.name,
            Engagement.status,
            Engagement.filing_deadline,
            Client.name.label("client_name"),
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm_id,
            Engagement.filing_deadline >= today,
            Engagement.filing_deadline <= cutoff,
        )
        .order_by(Engagement.filing_deadline.asc())
        .limit(30)
    ).fetchall()

    deadlines = [
        {
            "engagement_id": str(r.id),
            "engagement_name": r.name,
            "client_name": r.client_name,
            "status": str(r.status),
            "deadline": r.filing_deadline.isoformat() if r.filing_deadline else None,
            "days_until": (r.filing_deadline - today).days if r.filing_deadline else None,
        }
        for r in rows
    ]

    return {
        "days_ahead": days_ahead,
        "deadline_count": len(deadlines),
        "deadlines": deadlines,
    }


# ---------------------------------------------------------------------------
# Function 11: get_automation_health
# Returns enabled automation rules and their recent firing activity.
# ---------------------------------------------------------------------------
def get_automation_health(firm_id: uuid.UUID, db: Session) -> dict:
    rules = db.execute(
        select(AutomationRule.id, AutomationRule.name, AutomationRule.is_enabled)
        .where(AutomationRule.firm_id == firm_id)
        .order_by(AutomationRule.name.asc())
    ).fetchall()

    today = date.today()
    month_start = today.replace(day=1)

    results = []
    for rule in rules:
        fire_count = db.execute(
            select(func.count())
            .select_from(BehavioralEvent)
            .where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.event_type == "automation.fired",
                BehavioralEvent.extra_metadata["rule_id"].astext == str(rule.id),
                BehavioralEvent.occurred_at >= month_start,
            )
        ).scalar() or 0

        last_fired = db.execute(
            select(func.max(BehavioralEvent.occurred_at))
            .where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.event_type == "automation.fired",
                BehavioralEvent.extra_metadata["rule_id"].astext == str(rule.id),
            )
        ).scalar()

        results.append({
            "rule_id": str(rule.id),
            "rule_name": rule.name,
            "is_enabled": rule.is_enabled,
            "fires_this_month": fire_count,
            "last_fired": last_fired.isoformat() if last_fired else None,
            "status": "active_firing" if (rule.is_enabled and fire_count > 0)
                      else "active_not_firing" if (rule.is_enabled and fire_count == 0)
                      else "inactive",
        })

    enabled_count = sum(1 for r in results if r["is_enabled"])
    firing_count = sum(1 for r in results if r["fires_this_month"] > 0)

    return {
        "total_rules": len(results),
        "enabled_count": enabled_count,
        "firing_this_month": firing_count,
        "rules": results,
    }


# ---------------------------------------------------------------------------
# Function 12: get_portal_inactive_clients
# Returns clients who have not logged into the portal in N days
# and have active document requests outstanding.
# ---------------------------------------------------------------------------
def get_portal_inactive_clients(firm_id: uuid.UUID, db: Session, days: int = 14) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    clients_with_pending_requests = db.execute(
        select(func.distinct(DocumentRequest.client_id))
        .where(
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.status.in_(["pending", "partial"]),
        )
    ).scalars().all()

    inactive = []
    for client_id in clients_with_pending_requests:
        last_login = db.execute(
            select(func.max(BehavioralEvent.occurred_at))
            .where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.entity_id == client_id,
                BehavioralEvent.event_type == "portal.login",
            )
        ).scalar()

        if last_login is None or last_login < cutoff:
            client = db.execute(
                select(Client.name, Client.email)
                .where(Client.id == client_id)
            ).fetchone()

            if not client:
                continue

            days_since = (datetime.now(timezone.utc) - last_login).days if last_login else None

            inactive.append({
                "client_id": str(client_id),
                "client_name": client.name,
                "email": client.email,
                "last_portal_login": last_login.isoformat() if last_login else None,
                "days_since_login": days_since,
                "never_logged_in": last_login is None,
            })

    inactive.sort(
        key=lambda x: x["days_since_login"] if x["days_since_login"] is not None else 9999,
        reverse=True,
    )

    total_client_count = db.execute(
        select(func.count(Client.id)).where(Client.firm_id == firm_id)
    ).scalar() or 0

    portal_enabled_count = db.execute(
        select(func.count(Client.id)).where(
            Client.firm_id == firm_id,
            Client.portal_access_enabled == True,
        )
    ).scalar() or 0

    ever_logged_in_count = db.execute(
        select(func.count(Client.id)).where(
            Client.firm_id == firm_id,
            Client.portal_last_login_at != None,
        )
    ).scalar() or 0

    return {
        "inactive_count": len(inactive),
        "threshold_days": days,
        "clients": inactive[:20],
        "total_client_count": total_client_count,
        "portal_enabled_count": portal_enabled_count,
        "ever_logged_in_count": ever_logged_in_count,
    }


# ---------------------------------------------------------------------------
# Function 13: get_irs_auth_expiring
# Returns clients with IRS authorizations expiring within N days.
# ---------------------------------------------------------------------------
def get_irs_auth_expiring(firm_id: uuid.UUID, db: Session, days: int = 30) -> dict:
    today = date.today()
    cutoff = today + timedelta(days=days)

    rows = db.execute(
        select(
            IrsAuthorization.id,
            IrsAuthorization.form_type,
            IrsAuthorization.valid_until,
            Client.id.label("client_id"),
            Client.name.label("client_name"),
        )
        .join(Client, IrsAuthorization.client_id == Client.id)
        .where(
            IrsAuthorization.firm_id == firm_id,
            IrsAuthorization.valid_until >= today,
            IrsAuthorization.valid_until <= cutoff,
        )
        .order_by(IrsAuthorization.valid_until.asc())
        .limit(30)
    ).fetchall()

    items = [
        {
            "auth_id": str(r.id),
            "client_id": str(r.client_id),
            "client_name": r.client_name,
            "form_type": str(r.form_type) if r.form_type else None,
            "valid_until": r.valid_until.isoformat() if r.valid_until else None,
            "days_until_expiry": (r.valid_until - today).days if r.valid_until else None,
        }
        for r in rows
    ]

    return {
        "expiring_count": len(items),
        "threshold_days": days,
        "authorizations": items,
    }



# ---------------------------------------------------------------------------
# Function: get_outstanding_document_requests
# Returns all firm-wide pending or partial document requests with client and
# engagement context, for answering broad questions about which clients have
# outstanding requests across the firm.
# ---------------------------------------------------------------------------
def get_outstanding_document_requests(firm_id: uuid.UUID, db: Session) -> dict:
    rows = db.execute(
        select(
            DocumentRequest.id,
            DocumentRequest.title,
            DocumentRequest.status,
            DocumentRequest.due_date,
            Client.name.label("client_name"),
            Engagement.name.label("engagement_name"),
        )
        .join(Client, DocumentRequest.client_id == Client.id)
        .join(Engagement, DocumentRequest.engagement_id == Engagement.id)
        .where(
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.status.in_(["pending", "partial"]),
        )
        .order_by(DocumentRequest.due_date.asc().nulls_last())
        .limit(30)
    ).fetchall()

    outstanding = [
        {
            "client_name": r.client_name,
            "engagement_name": r.engagement_name,
            "request_title": r.title,
            "status": r.status,
            "due_date": r.due_date.isoformat() if r.due_date else None,
        }
        for r in rows
    ]

    return {
        "outstanding_count": len(outstanding),
        "requests": outstanding,
    }
# ---------------------------------------------------------------------------
# Function 14: get_client_document_status
# Returns document request status for a specific client and engagement.
# ---------------------------------------------------------------------------
def get_client_document_status(
    firm_id: uuid.UUID, client_id: uuid.UUID, db: Session,
    engagement_id: uuid.UUID | None = None,
) -> dict:
    query = select(DocumentRequest).where(
        DocumentRequest.firm_id == firm_id,
        DocumentRequest.client_id == client_id,
        DocumentRequest.status.in_(["pending", "partial"]),
    )
    if engagement_id:
        query = query.where(DocumentRequest.engagement_id == engagement_id)

    requests = db.execute(query.order_by(DocumentRequest.created_at.desc()).limit(5)).scalars().all()

    if not requests:
        return {
            "client_id": str(client_id),
            "open_requests": 0,
            "requests": [],
        }

    results = []
    for req in requests:
        items = req.checklist_items or []
        total = len(items)
        uploaded = sum(1 for i in items if i.get("status") in ("uploaded", "approved"))
        pending = total - uploaded

        last_upload = db.execute(
            select(func.max(BehavioralEvent.occurred_at))
            .where(
                BehavioralEvent.firm_id == firm_id,
                BehavioralEvent.event_type == "document.uploaded",
                BehavioralEvent.entity_id == req.id,
            )
        ).scalar()

        results.append({
            "request_id": str(req.id),
            "total_items": total,
            "uploaded": uploaded,
            "pending": pending,
            "last_upload": last_upload.isoformat() if last_upload else None,
            "days_since_upload": (datetime.now(timezone.utc) - last_upload).days if last_upload else None,
        })

    return {
        "client_id": str(client_id),
        "open_requests": len(results),
        "requests": results,
    }


# ---------------------------------------------------------------------------
# Function 16: get_task_status
# Returns incomplete tasks and unchecked QC checklist items firm-wide,
# independent of engagement completion status.
# ---------------------------------------------------------------------------
def get_task_status(firm_id: uuid.UUID, db: Session) -> dict:
    today = date.today()

    # Incomplete tasks with engagement and client context
    task_rows = db.execute(
        select(
            Task.id,
            Task.title,
            Task.status,
            Task.due_date,
            Task.is_completed,
            Client.name.label("client_name"),
            Engagement.name.label("engagement_name"),
            User.full_name.label("assigned_to_name"),
        )
        .join(Client, Task.client_id == Client.id)
        .join(Engagement, Task.engagement_id == Engagement.id)
        .outerjoin(User, Task.assigned_to == User.id)
        .where(
            Task.firm_id == firm_id,
            Task.is_completed == False,  # noqa: E712
        )
        .order_by(Task.due_date.asc().nullslast())
        .limit(30)
    ).fetchall()

    tasks = [
        {
            "task_id": str(r.id),
            "title": r.title,
            "status": r.status,
            "client_name": r.client_name,
            "engagement_name": r.engagement_name,
            "assigned_to": r.assigned_to_name,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "overdue": r.due_date is not None and r.due_date < today,
        }
        for r in task_rows
    ]

    # Unchecked QC checklist items with engagement and client context
    checklist_rows = db.execute(
        select(
            QcChecklistItem.id,
            QcChecklistItem.title,
            Engagement.id.label("engagement_id"),
            Engagement.name.label("engagement_name"),
            Client.name.label("client_name"),
        )
        .join(Engagement, QcChecklistItem.engagement_id == Engagement.id)
        .join(Client, Engagement.client_id == Client.id)
        .where(
            QcChecklistItem.firm_id == firm_id,
            QcChecklistItem.is_checked == False,  # noqa: E712
        )
        .order_by(Engagement.name.asc())
        .limit(30)
    ).fetchall()

    checklist_items = [
        {
            "item_id": str(r.id),
            "title": r.title,
            "engagement_name": r.engagement_name,
            "client_name": r.client_name,
        }
        for r in checklist_rows
    ]

    overdue_count = sum(1 for t in tasks if t["overdue"])

    return {
        "incomplete_tasks": len(tasks),
        "overdue_tasks": overdue_count,
        "unchecked_checklist_items": len(checklist_items),
        "tasks": tasks,
        "checklist_items": checklist_items,
    }


# ---------------------------------------------------------------------------
# Function 17: get_qc_checklist_status
# Returns engagements with outstanding QC checklist items, using the same
# unchecked-count logic as crud/qc_checklist.get_unchecked_counts but
# firm-wide and joined with client and engagement names for readability.
# ---------------------------------------------------------------------------
def get_qc_checklist_status(firm_id: uuid.UUID, db: Session) -> dict:
    rows = db.execute(
        select(
            Engagement.id,
            Engagement.name.label("engagement_name"),
            Client.name.label("client_name"),
            func.count(QcChecklistItem.id).label("unchecked_count"),
        )
        .join(QcChecklistItem, QcChecklistItem.engagement_id == Engagement.id)
        .join(Client, Engagement.client_id == Client.id)
        .where(
            QcChecklistItem.firm_id == firm_id,
            QcChecklistItem.is_checked == False,  # noqa: E712
        )
        .group_by(Engagement.id, Engagement.name, Client.name)
        .order_by(func.count(QcChecklistItem.id).desc())
        .limit(30)
    ).fetchall()

    engagements = [
        {
            "engagement_id": str(r.id),
            "engagement_name": r.engagement_name,
            "client_name": r.client_name,
            "unchecked_items": r.unchecked_count,
        }
        for r in rows
    ]

    return {
        "engagements_with_outstanding_qc": len(engagements),
        "engagements": engagements,
    }


# ---------------------------------------------------------------------------
# Function 18: get_time_tracking_detail
# Returns hours logged per staff member for the current week, split into
# billable and non-billable totals, and total firm-wide unbilled billable
# hours across ALL engagement statuses (distinct from get_unbilled_completed_work
# which covers completed engagements in the current month only).
# ---------------------------------------------------------------------------
def get_time_tracking_detail(firm_id: uuid.UUID, db: Session) -> dict:
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    month_start = today.replace(day=1)

    # Per-staff breakdown of billable vs non-billable hours this week
    staff_rows = db.execute(
        select(
            User.id,
            User.full_name,
            TimeEntry.is_billable,
            func.sum(TimeEntry.hours).label("total_hours"),
        )
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.firm_id == firm_id,
            TimeEntry.date >= week_start,
        )
        .group_by(User.id, User.full_name, TimeEntry.is_billable)
        .order_by(User.full_name.asc())
    ).fetchall()

    staff_map: dict = {}
    for r in staff_rows:
        uid = str(r.id)
        if uid not in staff_map:
            staff_map[uid] = {
                "user_id": uid,
                "name": r.full_name,
                "billable_hours": 0.0,
                "non_billable_hours": 0.0,
            }
        if r.is_billable:
            staff_map[uid]["billable_hours"] = round(float(r.total_hours or 0), 2)
        else:
            staff_map[uid]["non_billable_hours"] = round(float(r.total_hours or 0), 2)

    staff_list = sorted(staff_map.values(), key=lambda x: x["billable_hours"] + x["non_billable_hours"], reverse=True)

    firm_billable = sum(s["billable_hours"] for s in staff_list)
    firm_non_billable = sum(s["non_billable_hours"] for s in staff_list)

    # Unbilled billable hours this month across all engagements (not just completed)
    unbilled_all = db.execute(
        select(func.sum(TimeEntry.hours))
        .where(
            TimeEntry.firm_id == firm_id,
            TimeEntry.is_billable == True,  # noqa: E712
            TimeEntry.is_billed == False,  # noqa: E712
            TimeEntry.date >= month_start,
        )
    ).scalar()

    return {
        "week_start": week_start.isoformat(),
        "firm_billable_hours_this_week": round(firm_billable, 2),
        "firm_non_billable_hours_this_week": round(firm_non_billable, 2),
        "unbilled_billable_hours_this_month_all_engagements": round(float(unbilled_all or 0), 2),
        "staff": staff_list,
    }


# ---------------------------------------------------------------------------
# Function 19: get_signature_envelope_status
# Returns pending, declined, and expired envelopes firm-wide, or optionally
# scoped to a specific client, with signer-level detail and days pending.
# ---------------------------------------------------------------------------
def get_signature_envelope_status(
    firm_id: uuid.UUID,
    db: Session,
    client_id: uuid.UUID | None = None,
) -> dict:
    stmt = select(
        SignatureEnvelope.id,
        SignatureEnvelope.status,
        SignatureEnvelope.subject,
        SignatureEnvelope.signers,
        SignatureEnvelope.sent_at,
        SignatureEnvelope.expires_at,
        SignatureEnvelope.reminder_count,
        Client.name.label("client_name"),
        Engagement.name.label("engagement_name"),
    ).join(
        Client, SignatureEnvelope.client_id == Client.id
    ).outerjoin(
        Engagement, SignatureEnvelope.engagement_id == Engagement.id
    ).where(
        SignatureEnvelope.firm_id == firm_id,
        SignatureEnvelope.status.in_(["draft", "sent", "declined", "expired"]),
    )

    if client_id is not None:
        stmt = stmt.where(SignatureEnvelope.client_id == client_id)

    rows = db.execute(
        stmt.order_by(SignatureEnvelope.sent_at.asc().nullslast()).limit(30)
    ).fetchall()

    now = datetime.now(timezone.utc)
    envelopes = []
    for r in rows:
        sent_at = r.sent_at
        days_pending = (now - sent_at).days if sent_at and sent_at.tzinfo else None

        signers_pending = []
        signers_done = []
        for s in (r.signers or []):
            if s.get("status") in ("signed", "completed"):
                signers_done.append(s.get("name") or s.get("email", ""))
            else:
                signers_pending.append(s.get("name") or s.get("email", ""))

        envelopes.append({
            "envelope_id": str(r.id),
            "client_name": r.client_name,
            "engagement_name": r.engagement_name,
            "subject": r.subject,
            "status": r.status,
            "sent_at": sent_at.isoformat() if sent_at else None,
            "expires_at": r.expires_at.isoformat() if r.expires_at else None,
            "days_pending": days_pending,
            "reminders_sent": r.reminder_count,
            "signers_pending": signers_pending,
            "signers_completed": signers_done,
        })

    return {
        "pending_count": len(envelopes),
        "envelopes": envelopes,
    }


# ---------------------------------------------------------------------------
# Function: get_firm_settings
# Returns subscription tier, notification-relevant settings, staff policies,
# domain configuration, and real integration connection status where a
# verifiable signal exists in the database.
# ---------------------------------------------------------------------------
def get_firm_settings(firm_id: uuid.UUID, db: Session) -> dict:
    firm = db.execute(
        select(Firm).where(Firm.id == firm_id)
    ).scalar_one_or_none()

    if not firm:
        return {"error": "Firm not found"}

    # Real notification-relevant keys from the settings JSON field.
    # Keys are whatever the firm has set; we surface them as-is.
    settings = firm.settings or {}
    notification_keys = {k: v for k, v in settings.items() if "notif" in k.lower() or "email" in k.lower() or "reminder" in k.lower()}

    # QuickBooks: check Integration table for provider=quickbooks, status=connected
    qb_row = db.execute(
        select(Integration.status, Integration.connected_at, Integration.last_synced_at)
        .where(
            Integration.firm_id == firm_id,
            Integration.provider == "quickbooks",
        )
        .order_by(Integration.connected_at.desc())
        .limit(1)
    ).fetchone()

    if qb_row:
        qb_status = qb_row.status
        qb_connected_at = qb_row.connected_at.isoformat() if qb_row.connected_at else None
        qb_last_synced = qb_row.last_synced_at.isoformat() if qb_row.last_synced_at else None
    else:
        qb_status = "not_connected"
        qb_connected_at = None
        qb_last_synced = None

    # Stripe: check StripeConnection table, which is authoritative for Stripe status
    stripe_row = db.execute(
        select(StripeConnection.status, StripeConnection.connected_at, StripeConnection.disconnected_at, StripeConnection.charges_enabled)
        .where(StripeConnection.firm_id == firm_id)
    ).fetchone()

    if stripe_row:
        stripe_status = str(stripe_row.status.value) if hasattr(stripe_row.status, "value") else str(stripe_row.status)
        stripe_connected_at = stripe_row.connected_at.isoformat() if stripe_row.connected_at else None
        stripe_charges_enabled = stripe_row.charges_enabled
    else:
        stripe_status = "not_connected"
        stripe_connected_at = None
        stripe_charges_enabled = False

    # Dropbox Sign / e-sign: no dedicated connection table exists. The only
    # real signal is the esign_enabled feature flag. This indicates whether
    # the feature is enabled for the firm, not whether a live credential is
    # actively connected, since no connection record is stored.
    feature_flags = firm.feature_flags or {}
    esign_enabled = feature_flags.get("esign_enabled", False)

    return {
        "subscription_tier": firm.subscription_tier,
        "staff_auth_policy": firm.staff_auth_policy,
        "timesheet_approval_required": firm.timesheet_approval_required,
        "sending_domain": firm.sending_domain,
        "sending_domain_verified": firm.sending_domain_verified,
        "portal_domain": firm.portal_domain,
        "portal_domain_verified": firm.portal_domain_verified,
        "notification_settings": notification_keys,
        "settings_keys_present": list(settings.keys()),
        "integrations": {
            "quickbooks": {
                "status": qb_status,
                "connected_at": qb_connected_at,
                "last_synced_at": qb_last_synced,
            },
            "stripe": {
                "status": stripe_status,
                "connected_at": stripe_connected_at,
                "charges_enabled": stripe_charges_enabled,
            },
            "esign": {
                "status": "enabled" if esign_enabled else "not_enabled",
                "note": "esign_enabled feature flag only, no live credential record stored",
            },
        },
    }


# ---------------------------------------------------------------------------
# Function: get_my_tasks
# Returns all incomplete tasks assigned to a specific staff member, with
# client name, engagement name, due date, status, and overdue flag per task,
# plus the distinct engagement names those tasks belong to.
# ---------------------------------------------------------------------------
def get_my_tasks(firm_id: uuid.UUID, user_id: uuid.UUID, db: Session) -> dict:
    today = date.today()

    task_rows = db.execute(
        select(
            Task.id,
            Task.title,
            Task.status,
            Task.due_date,
            Client.name.label("client_name"),
            Engagement.name.label("engagement_name"),
        )
        .join(Client, Task.client_id == Client.id)
        .join(Engagement, Task.engagement_id == Engagement.id)
        .where(
            Task.firm_id == firm_id,
            Task.assigned_to == user_id,
            Task.is_completed == False,  # noqa: E712
        )
        .order_by(Task.due_date.asc().nullslast())
    ).fetchall()

    tasks = [
        {
            "task_id": str(r.id),
            "title": r.title,
            "status": r.status,
            "client_name": r.client_name,
            "engagement_name": r.engagement_name,
            "due_date": r.due_date.isoformat() if r.due_date else None,
            "overdue": r.due_date is not None and r.due_date < today,
        }
        for r in task_rows
    ]

    engagement_names = list(dict.fromkeys(r.engagement_name for r in task_rows))

    return {
        "task_count": len(tasks),
        "tasks": tasks,
        "engagements_with_my_tasks": engagement_names,
    }
