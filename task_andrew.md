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

1. alembic current -- confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full -- if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current -- confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

PHASE INSTRUCTIONS -- PER-STAFF INTEGRATION FIRM OVERRIDE

Firm owners can disable Gmail or Outlook integration for specific staff members independently of the firm-wide toggle. This is separate from the staff member's own opt-out (status = opted_out). Firm owner control uses a new firm_disabled boolean field.

---

STEP 1 -- MIGRATION

Current head: 0048_user_calendar_settings

Write a clean manual migration:
revision = '0049_integration_firm_disabled'
down_revision = '0048_user_calendar_settings'

Add one column to the integrations table:
  firm_disabled: BOOLEAN, nullable=False, server_default='false'

Run alembic upgrade head. Confirm at new head.

---

STEP 2 -- MODEL: app/models/integration.py

Read the file first.

Add after the status field:
    firm_disabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )

Import Boolean from sqlalchemy if not already imported.

---

STEP 3 -- SCHEMA: app/schemas/integration.py

Read the file. Add to IntegrationOut:
  firm_disabled: bool = False
  user_id: Optional[uuid.UUID] = None  -- add if not already present from session 1

---

STEP 4 -- CRUD: app/crud/integration.py

Read the file. Add two new functions:

def firm_disable_user_integration(db: Session, integration: Integration) -> Integration:
    integration.firm_disabled = True
    db.commit()
    db.refresh(integration)
    return integration

def firm_enable_user_integration(db: Session, integration: Integration) -> Integration:
    integration.firm_disabled = False
    db.commit()
    db.refresh(integration)
    return integration

---

STEP 5 -- BACKEND: New firm-owner endpoints in app/api/integrations.py

Read the file. Add two new endpoints:

-- POST /integrations/firm/{user_id}/{provider}/disable --
Requires require_firm_owner.
Looks up the integration by firm_id + user_id (from path) + provider.
If not found: return 404 "No integration found for this staff member."
Calls crud_integration.firm_disable_user_integration(db, integration).
Fires audit log: action="integration.firm_disabled", entity_type="integration", entity_id=integration.id, metadata={"provider": provider, "target_user_id": str(user_id)}
Returns IntegrationOut.

-- POST /integrations/firm/{user_id}/{provider}/enable --
Same pattern. Calls firm_enable_user_integration.
Fires audit log: action="integration.firm_enabled"
Returns IntegrationOut.

-- GET /integrations/firm/staff --
Requires require_firm_owner.
Returns all per-staff integrations for the firm (user_id is not null).
Calls: db.execute(select(Integration).where(Integration.firm_id == current_firm.id, Integration.user_id != None)).scalars().all()
Returns list[IntegrationOut].

---

STEP 6 -- INBOX API: Respect firm_disabled

Read app/api/inbox.py. In the _get_integration helper function that looks up the integration, after finding the integration record, add a check:

If integration.firm_disabled is True, raise HTTPException(status_code=403, detail="Email sync has been disabled for your account by your firm owner.")

This means if a firm owner disables a staff member's inbox, that staff member gets a clear error when trying to use it rather than a confusing failure.

---

STEP 7 -- FRONTEND: Per-staff controls in EmailCalendarTab

Read frontend/src/components/settings/EmailCalendarTab.tsx in full.

The tab currently shows four firm-wide toggles. Add a new section below them: "Staff Email Integration Controls".

This section:
1. On mount, fetches GET /api/v1/integrations/firm/staff to get all per-staff integrations
2. Also fetches GET /api/v1/users/ to get the staff list with names
3. Groups integrations by user_id, showing one row per staff member who has at least one integration

Staff member row layout:
- Staff name and email (from users list)
- Two status pills: one for Gmail, one for Outlook
  - If no integration record exists for that provider: gray pill "Not connected"
  - If integration exists and firm_disabled=false and status=connected: green pill "Active"
  - If integration exists and status=opted_out: amber pill "Paused by staff"
  - If integration exists and firm_disabled=true: red pill "Disabled by firm"
- Two toggle buttons per provider (Gmail / Outlook):
  - If firm_disabled=false: show "Disable" button (ghost, small, red text on hover)
  - If firm_disabled=true: show "Enable" button (ghost, small, brand color)
  - If no integration exists for that provider: show nothing (staff hasn't connected yet)
  - Disable calls POST /api/v1/integrations/firm/{user_id}/{provider}/disable
  - Enable calls POST /api/v1/integrations/firm/{user_id}/{provider}/enable
  - Optimistic update -- toggle immediately, revert on error with toast

Section heading: "Staff Integration Controls"
Subtext: "Manage email and calendar sync access for individual staff members. This overrides their personal connection -- disabling here prevents them from using their inbox in JAMM PX regardless of whether they have connected."

Empty state (no staff have connected anything yet): "No staff have connected their email yet. Controls will appear here once staff connect their Gmail or Outlook from My Integrations."

Loading state: skeleton rows.

Style: same card pattern as the rest of the tab. Separate card below the four toggles with a divider between them.

---

STEP 8 -- SIDEBAR: Respect firm_disabled

Read frontend/src/components/layout/Sidebar.tsx.

The sidebar currently hides Inbox when email_sync_enabled is false (firm-wide). Extend this to also hide Inbox for the current user if their integration is firm_disabled.

The sidebar already fetches firm settings via useQuery. Add a second query:

const { data: myIntegrations } = useQuery({
  queryKey: ['my-integrations-sidebar'],
  queryFn: () => api.get('/api/v1/integrations/staff/me').then((r) => r.data),
  staleTime: 5 * 60 * 1000,
})

const myEmailDisabledByFirm = Array.isArray(myIntegrations) && myIntegrations.some(
  (i: { provider: string; firm_disabled: boolean }) =>
    (i.provider === 'gmail' || i.provider === 'outlook') && i.firm_disabled
)

Update the visibleNavItems filter:
if (item.href === '/inbox') return emailSyncEnabled && !myEmailDisabledByFirm

---

DO NOT skip the migration. Requires alembic upgrade head on the droplet.

After completing confirm:
- Migration 0049 exists with firm_disabled boolean on integrations
- Integration model has firm_disabled field
- IntegrationOut schema has firm_disabled field
- Two new CRUD functions: firm_disable_user_integration, firm_enable_user_integration
- Three new endpoints: POST /integrations/firm/{user_id}/{provider}/disable, POST .../enable, GET /integrations/firm/staff
- _get_integration in inbox.py returns 403 when firm_disabled is true
- EmailCalendarTab has Staff Integration Controls section with per-staff disable/enable
- Sidebar hides Inbox when firm_disabled is true for current user's integration