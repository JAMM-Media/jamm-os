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

# PHASE INSTRUCTIONS — WEEK 3, RUN 2 OF 3: ENGAGEMENT STATUS MODEL + MIGRATION

## Context
We are adding two new fields to the Engagement model and a new status value.
This enables the Option 2 e-file acknowledgment workflow decided in planning.
The .ack parser endpoint that writes to these fields comes in Run 3.
This run is the data model only — no new endpoints, no frontend changes.
Current alembic head: 0040_add_billing_detail_reports

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before week 3 engagement efiled model"

---

## VERIFY BEFORE STARTING
grep -n "class Engagement\|filing_deadline\|extended_deadline\|class EngagementStatus" app/models/engagement.py
grep -n "EngagementStatus\|acknowledged" app/core/enums.py
Paste both outputs before touching anything.

---

## Change 1: Add EFILEABLE_ENGAGEMENT_TYPES constant to app/core/enums.py

Find the end of the existing enum and constant definitions in app/core/enums.py.
Add this constant after the existing enums — do not modify any existing enum:

EFILEABLE_ENGAGEMENT_TYPES = {
    "tax_return_1040",
    "tax_return_1120",
    "tax_return_1120s",
    "tax_return_1065",
    "tax_return_990",
    "tax_return_941",
    "tax_return_940",
    "tax_return_720",
    "tax_return_2290",
    "tax_return_706",
    "tax_return_709",
}

This is the single authoritative list of engagement types that go through
IRS e-file and therefore can receive an IRS acknowledgment.
Every other part of the codebase imports from here — never duplicates this list.

---

## Change 2: Add acknowledged to EngagementStatus enum in app/core/enums.py

Find the EngagementStatus enum. It currently has values including
planning, in_progress, review, complete, archived.
Add acknowledged as a new value:

    acknowledged = "acknowledged"

Place it after complete and before archived.
Use native_enum=False if this enum uses sa.Enum — check before editing.

---

## Change 3: Add two new fields to the Engagement model in app/models/engagement.py

Find the Engagement model class.
Add these two fields after the extended_deadline field:

    efiled_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    irs_confirmation_number: Mapped[Optional[str]] = mapped_column(
        String(100), nullable=True
    )

Both are nullable. No default. No index needed.
Import Optional from typing if not already imported at the top of the file.

---

## Change 4: Add is_efileable property to Engagement model

After the two new fields, add this property:

    @property
    def is_efileable(self) -> bool:
        from app.core.enums import EFILEABLE_ENGAGEMENT_TYPES
        return self.engagement_type in EFILEABLE_ENGAGEMENT_TYPES

This is the single place the codebase checks whether an engagement
can receive an IRS acknowledgment. The parser in Run 3 uses this.
The morning briefing will use this. Nothing else duplicates this logic.

---

## Change 5: Update EngagementOut schema in app/schemas/engagement.py

Find the EngagementOut schema.
Add these two fields:

    efiled_at: Optional[datetime] = None
    irs_confirmation_number: Optional[str] = None

Import Optional and datetime at the top if not already present.
Do not change any other schema.

---

## Change 6: Run the migration

First confirm starting head:
alembic current

Generate the migration:
alembic revision --autogenerate -m "0041_engagement_efiled_fields"

Read the generated file in full before running upgrade.
The migration should contain exactly two operations:
- Add column efiled_at to engagements table (nullable timestamp with timezone)
- Add column irs_confirmation_number to engagements table (nullable varchar 100)

If it contains anything else — any other table, any drop operation,
anything unexpected — delete the file and write a clean manual migration instead.

If the generated migration looks correct, run:
alembic upgrade head
alembic current
Confirm head is now 0041_engagement_efiled_fields.

Note: the acknowledged status value is added to an enum.
If EngagementStatus uses native_enum=True in PostgreSQL, the migration
will also need an ALTER TYPE statement to add the new value.
If it uses native_enum=False (sa.Enum with values list), no enum migration
is needed — the value is stored as a string.
Check which approach is used before running upgrade and handle accordingly.

---

## Verify after all changes
grep -n "efiled_at\|irs_confirmation_number\|is_efileable" app/models/engagement.py
grep -n "acknowledged\|EFILEABLE_ENGAGEMENT_TYPES" app/core/enums.py
grep -n "efiled_at\|irs_confirmation_number" app/schemas/engagement.py
python -m py_compile app/models/engagement.py
python -m py_compile app/core/enums.py
python -m py_compile app/schemas/engagement.py
All three compiles must pass before deploying.

---

## Deploy sequence
git add -A
git commit -m "week 3 engagement efiled fields and acknowledged status"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager