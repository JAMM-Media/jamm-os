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

# PHASE INSTRUCTIONS — WEEK 3, RUN 1 OF 3: CSV IMPORT EXPANSION

## Context
The CSV import endpoint already exists at POST /clients/import in app/api/clients.py.
It currently handles 5 fields: name, email, entity_type, phone, company_name.
The Client model has additional importable fields not yet wired in.
This run adds those fields and adds fuzzy name deduplication.
No migration required — all fields already exist on the Client model.

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before week 3 csv expansion"

---

## VERIFY BEFORE STARTING
grep -n "def import_clients_csv\|new_client = Client\|existing_emails" app/api/clients.py
Paste the output before touching anything.

---

## Change 1: Expand the import loop in app/api/clients.py

Add these 8 fields to the import loop using the same pattern as existing fields
(row.get("field_name", "").strip() or None):
- address_line1
- address_line2
- city
- state
- postal_code
- country
- tags (comma-separated string, stored as-is)
- notes

Add all 8 to the Client() constructor call alongside the existing fields.

---

## Change 2: Fuzzy name deduplication

Currently the import deduplicates on email only.
Add case-insensitive name deduplication within the same firm.

Before the import loop:
- Query existing client names for this firm
- Store as a set of lowercase stripped strings: existing_names

In the loop, before creating each client:
- Check if name.lower().strip() is in existing_names
- If yes: increment skipped, append to errors list as
  {"row": i, "reason": "Client with this name already exists"}, continue
- If no: after creating the client, add name.lower().strip() to existing_names

---

## Change 3: Check ClientImportResult schema in app/schemas/client.py

If the errors field is typed as list[str], change it to list[dict].
The created and skipped integer fields stay unchanged.

---

## Change 4: Behavioral event log on import completion

After db.commit() at the end of the import, fire a single log_event call:
- event_type: "client.csv_import_completed"
- entity_type: "firm"
- entity_id: current_firm.id
- actor_type: "staff"
- metadata: created count, skipped count, error count, total rows processed

Fire-and-forget only. Never block on a failed log write.

---

## Verify after all changes
grep -n "address_line1\|existing_names\|csv_import_completed" app/api/clients.py
Confirm all three appear.
python -m py_compile app/api/clients.py
Must pass with no errors.

---

## Deploy sequence
git add -A
git commit -m "week 3 csv import expansion — 8 new fields plus name dedup"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager