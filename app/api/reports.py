# app/api/reports.py

import io
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.dependencies.tenant import get_current_firm
from app.dependencies.roles import require_manager_or_above
from app.models.firm import Firm
from app.models.time_entry import TimeEntry
from app.models.engagement import Engagement
from app.models.client import Client
from app.models.user import User
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


def _query_billing_detail_entries(
    db: Session,
    firm_id: UUID,
    client_id: UUID,
    date_from: Optional[date],
    date_to: Optional[date],
    engagement_id: Optional[UUID],
) -> list[dict]:
    stmt = (
        select(
            TimeEntry.date,
            TimeEntry.description,
            TimeEntry.hours,
            TimeEntry.hourly_rate,
            TimeEntry.is_billable,
            TimeEntry.activity_type,
            TimeEntry.created_at,
            User.full_name.label("staff_name"),
            Engagement.name.label("engagement_name"),
        )
        .join(Engagement, TimeEntry.engagement_id == Engagement.id)
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.firm_id == firm_id,
            Engagement.client_id == client_id,
            Engagement.firm_id == firm_id,
        )
    )

    if engagement_id is not None:
        stmt = stmt.where(TimeEntry.engagement_id == engagement_id)
    if date_from is not None:
        stmt = stmt.where(TimeEntry.date >= date_from)
    if date_to is not None:
        stmt = stmt.where(TimeEntry.date <= date_to)

    stmt = stmt.order_by(TimeEntry.date.asc(), TimeEntry.created_at.asc())

    rows = db.execute(stmt).all()
    return [
        {
            "date": str(r.date),
            "staff_name": r.staff_name or "",
            "engagement_name": r.engagement_name,
            "activity_type": r.activity_type,
            "description": r.description,
            "hours": float(r.hours),
            "hourly_rate": float(r.hourly_rate),
            "amount": round(float(r.hours) * float(r.hourly_rate), 2),
            "is_billable": r.is_billable,
        }
        for r in rows
    ]


def _build_billing_detail_html(data: dict) -> str:
    date_range = ""
    if data["date_from"] or data["date_to"]:
        parts = []
        if data["date_from"]:
            parts.append(data["date_from"])
        if data["date_to"]:
            parts.append(data["date_to"])
        date_range = " – ".join(parts)

    entry_rows = ""
    for e in data["entries"]:
        amount_fmt = f"${e['amount']:,.2f}"
        hours_fmt = f"{e['hours']:.2f}"
        rate_fmt = f"${e['hourly_rate']:,.2f}"
        entry_rows += f"""
        <tr style="border-bottom:1px solid #e5e7eb;">
            <td style="padding:9px 10px;font-size:13px;">{e['date']}</td>
            <td style="padding:9px 10px;font-size:13px;">{e['staff_name']}</td>
            <td style="padding:9px 10px;font-size:13px;">{e['engagement_name']}</td>
            <td style="padding:9px 10px;font-size:13px;">{e['activity_type'] or ''}</td>
            <td style="padding:9px 10px;font-size:13px;">{e['description']}</td>
            <td style="padding:9px 10px;font-size:13px;text-align:right;">{hours_fmt}</td>
            <td style="padding:9px 10px;font-size:13px;text-align:right;">{rate_fmt}</td>
            <td style="padding:9px 10px;font-size:13px;text-align:right;">{amount_fmt}</td>
        </tr>"""

    total_hours_fmt = f"{data['total_hours']:.2f}"
    total_amount_fmt = f"${data['total_amount']:,.2f}"
    date_range_display = date_range if date_range else "All dates"

    return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
    @page {{ size: Letter landscape; margin: 0.6in; }}
    body {{
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Helvetica, Arial, sans-serif;
        font-size: 13px;
        color: #111827;
        background: #ffffff;
        margin: 0;
        padding: 0;
    }}
