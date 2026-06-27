# app/schemas/dashboard.py

from datetime import date, datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class StaffUtilizationItem(BaseModel):
    user_id: UUID
    full_name: str
    hours_this_week: float
    utilization_pct: float


class UpcomingDeadlineItem(BaseModel):
    engagement_id: UUID
    client_name: str
    engagement_type: str
    deadline: date
    days_until: int
    status: str


class OverdueEngagementItem(BaseModel):
    engagement_id: UUID
    client_name: str
    engagement_type: str
    deadline: date
    days_overdue: int
    status: str
    assigned_staff_name: Optional[str]


class UnsignedDocumentItem(BaseModel):
    envelope_id: UUID
    client_name: str
    document_title: str
    sent_at: datetime
    days_waiting: int
    reminder_count: int
    auto_reminder_sent_at: Optional[datetime] = None
    last_reminder_sent_at: Optional[datetime] = None
    escalated_at: Optional[datetime] = None
    followup_task_id: Optional[UUID] = None
    reminder_state: str


class DashboardMetricsOut(BaseModel):
    mrr: float
    mrr_invoice_count: int
    outstanding_ar: float
    outstanding_ar_count: int
    oldest_overdue_days: Optional[int]
    wip_value: float
    wip_hours: float
    overdue_engagement_count: int
    overdue_engagements: list[OverdueEngagementItem]
    upcoming_deadlines: list[UpcomingDeadlineItem]
    staff_utilization: list[StaffUtilizationItem]
    unsigned_document_count: int
    unsigned_documents: list[UnsignedDocumentItem]
