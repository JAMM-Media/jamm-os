# STANDING RULES — READ FIRST, NEVER VIOLATE

- Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0 (Mapped[] syntax only), Pydantic v2, Alembic
- Every model: UUID primary key, firm_id FK, created_at + updated_at (timezone-aware)
- Every module: XBase, XCreate, XUpdate, XOut Pydantic schemas
- Routers are thin — zero business logic, ever
- All list endpoints use PaginatedResponse[T]
- Tenant isolation absolute — every query scoped to firm_id
- Service layer only for business logic and event logging
- Background tasks create their own SessionLocal() in try/finally — never inherit request session
- Never use native_enum=True for enums with dots or special characters
- Always use string names in relationship() to avoid circular imports
- Every generated file starts with a path comment

# MIGRATION RULES — FOLLOW EVERY TIME

1. alembic current — verify starting state (must be at 0034)
2. Write a clean manual migration — do NOT use autogenerate (it picks up noise from existing drift)
3. alembic upgrade head
4. alembic current — confirm at new head

# PHASE 0035 — RECURRING ENGAGEMENTS

## What we are building

A recurring engagement system. A firm configures a recurrence schedule on an engagement template. A daily scheduler job reads all active recurring templates and creates engagements automatically on a calendar-based cadence. The scheduler also auto-creates tasks and a document request from the template definition when it spawns a new engagement — same logic already used when a user manually applies a template.

This is infrastructure, not an automation rule. It does not live in the automations tab.

---

## STEP 1 — DATABASE MIGRATION

Create a clean manual migration file at:
`alembic/versions/0035_recurring_engagements.py`

Add the following four columns to the existing `engagement_templates` table:

```
is_recurring         BOOLEAN    NOT NULL DEFAULT FALSE
recurrence_cadence   VARCHAR(20) NULLABLE  -- values: 'monthly', 'quarterly', 'annually'
recurrence_day       INTEGER    NULLABLE  -- day of month (1-28) to create the engagement
recurrence_month     INTEGER    NULLABLE  -- month of year (1-12), only used when cadence = 'annually'
recurrence_advance_days INTEGER NULLABLE DEFAULT 14  -- how many days before due date to create it
last_spawned_at      TIMESTAMP WITH TIME ZONE NULLABLE  -- tracks when we last created an engagement from this template
```

Add a new table `recurring_engagement_log`:
```
id              UUID PRIMARY KEY DEFAULT gen_random_uuid()
firm_id         UUID NOT NULL FK → firms.id ON DELETE CASCADE
template_id     UUID NOT NULL FK → engagement_templates.id ON DELETE CASCADE
client_id       UUID NOT NULL FK → clients.id ON DELETE CASCADE
engagement_id   UUID NOT NULL FK → engagements.id ON DELETE CASCADE
spawned_at      TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
```

Add indexes:
- `engagement_templates.is_recurring` (for efficient scheduler query)
- `recurring_engagement_log.template_id`
- `recurring_engagement_log.firm_id`

---

## STEP 2 — UPDATE THE MODEL

File: `app/models/engagement_template.py`

Add the six new columns to the `EngagementTemplate` class using Mapped[] syntax:

```python
is_recurring: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
recurrence_cadence: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
recurrence_day: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
recurrence_month: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
recurrence_advance_days: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=14)
last_spawned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
```

Create a new model file: `app/models/recurring_engagement_log.py`

```python
# app/models/recurring_engagement_log.py
import uuid
from datetime import datetime, timezone
from sqlalchemy import ForeignKey, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.db.base_class import Base

class RecurringEngagementLog(Base):
    __tablename__ = "recurring_engagement_log"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    firm_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("firms.id", ondelete="CASCADE"), nullable=False, index=True)
    template_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagement_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    client_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    engagement_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False)
    spawned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
```

Import `RecurringEngagementLog` in `alembic/env.py` so it is present for future autogenerate runs.

---

## STEP 3 — UPDATE SCHEMAS

File: `app/schemas/engagement_template.py`

Add the new fields to `EngagementTemplateBase`:

```python
is_recurring: bool = False
recurrence_cadence: Optional[str] = None   # 'monthly', 'quarterly', 'annually'
recurrence_day: Optional[int] = None       # 1–28
recurrence_month: Optional[int] = None     # 1–12, annually only
recurrence_advance_days: Optional[int] = 14
```

Add a Pydantic validator to `EngagementTemplateBase` that enforces:
- If `is_recurring` is True, `recurrence_cadence` must be one of `monthly`, `quarterly`, `annually`
- If `is_recurring` is True, `recurrence_day` must be between 1 and 28
- If `recurrence_cadence` is `annually`, `recurrence_month` must be between 1 and 12

Add `last_spawned_at: Optional[datetime] = None` to `EngagementTemplateOut` only (read-only, not settable by clients).

Add `is_recurring` and `last_spawned_at` to `EngagementTemplateUpdate` as optional fields.

---

## STEP 4 — UPDATE CRUD

File: `app/crud/engagement_template.py`

Add one new function:

```python
def list_active_recurring_templates(db: Session) -> list[EngagementTemplate]:
    """Returns all recurring templates across all firms where is_recurring=True and is_active=True.
    Used exclusively by the scheduler job."""
    stmt = (
        select(EngagementTemplate)
        .where(EngagementTemplate.is_recurring == True)
        .where(EngagementTemplate.is_active == True)
    )
    return db.execute(stmt).scalars().all()
```

---

## STEP 5 — RECURRING SERVICE

Create: `app/services/recurring_engagement_service.py`

