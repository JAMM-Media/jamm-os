# app/api/dashboard.py

import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_manager_or_above
from app.models.firm import Firm
from app.models.user import User
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.engagement import Engagement
from app.models.client import Client
from app.models.signature_envelope import SignatureEnvelope
from app.models.dashboard_layout import UserDashboardSection
from app.core.enums import InvoiceStatus, UserRole
from app.api.concierge.functions import (
    get_task_status,
    get_client_communication_gap,
    get_outstanding_document_requests,
    get_time_tracking_detail,
    get_recent_firm_chat_activity,
    get_client_full_snapshot,
)
from app.services.client_health_service import compute_client_health
from app.schemas.dashboard import (
    DashboardMetricsOut,
    WIPEngagementItem,
    DashboardSectionItem,
    OverdueEngagementItem,
    StaffUtilizationItem,
    UnsignedDocumentItem,
    UpcomingDeadlineItem,
)

router = APIRouter(tags=["dashboard"])

# ---------------------------------------------------------------------------
# Default six sections
# ---------------------------------------------------------------------------

DEFAULT_SECTIONS: list[dict] = [
    {"key": "morning_briefing",  "visible": True, "order": 0},
    {"key": "financial_stats",   "visible": True, "order": 1},
    {"key": "work_in_progress",  "visible": True, "order": 2},
    {"key": "staff_utilization", "visible": True, "order": 3},
    {"key": "upcoming_deadlines","visible": True, "order": 4},
    {"key": "awaiting_signature","visible": True, "order": 5},
]


def _trend(current: float, prior: float) -> tuple[Optional[float], Optional[str]]:
    """Return (trend_pct, trend_direction) or (None, None) when prior is zero."""
    if prior == 0:
        return None, None
    pct = round(((current - prior) / prior) * 100, 1)
    direction = "up" if current >= prior else "down"
    return pct, direction


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------

def _get_mrr_section(db: Session, firm: Firm) -> dict:
    today = date.today()
    start_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    # Prior month bounds
    if today.month == 1:
        prior_start = datetime(today.year - 1, 12, 1, tzinfo=timezone.utc)
    else:
        prior_start = datetime(today.year, today.month - 1, 1, tzinfo=timezone.utc)
    prior_end = start_of_month

    mrr_stmt = select(
        func.coalesce(func.sum(Invoice.total_amount), 0).label("total"),
        func.count(Invoice.id).label("count"),
    ).where(
        Invoice.firm_id == firm.id,
        Invoice.status == InvoiceStatus.paid,
        Invoice.paid_at >= start_of_month,
    )
    mrr_row = db.execute(mrr_stmt).one()
    mrr = float(mrr_row.total or 0)

    prior_stmt = select(
        func.coalesce(func.sum(Invoice.total_amount), 0).label("total"),
    ).where(
        Invoice.firm_id == firm.id,
        Invoice.status == InvoiceStatus.paid,
        Invoice.paid_at >= prior_start,
        Invoice.paid_at < prior_end,
    )
    prior_val = float(db.execute(prior_stmt).scalar() or 0)

    trend_pct, trend_dir = _trend(mrr, prior_val)
    return {
        "mrr": mrr,
        "mrr_invoice_count": int(mrr_row.count or 0),
        "mrr_trend_pct": trend_pct,
        "mrr_trend_direction": trend_dir,
    }


def _get_outstanding_ar_section(db: Session, firm: Firm) -> dict:
    today = date.today()
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    ar_stmt = select(
        Invoice.total_amount,
        Invoice.due_date,
        Invoice.status,
    ).where(
        Invoice.firm_id == firm.id,
        Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.overdue]),
    )
    ar_rows = db.execute(ar_stmt).all()
    outstanding_ar = float(sum(r.total_amount or 0 for r in ar_rows))
    outstanding_ar_count = len(ar_rows)
    overdue_days_list = [
        (today - r.due_date).days
        for r in ar_rows
        if r.status == InvoiceStatus.overdue and r.due_date is not None
    ]
    oldest_overdue_days = max(overdue_days_list) if overdue_days_list else None

    # Reconstruct AR 30 days ago:
    # invoices sent on or before cutoff that were not yet paid (paid_at > cutoff or null)
    # and were not voided.
    prior_stmt = select(
        func.coalesce(func.sum(Invoice.total_amount), 0).label("total"),
    ).where(
        Invoice.firm_id == firm.id,
        Invoice.sent_at.isnot(None),
        Invoice.sent_at <= cutoff,
        Invoice.status != InvoiceStatus.void,
        (Invoice.paid_at.is_(None)) | (Invoice.paid_at > cutoff),
    )
    prior_ar = float(db.execute(prior_stmt).scalar() or 0)
    trend_pct, trend_dir = _trend(outstanding_ar, prior_ar)

    return {
        "outstanding_ar": outstanding_ar,
        "outstanding_ar_count": outstanding_ar_count,
        "oldest_overdue_days": oldest_overdue_days,
        "ar_trend_pct": trend_pct,
        "ar_trend_direction": trend_dir,
    }


