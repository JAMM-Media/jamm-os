STANDING RULES — ALWAYS FOLLOW THESE

Product name is JAMM PX. Never refer to it as JAMM OS.

Domain language: Firm = accounting business. Client = firm's customer. Engagement = unit of billable work. Staff = firm employees.

Tech stack — never deviate without explicit instruction:
Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0 (Mapped[] syntax only), Pydantic v2, Alembic, Uvicorn + Gunicorn.
Frontend: Next.js 14+ App Router, TypeScript always, Tailwind CSS, shadcn/ui, Axios with JWT interceptor.

Architecture rules:
- Routers are thin — no business logic ever.
- Tenant isolation is absolute — every query scoped to firm_id.
- Every generated file starts with a path comment.
- Background tasks that touch the database must create their own SessionLocal() session in a try/finally block.

Windows / PowerShell:
- No && chaining — separate commands
- Quoted paths for directories with parentheses

---

PHASE-SPECIFIC INSTRUCTIONS — Billing Detail (sendable timesheet report)

Four parts. No migration needed.

---

PART 1 — BACKEND: billing detail endpoint + PDF generation

File: app/api/reports.py (add to existing reports router)

Add a new GET endpoint: GET /reports/billing-detail

Query params:
- client_id: UUID (required)
- date_from: date (optional)
- date_to: date (optional)
- engagement_id: UUID (optional)
- format: str = "json" (accepts "json" or "pdf")

Auth: requires manager_or_above. Tenant isolation: all queries scoped to firm_id from current_firm.

Logic:
- Query time_entries table where firm_id = current_firm.id AND engagement_id in (engagements where client_id = client_id AND firm_id = firm_id)
- If engagement_id param is provided, additionally filter by that engagement_id
- If date_from is provided, filter time_entries.date >= date_from
- If date_to is provided, filter time_entries.date <= date_to
- Join to users table to get staff full_name for each entry
- Join to engagements table to get engagement name for each entry
- Order by date ASC, then created_at ASC

JSON response shape:
{
  "client_name": str,
  "firm_name": str,
  "date_from": str | null,
  "date_to": str | null,
  "entries": [
    {
      "date": str (YYYY-MM-DD),
      "staff_name": str,
      "engagement_name": str,
      "activity_type": str | null,
      "description": str,
      "hours": float,
      "hourly_rate": float,
      "amount": float,
      "is_billable": bool
    }
  ],
  "total_hours": float,
  "total_amount": float
}

