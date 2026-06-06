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

PHASE INSTRUCTIONS — FIX ENGAGEMENT TEMPLATE RESPONSE VALIDATION ERROR

No migration required. One file only: app/schemas/engagement_template.py

The problem: EngagementTemplateOut inherits from EngagementTemplateBase, which contains a model_validator that raises a ValueError when is_recurring is True but recurrence_cadence is invalid. This validator fires during response serialization, which means existing database records with bad data cause the entire list endpoint to blow up with a ResponseValidationError. Validation should only run on input, not on output.

The fix: Remove the validate_recurrence model_validator from EngagementTemplateBase entirely. Add it to EngagementTemplateCreate instead, so it only runs when a new template is being created. Also add it to EngagementTemplateUpdate with a model_validator that only fires the recurrence check when is_recurring is explicitly set to True in the update payload.

Read app/schemas/engagement_template.py first.

-- In EngagementTemplateBase --

Remove the entire validate_recurrence model_validator method from EngagementTemplateBase. The base class should have no validators -- only fields.

-- In EngagementTemplateCreate --

EngagementTemplateCreate currently just has pass. Add the validator here:

    @model_validator(mode='after')
    def validate_recurrence(self) -> 'EngagementTemplateCreate':
        if self.is_recurring:
            if self.recurrence_cadence not in ('monthly', 'quarterly', 'annually'):
                raise ValueError("recurrence_cadence must be 'monthly', 'quarterly', or 'annually' when is_recurring is True")
            if self.recurrence_day is None or not (1 <= self.recurrence_day <= 28):
                raise ValueError("recurrence_day must be between 1 and 28 when is_recurring is True")
        if self.recurrence_cadence == 'annually':
            if self.recurrence_month is None or not (1 <= self.recurrence_month <= 12):
                raise ValueError("recurrence_month must be between 1 and 12 when cadence is 'annually'")
        return self

-- In EngagementTemplateUpdate --

Add a model_validator that only checks recurrence when is_recurring is explicitly True in the update:

    @model_validator(mode='after')
    def validate_recurrence(self) -> 'EngagementTemplateUpdate':
        if self.is_recurring is True:
            if self.recurrence_cadence not in ('monthly', 'quarterly', 'annually'):
                raise ValueError("recurrence_cadence must be 'monthly', 'quarterly', or 'annually' when is_recurring is True")
            if self.recurrence_day is None or not (1 <= self.recurrence_day <= 28):
                raise ValueError("recurrence_day must be between 1 and 28 when is_recurring is True")
        if self.recurrence_cadence == 'annually':
            if self.recurrence_month is None or not (1 <= self.recurrence_month <= 12):
                raise ValueError("recurrence_month must be between 1 and 12 when cadence is 'annually'")
        return self

EngagementTemplateOut inherits from EngagementTemplateBase and must have NO validators -- it should serialize whatever is in the database without raising errors.

DO NOT run migrations. One file change only.

After completing confirm:
- validate_recurrence removed from EngagementTemplateBase
- validate_recurrence added to EngagementTemplateCreate
- validate_recurrence added to EngagementTemplateUpdate
- EngagementTemplateOut unchanged