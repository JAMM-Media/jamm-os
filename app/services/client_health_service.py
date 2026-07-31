# app/services/client_health_service.py

from datetime import datetime, timezone, timedelta
from uuid import UUID

from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.client import Client
from app.models.invoice import Invoice
from app.models.document_request import DocumentRequest
from app.models.irs_authorization import IrsAuthorization
from app.models.engagement import Engagement
from app.core.enums import InvoiceStatus


def _ensure_tz(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def compute_client_health(client_id: UUID, firm_id: UUID, db: Session) -> dict:
    now = datetime.now(timezone.utc)
    today = now.date()

    client = db.execute(
        select(Client).where(Client.id == client_id, Client.firm_id == firm_id)
    ).scalar_one_or_none()

    if client is None:
        return {"status": "healthy", "reasons": []}

    active_engagements = db.execute(
        select(Engagement).where(
            Engagement.client_id == client_id,
            Engagement.firm_id == firm_id,
            Engagement.status.notin_(["completed", "archived"]),
            (Engagement.extended_deadline.isnot(None) | Engagement.filing_deadline.isnot(None)),
        )
    ).scalars().all()

    invoices = db.execute(
        select(Invoice).where(
            Invoice.client_id == client_id,
            Invoice.firm_id == firm_id,
            Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.overdue]),
            Invoice.is_deleted == False,
        )
    ).scalars().all()

    doc_requests = db.execute(
        select(DocumentRequest).where(
            DocumentRequest.client_id == client_id,
            DocumentRequest.firm_id == firm_id,
            DocumentRequest.status != "completed",
        )
    ).scalars().all()

    irs_auths = db.execute(
        select(IrsAuthorization).where(
            IrsAuthorization.client_id == client_id,
            IrsAuthorization.firm_id == firm_id,
        )
    ).scalars().all()

    def effective_deadline(eng):
        return eng.extended_deadline or eng.filing_deadline

    # --- AT RISK ---
    at_risk_reasons = []

    overdue_engs = [
        eng for eng in active_engagements
        if effective_deadline(eng) is not None and effective_deadline(eng) < today
    ]
    for eng in overdue_engs:
        deadline = effective_deadline(eng)
        days_past = (today - deadline).days
        at_risk_reasons.append({
            "severity": "at_risk",
            "text": f"{eng.name}: {days_past} day{'s' if days_past != 1 else ''} past deadline"
        })

    urgent_engs = [
        eng for eng in active_engagements
        if effective_deadline(eng) is not None
        and today <= effective_deadline(eng) <= today + timedelta(days=3)
    ]
    for eng in urgent_engs:
        deadline = effective_deadline(eng)
        days_left = (deadline - today).days
        at_risk_reasons.append({
            "severity": "at_risk",
            "text": f"{eng.name}: due in {days_left} day{'s' if days_left != 1 else ''}"
        })

    overdue_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.overdue]
    for inv in overdue_invoices:
        amount_str = f"${inv.total_amount:,.0f}" if inv.total_amount else "Invoice"
        at_risk_reasons.append({
            "severity": "at_risk",
            "text": f"{amount_str} invoice overdue"
        })

    # --- NEEDS ATTENTION ---
    needs_attention_reasons = []

    approaching_engs = [
        eng for eng in active_engagements
        if effective_deadline(eng) is not None
        and today + timedelta(days=3) < effective_deadline(eng) <= today + timedelta(days=14)
    ]
    for eng in approaching_engs:
        deadline = effective_deadline(eng)
        days_left = (deadline - today).days
        needs_attention_reasons.append({
            "severity": "needs_attention",
            "text": f"{eng.name}: due in {days_left} day{'s' if days_left != 1 else ''}"
        })

    for inv in invoices:
        if inv.status == InvoiceStatus.sent:
            ref_date = inv.sent_at or inv.created_at
            if ref_date is not None and (now - _ensure_tz(ref_date)).days >= 14:
                needs_attention_reasons.append({
                    "severity": "needs_attention",
                    "text": "Unpaid invoice older than 14 days"
                })
                break

    stale_doc_requests = [
        req for req in doc_requests
        if (now - _ensure_tz(req.created_at)).days >= 7
    ]
    for req in stale_doc_requests:
        days_open = (now - _ensure_tz(req.created_at)).days
        needs_attention_reasons.append({
            "severity": "needs_attention",
            "text": f"Document request open {days_open} days"
        })

    cutoff = today + timedelta(days=60)
    for auth in irs_auths:
        if auth.valid_until is not None and auth.valid_until < cutoff:
            form = f"Form {auth.form_type}" if auth.form_type else "IRS authorization"
            days_left = (auth.valid_until - today).days
            needs_attention_reasons.append({
                "severity": "needs_attention",
                "text": f"{form} expiring in {days_left} day{'s' if days_left != 1 else ''}"
            })

    if not active_engagements:
        any_engagement = db.execute(
            select(Engagement)
            .where(
                Engagement.client_id == client_id,
                Engagement.firm_id == firm_id,
            )
            .order_by(Engagement.updated_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        if any_engagement is not None:
            if (now - _ensure_tz(any_engagement.updated_at)).days >= 30:
                needs_attention_reasons.append({
                    "severity": "needs_attention",
                    "text": "No engagement activity in 30+ days"
                })

    if at_risk_reasons:
        return {"status": "at_risk", "reasons": at_risk_reasons + needs_attention_reasons}
    elif needs_attention_reasons:
        return {"status": "needs_attention", "reasons": needs_attention_reasons}
    else:
        return {"status": "healthy", "reasons": [{"severity": "healthy", "text": "Everything is on track"}]}
