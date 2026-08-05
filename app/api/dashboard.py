# app/api/dashboard.py

import uuid
from datetime import date, datetime, timezone, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_manager_or_above, require_firm_owner
from app.models.firm import Firm
from app.models.user import User
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.engagement import Engagement
from app.models.client import Client
from app.models.signature_envelope import SignatureEnvelope
from app.models.dashboard_layout import DashboardLayout, FirmDefaultDashboardLayout
from app.core.enums import InvoiceStatus, UserRole
from app.core.dashboard_widgets import WIDGET_REGISTRY, WIDGET_BY_TYPE_KEY
from app.schemas.dashboard import (
    DashboardMetricsOut,
    OverdueEngagementItem,
    StaffUtilizationItem,
    UnsignedDocumentItem,
    UpcomingDeadlineItem,
)

router = APIRouter(tags=["dashboard"])


# ---------------------------------------------------------------------------
# Section extractors
# ---------------------------------------------------------------------------

def _get_mrr_section(db: Session, firm: Firm) -> dict:
    today = date.today()
    start_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    mrr_stmt = select(
        func.coalesce(func.sum(Invoice.total_amount), 0).label("total"),
        func.count(Invoice.id).label("count"),
    ).where(
        Invoice.firm_id == firm.id,
        Invoice.status == InvoiceStatus.paid,
        Invoice.paid_at >= start_of_month,
    )
    mrr_row = db.execute(mrr_stmt).one()
    return {
        "mrr": float(mrr_row.total or 0),
        "mrr_invoice_count": int(mrr_row.count or 0),
    }


def _get_outstanding_ar_section(db: Session, firm: Firm) -> dict:
    today = date.today()
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
    return {
        "outstanding_ar": outstanding_ar,
        "outstanding_ar_count": outstanding_ar_count,
        "oldest_overdue_days": oldest_overdue_days,
    }


def _get_wip_section(db: Session, firm: Firm) -> dict:
    wip_stmt = select(
        func.coalesce(func.sum(TimeEntry.hours * TimeEntry.hourly_rate), 0).label("wip_value"),
        func.coalesce(func.sum(TimeEntry.hours), 0).label("wip_hours"),
    ).where(
        TimeEntry.firm_id == firm.id,
        TimeEntry.is_billed == False,  # noqa: E712
        TimeEntry.is_billable == True,  # noqa: E712
    )
    wip_row = db.execute(wip_stmt).one()
    return {
        "wip_value": float(wip_row.wip_value or 0),
        "wip_hours": float(wip_row.wip_hours or 0),
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
    """Detailed WIP widget: top engagements by unbilled value.
    Sources the same query logic as reports.get_wip_summary."""
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
            for r in rows[:5]
        ],
    }


# ---------------------------------------------------------------------------
# Dispatch table: type_key -> section function
# ---------------------------------------------------------------------------

_WIDGET_DISPATCH = {
    "revenue_this_month": _get_mrr_section,
    "outstanding_ar": _get_outstanding_ar_section,
    "unbilled_wip_stat": _get_wip_section,
    "overdue_engagements_count": _get_overdue_engagements_section,
    "work_in_progress": _get_work_in_progress_section,
    "upcoming_deadlines": _get_upcoming_deadlines_section,
    "staff_utilization": _get_staff_utilization_section,
    "overdue_engagements_table": _get_overdue_engagements_section,
    "awaiting_signature": _get_unsigned_documents_section,
}


# ---------------------------------------------------------------------------
# System default layout
# ---------------------------------------------------------------------------