def _get_wip_section(db: Session, firm: Firm) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)

    wip_stmt = select(
        func.coalesce(func.sum(TimeEntry.hours * TimeEntry.hourly_rate), 0).label("wip_value"),
        func.coalesce(func.sum(TimeEntry.hours), 0).label("wip_hours"),
    ).where(
        TimeEntry.firm_id == firm.id,
        TimeEntry.is_billed == False,  # noqa: E712
        TimeEntry.is_billable == True,  # noqa: E712
    )
    wip_row = db.execute(wip_stmt).one()
    wip_value = float(wip_row.wip_value or 0)

    # WIP 30 days ago: billable entries that existed by the cutoff date
    # and either remain unbilled today OR were billed after the cutoff
    # (i.e. were attached to an invoice created after the cutoff).
    prior_stmt = (
        select(
            func.coalesce(func.sum(TimeEntry.hours * TimeEntry.hourly_rate), 0).label("wip_value"),
        )
        .outerjoin(Invoice, TimeEntry.invoice_id == Invoice.id)
        .where(
            TimeEntry.firm_id == firm.id,
            TimeEntry.is_billable == True,  # noqa: E712
            TimeEntry.created_at <= cutoff,
            (TimeEntry.is_billed == False) | (  # noqa: E712
                (TimeEntry.is_billed == True) & (Invoice.created_at > cutoff)  # noqa: E712
            ),
        )
    )
    prior_wip = float(db.execute(prior_stmt).scalar() or 0)
    trend_pct, trend_dir = _trend(wip_value, prior_wip)

    return {
        "wip_value": wip_value,
        "wip_hours": float(wip_row.wip_hours or 0),
        "wip_trend_pct": trend_pct,
        "wip_trend_direction": trend_dir,
    }


def _get_overdue_engagements_section(db: Session, firm: Firm) -> dict:
    today = date.today()
    effective_deadline = func.coalesce(Engagement.extended_deadline, Engagement.filing_deadline)
    overdue_stmt = (
        select(
            Engagement.id,
            Client.name.label("client_name"),
            Engagement.engagement_type,
            effective_deadline.label("deadline"),
            Engagement.status,
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm.id,
            Engagement.status.notin_(["completed", "archived"]),
            effective_deadline.isnot(None),
            effective_deadline < today,
        )
        .order_by(effective_deadline.asc())
        .limit(20)
    )
    overdue_rows = db.execute(overdue_stmt).all()
    overdue_engagements = [
        OverdueEngagementItem(
            engagement_id=r.id,
            client_name=r.client_name,
            engagement_type=r.engagement_type or "",
            deadline=r.deadline,
            days_overdue=(today - r.deadline).days,
            status=r.status,
            assigned_staff_name=None,
        )
        for r in overdue_rows
    ]
    return {
        "overdue_engagement_count": len(overdue_engagements),
        "overdue_engagements": overdue_engagements,
    }


def _get_upcoming_deadlines_section(db: Session, firm: Firm) -> dict:
    today = date.today()
    window_end = today + timedelta(days=14)
    effective_deadline = func.coalesce(Engagement.extended_deadline, Engagement.filing_deadline)
    upcoming_stmt = (
        select(
            Engagement.id,
            Client.name.label("client_name"),
            Engagement.engagement_type,
            effective_deadline.label("deadline"),
            Engagement.status,
        )
        .join(Client, Engagement.client_id == Client.id)
        .where(
            Engagement.firm_id == firm.id,
            Engagement.status.notin_(["completed", "archived"]),
            effective_deadline.isnot(None),
            effective_deadline >= today,
            effective_deadline <= window_end,
        )
        .order_by(effective_deadline.asc())
        .limit(20)
    )
    upcoming_rows = db.execute(upcoming_stmt).all()
    upcoming_deadlines = [
        UpcomingDeadlineItem(
            engagement_id=r.id,
            client_name=r.client_name,
            engagement_type=r.engagement_type or "",
            deadline=r.deadline,
            days_until=(r.deadline - today).days,
            status=r.status,
        )
        for r in upcoming_rows
    ]
    return {"upcoming_deadlines": upcoming_deadlines}


