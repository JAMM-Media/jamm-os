# app/api/reports.py

from decimal import Decimal

from fastapi import APIRouter, Depends
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_manager_or_above
from app.models.firm import Firm
from app.models.time_entry import TimeEntry
from app.models.engagement import Engagement
from app.models.client import Client
from app.schemas.reports import WIPEngagementOut, WIPSummaryOut

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/wip", response_model=WIPSummaryOut)
def get_wip_summary(
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
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
            TimeEntry.firm_id == current_firm.id,
            TimeEntry.is_billed == False,  # noqa: E712
            TimeEntry.is_billable == True,  # noqa: E712
        )
        .group_by(TimeEntry.engagement_id, Engagement.name, Client.name)
        .order_by(func.sum(TimeEntry.hours * TimeEntry.hourly_rate).desc())
    )

    rows = db.execute(stmt).all()

    total_wip_value = sum((r.wip_value or Decimal(0)) for r in rows)
    total_hours = sum((r.total_hours or Decimal(0)) for r in rows)

    top_engagements = [
        WIPEngagementOut(
            engagement_id=r.engagement_id,
            engagement_name=r.engagement_name,
            client_name=r.client_name,
            total_hours=r.total_hours or Decimal(0),
            wip_value=r.wip_value or Decimal(0),
        )
        for r in rows[:5]
    ]

    return WIPSummaryOut(
        total_wip_value=total_wip_value,
        total_hours=total_hours,
        top_engagements=top_engagements,
    )
