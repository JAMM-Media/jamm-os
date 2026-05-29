# STANDING RULES — READ BEFORE EVERY TASK
- Backend: FastAPI, PostgreSQL, SQLAlchemy 2.0 (Mapped[] syntax), Pydantic v2
- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui
- Every router is thin — no business logic in routers, ever
- Tenant isolation: every query scoped to firm_id without exception
- Never use && chaining in PowerShell — use separate commands
- All new files start with a path comment

---

# TASK: Rewrite app/services/client_health_service.py cleanly

## What happened
The file was corrupted by failed sed commands on the server.
It now has a broken `if client is None` block and duplicate return
statements at the bottom. This task replaces the entire file with
the correct version.

## Instruction
Replace the entire contents of `app/services/client_health_service.py`
with exactly the following. Do not modify any logic — this is a
clean rewrite of what was already built:

```python
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
    if overdue_engs:
        count = len(overdue_engs)
        at_risk_reasons.append(
            f"{count} engagement{'s' if count > 1 else ''} past deadline"
        )

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

    overdue_invoices = [inv for inv in invoices if inv.status == InvoiceStatus.overdue]
    if overdue_invoices:
        count = len(overdue_invoices)
        at_risk_reasons.append(
            f"{count} overdue invoice{'s' if count > 1 else ''}"
        )

    # --- NEEDS ATTENTION ---
    needs_attention_reasons = []

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

    for inv in invoices:
        if inv.status == InvoiceStatus.sent:
            ref_date = inv.sent_at or inv.created_at
            if ref_date is not None and (now - _ensure_tz(ref_date)).days >= 14:
                needs_attention_reasons.append("Unpaid invoice older than 14 days")
                break

    stale_doc_requests = [
        req for req in doc_requests
        if (now - _ensure_tz(req.created_at)).days >= 7
    ]
    if stale_doc_requests:
        count = len(stale_doc_requests)
        needs_attention_reasons.append(
            f"{count} document request{'s' if count > 1 else ''} open 7+ days"
        )

    cutoff = today + timedelta(days=60)
    irs_expiring = any(
        auth.status == "expiring_soon"
        or (auth.valid_until is not None and auth.valid_until < cutoff)
        for auth in irs_auths
    )
    if irs_expiring:
        needs_attention_reasons.append("IRS authorization expiring within 60 days")

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
```

## Verification
After writing the file, run:
`python -c "import ast; ast.parse(open('app/services/client_health_service.py').read()); print('Syntax OK')"`

If it prints Syntax OK, the file is clean. If it raises a SyntaxError,
read the error and fix it before finishing.

## Files to modify
- app/services/client_health_service.py — full rewrite