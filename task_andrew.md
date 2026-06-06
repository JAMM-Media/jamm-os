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

# PHASE INSTRUCTIONS — SECURITY TAB UI FIXES

## Context
Three bugs to fix in SecurityTab.tsx only.
No backend changes. No other files touched.

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before security tab ui fixes"

---

## VERIFY BEFORE STARTING
grep -n "translate-x-4\|translate-x-0\|w-16\|Number(e.target" frontend/src/components/settings/SecurityTab.tsx
Paste output before touching anything.

---

## Fix 1: Toggle sliding outside container

Find every toggle button in the password policy section.
The toggle button currently has:
  className={cn('relative w-9 h-5 rounded-full transition-colors flex-shrink-0', ...)}

Add overflow-hidden to the button className so the sliding dot stays clipped:
  className={cn('relative w-9 h-5 rounded-full transition-colors flex-shrink-0 overflow-hidden', ...)}

There are three toggle buttons (uppercase, number, special character).
Apply overflow-hidden to all three.

---

## Fix 2: Number input text too faint

Find every number input in the password policy section.
There are two: minLength and maxFailedAttempts.

Both currently have className containing bg-white.
Add text-[#1F3148] to each input className so the text is visible:

Change:
  className="w-16 text-center text-[13px] rounded-[6px] border border-[#C8CDD6] bg-white px-2 py-1 outline-none focus:border-[#1F3148]"

To:
  className="w-16 text-center text-[13px] text-[#1F3148] rounded-[6px] border border-[#C8CDD6] bg-white px-2 py-1 outline-none focus:border-[#1F3148]"

Apply to both number inputs.

---

## Fix 3: Number input showing 0 when typing double digits

The issue is that Number("12") works fine but the controlled input
loses the value mid-type because Number("1") then Number("12") causes
a re-render that resets to 0 in some cases.

Fix: change both onChange handlers to use parseInt with a fallback:

For minLength input, change:
  onChange={(e) => setMinLength(Number(e.target.value))}
To:
  onChange={(e) => { const v = parseInt(e.target.value, 10); if (!isNaN(v)) setMinLength(v) }}

For maxFailedAttempts input, change:
  onChange={(e) => setMaxFailedAttempts(Number(e.target.value))}
To:
  onChange={(e) => { const v = parseInt(e.target.value, 10); if (!isNaN(v)) setMaxFailedAttempts(v) }}

---

## Verify after all changes
grep -n "overflow-hidden\|text-\[#1F3148\]\|parseInt" frontend/src/components/settings/SecurityTab.tsx
Confirm overflow-hidden appears 3 times, text-[#1F3148] appears on both inputs, parseInt appears twice.

Check TypeScript:
cd frontend
npx tsc --noEmit
Zero errors required before deploying.

---

## Deploy sequence
git add -A
git commit -m "security tab password policy ui fixes"
git push origin main
Frontend deploys automatically via Vercel. No backend deploy needed.