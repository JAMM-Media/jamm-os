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

# PHASE INSTRUCTIONS — TOGGLE DOT SIZE FIX

## Context
One fix only in frontend/src/components/settings/SecurityTab.tsx.
No other files. No backend. No migration.

The toggle track is w-9 h-5 (36x20px).
The dot is currently w-4 h-4 (16px) which is too large for the track.
Positions translate-x-[19px] off and translate-x-1 on are also wrong.

---

## VERIFY BEFORE STARTING
grep -n "translate-x-\|w-4 h-4\|absolute top" frontend/src/components/settings/SecurityTab.tsx
Paste output before touching anything.

---

## Fix: Correct dot size and position

Find exactly:
                  'absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform',
                  value ? 'translate-x-[19px]' : 'translate-x-1',

Replace with:
                  'absolute top-[3px] left-[3px] w-3.5 h-3.5 rounded-full bg-white shadow transition-transform',
                  value ? 'translate-x-[16px]' : 'translate-x-0',

---

## Verify
grep -n "translate-x-\[16px\]\|w-3.5 h-3.5\|left-\[3px\]" frontend/src/components/settings/SecurityTab.tsx
All three must appear.
cd frontend
npx tsc --noEmit

---

## Deploy
git add -A
git commit -m "fix toggle dot size and position"
git push origin main