PDF response: when format=pdf, generate a PDF using WeasyPrint (same pattern as render_invoice_to_pdf in app/services/invoice_renderer.py). Build an HTML string with:
- Header: firm name (large), "Billing Detail" subtitle, client name, date range if provided
- Table: Date | Staff | Engagement | Activity | Description | Hours | Rate | Amount
- Footer row: totals for Hours and Amount columns
- Clean professional styling matching the invoice renderer aesthetic — white background, brand blue (#1F3148) header row, clean sans-serif font
Return as StreamingResponse with content_type="application/pdf" and Content-Disposition header: attachment; filename="billing-detail-{client_name}.pdf"

Add a POST endpoint: POST /reports/billing-detail/send-to-portal
Body: { client_id: UUID, date_from: date | null, date_to: date | null, engagement_id: UUID | null }
Auth: requires manager_or_above.
Logic: Generate the billing detail data (same query as above), store it as a new record in a new simple table billing_detail_reports (id UUID PK, firm_id UUID FK, client_id UUID FK, created_by UUID FK, date_from date nullable, date_to date nullable, engagement_id UUID nullable, entries JSONB, total_hours numeric, total_amount numeric, created_at timestamptz). Return { id: str, created_at: str }.

Wait — no migration needed was stated but the billing_detail_reports table is new. Write a clean manual migration for it:
- Migration file: migrations/versions/0040_add_billing_detail_reports.py
- Revises: 0039_add_complexity_flags_to_engagements
- Creates table billing_detail_reports with the fields above
- Follow the exact migration file pattern used in 0039

Also add the model: app/models/billing_detail_report.py
And add a portal endpoint: GET /portal/billing-detail — returns all billing_detail_reports for the current portal client, ordered by created_at DESC. Returns array of { id, date_from, date_to, engagement_id, total_hours, total_amount, created_at, entries }.

---

PART 2 — FIRM SIDE: Generate Billing Detail UI on client detail page

File: frontend/src/app/clients/[id]/page.tsx

Add a "Billing Detail" button to the Billing tab toolbar area (near the existing "New Invoice" button). Style it as a secondary button — border border-surface-border, bg transparent, text-brand, same height as other toolbar buttons.

Clicking it opens a modal: BillingDetailModal. Create this as a new file: frontend/src/components/billing/BillingDetailModal.tsx

BillingDetailModal props: { open: boolean, onClose: () => void, clientId: string, clientName: string }

Modal content:
- Title: "Billing Detail"
- Form fields:
  - Date From: date input (optional)
  - Date To: date input (optional)
  - Engagement: select dropdown populated from /engagements/?client_id={clientId}&limit=100. First option "All engagements".
- Two action buttons at the bottom: "Download PDF" and "Send to Portal"
- A preview table section that loads when any filter changes: calls GET /reports/billing-detail?client_id={clientId}&format=json with the current filters. Shows a table matching the JSON response shape: Date, Staff, Engagement, Activity, Hours, Amount columns. Shows total row at the bottom. Loading skeleton while fetching.

Download PDF: calls GET /reports/billing-detail?client_id={clientId}&format=pdf&... with current filters. Use fetch with the portal auth headers pattern — actually use the staff api client (axios instance from @/lib/api.ts) with responseType: 'blob'. Then create an object URL and trigger a download link click.

Send to Portal: calls POST /reports/billing-detail/send-to-portal with current filters. On success shows toast.success("Billing detail sent to client portal") and closes the modal.

---

PART 3 — PORTAL SIDE: Billing Detail tab

Step 1 — Add "Billing Detail" tab to PortalShell.tsx:
In the tabs array add: { key: 'billing-detail', label: 'Billing Detail' }
Place it after 'invoices' and before 'messages'.

Step 2 — Create new component: frontend/src/components/portal/PortalBillingDetail.tsx
Props: { cardColor, accentColor, portalMode, textPrimary, textMuted } — same pattern as other portal components.

Fetch billing detail reports from GET /portal/billing-detail using the portal auth pattern (same as getPortalDocuments in portal-api.ts — use localStorage portal_access_token, fetch directly).

Add getPortalBillingDetail to frontend/src/lib/portal-api.ts:
export async function getPortalBillingDetail(): Promise<BillingDetailReport[]>
where BillingDetailReport = { id: string, date_from: string | null, date_to: string | null, total_hours: number, total_amount: number, created_at: string, entries: BillingDetailEntry[] }
and BillingDetailEntry = { date: string, staff_name: string, engagement_name: string, activity_type: string | null, description: string, hours: number, hourly_rate: number, amount: number, is_billable: boolean }

Component renders a list of billing detail report cards. Each card shows:
- Date range or "All dates" if no range
- Total: X hours · $X,XXX
- Created date in muted text
- An expand/collapse chevron — expanded shows the full entries table inline

If no reports: empty state "No billing details shared yet. Your firm will share billing summaries here."

Step 3 — Wire up in portal/page.tsx:
Import PortalBillingDetail and add:
{activeTab === 'billing-detail' && <PortalBillingDetail cardColor={me.portal_card_color} accentColor={me.portal_accent_color} portalMode={me.portal_mode} textPrimary={me.portal_text_primary} textMuted={me.portal_text_muted} />}

---

VERIFICATION

1. alembic upgrade head runs cleanly on the new 0040 migration
2. npx tsc --noEmit in frontend/ passes with no errors
3. GET /reports/billing-detail returns correct JSON for a client with time entries
4. PDF download triggers correctly from the modal
5. Send to Portal creates a record and it appears in the portal Billing Detail tab