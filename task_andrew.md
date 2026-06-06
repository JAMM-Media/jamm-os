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

PHASE INSTRUCTIONS — CANOPY AND KARBON MIGRATION IMPORTERS

No migrations required. Two backend additions to app/api/migration.py and one frontend addition to MigrationTab.tsx.

---

STEP 1 — BACKEND: Add Canopy and Karbon endpoints to app/api/migration.py

Read app/api/migration.py first. It already has the TaxDome endpoints and shared helpers (_validate_csv_extension, _read_csv_rows, _parse_date, ENTITY_TYPE_MAP, ENGAGEMENT_STATUS_MAP). Add the following four endpoints to the same file.

-- CANOPY ENDPOINTS --

Canopy exports a single CSV with both individuals and businesses. The key column is "Contact Type" which contains "Individual" or "Business".

Canopy CSV columns (exact header names):
  "Contact Type" -> entity_type: Individual -> individual, Business -> business. Any other value -> individual with a warning.
  "First Name" + "Last Name" -> combined as "{First Name} {Last Name}".strip() for individuals
  "Business Name" -> name for businesses. If Contact Type is Business and Business Name is blank, skip row with warning.
  "Email" -> email
  "Tags" -> tags
  "Street 1" -> address_line1
  "Street 2" -> address_line2
  "City" -> city
  "State" -> state
  "Zip" -> postal_code
  "Country" -> country

Name resolution logic:
  If Contact Type is Business: name = Business Name
  If Contact Type is Individual (or anything else): name = (First Name + " " + Last Name).strip()
  If resolved name is blank after this: skip row with warning "Could not determine client name."

POST /canopy/preview-clients

Deduplication: same as TaxDome -- ILIKE name match scoped to firm_id marks row as skip.

Return shape: same as TaxDome ClientPreviewResult (total_rows, will_import, will_skip, warnings, rows). Each row includes: row_number, name, email, entity_type, tags, state, status, reason.

POST /canopy/import-clients

Same logic as preview but writes Client records. Fires behavioral event:
  event_type: "migration.canopy_clients_imported"
  metadata: { created, skipped, warnings, total_rows }

Return shape: same as TaxDome ClientImportResult (created, skipped, warnings, errors).

-- KARBON ENDPOINTS --

Karbon exports a single "All contacts" CSV. The key column is "Type" which contains "Person" or "Organisation". We use this to set entity_type automatically.

Karbon CSV columns (exact header names):
  "Name" -> name (required -- skip if blank)
  "Type" -> entity_type: Person -> individual, Organisation -> business. Any other value -> individual with a warning.
  "Email" -> email (may contain multiple comma-separated emails -- take the first one only)
  "Phone" -> phone (may contain multiple -- take the first one only)
  "Street" -> address_line1
  "City" -> city
  "State/Region" -> state
  "Postcode" -> postal_code
  "Country" -> country

POST /karbon/preview-clients

Same deduplication and return shape as Canopy and TaxDome.

POST /karbon/import-clients

Same import logic. Fires behavioral event:
  event_type: "migration.karbon_clients_imported"
  metadata: { created, skipped, warnings, total_rows }

All four endpoints: require firm_owner role, validate .csv extension, tenant-scoped, fire-and-forget behavioral events.

---

STEP 2 — FRONTEND: Add Canopy and Karbon sections to MigrationTab.tsx

Read frontend/src/components/settings/MigrationTab.tsx first.

The file currently has three sections in this order:
1. CsvImportSection (general CSV) at the top
2. ClientSection (TaxDome clients)
3. JobSection (TaxDome jobs)

Add two new sections between the general CSV section and the TaxDome sections. New order:
1. CsvImportSection (general CSV)
2. CanopyImportSection (new)
3. KarbonImportSection (new)
4. TaxDome divider + heading
5. ClientSection (TaxDome clients)
6. JobSection (TaxDome jobs)

Each new section (Canopy and Karbon) follows the exact same two-step pattern as the existing TaxDome sections in this file: upload state with drag-drop zone and preview button, then preview state with summary pills, colored table, Start Over and Confirm Import buttons, then success or error state.

-- CanopyImportSection component --

Section heading: "Import from Canopy"

Description: "Upload your Canopy contacts export. In Canopy, go to Clients, select all contacts, and export as CSV. JAMM PX reads the Contact Type column automatically -- individuals and businesses are assigned the correct entity type."

Upload step: POST to /api/v1/migration/canopy/preview-clients with file as FormData.
Confirm step: POST to /api/v1/migration/canopy/import-clients with same file.

Preview table columns: Row, Name, Email, Entity Type (formatted using formatEntityType from @/lib/utils), Status badge, Reason.

Success message: "Import complete -- X clients imported, X skipped."

-- KarbonImportSection component --

Section heading: "Import from Karbon"

Description: "Upload your Karbon contacts export. In Karbon, go to Contacts, click the cloud icon, and select All contacts. The Type column (Person or Organisation) maps automatically to Individual or Business in JAMM PX."

Upload step: POST to /api/v1/migration/karbon/preview-clients with file as FormData.
Confirm step: POST to /api/v1/migration/karbon/import-clients with same file.

Preview table columns: Row, Name, Email, Entity Type (formatted using formatEntityType), Status badge, Reason.

Success message: "Import complete -- X clients imported, X skipped."

-- Section layout in MigrationTab --

Between the CsvImportSection card and the TaxDome sections, add:

<divider />
<CanopyImportSection in its own card />
<divider />
<KarbonImportSection in its own card />
<divider />
<p className heading style>TaxDome Import</p>
<p className description style>If migrating from TaxDome, import clients first, then jobs. Job matching uses client names.</p>
<existing ClientSection card />
<divider />
<existing JobSection card />

The heading and description for TaxDome should match the style of the section headings inside the existing cards (13px weight 500 brand color for heading, 12px muted for description), but placed outside the card as a section label, same as how the general CSV section is laid out.

Use the exact same card wrapper, divider, drag-drop zone, summary pills, status badge, and button styles already in the file. Do not invent new patterns -- read the file and replicate what is already there.

---

DO NOT run migrations. No schema changes.

After completing confirm:
- Four new endpoints in app/api/migration.py (canopy preview, canopy import, karbon preview, karbon import)
- CanopyImportSection and KarbonImportSection components in MigrationTab.tsx
- Correct section order in MigrationTab render
- TaxDome heading added above existing sections