</style>
</head>
<body>
    <div style="margin-bottom:28px;padding-bottom:18px;border-bottom:3px solid #111111;">
        {('<img src="' + data['logo_url'] + '" style="max-height:60px;'
        'width:auto;display:block;margin-bottom:4px;" />')
        if data.get('logo_url') else
        ('<div style="font-size:22px;font-weight:700;color:#111111;">'
        + data['firm_name'] + '</div>')}
        <div style="font-size:16px;font-weight:600;color:#111111;margin-top:4px;">Billing Detail</div>
        <div style="margin-top:10px;display:flex;gap:32px;">
            <div>
                <span style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Client</span>
                <div style="font-size:14px;font-weight:600;color:#111111;">{data['client_name']}</div>
            </div>
            <div>
                <span style="font-size:11px;color:#6b7280;text-transform:uppercase;letter-spacing:1px;">Period</span>
                <div style="font-size:14px;color:#374151;">{date_range_display}</div>
            </div>
        </div>
    </div>

    <table style="width:100%;border-collapse:collapse;">
        <thead>
            <tr style="background:#111111;color:#ffffff;">
                <th style="padding:10px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Date</th>
                <th style="padding:10px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Staff</th>
                <th style="padding:10px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Engagement</th>
                <th style="padding:10px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Activity</th>
                <th style="padding:10px;text-align:left;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Description</th>
                <th style="padding:10px;text-align:right;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Hours</th>
                <th style="padding:10px;text-align:right;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Rate</th>
                <th style="padding:10px;text-align:right;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:0.5px;">Amount</th>
            </tr>
        </thead>
        <tbody>
            {entry_rows}
        </tbody>
        <tfoot>
            <tr style="background:#f9fafb;border-top:2px solid #111111;">
                <td colspan="5" style="padding:10px;font-size:13px;font-weight:700;color:#111111;">Total</td>
                <td style="padding:10px;text-align:right;font-size:13px;font-weight:700;color:#111111;">{total_hours_fmt}</td>
                <td style="padding:10px;"></td>
                <td style="padding:10px;text-align:right;font-size:13px;font-weight:700;color:#111111;">{total_amount_fmt}</td>
            </tr>
        </tfoot>
    </table>
</body>
</html>"""


@router.get("/billing-detail")
def get_billing_detail(
    client_id: UUID,
    date_from: Optional[date] = None,
    date_to: Optional[date] = None,
    engagement_id: Optional[UUID] = None,
    format: str = Query("json"),
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    _: object = Depends(require_manager_or_above),
):
    client = db.execute(
        select(Client).where(Client.id == client_id, Client.firm_id == current_firm.id)
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    entries = _query_billing_detail_entries(
        db, current_firm.id, client_id, date_from, date_to, engagement_id
    )

    total_hours = round(sum(e["hours"] for e in entries), 2)
    total_amount = round(sum(e["amount"] for e in entries), 2)

    firm_settings = current_firm.settings or {}
    s3_key = firm_settings.get("portal_logo_s3_key")
    logo_url = None
    if s3_key:
        try:
            from app.services.s3 import generate_presigned_url
            logo_url = generate_presigned_url(s3_key)
        except Exception:
            pass

    data = {
        "client_name": client.name,
        "firm_name": current_firm.name,
        "logo_url": logo_url,
        "date_from": str(date_from) if date_from else None,
        "date_to": str(date_to) if date_to else None,
        "entries": entries,
        "total_hours": total_hours,
        "total_amount": total_amount,
    }

    if format == "pdf":
        from weasyprint import HTML  # lazy import — requires GTK system libraries at runtime
        html = _build_billing_detail_html(data)
        pdf_bytes = HTML(string=html).write_pdf()
        safe_name = client.name.replace(" ", "-").replace("/", "-")
        filename = f"billing-detail-{safe_name}.pdf"
        return StreamingResponse(
            io.BytesIO(pdf_bytes),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return data


class BillingDetailSendRequest(BaseModel):
    client_id: UUID
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    engagement_id: Optional[UUID] = None


@router.post("/billing-detail/send-to-portal")
def send_billing_detail_to_portal(
    body: BillingDetailSendRequest,
    db: Session = Depends(get_db),
    current_firm: Firm = Depends(get_current_firm),
    current_user: User = Depends(require_manager_or_above),
):
    from app.models.billing_detail_report import BillingDetailReport

    client = db.execute(
        select(Client).where(
            Client.id == body.client_id, Client.firm_id == current_firm.id
        )
    ).scalar_one_or_none()
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    entries = _query_billing_detail_entries(
        db, current_firm.id, body.client_id, body.date_from, body.date_to, body.engagement_id
    )

    total_hours = round(sum(e["hours"] for e in entries), 2)
    total_amount = round(sum(e["amount"] for e in entries), 2)

    report = BillingDetailReport(
        firm_id=current_firm.id,
        client_id=body.client_id,
        created_by=current_user.id,
        date_from=body.date_from,
        date_to=body.date_to,
        engagement_id=body.engagement_id,
        entries=entries,
        total_hours=total_hours,
        total_amount=total_amount,
    )
    db.add(report)
    db.commit()
    db.refresh(report)

    return {"id": str(report.id), "created_at": report.created_at.isoformat()}
