STANDING RULES — PERMANENT — DO NOT SKIP

Architecture rules:
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

MIGRATION PROCEDURE — FOLLOW EVERY TIME

1. alembic current — confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

PHASE INSTRUCTIONS — TAXDOME MIGRATION IMPORT

No new database models or migrations required. This is a stateless CSV processing feature — preview and import both operate in memory against existing models.

---

STEP 1 — BACKEND: app/api/migration.py (new file)

Create app/api/migration.py with four endpoints. Router prefix: /migration. Tag: migration. All endpoints require firm_owner role only — staff and managers never see this.

All four endpoints accept multipart/form-data with a single file field named "file". Validate that the uploaded file is a .csv before processing. If not .csv, return 400 with message: "File must be a .csv export from TaxDome."

No migration needed — no new DB tables. All writes use existing Client and Engagement models.

-- ENDPOINT 1: POST /migration/taxdome/preview-clients --

Accepts TaxDome Accounts CSV. Reads and maps columns. Returns a preview object. Writes nothing to the database.

TaxDome Accounts CSV columns (exact header names from TaxDome export):
  "Account Name", "Account Type", "State", "Email", "Phone", "Tags", "Assigned Team Members", "Created Date"

Field mapping logic:
  "Account Name" -> name (required — skip row with warning if blank)
  "Email" -> email
  "Phone" -> phone
  "Account Type" -> entity_type using this exact mapping (case-insensitive):
    Individual -> individual
    Business -> business
    Trust -> trust
    Estate -> estate
    (any other value -> set entity_type to None, add a warning for that row)
  "Tags" -> tags
  "State" -> state
  "Assigned Team Members" -> ignored (JAMM PX uses its own staff assignments)
  "Created Date" -> ignored

Deduplication check: for each row, query Client table for firm_id = current firm AND name ILIKE the mapped name. If a match exists, mark that row as "will_skip" with reason "Client with this name already exists."

Return shape:
{
  "total_rows": int,
  "will_import": int,
  "will_skip": int,
  "warnings": int,
  "rows": [
    {
      "row_number": int,
      "name": str,
      "email": str or null,
      "phone": str or null,
      "entity_type": str or null,
      "tags": str or null,
      "state": str or null,
      "status": "import" | "skip" | "warning",
      "reason": str or null  -- only set on skip or warning rows
    }
  ]
}

-- ENDPOINT 2: POST /migration/taxdome/import-clients --

Accepts same TaxDome Accounts CSV. Applies same mapping and deduplication logic. This time actually writes to the database.

For each non-skipped row: create a Client record using the existing Client model directly (same pattern as app/api/clients.py CSV import — do not call that endpoint, replicate the write logic). Set firm_id from JWT. Set is_active=True.

After all rows processed: fire a single behavioral event:
  event_type: "migration.taxdome_clients_imported"
  metadata: { "created": int, "skipped": int, "warnings": int, "total_rows": int }

Return shape:
{
  "created": int,
  "skipped": int,
  "warnings": int,
  "errors": [ { "row": int, "reason": str } ]
}

-- ENDPOINT 3: POST /migration/taxdome/preview-jobs --

Accepts TaxDome Jobs CSV. Reads and maps columns. Returns a preview object. Writes nothing.

TaxDome Jobs CSV columns (exact header names from TaxDome export):
  "Client", "Job Name", "Pipeline", "Status", "Assignee", "Created Date", "Due Date", "Description"

Field mapping logic:
  "Client" -> matched to existing Client by name (case-insensitive ILIKE query scoped to firm_id). If no match found, mark row as "will_skip" with reason: "No matching client found for '[Client value]' -- import clients first."
  "Job Name" -> name (required -- skip row with warning if blank)
  "Status" -> mapped to EngagementStatus using this logic:
    "In Progress" | "Active" | "Open" -> active
    "Completed" | "Done" | "Finished" -> completed
    "Draft" | "Not Started" -> draft
    (any other value) -> draft, add warning note in reason field
  "Due Date" -> filing_deadline (parse as date, format YYYY-MM-DD. If unparseable, set to None and add warning)
  "Description" -> description
  "Pipeline" -> ignored
  "Assignee" -> ignored (JAMM PX uses its own staff assignments)
  "Created Date" -> ignored

Return shape:
{
  "total_rows": int,
  "will_import": int,
  "will_skip": int,
  "warnings": int,
  "rows": [
    {
      "row_number": int,
      "job_name": str,
      "client_name": str,
      "client_found": bool,
      "mapped_status": str or null,
      "filing_deadline": str or null,
      "description": str or null,
      "status": "import" | "skip" | "warning",
      "reason": str or null
    }
  ]
}