def _get_staff_utilization_section(db: Session, firm: Firm) -> dict:
    today = date.today()
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)
    util_stmt = (
        select(
            User.id.label("user_id"),
            User.full_name,
            func.coalesce(
                func.sum(
                    case(
                        (
                            (TimeEntry.date >= start_of_week) & (TimeEntry.date <= end_of_week),
                            TimeEntry.hours,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("hours_this_week"),
        )
        .outerjoin(
            TimeEntry,
            (TimeEntry.user_id == User.id) & (TimeEntry.firm_id == firm.id),
        )
        .where(
            User.firm_id == firm.id,
            User.is_active == True,
            User.role != UserRole.client_portal_user,
        )
        .group_by(User.id, User.full_name)
    )
    util_rows = db.execute(util_stmt).all()
    staff_utilization = [
        StaffUtilizationItem(
            user_id=r.user_id,
            full_name=r.full_name or "",
            hours_this_week=float(r.hours_this_week or 0),
            utilization_pct=min(float(r.hours_this_week or 0) / 40.0 * 100, 100.0),
        )
        for r in util_rows
    ]
    return {"staff_utilization": staff_utilization}


def _get_unsigned_documents_section(db: Session, firm: Firm) -> dict:
    now = datetime.now(timezone.utc)
    firm_settings = firm.settings or {}
    first_days = int(firm_settings.get('esign_first_reminder_days', 2))
    second_days = int(firm_settings.get('esign_second_reminder_days', 4))
    escalation_days = int(firm_settings.get('esign_escalation_days', 3))

    def compute_reminder_state(row, _now, _first_days, _second_days, _escalation_days):
        if row.followup_task_id is not None:
            return 'followup_created'
        if row.escalated_at is not None:
            return 'escalated'
        sent_at = row.sent_at
        if sent_at is not None and sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        days_since_sent = (_now - sent_at).days if sent_at else 0
        if row.reminder_count == 0 and row.auto_reminder_sent_at is None:
            if days_since_sent < _first_days:
                return 'too_new'
            return 'ready_first'
        if row.reminder_count == 1:
            last = row.last_reminder_sent_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days_since_last = (_now - last).days if last else 0
            if days_since_last < _second_days:
                return 'cooldown'
            return 'ready_second'
        if row.reminder_count >= 2:
            last = row.last_reminder_sent_at
            if last is not None and last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            days_since_last = (_now - last).days if last else 0
            if days_since_last < _escalation_days:
                return 'cooldown'
            return 'escalated'
        return 'too_new'

    unsigned_stmt = (
        select(
            SignatureEnvelope.id,
            Client.name.label("client_name"),
            SignatureEnvelope.subject.label("document_title"),
            SignatureEnvelope.sent_at,
            SignatureEnvelope.reminder_count,
            SignatureEnvelope.auto_reminder_sent_at,
            SignatureEnvelope.last_reminder_sent_at,
            SignatureEnvelope.escalated_at,
            SignatureEnvelope.followup_task_id,
        )
        .join(Client, SignatureEnvelope.client_id == Client.id)
        .where(
            SignatureEnvelope.firm_id == firm.id,
            SignatureEnvelope.status == "sent",
        )
        .order_by(SignatureEnvelope.sent_at.asc())
        .limit(20)
    )
    unsigned_rows = db.execute(unsigned_stmt).all()
    unsigned_documents = []
    for r in unsigned_rows:
        reminder_state = compute_reminder_state(
            r, now, first_days, second_days, escalation_days
        )
        if reminder_state in ('too_new', 'cooldown', 'followup_created'):
            continue
        sent_at = r.sent_at
        if sent_at is not None and sent_at.tzinfo is None:
            sent_at = sent_at.replace(tzinfo=timezone.utc)
        days_waiting = (now - sent_at).days if sent_at is not None else 0
        unsigned_documents.append(
            UnsignedDocumentItem(
                envelope_id=r.id,
                client_name=r.client_name,
                document_title=r.document_title or "",
                sent_at=r.sent_at,
                days_waiting=days_waiting,
                reminder_count=r.reminder_count or 0,
                auto_reminder_sent_at=r.auto_reminder_sent_at,
                last_reminder_sent_at=r.last_reminder_sent_at,
                escalated_at=r.escalated_at,
                followup_task_id=r.followup_task_id,
                reminder_state=reminder_state,
            )
        )
    return {
        "unsigned_document_count": len(unsigned_documents),
        "unsigned_documents": unsigned_documents,
    }


def _get_work_in_progress_section(db: Session, firm: Firm) -> dict:
    """Detailed WIP: top engagements by unbilled value."""
    stmt = (
        select(
            TimeEntry.engagement_id,
            Engagement.name.label("engagement_name"),
            Client.name.label("client_name"),
            func.sum(TimeEntry.hours).label("total_hours"),
            func.sum(TimeEntry.hours * TimeEntry.hourly_rate).label("wip_value"),
        )
        .join(Engagement, TimeEntry.engagement_id == Engagement.id)
        .join(Client, Engagement.client_id == Client.id)
        .where(
            TimeEntry.firm_id == firm.id,
            TimeEntry.is_billed == False,  # noqa: E712
            TimeEntry.is_billable == True,  # noqa: E712
        )
        .group_by(TimeEntry.engagement_id, Engagement.name, Client.name)
        .order_by(func.sum(TimeEntry.hours * TimeEntry.hourly_rate).desc())
    )
    rows = db.execute(stmt).all()
    total_wip_value = float(sum(r.wip_value or 0 for r in rows))
    total_hours = float(sum(r.total_hours or 0 for r in rows))
    return {
        "total_wip_value": total_wip_value,
        "total_hours": total_hours,
        "top_engagements": [
            {
                "engagement_id": str(r.engagement_id),
                "engagement_name": r.engagement_name,
                "client_name": r.client_name,
                "total_hours": float(r.total_hours or 0),
                "wip_value": float(r.wip_value or 0),
            }
            for r in rows[:10]
        ],
    }


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class SectionItemIn(BaseModel):
    key: str
    visible: bool
    order: int


class SectionsIn(BaseModel):
    sections: list[SectionItemIn]


# ---------------------------------------------------------------------------
# Metrics endpoint
# ---------------------------------------------------------------------------

@router.get("/metrics", response_model=DashboardMetricsOut)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    mrr_data = _get_mrr_section(db, current_firm)
    ar_data = _get_outstanding_ar_section(db, current_firm)
    wip_data = _get_wip_section(db, current_firm)
    wip_detail_data = _get_work_in_progress_section(db, current_firm)
    overdue_data = _get_overdue_engagements_section(db, current_firm)
    upcoming_data = _get_upcoming_deadlines_section(db, current_firm)
    util_data = _get_staff_utilization_section(db, current_firm)
    unsigned_data = _get_unsigned_documents_section(db, current_firm)

    return DashboardMetricsOut(
        mrr=mrr_data["mrr"],
        mrr_invoice_count=mrr_data["mrr_invoice_count"],
        mrr_trend_pct=mrr_data["mrr_trend_pct"],
        mrr_trend_direction=mrr_data["mrr_trend_direction"],
        outstanding_ar=ar_data["outstanding_ar"],
        outstanding_ar_count=ar_data["outstanding_ar_count"],
        oldest_overdue_days=ar_data["oldest_overdue_days"],
        ar_trend_pct=ar_data["ar_trend_pct"],
        ar_trend_direction=ar_data["ar_trend_direction"],
        wip_value=wip_data["wip_value"],
        wip_hours=wip_data["wip_hours"],
        wip_trend_pct=wip_data["wip_trend_pct"],
        wip_trend_direction=wip_data["wip_trend_direction"],
        overdue_engagement_count=overdue_data["overdue_engagement_count"],
        overdue_engagements=overdue_data["overdue_engagements"],
        upcoming_deadlines=upcoming_data["upcoming_deadlines"],
        staff_utilization=util_data["staff_utilization"],
        unsigned_document_count=unsigned_data["unsigned_document_count"],
        unsigned_documents=unsigned_data["unsigned_documents"],
        top_engagements=[
            WIPEngagementItem(**e) for e in wip_detail_data["top_engagements"]
        ],
    )


# ---------------------------------------------------------------------------
# Sections endpoints
# ---------------------------------------------------------------------------

@router.get("/sections")
def get_sections(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """Returns the current user's section visibility/order, seeding defaults if no row exists."""
    row = db.execute(
        select(UserDashboardSection).where(
            UserDashboardSection.user_id == current_user.id,
            UserDashboardSection.firm_id == current_firm.id,
        )
    ).scalar_one_or_none()
    if row is not None:
        return {"sections": row.sections}
    return {"sections": DEFAULT_SECTIONS}


@router.put("/sections")
def put_sections(
    payload: SectionsIn,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """Upserts the current user's section visibility/order."""
    sections = [s.model_dump() for s in payload.sections]
    row = db.execute(
        select(UserDashboardSection).where(
            UserDashboardSection.user_id == current_user.id,
            UserDashboardSection.firm_id == current_firm.id,
        )
    ).scalar_one_or_none()
    if row is None:
        row = UserDashboardSection(
            user_id=current_user.id,
            firm_id=current_firm.id,
            sections=sections,
        )
        db.add(row)
    else:
        row.sections = sections
        row.updated_at = datetime.now(timezone.utc)
    db.commit()
    return {"sections": row.sections}
