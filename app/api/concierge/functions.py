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
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.models.client import Client
from app.models.engagement import Engagement
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.user import User
from app.models.automation_rule import AutomationRule
from app.models.behavioral_event import BehavioralEvent
from app.models.document_request import DocumentRequest


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
            Engagement.status.notin_(["completed", "archived"]),
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
            Invoice.status.in_(["sent", "overdue"]),
            Invoice.due_date < today,
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
            Engagement.status.notin_(["completed", "archived"]),
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