-- ENDPOINT 4: POST /migration/taxdome/import-jobs --

Accepts same TaxDome Jobs CSV. Applies same mapping logic. Writes to database.

For each non-skipped row: create an Engagement record using the existing Engagement model directly. Set firm_id from JWT. Set client_id from the matched Client. Set engagement_type to None (TaxDome does not export IRS form types). Set is_active=True.

After all rows processed: fire a single behavioral event:
  event_type: "migration.taxdome_jobs_imported"
  metadata: { "created": int, "skipped": int, "warnings": int, "total_rows": int }

Return shape:
{
  "created": int,
  "skipped": int,
  "warnings": int,
  "errors": [ { "row": int, "reason": str } ]
}

---

STEP 2 — REGISTER ROUTER: app/main.py

Import the migration router and register it:
  from app.api.migration import router as migration_router
  app.include_router(migration_router, prefix="/api/v1")

---

STEP 3 — FRONTEND: MigrationTab component

Create frontend/src/components/settings/MigrationTab.tsx

This is a firm_owner-only tab. The component renders two stacked sections separated by a visible divider. Section 1 is client import. Section 2 is job import. Both sections are always visible -- no hiding section 2 until section 1 is done, but add a note in section 2: "Import clients first -- job matching depends on client names existing in JAMM PX."

Each section follows the exact same two-step wizard pattern:

STEP A -- UPLOAD STATE (default):
- Section heading: "Import Clients from TaxDome" (or "Import Jobs from TaxDome")
- One paragraph of plain text below heading:
  Clients section: "Upload your TaxDome Accounts export. Download it from TaxDome under Clients, select all, and export as CSV. JAMM PX will preview every row before importing anything."
  Jobs section: "Upload your TaxDome Jobs export. Download it from TaxDome under Work, select all jobs, and export as CSV. Import clients first -- job matching uses client names."
- File input: drag-and-drop zone, accepts .csv only, same visual pattern as AckFileUploader (drag-drop border, upload icon, label). Show filename after selection.
- "Preview Import" button: brand color, disabled until a file is selected. On click: POST to the preview endpoint with the file as FormData, show loading state on button.

STEP B -- PREVIEW STATE (after preview API returns):
- Show summary bar: four stat pills in a row -- "X rows found", "X will import" (green), "X will skip" (amber), "X warnings" (amber if > 0, gray if 0).
- Show preview table with columns matching the return shape for that endpoint. Status column shows colored badge: "Import" (green), "Skip" (amber), "Warning" (amber with warning icon). Reason column shows the reason text for skip/warning rows, blank for import rows.
- Two buttons right-aligned: "Start Over" (ghost, resets to upload state) and "Confirm Import" (brand color).
- On "Confirm Import": POST to the import endpoint with the same file, show loading state, disable both buttons.
- On import success: show inline success message (green checkmark, text: "Import complete -- X clients imported, X skipped." or jobs equivalent). Show "Import Another File" button that resets to upload state. Do not auto-reset.
- On import error: show inline error message in red. Keep the preview visible. Show "Try Again" button.

Styling: match the existing settings tab aesthetic exactly -- same card container (bg-[#EDEEF0] dark:bg-[#383838], rounded-[10px], border border-[#C8CDD6] dark:border-[#484848]), same heading sizes (13px weight 500), same body text (12px #6B7280). Use the same table style as other JAMM PX tables (header row bg-[#EDEEF0], uppercase 11px headers, 12px row text).

---

STEP 4 — WIRE TAB INTO SETTINGS PAGE: frontend/src/app/settings/page.tsx

1. Import MigrationTab at the top with the other tab imports:
   import MigrationTab from '@/components/settings/MigrationTab'

2. Add Migration to the TABS constant after 'portal_branding':
   { key: 'migration', label: 'Migration' }

3. Add TabKey type -- add 'migration' to the union if TabKey is explicitly typed.

4. Add visibility rule -- Migration tab is firm_owner only. Find where canSeeSecurity and canSeeAutomations are defined and add:
   const canSeeMigration = user?.role === 'firm_owner'

5. Filter Migration tab from the tab list for non-owners (same pattern as security and automations tabs).

6. Render MigrationTab in the tab content section:
   {activeTab === 'migration' && canSeeMigration && <MigrationTab />}

---

DO NOT run migrations -- no schema changes in this build.
After completing all steps, confirm:
- app/api/migration.py exists with four endpoints
- migration_router registered in app/main.py
- frontend/src/components/settings/MigrationTab.tsx exists
- Settings page imports MigrationTab, adds it to TABS, and renders it correctly