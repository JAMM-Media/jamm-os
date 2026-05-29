# STANDING RULES — READ BEFORE EVERY TASK
- Backend: FastAPI, PostgreSQL, SQLAlchemy 2.0 (Mapped[] syntax), Pydantic v2
- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui
- Every router is thin — no business logic in routers, ever
- Tenant isolation: every query scoped to firm_id without exception
- Never use && chaining in PowerShell — use separate commands
- All new files start with a path comment

---

# TASK: Structured health reasons with per-reason severity colors

## What this does
Two changes working together:

1. Backend — change the health API response so each reason is a structured
   object with a severity tag ("at_risk" or "needs_attention") and specific
   text that names the exact engagement, invoice amount, or auth form.

2. Frontend — update the HealthDot tooltip to render each reason with its
   own colored dot matching that reason's severity, not the overall status.

The initial dot color stays driven by the worst severity (red if anything
is at_risk, amber if only needs_attention). The tooltip shows every reason
with individual dot colors — red bullets for at_risk items, amber bullets
for needs_attention items.

---

## Step 1 — Backend: app/services/client_health_service.py

Change the reasons list from plain strings to structured dicts.
Each reason is: {"severity": "at_risk" | "needs_attention", "text": "..."}

The text should be as specific as possible using the data already available.

### AT RISK reason text formats

Overdue engagements — use eng.name and days past deadline:
```python
deadline = effective_deadline(eng)
days_past = (today - deadline).days
at_risk_reasons.append({
    "severity": "at_risk",
    "text": f"{eng.name}: {days_past} day{'s' if days_past != 1 else ''} past deadline"
})
```
Do this per engagement in a loop — one reason per engagement, not a count.

Urgent engagements (due within 3 days) — use eng.name and days remaining:
```python
deadline = effective_deadline(eng)
days_left = (deadline - today).days
at_risk_reasons.append({
    "severity": "at_risk",
    "text": f"{eng.name}: due in {days_left} day{'s' if days_left != 1 else ''}"
})
```
Do this per engagement in a loop.

Overdue invoices — include amount if available:
```python
for inv in overdue_invoices:
    amount_str = f"${inv.total_amount:,.0f}" if inv.total_amount else "Invoice"
    at_risk_reasons.append({
        "severity": "at_risk",
        "text": f"{amount_str} invoice overdue"
    })
```

### NEEDS ATTENTION reason text formats

Approaching engagements (4-14 days):
```python
for eng in approaching_engs:
    deadline = effective_deadline(eng)
    days_left = (deadline - today).days
    needs_attention_reasons.append({
        "severity": "needs_attention",
        "text": f"{eng.name}: due in {days_left} day{'s' if days_left != 1 else ''}"
    })
```
Do this per engagement in a loop.

Unpaid invoice (unchanged trigger logic, new text):
```python
needs_attention_reasons.append({
    "severity": "needs_attention",
    "text": "Unpaid invoice older than 14 days"
})
```

Stale document requests — per request:
```python
for req in stale_doc_requests:
    days_open = (now - _ensure_tz(req.created_at)).days
    needs_attention_reasons.append({
        "severity": "needs_attention",
        "text": f"Document request open {days_open} days"
    })
```

IRS authorization expiring — include days until expiry:
```python
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
```
Replace the current `irs_expiring = any(...)` block with this loop.
Remove the `if irs_expiring:` block that follows it.

No engagement activity:
```python
needs_attention_reasons.append({
    "severity": "needs_attention",
    "text": "No engagement activity in 30+ days"
})
```

### Final return block — unchanged structure, reasons are now dicts
```python
if at_risk_reasons:
    return {"status": "at_risk", "reasons": at_risk_reasons + needs_attention_reasons}
elif needs_attention_reasons:
    return {"status": "needs_attention", "reasons": needs_attention_reasons}
else:
    return {"status": "healthy", "reasons": [{"severity": "healthy", "text": "Everything is on track"}]}
```

---

## Step 2 — Frontend: frontend/src/lib/api/clients.ts

Update the ClientHealth interface. The reasons array now contains objects:

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

---

## Step 3 — Frontend: frontend/src/components/clients/HealthDot.tsx

Update the tooltip to render each reason with its own severity-colored dot.

Add a severity color map at the top of the file:
```typescript
const SEVERITY_COLOR: Record<string, string> = {
  at_risk: '#E24B4A',
  needs_attention: '#F59E0B',
  healthy: '#10B981',
}
```

Update the tooltip content section. Replace the current reasons.map block with:
```tsx
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
```

Update the hasReasons check — reasons are now objects not strings:
```typescript
const hasReasons = data && data.reasons.length > 0 &&
  !(data.reasons.length === 1 && data.reasons[0].severity === 'healthy')
```

---

## Verification

After changes, hit GET /clients/{id}/health and confirm the response looks like:
```json
{
  "status": "at_risk",
  "reasons": [
    {"severity": "at_risk", "text": "2024 Tax Return — 1040: 12 days past deadline"},
    {"severity": "needs_attention", "text": "IRS authorization expiring in 43 days"}
  ]
}
```

Then check the frontend tooltip shows a red dot next to the first reason
and an amber dot next to the second.

---

## Files to modify
- app/services/client_health_service.py — structured reasons with severity tags
- frontend/src/lib/api/clients.ts — update ClientHealth interface
- frontend/src/components/clients/HealthDot.tsx — per-reason severity colors