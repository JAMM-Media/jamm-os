# app/services/financial_intelligence_service.py

import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_, case

from app.models.user import User
from app.models.time_entry import TimeEntry
from app.models.invoice import Invoice
from app.models.engagement import Engagement
from app.models.client import Client
from app.core.enums import InvoiceStatus


def get_realization_rate(db: Session, firm_id: uuid.UUID) -> dict:
    firm_row = db.execute(
        select(
            func.coalesce(
                func.sum(case((TimeEntry.is_billable == True, TimeEntry.hours), else_=0)),
                0,
            ).label("total_billable"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(TimeEntry.is_billable == True, TimeEntry.is_billed == True),
                            TimeEntry.hours,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("total_billed"),
        ).where(TimeEntry.firm_id == firm_id)
    ).first()

    total_billable = float(firm_row.total_billable)
    total_billed = float(firm_row.total_billed)
    firm_rate = round(total_billed / total_billable * 100, 1) if total_billable > 0 else 0.0

    staff_rows = db.execute(
        select(
            TimeEntry.user_id,
            User.full_name,
            func.coalesce(
                func.sum(case((TimeEntry.is_billable == True, TimeEntry.hours), else_=0)),
                0,
            ).label("billable_hours"),
            func.coalesce(
                func.sum(
                    case(
                        (
                            and_(TimeEntry.is_billable == True, TimeEntry.is_billed == True),
                            TimeEntry.hours,
                        ),
                        else_=0,
                    )
                ),
                0,
            ).label("billed_hours"),
        )
        .join(User, TimeEntry.user_id == User.id)
        .where(TimeEntry.firm_id == firm_id)
        .group_by(TimeEntry.user_id, User.full_name)
    ).all()

    by_staff = []
    for row in staff_rows:
        billable = float(row.billable_hours)
        billed = float(row.billed_hours)
        rate = round(billed / billable * 100, 1) if billable > 0 else 0.0
        by_staff.append({
            "user_id": str(row.user_id),
            "full_name": row.full_name,
            "billable_hours": billable,
            "billed_hours": billed,
            "realization_rate": rate,
        })

    return {
        "firm_realization_rate": firm_rate,
        "total_billable_hours": total_billable,
        "total_billed_hours": total_billed,
        "by_staff": by_staff,
    }


def get_effective_hourly_rate(db: Session, firm_id: uuid.UUID) -> dict:
    revenue_rows = db.execute(
        select(
            Engagement.engagement_type,
            func.sum(Invoice.total_amount).label("total_revenue"),
        )
        .join(Invoice, Invoice.engagement_id == Engagement.id)
        .where(
            Engagement.firm_id == firm_id,
            Invoice.firm_id == firm_id,
            Invoice.status == InvoiceStatus.paid,
            Invoice.is_deleted == False,
            Invoice.engagement_id.isnot(None),
            Engagement.engagement_type.isnot(None),
        )
        .group_by(Engagement.engagement_type)
    ).all()

    hours_rows = db.execute(
        select(
            Engagement.engagement_type,
            func.sum(TimeEntry.hours).label("total_hours"),
        )
        .join(TimeEntry, TimeEntry.engagement_id == Engagement.id)
        .where(
            Engagement.firm_id == firm_id,
            TimeEntry.firm_id == firm_id,
            Engagement.engagement_type.isnot(None),
        )
        .group_by(Engagement.engagement_type)
    ).all()

    revenue_map = {row.engagement_type: float(row.total_revenue) for row in revenue_rows}
    hours_map = {row.engagement_type: float(row.total_hours) for row in hours_rows}

    all_types = set(revenue_map) | set(hours_map)
    by_type = []
    total_revenue = 0.0
    total_hours = 0.0

    for eng_type in sorted(all_types):
        rev = revenue_map.get(eng_type, 0.0)
        hrs = hours_map.get(eng_type, 0.0)
        if hrs == 0:
            continue
        rate = round(rev / hrs, 2)
        total_revenue += rev
        total_hours += hrs
        by_type.append({
            "engagement_type": eng_type,
            "total_revenue": rev,
            "total_hours": hrs,
            "effective_rate": rate,
        })

    firm_rate = round(total_revenue / total_hours, 2) if total_hours > 0 else 0.0

    return {
        "firm_effective_rate": firm_rate,
        "by_engagement_type": by_type,
    }


def get_gross_margin(db: Session, firm_id: uuid.UUID) -> dict:
    has_cost_rates = (
        db.execute(
            select(func.count(User.id)).where(
                User.firm_id == firm_id,
                User.cost_rate.isnot(None),
            )
        ).scalar()
        or 0
    ) > 0

    empty = {
        "cost_rates_configured": False,
        "by_engagement": [],
        "by_client": [],
        "by_staff": [],
        "by_service_type": [],
    }
    if not has_cost_rates:
        return empty

    # Revenue per engagement from paid invoices
    eng_revenue_rows = db.execute(
        select(
            Engagement.id.label("engagement_id"),
            Engagement.name.label("engagement_name"),
            Engagement.client_id,
            Engagement.engagement_type,
            func.sum(Invoice.total_amount).label("revenue"),
        )
        .join(Invoice, Invoice.engagement_id == Engagement.id)
        .where(
            Engagement.firm_id == firm_id,
            Invoice.firm_id == firm_id,
            Invoice.status == InvoiceStatus.paid,
            Invoice.is_deleted == False,
            Invoice.engagement_id.isnot(None),
        )
        .group_by(
            Engagement.id,
            Engagement.name,
            Engagement.client_id,
            Engagement.engagement_type,
        )
    ).all()

    # Cost per engagement from time entries with cost_rate set
    eng_cost_rows = db.execute(
        select(
            TimeEntry.engagement_id,
            func.sum(TimeEntry.hours * User.cost_rate).label("cost"),
        )
        .join(User, TimeEntry.user_id == User.id)
        .where(
            TimeEntry.firm_id == firm_id,
            User.cost_rate.isnot(None),
        )
        .group_by(TimeEntry.engagement_id)
    ).all()

    cost_by_eng = {str(row.engagement_id): float(row.cost) for row in eng_cost_rows}

    # Client names
    client_ids = {row.client_id for row in eng_revenue_rows}
    if client_ids:
        client_rows = db.execute(
            select(Client.id, Client.name).where(
                Client.firm_id == firm_id,
                Client.id.in_(client_ids),
            )
        ).all()
        client_names = {row.id: row.name for row in client_rows}
    else:
        client_names = {}

    by_engagement = []
    client_agg: dict = {}
    service_agg: dict = {}

    for row in eng_revenue_rows:
        eng_id = str(row.engagement_id)
        revenue = float(row.revenue)
        cost = cost_by_eng.get(eng_id, 0.0)
        margin = revenue - cost
        margin_pct = round(margin / revenue * 100, 2) if revenue > 0 else 0.0
        by_engagement.append({
            "engagement_id": eng_id,
            "engagement_title": row.engagement_name,
            "client_id": str(row.client_id),
            "revenue": revenue,
            "cost": cost,
            "gross_margin": margin,
            "gross_margin_pct": margin_pct,
        })

        cid = str(row.client_id)
        if cid not in client_agg:
            client_agg[cid] = {"revenue": 0.0, "cost": 0.0}
        client_agg[cid]["revenue"] += revenue
        client_agg[cid]["cost"] += cost

        if row.engagement_type:
            if row.engagement_type not in service_agg:
                service_agg[row.engagement_type] = {"revenue": 0.0, "cost": 0.0}
            service_agg[row.engagement_type]["revenue"] += revenue
            service_agg[row.engagement_type]["cost"] += cost

    by_client = []
    for cid, vals in client_agg.items():
        rev = vals["revenue"]
        cst = vals["cost"]
        mgn = rev - cst
        by_client.append({
            "client_id": cid,
            "client_name": client_names.get(uuid.UUID(cid)),
            "revenue": rev,
            "cost": cst,
            "gross_margin": mgn,
            "gross_margin_pct": round(mgn / rev * 100, 2) if rev > 0 else 0.0,
        })

    # Per staff: revenue from time entries on paid invoices (hours * hourly_rate), cost from cost_rate
    staff_rows = db.execute(
        select(
            TimeEntry.user_id,
            User.full_name,
            func.sum(TimeEntry.hours * TimeEntry.hourly_rate).label("revenue"),
            func.sum(TimeEntry.hours * User.cost_rate).label("cost"),
        )
        .join(User, TimeEntry.user_id == User.id)
        .join(Invoice, TimeEntry.invoice_id == Invoice.id)
        .where(
            TimeEntry.firm_id == firm_id,
            Invoice.status == InvoiceStatus.paid,
            Invoice.is_deleted == False,
            User.cost_rate.isnot(None),
        )
        .group_by(TimeEntry.user_id, User.full_name)
    ).all()

    by_staff = []
    for row in staff_rows:
        rev = float(row.revenue or 0)
        cst = float(row.cost or 0)
        mgn = rev - cst
        by_staff.append({
            "user_id": str(row.user_id),
            "full_name": row.full_name,
            "revenue": rev,
            "cost": cst,
            "gross_margin": mgn,
            "gross_margin_pct": round(mgn / rev * 100, 2) if rev > 0 else 0.0,
        })

    by_service_type = []
    for stype, vals in sorted(service_agg.items()):
        rev = vals["revenue"]
        cst = vals["cost"]
        mgn = rev - cst
        by_service_type.append({
            "engagement_type": stype,
            "revenue": rev,
            "cost": cst,
            "gross_margin": mgn,
            "gross_margin_pct": round(mgn / rev * 100, 2) if rev > 0 else 0.0,
        })

    return {
        "cost_rates_configured": True,
        "by_engagement": by_engagement,
        "by_client": by_client,
        "by_staff": by_staff,
        "by_service_type": by_service_type,
    }


def get_pricing_drift(db: Session, firm_id: uuid.UUID) -> dict:
    now = datetime.now(timezone.utc)
    twelve_months_ago = now - timedelta(days=365)
    twenty_four_months_ago = now - timedelta(days=730)

    firm_recent = db.execute(
        select(func.avg(TimeEntry.hourly_rate)).where(
            TimeEntry.firm_id == firm_id,
            TimeEntry.created_at >= twelve_months_ago,
        )
    ).scalar()

    firm_prior = db.execute(
        select(func.avg(TimeEntry.hourly_rate)).where(
            TimeEntry.firm_id == firm_id,
            TimeEntry.created_at >= twenty_four_months_ago,
            TimeEntry.created_at < twelve_months_ago,
        )
    ).scalar()

    if firm_recent is None and firm_prior is None:
        return {
            "firm_pricing_stagnant": False,
            "last_12_months_avg_rate": 0.0,
            "prior_12_months_avg_rate": 0.0,
            "rate_change_pct": 0.0,
            "by_engagement_type": [],
        }

    firm_recent_f = float(firm_recent or 0)
    firm_prior_f = float(firm_prior or 0)
    if firm_prior_f > 0:
        firm_change_pct = round((firm_recent_f - firm_prior_f) / firm_prior_f * 100, 2)
    else:
        firm_change_pct = 0.0
    firm_stagnant = abs(firm_change_pct) < 5.0

    recent_rows = db.execute(
        select(
            Engagement.engagement_type,
            func.avg(TimeEntry.hourly_rate).label("avg_rate"),
        )
        .join(Engagement, TimeEntry.engagement_id == Engagement.id)
        .where(
            TimeEntry.firm_id == firm_id,
            TimeEntry.created_at >= twelve_months_ago,
            Engagement.engagement_type.isnot(None),
        )
        .group_by(Engagement.engagement_type)
    ).all()

    prior_rows = db.execute(
        select(
            Engagement.engagement_type,
            func.avg(TimeEntry.hourly_rate).label("avg_rate"),
        )
        .join(Engagement, TimeEntry.engagement_id == Engagement.id)
        .where(
            TimeEntry.firm_id == firm_id,
            TimeEntry.created_at >= twenty_four_months_ago,
            TimeEntry.created_at < twelve_months_ago,
            Engagement.engagement_type.isnot(None),
        )
        .group_by(Engagement.engagement_type)
    ).all()

    recent_map = {row.engagement_type: float(row.avg_rate) for row in recent_rows}
    prior_map = {row.engagement_type: float(row.avg_rate) for row in prior_rows}

    by_type = []
    for eng_type in sorted(set(recent_map) & set(prior_map)):
        rec = recent_map[eng_type]
        pri = prior_map[eng_type]
        if pri > 0:
            change_pct = round((rec - pri) / pri * 100, 2)
        else:
            change_pct = 0.0
        by_type.append({
            "engagement_type": eng_type,
            "last_12_months_avg_rate": rec,
            "prior_12_months_avg_rate": pri,
            "rate_change_pct": change_pct,
            "stagnant": abs(change_pct) < 5.0,
        })

    return {
        "firm_pricing_stagnant": firm_stagnant,
        "last_12_months_avg_rate": firm_recent_f,
        "prior_12_months_avg_rate": firm_prior_f,
        "rate_change_pct": firm_change_pct,
        "by_engagement_type": by_type,
    }
