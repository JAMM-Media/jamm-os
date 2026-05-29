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

    def effective_deadline(eng):
        return eng.extended_deadline or eng.filing_deadline

    # --- AT RISK ---
    at_risk_reasons = []

    # 1. Any active engagement with deadline already passed
    overdue_engs = [
        eng for eng in active_engagements
        if effective_deadline(eng) is not None and effective_deadline(eng) < today
    ]
    if overdue_engs:
        count = len(overdue_engs)
        at_risk_reasons.append(
            f"{count} engagement{'s' if count > 1 else ''} past deadline"
        )

    # 2. Any active engagement with deadline within 3 days
    urgent_engs = [
        eng for eng in active_engagements
        if effective_deadline(eng) is not None
        and today <= effective_deadline(eng) <= today + timedelta(days=3)
    ]
    if urgent_engs:
        count = len(urgent_engs)
        at_risk_reasons.append(
            f"{count} engagement{'s' if count > 1 else ''} due within 3 days"
        )

    # 3. Any overdue invoice (no longer requires stale portal login)
    overdue_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.overdue]
    if overdue_invoices:
        count = len(overdue_invoices)
        at_risk_reasons.append(
            f"{count} overdue invoice{'s' if count > 1 else ''}"
        )

    # --- NEEDS ATTENTION ---
    needs_attention_reasons = []

    # 1. Any active engagement with deadline within 14 days (but not within 3 — already caught above)
    approaching_engs = [
        eng for eng in active_engagements
        if effective_deadline(eng) is not None
        and today + timedelta(days=3) < effective_deadline(eng) <= today + timedelta(days=14)
    ]
    if approaching_engs:
        count = len(approaching_engs)
        needs_attention_reasons.append(
            f"{count} engagement{'s' if count > 1 else ''} due within 14 days"
        )

    # 2. Unpaid invoice sent 14+ days ago
    for inv in invoices:
        if inv.status == InvoiceStatus.sent:
            ref_date = inv.sent_at or inv.created_at
            if ref_date is not None and (now - _ensure_tz(ref_date)).days >= 14:
                needs_attention_reasons.append("Unpaid invoice older than 14 days")
                break

    # 3. Open document request older than 7 days
    stale_doc_requests = [
        req for req in doc_requests
        if (now - _ensure_tz(req.created_at)).days >= 7
    ]
    if stale_doc_requests:
        count = len(stale_doc_requests)
        needs_attention_reasons.append(
            f"{count} document request{'s' if count > 1 else ''} open 7+ days"
        )

    # 4. IRS authorization expiring within 60 days
    cutoff = today + timedelta(days=60)
    irs_expiring = any(
        auth.status == "expiring_soon"
        or (auth.valid_until is not None and auth.valid_until < cutoff)
        for auth in irs_auths
    )
    if irs_expiring:
        needs_attention_reasons.append("IRS authorization expiring within 60 days")

    # 5. No active engagements with deadlines AND no engagement activity in 30+ days
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
                needs_attention_reasons.append("No engagement activity in 30+ days")

    if at_risk_reasons:
        return {"status": "at_risk", "reasons": at_risk_reasons + needs_attention_reasons}
    elif needs_attention_reasons:
        return {"status": "needs_attention", "reasons": needs_attention_reasons}
    else:
        return {"status": "healthy", "reasons": ["Everything is on track"]}
