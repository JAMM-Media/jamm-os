# STANDING RULES — READ BEFORE EVERY TASK
- Backend: FastAPI, PostgreSQL, SQLAlchemy 2.0 (Mapped[] syntax), Pydantic v2
- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui
- Every router is thin — no business logic in routers, ever
- Tenant isolation: every query scoped to firm_id without exception
- Never use && chaining in PowerShell — use separate commands
- All new files start with a path comment

---

# TASK: Rebuild four features lost in forced push

Four independent changes. All files are different. Claude Code can
make all four in sequence without any conflicts.

---

## CHANGE 1 — Backend: Add quickbooks_customer_id to ClientOut schema
File: `app/schemas/client.py`

In the `ClientOut` class, add one field:
```python
quickbooks_customer_id: Optional[str] = None
```

Add it directly to `ClientOut` (not `ClientBase`). The field already
exists on the Client model. No migration needed.

Also find `ClientHealthOut` class and change:
```python
reasons: list[str]
```
to:
```python
reasons: list[dict]
```

---

## CHANGE 2 — Backend: Rewrite client_health_service.py completely

File: `app/services/client_health_service.py`

Replace the entire file contents with exactly this:

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
        if auth.status == "expiring_soon" or (
            auth.valid_until is not None and auth.valid_until < cutoff
        ):
            form = f"Form {auth.form_type}" if auth.form_type else "IRS authorization"
            if auth.valid_until is not None:
                days_left = (auth.valid_until - today).days
                needs_attention_reasons.append({
                    "severity": "needs_attention",
                    "text": f"{form} expiring in {days_left} day{'s' if days_left != 1 else ''}"
                })
            else:
                needs_attention_reasons.append({
                    "severity": "needs_attention",
                    "text": f"{form} expiring soon"
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
```

After writing the file run:
`python -c "import ast; ast.parse(open('app/services/client_health_service.py').read()); print('Syntax OK')"`

If it does not print Syntax OK, fix before continuing.

---

## CHANGE 3 — Frontend: clients.ts — three additions

File: `frontend/src/lib/api/clients.ts`

**3a.** In the `Client` interface, add:
```typescript
quickbooksCustomerId: string | null
```

**3b.** In the `mapClient` function, add:
```typescript
quickbooksCustomerId: raw.quickbooks_customer_id ? String(raw.quickbooks_customer_id) : null,
```

**3c.** Add two new interfaces (place them near the existing
`ClientHealth` interface):
```typescript
export interface HealthReason {
  severity: 'at_risk' | 'needs_attention' | 'healthy'
  text: string
}

export interface ClientHealth {
  status: string
  reasons: HealthReason[]
}
```

If `ClientHealth` already exists with `reasons: string[]`, replace
it with the version above. If it doesn't exist, add both interfaces.

---

## CHANGE 4 — Frontend: Rewrite HealthDot.tsx completely

File: `frontend/src/components/clients/HealthDot.tsx`

Replace the entire file contents with exactly this:

```tsx
// frontend/src/components/clients/HealthDot.tsx
'use client'

import { useQuery } from '@tanstack/react-query'
import { clientsApi } from '@/lib/api/clients'
import type { ClientHealth } from '@/lib/api/clients'
import {
  Tooltip,
  TooltipTrigger,
  TooltipContent,
  TooltipProvider,
} from '@/components/ui/tooltip'

const SEVERITY_COLOR: Record<string, string> = {
  at_risk: '#E24B4A',
  needs_attention: '#F59E0B',
  healthy: '#10B981',
}

const STATUS_CONFIG = {
  healthy: { color: '#10B981', label: 'Healthy' },
  needs_attention: { color: '#F59E0B', label: 'Needs Attention' },
  at_risk: { color: '#E24B4A', label: 'At Risk' },
} as const

interface HealthDotProps {
  clientId: string
  showLabel?: boolean
}

export function HealthDot({ clientId, showLabel = false }: HealthDotProps) {
  const { data, isLoading, isError } = useQuery<ClientHealth>({
    queryKey: ['client-health', clientId],
    queryFn: () => clientsApi.getHealth(clientId),
    staleTime: 10 * 60 * 1000,
    refetchOnWindowFocus: false,
  })

  if (isError) return null

  const config = data
    ? STATUS_CONFIG[data.status as keyof typeof STATUS_CONFIG] ?? null
    : null
  const color = isLoading || !config ? '#C8CDD6' : config.color

  const hasReasons = data && data.reasons.length > 0

  const dot = (
    <span
      style={{
        display: 'inline-block',
        width: 8,
        height: 8,
        borderRadius: '50%',
        backgroundColor: color,
        flexShrink: 0,
      }}
    />
  )

  if (!hasReasons) {
    if (showLabel) {
      return (
        <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: isLoading || !config ? '#C8CDD6' : config.color }}>
          {dot}
          {!isLoading && config && config.label}
        </span>
      )
    }
    return (
      <span style={{ display: 'inline-flex', alignItems: 'center' }}>
        {dot}
      </span>
    )
  }

  return (
    <TooltipProvider>
      <Tooltip>
        <TooltipTrigger>
          {showLabel ? (
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 6, fontSize: 12, color: isLoading || !config ? '#C8CDD6' : config.color, cursor: 'default' }}>
              {dot}
              {!isLoading && config && config.label}
            </span>
          ) : (
            <span style={{ display: 'inline-flex', alignItems: 'center' }}>
              {dot}
            </span>
          )}
        </TooltipTrigger>
        <TooltipContent side="right" className="max-w-[240px]">
          <div className="flex flex-col gap-1">
            {data.reasons.map((reason, i) => (
              <div key={i} className="flex items-start gap-1.5">
                <span
                  style={{
                    width: 6,
                    height: 6,
                    borderRadius: '50%',
                    backgroundColor: SEVERITY_COLOR[reason.severity] ?? color,
                    flexShrink: 0,
                    marginTop: 4,
                  }}
                />
                <span className="text-[11px] leading-tight">{reason.text}</span>
              </div>
            ))}
          </div>
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  )
}
```

---

## CHANGE 5 — Frontend: Add QBO deep link to client detail page

File: `frontend/src/app/(dashboard)/clients/[id]/page.tsx`

Find the QBO AR Balance card section. It contains a connected state
block with an outstanding balance paragraph and a last payment date
paragraph inside a `space-y-1` div.

Add this anchor link after the last payment date paragraph, still
inside the same `space-y-1` div:

```tsx
{client.quickbooksCustomerId && (
  <a
    href={`https://app.qbo.intuit.com/app/customerdetail?nameId=${client.quickbooksCustomerId}`}
    target="_blank"
    rel="noopener noreferrer"
    className="text-[11px] text-brand-light dark:text-brand-light hover:underline inline-flex items-center gap-1 mt-1"
  >
    Open in QuickBooks
    <svg width="10" height="10" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M2 10L10 2M10 2H5M10 2V7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  </a>
)}
```

---

## Verification

After all five changes run:
`python -c "import ast; ast.parse(open('app/services/client_health_service.py').read()); print('Syntax OK')"`

Confirm Syntax OK before finishing.

---

## Files modified
- app/schemas/client.py — quickbooks_customer_id on ClientOut, list[dict] on ClientHealthOut
- app/services/client_health_service.py — full rewrite with structured reasons
- frontend/src/lib/api/clients.ts — quickbooksCustomerId field, HealthReason interface
- frontend/src/components/clients/HealthDot.tsx — full rewrite with per-severity colors
- frontend/src/app/(dashboard)/clients/[id]/page.tsx — QBO deep link anchor