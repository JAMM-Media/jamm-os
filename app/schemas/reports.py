# app/schemas/reports.py

from decimal import Decimal
from uuid import UUID
from pydantic import BaseModel


class WIPEngagementOut(BaseModel):
    engagement_id: UUID
    engagement_name: str
    client_name: str
    total_hours: Decimal
    wip_value: Decimal


class WIPSummaryOut(BaseModel):
    total_wip_value: Decimal
    total_hours: Decimal
    top_engagements: list[WIPEngagementOut]
