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

PHASE INSTRUCTIONS — FINANCIAL CENTS MIGRATION SECTION

No backend changes. No migrations. One file only: frontend/src/components/settings/MigrationTab.tsx

Read the file first.

Add a new FinancialCentsImportSection component. It follows the exact same two-step upload/result pattern as CsvImportSection (the general CSV section at the top of the file) -- same states, same drag-drop zone, same result display. The only differences are the heading, description text, and it is a separate component so firm owners see their tool listed by name.

-- FinancialCentsImportSection component --

Copy the CsvImportSection component exactly and rename it FinancialCentsImportSection. Change only these things:

1. Heading text: "Import from Financial Cents"

2. Description text: "Upload your Financial Cents client export. In Financial Cents, go to Clients, click Export, and download as CSV. JAMM PX will import the Name, Email, Phone, and Address fields automatically."

3. Button label: "Import Clients" (same as CsvImportSection -- no change needed here)

4. Success message: "Import complete -- X clients imported, X skipped." (same pattern as CsvImportSection)

The API endpoint is identical: POST /api/v1/clients/import with the file as FormData field named "file".

-- Section placement in MigrationTab render --

Read the current render order in MigrationTab. It currently is:
1. CsvImportSection card
2. divider
3. CanopyImportSection card
4. divider
5. KarbonImportSection card
6. divider
7. TaxDome heading + description
8. ClientSection card
9. divider
10. JobSection card

Insert FinancialCentsImportSection between KarbonImportSection and the TaxDome heading. New order:
1. CsvImportSection card
2. divider
3. CanopyImportSection card
4. divider
5. KarbonImportSection card
6. divider
7. FinancialCentsImportSection card (new)
8. divider
9. TaxDome heading + description
10. ClientSection card
11. divider
12. JobSection card

Use the exact same card wrapper and divider pattern already in the file.

DO NOT run migrations. No backend changes. One file only.

After completing confirm:
- FinancialCentsImportSection component exists in MigrationTab.tsx
- It hits POST /api/v1/clients/import (same as CsvImportSection)
- It appears between KarbonImportSection and the TaxDome heading in the render