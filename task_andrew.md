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

PHASE INSTRUCTIONS — FIX CANOPY IMPORTER (TWO UPLOAD ZONES)

No migrations. Two files only: app/api/migration.py and frontend/src/components/settings/MigrationTab.tsx.

Context: Canopy exports two separate CSV files -- one for Individuals and one for Businesses. They have different column structures. The current Canopy importer reads a "Contact Type" column that does not exist in Canopy's actual exports. Replace the existing two Canopy endpoints with four, and replace the single Canopy frontend section with two upload zones.

---

STEP 1 — BACKEND: Replace Canopy endpoints in app/api/migration.py

Read the file first. Find the two existing Canopy endpoints:
  POST /canopy/preview-clients
  POST /canopy/import-clients

Replace them with four endpoints:

-- ENDPOINT: POST /canopy/individuals/preview --

Canopy Individuals CSV columns:
  "First Name" + "Last Name" -> combined as "{First Name} {Last Name}".strip() -> name (required -- skip row if blank after combining)
  "Email" -> email
  "Phone" -> phone
  "Street 1" -> address_line1
  "Street 2" -> address_line2
  "City" -> city
  "State" -> state
  "Zip" -> postal_code
  "Country" -> country
  "Tags" -> tags

entity_type is hardcoded to "individual" for every row -- no detection needed.

Deduplication: ILIKE name match scoped to firm_id marks row as skip.
Return shape: ClientPreviewResult (same as all other preview endpoints)

-- ENDPOINT: POST /canopy/individuals/import --

Same column mapping as preview. Writes Client records with entity_type="individual" hardcoded.
Fires behavioral event: event_type="migration.canopy_individuals_imported"
Return shape: ClientImportResult

-- ENDPOINT: POST /canopy/businesses/preview --

Canopy Businesses CSV columns:
  "Business Name" -> name (required -- skip row if blank)
  "Email" -> email
  "Phone" -> phone
  "Street 1" -> address_line1
  "Street 2" -> address_line2
  "City" -> city
  "State" -> state
  "Zip" -> postal_code
  "Country" -> country
  "Tags" -> tags

entity_type is hardcoded to "business" for every row.

Deduplication: same ILIKE pattern.
Return shape: ClientPreviewResult

-- ENDPOINT: POST /canopy/businesses/import --

Same column mapping as preview. Writes Client records with entity_type="business" hardcoded.
Fires behavioral event: event_type="migration.canopy_businesses_imported"
Return shape: ClientImportResult

All four endpoints: require firm_owner role, validate .csv extension, tenant-scoped.

---

STEP 2 — FRONTEND: Replace CanopyImportSection in MigrationTab.tsx

Read the file first. Find CanopyImportSection. Replace it entirely with two separate components: CanopyIndividualsSection and CanopyBusinessesSection.

Each component follows the exact same two-step pattern as the existing KarbonImportSection (upload -> preview table -> confirm -> success/error).

-- CanopyIndividualsSection --

Heading: "Import Individuals from Canopy"
Description: "Upload your Canopy Individuals export. In Canopy, go to Clients, select Import clients, choose Individual as the client type, and export your current individual clients as CSV."
Preview endpoint: POST /api/v1/migration/canopy/individuals/preview
Import endpoint: POST /api/v1/migration/canopy/individuals/import
Success message: "Import complete -- X clients imported, X skipped."

-- CanopyBusinessesSection --

Heading: "Import Businesses from Canopy"
Description: "Upload your Canopy Businesses export. In Canopy, go to Clients, select Import clients, choose Business as the client type, and export your current business clients as CSV."
Preview endpoint: POST /api/v1/migration/canopy/businesses/preview
Import endpoint: POST /api/v1/migration/canopy/businesses/import
Success message: "Import complete -- X clients imported, X skipped."

-- Section layout in MigrationTab render --

Find where CanopyImportSection is rendered. Replace the single CanopyImportSection card with two cards separated by a divider:

<card><CanopyIndividualsSection /></card>
<divider />
<card><CanopyBusinessesSection /></card>

Keep the dividers before and after the Canopy block exactly as they are. Only the interior changes.

---

DO NOT run migrations. No schema changes.

After completing confirm:
- Old /canopy/preview-clients and /canopy/import-clients endpoints removed
- Four new endpoints exist: /canopy/individuals/preview, /canopy/individuals/import, /canopy/businesses/preview, /canopy/businesses/import
- CanopyImportSection removed from MigrationTab
- CanopyIndividualsSection and CanopyBusinessesSection replace it
- Karbon, Financial Cents, and TaxDome sections unchanged