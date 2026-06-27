# app/api/dashboard.py

from datetime import date, datetime, timezone, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import select, func, case
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_manager_or_above
from app.models.firm import Firm
from app.models.invoice import Invoice
from app.models.time_entry import TimeEntry
from app.models.engagement import Engagement
from app.models.client import Client
from app.models.user import User
from app.models.signature_envelope import SignatureEnvelope
from app.core.enums import InvoiceStatus, UserRole
from app.schemas.dashboard import (
    DashboardMetricsOut,
    OverdueEngagementItem,
    StaffUtilizationItem,
    UnsignedDocumentItem,
    UpcomingDeadlineItem,
)

router = APIRouter(tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetricsOut)
def get_dashboard_metrics(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    today = date.today()
    now = datetime.now(timezone.utc)
    start_of_month = datetime(today.year, today.month, 1, tzinfo=timezone.utc)
    start_of_week = today - timedelta(days=today.weekday())
    end_of_week = start_of_week + timedelta(days=6)

    # --- MRR ---
    mrr_stmt = select(
        func.coalesce(func.sum(Invoice.total_amount), 0).label("total"),
        func.count(Invoice.id).label("count"),
    ).where(
        Invoice.firm_id == current_firm.id,
        Invoice.status == InvoiceStatus.paid,
        Invoice.paid_at >= start_of_month,
    )
    mrr_row = db.execute(mrr_stmt).one()
    mrr = float(mrr_row.total or 0)
    mrr_invoice_count = int(mrr_row.count or 0)

    # --- Outstanding AR ---
    ar_stmt = select(
        Invoice.total_amount,
        Invoice.due_date,
        Invoice.status,
    ).where(
        Invoice.firm_id == current_firm.id,
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

    # --- WIP ---
    wip_stmt = select(
        func.coalesce(func.sum(TimeEntry.hours * TimeEntry.hourly_rate), 0).label("wip_value"),
        func.coalesce(func.sum(TimeEntry.hours), 0).label("wip_hours"),
    ).where(
        TimeEntry.firm_id == current_firm.id,
        TimeEntry.is_billed == False,  # noqa: E712
        TimeEntry.is_billable == True,  # noqa: E712
    )
    wip_row = db.execute(wip_stmt).one()
    wip_value = float(wip_row.wip_value or 0)
    wip_hours = float(wip_row.wip_hours or 0)

    # --- Overdue Engagements ---
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
            Engagement.firm_id == current_firm.id,
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

    # --- Upcoming Deadlines ---
    window_end = today + timedelta(days=14)
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
            Engagement.firm_id == current_firm.id,
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

    # --- Staff Utilization (current ISO week) ---
    # Start from User so staff with zero hours still appear
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
            (TimeEntry.user_id == User.id) & (TimeEntry.firm_id == current_firm.id),
        )
        .where(
            User.firm_id == current_firm.id,
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

    # --- Unsigned Documents — reminder state machine ---
    firm_settings = current_firm.settings or {}
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
            SignatureEnvelope.firm_id == current_firm.id,
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

    return DashboardMetricsOut(
        mrr=mrr,
        mrr_invoice_count=mrr_invoice_count,
        outstanding_ar=outstanding_ar,
        outstanding_ar_count=outstanding_ar_count,
        oldest_overdue_days=oldest_overdue_days,
        wip_value=wip_value,
        wip_hours=wip_hours,
        overdue_engagement_count=len(overdue_engagements),
        overdue_engagements=overdue_engagements,
        upcoming_deadlines=upcoming_deadlines,
        staff_utilization=staff_utilization,
        unsigned_document_count=len(unsigned_documents),
        unsigned_documents=unsigned_documents,
    )
