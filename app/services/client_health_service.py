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

    invoices = db.execute(
        select(Invoice).where(
            Invoice.client_id == client_id,
            Invoice.firm_id == firm_id,
            Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.overdue]),
            Invoice.is_deleted == False,  # noqa: E712
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

    recent_engagement = db.execute(
        select(Engagement)
        .where(
            Engagement.client_id == client_id,
            Engagement.firm_id == firm_id,
        )
        .order_by(Engagement.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    # --- AT RISK ---
    at_risk_reasons = []

    has_overdue = any(inv.status == InvoiceStatus.overdue for inv in invoices)
    if has_overdue:
        portal_login = client.portal_last_login_at
        login_stale = portal_login is None or (now - _ensure_tz(portal_login)).days > 30
        if login_stale:
            at_risk_reasons.append("Overdue invoice")

    if any(auth.status == "expired" for auth in irs_auths):
        at_risk_reasons.append("Expired IRS authorization")

    if at_risk_reasons:
        return {"status": "at_risk", "reasons": at_risk_reasons}

    # --- NEEDS ATTENTION ---
    needs_attention_reasons = []

    for inv in invoices:
        if inv.status == InvoiceStatus.sent:
            ref_date = inv.sent_at or inv.created_at
            if ref_date is not None and (now - _ensure_tz(ref_date)).days >= 14:
                needs_attention_reasons.append("Unpaid invoice older than 14 days")
                break

    for req in doc_requests:
        if (now - _ensure_tz(req.created_at)).days >= 7:
            needs_attention_reasons.append("Open document request older than 7 days")
            break

    cutoff = today + timedelta(days=60)
    irs_expiring = any(
        auth.status == "expiring_soon"
        or (auth.valid_until is not None and auth.valid_until < cutoff)
        for auth in irs_auths
    )
    if irs_expiring:
        needs_attention_reasons.append("IRS authorization expiring within 60 days")

    if recent_engagement is not None:
        if (now - _ensure_tz(recent_engagement.updated_at)).days >= 30:
            needs_attention_reasons.append("No engagement activity in 30+ days")

    if needs_attention_reasons:
        return {"status": "needs_attention", "reasons": needs_attention_reasons}

    return {"status": "healthy", "reasons": []}
