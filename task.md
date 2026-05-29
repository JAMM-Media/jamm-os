# STANDING RULES — READ BEFORE EVERY TASK
- Backend: FastAPI, PostgreSQL, SQLAlchemy 2.0 (Mapped[] syntax), Pydantic v2
- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui
- Every router is thin — no business logic in routers, ever
- Tenant isolation: every query scoped to firm_id without exception
- Never use && chaining in PowerShell — use separate commands
- All new files start with a path comment

---

# TASK: Rework client health score logic

## What this does
Rewrites the health score logic in `app/services/client_health_service.py`
to make deadline proximity the primary driver of health status. The current
logic over-indexes on IRS authorization status and misses the most important
signal: a client with an active engagement whose deadline is approaching or
overdue should never show green.

No migration. No schema changes. No frontend changes. Backend service only.

---

## Current problems to fix

1. A client with an active engagement due in 3 days shows green — deadline
   proximity is not checked at all today.
2. Expired IRS authorization is an at_risk trigger even when there are no
   active engagements — too aggressive for firms that don't use IRS auth.
3. The at_risk condition for overdue invoice requires BOTH overdue invoice
   AND stale portal login — an overdue invoice alone should be at_risk.
4. Reasons are not specific enough — "Overdue invoice" should say how many,
   "Open document request" should say how many days old.

---

## New logic — rewrite compute_client_health() completely

File: `app/services/client_health_service.py`

Keep all existing imports. Add `timedelta` if not already imported (it is).
Keep the `_ensure_tz` helper unchanged.

Replace the entire `compute_client_health()` function body with the following
logic. The function signature stays identical:
`def compute_client_health(client_id: UUID, firm_id: UUID, db: Session) -> dict`

### Data to query (same queries as before, plus one new one)

Query 1 — Client (unchanged):
```python
client = db.execute(
    select(Client).where(Client.id == client_id, Client.firm_id == firm_id)
).scalar_one_or_none()

if client is None:
    return {"status": "healthy", "reasons": []}
```

Query 2 — Active engagements (new — replaces the single recent_engagement query):
Fetch ALL active engagements for the client, not just the most recent one.
Active means status not in ("completed", "archived").
Include only engagements that have at least one deadline set
(filing_deadline is not None OR extended_deadline is not None).

```python
active_engagements = db.execute(
    select(Engagement).where(
        Engagement.client_id == client_id,
        Engagement.firm_id == firm_id,
        Engagement.status.notin_(["completed", "archived"]),
        (Engagement.extended_deadline.isnot(None) | Engagement.filing_deadline.isnot(None)),
    )
).scalars().all()
```

Query 3 — Unpaid invoices (unchanged):
```python
invoices = db.execute(
    select(Invoice).where(
        Invoice.client_id == client_id,
        Invoice.firm_id == firm_id,
        Invoice.status.in_([InvoiceStatus.sent, InvoiceStatus.overdue]),
        Invoice.is_deleted == False,
    )
).scalars().all()
```

Query 4 — Open document requests (unchanged):
```python
doc_requests = db.execute(
    select(DocumentRequest).where(
        DocumentRequest.client_id == client_id,
        DocumentRequest.firm_id == firm_id,
        DocumentRequest.status != "completed",
    )
).scalars().all()
```

Query 5 — IRS authorizations (unchanged):
```python
irs_auths = db.execute(
    select(IrsAuthorization).where(
        IrsAuthorization.client_id == client_id,
        IrsAuthorization.firm_id == firm_id,
    )
).scalars().all()
```

### Deadline helper

Add this helper inline before the at_risk checks. It returns the effective
deadline for an engagement — extended_deadline takes priority over
filing_deadline:

```python
def effective_deadline(eng):
    return eng.extended_deadline or eng.filing_deadline
```

### AT RISK — check in this order, collect all reasons

```python
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

if at_risk_reasons:
    return {"status": "at_risk", "reasons": at_risk_reasons}
```

### NEEDS ATTENTION — check in this order, collect all reasons

```python
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
# (only fire this if there are no active deadline engagements — avoids noise)
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

if needs_attention_reasons:
    return {"status": "needs_attention", "reasons": needs_attention_reasons}

return {"status": "healthy", "reasons": []}
```

---

## What changed and why

- Deadline proximity is now the primary at_risk signal. A client with an
  engagement due in 1-3 days is at_risk regardless of invoices or IRS auth.
- Deadline approaching (4-14 days) is needs_attention.
- Overdue invoice now stands alone as an at_risk signal — no longer requires
  stale portal login combined with it.
- Expired IRS authorization removed from at_risk — it was too aggressive.
  IRS auth expiring within 60 days remains as needs_attention.
- Reasons are now specific and countable — "3 engagements past deadline"
  instead of "Overdue engagement".
- The "no activity in 30 days" check only fires when there are no active
  deadline engagements, so it does not add noise for active clients.

---

## Verification

1. Run the backend: confirm no import errors on startup
2. Hit GET /clients/{any_client_id}/health in the browser or Postman
3. Confirm the response still matches the shape: {"status": "...", "reasons": [...]}
4. Check production logs: journalctl -u jammpx -n 20 --no-pager
   Confirm no errors related to client_health_service

No frontend changes needed. The HealthDot component already renders all
reasons from the reasons array in the tooltip — more specific reason strings
will show up automatically.

---

## Files to modify
- app/services/client_health_service.py — full rewrite of compute_client_health()