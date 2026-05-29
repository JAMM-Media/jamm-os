# STANDING RULES — READ BEFORE EVERY TASK
- Backend: FastAPI, PostgreSQL, SQLAlchemy 2.0 (Mapped[] syntax), Pydantic v2
- Frontend: Next.js 14+ App Router, TypeScript, Tailwind, shadcn/ui
- Every router is thin — no business logic in routers, ever
- Tenant isolation: every query scoped to firm_id without exception
- Never use && chaining in PowerShell — use separate commands
- All new files start with a path comment

---

# TASK: Add QuickBooks deep link to client detail QBO AR card

## What this does
When a client has a QuickBooks customer ID, show an "Open in QuickBooks" link
on the QBO AR card on the client detail page. Clicking it opens the QBO customer
page for that client in a new tab. If the client has no QBO customer ID, nothing
changes — the link simply does not render.

## Why this is frontend-only mostly
The `quickbooks_customer_id` field already exists on the Client model in the
database. It is NOT currently included in the `ClientOut` schema or the frontend
Client interface, so we need to thread it through. No migration needed.

---

## Step 1 — Backend: Add quickbooks_customer_id to ClientOut schema

File: `app/schemas/client.py`

In the `ClientOut` class, add one field:

```python
quickbooks_customer_id: Optional[str] = None
```

`ClientOut` inherits from `ClientBase` and currently only adds `id`,
`created_at`, and `updated_at`. Add `quickbooks_customer_id` to `ClientOut`
directly (not `ClientBase`) since it is a read-only sync field, not something
firms set manually.

The field already exists on the `Client` model as `quickbooks_customer_id:
Mapped[Optional[str]]`. SQLAlchemy will populate it automatically via
`model_config = ConfigDict(from_attributes=True)` which is already set on
`ClientOut`.

No migration. No router change. The field is already in the database.

---

## Step 2 — Frontend: Add quickbooks_customer_id to Client interface and mapClient

File: `frontend/src/lib/api/clients.ts`

**In the `Client` interface**, add:
```typescript
quickbooksCustomerId: string | null
```

**In the `mapClient` function**, add:
```typescript
quickbooksCustomerId: raw.quickbooks_customer_id ? String(raw.quickbooks_customer_id) : null,
```

This is the same pattern used for every other snake_case to camelCase field
in that file (e.g. companyName, entityType, addressLine1).

---

## Step 3 — Frontend: Add the deep link to the QBO AR card

File: `frontend/src/app/(dashboard)/clients/[id]/page.tsx`

Find the QBO AR Balance card section. It currently renders the connected state
as a div with space-y-1 containing the outstanding balance paragraph and the
last payment date paragraph.

Add an "Open in QuickBooks" anchor link below the last payment date line,
inside that same space-y-1 div. The link should only render when
client.quickbooksCustomerId is not null.

The QBO direct URL for a customer is:
https://app.qbo.intuit.com/app/customerdetail?nameId={quickbooksCustomerId}

Exact implementation to add inside the space-y-1 div, after the last payment
date paragraph:

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

The link uses text-brand-light (#4A7FA5) to match the existing QuickBooks AR
label color in the card header. Opens in a new tab with rel="noopener noreferrer"
for security on external links.

The link renders inside the connected state block only. It will never appear
when QBO is not connected, when the card is loading, or when there is an error,
because those states render different content entirely. No additional conditional
logic needed beyond the client.quickbooksCustomerId check.

---

## Verification

After making these three changes:

1. Log in as admin@demofirm.com / Demo2026!
2. Navigate to any client that has a QuickBooks customer ID linked
3. On the Overview tab, the QBO AR card should show the Open in QuickBooks
   link below the last payment date
4. Clicking the link should open a new tab to the correct QBO customer URL
5. For clients without a QBO customer ID, the card should look exactly the
   same as before — no link, no change

If no test client has a quickbooks_customer_id set, verify the schema change
is correct by checking that the /clients/{id} API response now includes
"quickbooks_customer_id": null in its JSON.

---

## Files to modify
- app/schemas/client.py — add quickbooks_customer_id field to ClientOut
- frontend/src/lib/api/clients.ts — add field to Client interface and mapClient
- frontend/src/app/(dashboard)/clients/[id]/page.tsx — add deep link anchor