This is the scheduler job. It runs daily at 8:30 UTC (staggered from existing jobs at 8:00 and 8:15).

Logic:

```
def spawn_recurring_engagements() -> None:
    Creates its own SessionLocal() in try/finally.
    
    1. Call list_active_recurring_templates(db) — gets all recurring templates across all firms
    
    2. For each template, get all active clients for that firm:
       SELECT clients WHERE firm_id = template.firm_id AND is_active = True
    
    3. For each client, determine if we should spawn an engagement today:
       - Call should_spawn(template, client, db) — see logic below
    
    4. If should_spawn returns True:
       - Create an Engagement from the template fields:
         name = template.name
         description = template.description
         engagement_type = template.engagement_type
         firm_id = template.firm_id
         client_id = client.id
         status = "planning"
         start_date = today
         end_date = None (filing deadline handling below)
       
       - If template.engagement_type is set and maps to a known IRS deadline,
         set filing_deadline using the same deadline logic used in engagement creation.
         Do not duplicate that logic — import and call the existing deadline calculator
         from app/services/engagement_service.py or wherever it lives. If no such
         function exists, leave filing_deadline as None for now.
       
       - Create tasks from template.task_templates (same pattern as existing template apply logic)
       
       - If template.document_checklist is non-empty, create a DocumentRequest with
         those items (same pattern as existing template apply logic)
       
       - Write to recurring_engagement_log: template_id, client_id, engagement_id, firm_id
       
       - Update template.last_spawned_at = now() and commit
       
       - Fire-and-forget audit log: action="engagement.recurring_spawn",
         entity_type="engagement", entity_id=new_engagement.id, actor_type="system"
    
    5. Log summary: "Recurring engagement check complete: N engagements spawned"
    
    Wrap entire function in try/except/finally. Errors logged, never raised.
```

`should_spawn(template, client, db)` logic:

```
Determines whether today is the day to create a new recurring engagement for this client.

Rules:
1. Check recurring_engagement_log for this template + client combo.
   Get the most recent spawned_at date.

2. If never spawned before, check if today matches the spawn date:
   - monthly: today.day == template.recurrence_day
   - quarterly: today.day == template.recurrence_day AND today.month in [1,4,7,10]
   - annually: today.day == template.recurrence_day AND today.month == template.recurrence_month
   If it matches → spawn.

3. If previously spawned, check that enough time has elapsed since last spawn:
   - monthly: last_spawned_at < first day of current month
   - quarterly: last_spawned_at < first day of current quarter
   - annually: last_spawned_at.year < current year
   AND today matches the spawn day condition above.
   If both → spawn. Otherwise → skip.

4. Return True if spawn, False if skip.
```

---

## STEP 6 — WIRE SCHEDULER JOB

File: `app/main.py`

Add import:
```python
from app.services.recurring_engagement_service import spawn_recurring_engagements
```

Add to the scheduler in the lifespan function (after existing jobs):
```python
scheduler.add_job(
    spawn_recurring_engagements,
    trigger="cron",
    hour=8,
    minute=30,
    id="recurring_engagement_spawn",
    replace_existing=True,
)
```

---

## STEP 7 — FRONTEND: TEMPLATE CREATE/EDIT MODAL

File: `frontend/src/components/settings/EngagementTemplatesTab.tsx`
(or wherever the template create/edit modal lives — find it in the codebase)

Add a "Repeat" section to the template create and edit modals. This section appears below the existing fields.

UI spec:

**Toggle row:**
- Label: "Repeat this template on a schedule"
- Toggle switch (same style as automations tab). Default OFF.
- When OFF: all fields below are hidden.
- When ON: fields below appear.

**When toggle is ON, show:**

1. Cadence select (required):
   - Label: "Cadence"
   - Options: Monthly / Quarterly / Annually

2. Day of month (required):
   - Label: "Create on day"
   - Number input, 1–28. Helper text: "We cap at day 28 to avoid month-end issues."

3. Month of year (only shown when cadence = Annually):
   - Label: "Month"
   - Select: January through December (values 1–12)

4. Advance days (optional):
   - Label: "Create this many days before the due date"
   - Number input, default 14. Helper text: "Leave at 14 to give staff two weeks of lead time."
   - NOTE: This field is informational for now — it is stored but the scheduler currently creates on the exact cadence date, not N days before a due date. Do not implement advance-days offset logic in the scheduler yet. Just store the value.

All new fields are included in the create and update POST/PATCH payloads to the existing template endpoints. No new endpoints needed — the existing PATCH /api/v1/engagement-templates/{id} endpoint now accepts and persists the new fields.

---

## STEP 8 — FRONTEND: TEMPLATE LIST — RECURRING INDICATOR

In the template list (wherever templates are displayed in the Settings page), add a small "Recurring" pill badge next to the template name when `is_recurring = true`.

Badge spec: same pill style as other badges in the app. Use the blue status color (#DBEAFE bg, #1E40AF text). Text: "Recurring". 11px, weight 500.

Also show the cadence below the template name in muted text when is_recurring is true:
- monthly → "Repeats monthly on day {recurrence_day}"
- quarterly → "Repeats quarterly on day {recurrence_day}"
- annually → "Repeats annually on {month name} {recurrence_day}"

---

## STEP 9 — VERIFY

After all steps:
1. alembic current — confirm head is 0035
2. Confirm the scheduler job is registered in main.py at 8:30 UTC
3. Confirm the EngagementTemplate model has all 6 new fields
4. Confirm the recurring_engagement_log table exists in the DB
5. Confirm the frontend modal shows the Repeat toggle and fields
6. Restart: systemctl restart jammpx.service