def _system_default_widgets() -> list:
    return [
        {"instance_id": str(uuid.uuid4()), "type_key": "revenue_this_month",        "grid_x": 0, "grid_y": 0, "size": "small",  "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "outstanding_ar",             "grid_x": 1, "grid_y": 0, "size": "small",  "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "unbilled_wip_stat",          "grid_x": 2, "grid_y": 0, "size": "small",  "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "overdue_engagements_count",  "grid_x": 3, "grid_y": 0, "size": "small",  "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "work_in_progress",           "grid_x": 0, "grid_y": 1, "size": "medium", "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "upcoming_deadlines",         "grid_x": 0, "grid_y": 2, "size": "medium", "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "staff_utilization",          "grid_x": 1, "grid_y": 2, "size": "medium", "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "overdue_engagements_table",  "grid_x": 0, "grid_y": 3, "size": "large",  "minimized": False, "config": {}},
        {"instance_id": str(uuid.uuid4()), "type_key": "awaiting_signature",         "grid_x": 0, "grid_y": 4, "size": "large",  "minimized": False, "config": {}},
    ]


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class WidgetInstanceIn(BaseModel):
    instance_id: str
    type_key: str
    grid_x: int
    grid_y: int
    size: str
    minimized: bool = False
    config: dict = {}


class LayoutIn(BaseModel):
    widgets: list[WidgetInstanceIn]


# ---------------------------------------------------------------------------
# Existing endpoint (behavior-preserving, now uses extracted section fns)
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
    overdue_data = _get_overdue_engagements_section(db, current_firm)
    upcoming_data = _get_upcoming_deadlines_section(db, current_firm)
    util_data = _get_staff_utilization_section(db, current_firm)
    unsigned_data = _get_unsigned_documents_section(db, current_firm)

    return DashboardMetricsOut(
        mrr=mrr_data["mrr"],
        mrr_invoice_count=mrr_data["mrr_invoice_count"],
        outstanding_ar=ar_data["outstanding_ar"],
        outstanding_ar_count=ar_data["outstanding_ar_count"],
        oldest_overdue_days=ar_data["oldest_overdue_days"],
        wip_value=wip_data["wip_value"],
        wip_hours=wip_data["wip_hours"],
        overdue_engagement_count=overdue_data["overdue_engagement_count"],
        overdue_engagements=overdue_data["overdue_engagements"],
        upcoming_deadlines=upcoming_data["upcoming_deadlines"],
        staff_utilization=util_data["staff_utilization"],
        unsigned_document_count=unsigned_data["unsigned_document_count"],
        unsigned_documents=unsigned_data["unsigned_documents"],
    )


# ---------------------------------------------------------------------------
# New endpoints
# ---------------------------------------------------------------------------

@router.get("/widget-catalog")
def get_widget_catalog(
    current_user: User = Depends(require_manager_or_above),
):
    """Returns all widget types whose role_requirement is satisfied by the caller."""
    role = str(current_user.role)
    is_manager_or_above = role in ("firm_owner", "manager")
    return [
        w for w in WIDGET_REGISTRY
        if w["role_requirement"] == "manager_or_above" and is_manager_or_above
    ]


@router.get("/layout")
def get_layout(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """Resolves the caller's dashboard layout (user -> firm default -> system default)."""
    row = db.execute(
        select(DashboardLayout).where(DashboardLayout.user_id == current_user.id)
    ).scalar_one_or_none()

    if row is not None:
        return {"widgets": row.widgets}

    firm_default = db.execute(
        select(FirmDefaultDashboardLayout).where(
            FirmDefaultDashboardLayout.firm_id == current_firm.id
        )
    ).scalar_one_or_none()

    widgets = firm_default.widgets if firm_default is not None else _system_default_widgets()

    new_row = DashboardLayout(
        firm_id=current_firm.id,
        user_id=current_user.id,
        widgets=widgets,
    )
    db.add(new_row)
    db.commit()
    return {"widgets": widgets}


@router.put("/layout")
def put_layout(
    payload: LayoutIn,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    """Upserts the caller's personal dashboard layout."""
    widgets = [w.model_dump() for w in payload.widgets]
    row = db.execute(
        select(DashboardLayout).where(DashboardLayout.user_id == current_user.id)
    ).scalar_one_or_none()

    if row is None:
        row = DashboardLayout(firm_id=current_firm.id, user_id=current_user.id, widgets=widgets)
        db.add(row)
    else:
        row.widgets = widgets
        row.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"widgets": row.widgets}


@router.put("/firm-default-layout")
def put_firm_default_layout(
    payload: LayoutIn,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_firm_owner),
):
    """Upserts the firm-wide default layout. Firm owners only."""
    widgets = [w.model_dump() for w in payload.widgets]
    row = db.execute(
        select(FirmDefaultDashboardLayout).where(
            FirmDefaultDashboardLayout.firm_id == current_firm.id
        )
    ).scalar_one_or_none()

    if row is None:
        row = FirmDefaultDashboardLayout(firm_id=current_firm.id, widgets=widgets)
        db.add(row)
    else:
        row.widgets = widgets
        row.updated_at = datetime.now(timezone.utc)

    db.commit()
    return {"widgets": row.widgets}


@router.get("/widgets/{type_key}/data")
def get_widget_data(
    type_key: str,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    """Returns live data for a single widget type."""
    if type_key not in WIDGET_BY_TYPE_KEY:
        raise HTTPException(status_code=404, detail=f"Unknown widget type: {type_key}")
    section_fn = _WIDGET_DISPATCH.get(type_key)
    if section_fn is None:
        raise HTTPException(status_code=404, detail=f"No data function for: {type_key}")
    return section_fn(db, current_firm)
