# STANDING RULES — PERMANENT, NEVER OVERWRITE THIS BLOCK
- All models use UUID primary keys, firm_id FK, created_at and updated_at (timezone-aware)
- Every module has 4 Pydantic schemas: XBase, XCreate, XUpdate, XOut
- Routers are thin — no business logic ever
- All list endpoints paginated using PaginatedResponse[T]
- RBAC enforced at every endpoint
- Tenant isolation absolute — every query scoped to firm_id without exception
- Signed URLs only for all file access — never public S3 URLs, 1 hour maximum expiry
- Audit logging on every sensitive action
- Always use string names in relationship() to avoid circular imports
- Every generated file starts with a path comment
- Background tasks that touch the database must create their own SessionLocal() in a try/finally block — never pass the request db session into a background task
- Never use native_enum=True for enums whose values contain dots or special characters — always use sa.Enum(MyEnum, native_enum=False)
- Behavioral event log: fire-and-forget only, never block the main operation, service layer only, own session, never inherit the request session
- Always use SQLAlchemy 2.0 Mapped[] syntax — never Column() style
- Always use Pydantic v2 — model_dump() and field_validator() only, never .dict() or @validator
- DATABASE_URL uses postgresql+psycopg:// dialect prefix — never plain postgresql://
- Never use && to chain commands in PowerShell — separate every command onto its own line
- Never use em dashes anywhere in any string, copy, or comment

---

# MIGRATION PROCEDURE — FOLLOW EVERY TIME
1. alembic current — confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

# PHASE INSTRUCTIONS — FULL FIRM DATA EXPORT

## Context
No migration needed. No frontend changes beyond a single button in settings.
This is a new backend endpoint plus a minimal frontend trigger.

The export produces a ZIP file containing these CSVs:
- clients.csv
- engagements.csv
- invoices.csv
- tasks.csv
- irs_authorizations.csv
- notes.csv
- time_entries.csv
- documents_manifest.csv (metadata only — no actual files)

The endpoint streams the ZIP directly as a file download response.
Firm owner only. No data from other firms ever included.

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before firm data export"

---

## VERIFY BEFORE STARTING
grep -n "require_firm_owner\|firm_owner" app/dependencies/roles.py | head -5
grep -n "StreamingResponse\|FileResponse\|BytesIO" app/api/timesheets.py | head -5
Paste both outputs before touching anything.

---

## Change 1: Create app/services/firm_export_service.py

Create this file from scratch. Path comment at top.

Import: io, csv, zipfile, datetime, uuid, from sqlalchemy.orm import Session,
and all relevant models.

Write one function: generate_firm_export_zip(firm_id: UUID, db: Session) -> bytes

This function:
1. Creates an in-memory ZIP using zipfile.ZipFile with BytesIO
2. For each CSV below, queries the database scoped to firm_id,
   writes rows using csv.DictWriter, and adds to the ZIP
3. Returns the ZIP as bytes

### clients.csv
Query: all Client records where firm_id == firm_id
Columns: id, name, email, phone, company_name, entity_type,
         address_line1, address_line2, city, state, postal_code,
         country, tags, notes, is_active, created_at

Exclude: portal_password_hash, portal_invite_token, tax_id,
         quickbooks_customer_id — never export sensitive or
         integration-specific fields

### engagements.csv
Query: all Engagement records where firm_id == firm_id
Columns: id, client_id, name, description, status,
         engagement_type, start_date, end_date,
         filing_deadline, extended_deadline,
         efiled_at, irs_confirmation_number,
         notes, is_active, created_at

### invoices.csv
Query: all Invoice records where firm_id == firm_id
       and is_deleted == False
Columns: id, client_id, engagement_id, invoice_number,
         subtotal, tax_rate, tax_amount, total_amount,
         status, due_date, paid_at, sent_at, created_at

Exclude: stripe_payment_intent_id, stripe_charge_id

### tasks.csv
Query: all Task records where firm_id == firm_id
Columns: id, client_id, engagement_id, title, description,
         status, assigned_to, due_date, completed_at, created_at

### irs_authorizations.csv
Query: all IrsAuthorization records where firm_id == firm_id
Columns: id, client_id, form_type, status, expiry_date,
         granted_at, created_at

### notes.csv
Query: all Note records where firm_id == firm_id
Columns: id, entity_type, entity_id, author_id,
         content, is_private, created_at

### time_entries.csv
Query: all TimeEntry records where firm_id == firm_id
Columns: id, engagement_id, client_id, user_id,
         date, hours, hourly_rate, is_billable,
         is_billed, description, activity_type, created_at

### documents_manifest.csv
Query: all Document records where firm_id == firm_id
Columns: id, client_id, engagement_id, filename,
         file_type, file_size, uploaded_by,
         is_superseded, created_at

Note: document_manifest is metadata only.
Never attempt to download or include actual document files.

All datetime values: format as ISO 8601 strings.
All None values: write as empty string.
All UUID values: write as string.

ZIP filename inside the archive: use the column names above.
ZIP compression: zipfile.ZIP_DEFLATED

---

## Change 2: Create app/api/firm_export.py

Create this router from scratch. Path comment at top.

Single endpoint: GET /firm-export/download
- Auth: require_firm_owner
- Calls generate_firm_export_zip(firm_id, db)
- Returns StreamingResponse with:
  - media_type: "application/zip"
  - headers: Content-Disposition: attachment; filename="jammpx_export_{date}.zip"
    where date is today in YYYY-MM-DD format
- Write audit log entry: action "firm.data_exported"
- Fire behavioral event: event_type "firm.data_exported"

---

## Change 3: Register router in app/main.py

Find where other routers are registered.
Add:
from app.api.firm_export import router as firm_export_router
app.include_router(firm_export_router, prefix="/api/v1", tags=["Firm Export"])

---

## Change 4: Add export button to settings frontend

Find the firm settings tab in the frontend.
It is likely at: frontend/src/components/settings/FirmTab.tsx
or similar — grep for "firm settings" or "firm name" in the
frontend components to find the right file.

Add a new section at the bottom of the firm settings tab with:
- Section heading: "Data export" (13px, font-500, brand color)
- Subtext: "Download a complete export of your firm data as a ZIP file containing CSVs for all clients, engagements, invoices, tasks, IRS authorizations, notes, time entries, and documents." (12px, muted)
- A single button: "Download export"
  - Brand blue background, white text, 32px height
  - On click: calls GET /api/v1/firm-export/download via axios
    with responseType: 'blob', then triggers a browser download
  - Shows loading spinner while in flight
  - Shows success toast on complete: "Export downloaded"
  - Shows error toast on failure: "Export failed. Please try again."

---

## Verify after all changes
grep -n "def generate_firm_export_zip\|clients.csv\|documents_manifest" app/services/firm_export_service.py
grep -n "firm-export\|firm_export_router\|data_exported" app/api/firm_export.py
grep -n "firm_export_router" app/main.py
python -m py_compile app/services/firm_export_service.py
python -m py_compile app/api/firm_export.py
Both compiles must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "full firm data export endpoint and settings button"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager