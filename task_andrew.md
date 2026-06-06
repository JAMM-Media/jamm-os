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

PHASE INSTRUCTIONS — EMAIL AND CALENDAR INTEGRATION SESSION 1
Architecture migration + per-staff OAuth + firm toggle settings

This session establishes the foundation for full Gmail and Outlook inbox + calendar integration. It does NOT build the inbox UI or calendar UI -- those are Session 2 and Session 3. This session only:
1. Migrates the Integration model to support per-staff connections
2. Extends Gmail and Outlook OAuth scopes
3. Adds per-staff connect/callback endpoints
4. Adds firm-level toggle settings for email and calendar sync
5. Builds the "My Integrations" page where each staff member connects their own account

---

STEP 1 — MIGRATION

Current head: 0046_add_portal_domain_to_firms

Write a clean manual migration:

revision = '0047_per_staff_integrations'
down_revision = '0046_add_portal_domain_to_firms'

Changes:

A) Add user_id column to integrations table:
  op.add_column('integrations', sa.Column('user_id', sa.dialects.postgresql.UUID(as_uuid=True), nullable=True))

B) Add FK constraint for user_id:
  op.create_foreign_key('fk_integrations_user_id', 'integrations', 'users', ['user_id'], ['id'], ondelete='CASCADE')

C) Drop the old unique constraint (firm_id, provider):
  op.drop_constraint('uq_integration_firm_provider', 'integrations', type_='unique')

D) Create new unique constraint (firm_id, user_id, provider) -- user_id nullable so firm-level integrations (QBO) still have unique (firm_id, NULL, provider):
  op.create_unique_constraint('uq_integration_firm_user_provider', 'integrations', ['firm_id', 'user_id', 'provider'])

Note: PostgreSQL treats NULL as distinct in unique constraints, so multiple rows with user_id=NULL and the same firm_id+provider cannot exist without additional handling. Since QBO is firm-level and only one QBO per firm is expected, this is fine.

Run alembic upgrade head. Confirm at new head.

---

STEP 2 — MODEL: app/models/integration.py

Read the file first.

Add user_id field after firm_id:

    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PG_UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )

Update the __table_args__ UniqueConstraint:
  Old: UniqueConstraint("firm_id", "provider", name="uq_integration_firm_provider")
  New: UniqueConstraint("firm_id", "user_id", "provider", name="uq_integration_firm_user_provider")

Add relationship to User using string name to avoid circular imports:
    user: Mapped[Optional["User"]] = relationship("User", back_populates=None, foreign_keys=[user_id])

---

STEP 3 — CRUD: app/crud/integration.py

Read the file first.

Add a new function get_user_integration that looks up by firm_id + user_id + provider:

def get_user_integration(db: Session, firm_id: uuid.UUID, user_id: uuid.UUID, provider: str) -> Optional[Integration]:
    return db.execute(
        select(Integration).where(
            Integration.firm_id == firm_id,
            Integration.user_id == user_id,
            Integration.provider == provider,
        )
    ).scalar_one_or_none()

Add a new function create_user_integration that creates with user_id:

def create_user_integration(db: Session, firm_id: uuid.UUID, user_id: uuid.UUID, provider: str) -> Integration:
    integration = Integration(firm_id=firm_id, user_id=user_id, provider=provider, status="disconnected")
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration

Add a new function get_integrations_for_user:

def get_integrations_for_user(db: Session, firm_id: uuid.UUID, user_id: uuid.UUID) -> list[Integration]:
    return list(db.execute(
        select(Integration).where(
            Integration.firm_id == firm_id,
            Integration.user_id == user_id,
        )
    ).scalars().all())

---

STEP 4 — GMAIL SERVICE: app/services/gmail_service.py

Read the file first.

Update GMAIL_SCOPES to include inbox and calendar read access:

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar.readonly",
    "https://www.googleapis.com/auth/userinfo.email",
    "openid",
]

Update get_authorization_url to accept user_id in addition to firm_id. Encode both in the state parameter as "{firm_id}:{user_id}":

def get_authorization_url(self, firm_id: UUID, user_id: UUID) -> str:
    flow = self._build_flow()
    state = f"{firm_id}:{user_id}"
    authorization_url, _ = flow.authorization_url(
        access_type="offline",
        state=state,
        include_granted_scopes="true",
        prompt="consent",
    )
    return authorization_url

Update handle_callback to parse both firm_id and user_id from state, and use get_user_integration / create_user_integration:

def handle_callback(self, code: str, state: str, db: Session) -> Integration:
    try:
        firm_id_str, user_id_str = state.split(":")
        firm_id = UUID(firm_id_str)
        user_id = UUID(user_id_str)
    except (ValueError, AttributeError) as e:
        logger.error("Invalid state parameter: %s", type(e).__name__)
        raise ValueError("Invalid state parameter") from e

    integration = crud_integration.get_user_integration(db, firm_id=firm_id, user_id=user_id, provider=GMAIL_PROVIDER)
    if not integration:
        integration = crud_integration.create_user_integration(db, firm_id=firm_id, user_id=user_id, provider=GMAIL_PROVIDER)

    # Rest of token storage logic stays exactly the same

Add prompt="consent" to force Google to return a refresh token on every connect (without this, refresh tokens are only returned on first authorization).

---

STEP 5 — OUTLOOK SERVICE: app/services/outlook_service.py

Read the file first.

Update OUTLOOK_SCOPES to include inbox and calendar:

OUTLOOK_SCOPES = [
    "https://graph.microsoft.com/Mail.Read",
    "https://graph.microsoft.com/Mail.Send",
    "https://graph.microsoft.com/Calendars.Read",
    "https://graph.microsoft.com/User.Read",
    "offline_access",
]

Update get_authorization_url to accept user_id and encode state as "{firm_id}:{user_id}":

def get_authorization_url(self, firm_id: UUID, user_id: UUID) -> str:
    state = f"{firm_id}:{user_id}"
    # rest of method same but use state variable

Update handle_callback to parse both from state and use get_user_integration / create_user_integration. Same pattern as Gmail service update.

---

STEP 6 — BACKEND: New per-staff integration endpoints in app/api/integrations.py

Read the file first.

Add four new endpoints. These are staff-facing (any authenticated staff member can connect their own account):

-- GET /integrations/staff/gmail/connect --
Requires get_current_user (any role, not just firm_owner).
Creates or gets the integration for current_user.id + current_firm.id + "gmail".
Calls _gmail_service.get_authorization_url(current_firm.id, current_user.id)
Returns { "authorization_url": str }

-- GET /integrations/staff/gmail/callback --
No JWT required (Google calls this directly).
Calls _gmail_service.handle_callback(code, state, db) -- state now contains firm_id:user_id.
On success redirects to: {FRONTEND_URL}/settings/my-integrations?connected=gmail
On error redirects to: {FRONTEND_URL}/settings/my-integrations?error=gmail_failed

-- GET /integrations/staff/outlook/connect --
Same pattern as gmail/connect but for Outlook.
Calls _outlook_service.get_authorization_url(current_firm.id, current_user.id)
Returns { "authorization_url": str }

-- GET /integrations/staff/outlook/callback --
Same pattern as gmail/callback but for Outlook.
On success redirects to: {FRONTEND_URL}/settings/my-integrations?connected=outlook
On error redirects to: {FRONTEND_URL}/settings/my-integrations?error=outlook_failed

-- GET /integrations/staff/me --
Returns the current user's integrations. Requires get_current_user.
Calls crud_integration.get_integrations_for_user(db, firm_id=current_firm.id, user_id=current_user.id)
Returns list[IntegrationOut]

-- DELETE /integrations/staff/{provider} --
Disconnects the current user's integration for the given provider.
Finds integration by firm_id + user_id + provider. Clears tokens. Sets status disconnected.
Returns 204.

Keep all existing firm-level endpoints (gmail/connect, gmail/callback, outlook/connect, outlook/callback) unchanged -- they are still used for the firm-level signal extraction integrations (the existing Gmail/Outlook behavioral signal crons). The new staff/ endpoints are separate.

---

STEP 7 — FIRM SETTINGS: email and calendar sync toggles

These are stored in firm.settings JSON blob -- no migration needed.

In app/schemas/settings.py, add a new schema:

class EmailCalendarSyncUpdate(BaseModel):
    email_sync_enabled: bool | None = None
    calendar_sync_enabled: bool | None = None
    staff_can_disable_email_sync: bool | None = None
    staff_can_disable_calendar_sync: bool | None = None

In app/api/settings.py, add a new endpoint:

PATCH /settings/email-calendar-sync
Requires firm_owner.
Reads body as EmailCalendarSyncUpdate.
Merges into firm.settings JSON blob:
  if body.email_sync_enabled is not None: merged["email_sync_enabled"] = body.email_sync_enabled
  if body.calendar_sync_enabled is not None: merged["calendar_sync_enabled"] = body.calendar_sync_enabled
  if body.staff_can_disable_email_sync is not None: merged["staff_can_disable_email_sync"] = body.staff_can_disable_email_sync
  if body.staff_can_disable_calendar_sync is not None: merged["staff_can_disable_calendar_sync"] = body.staff_can_disable_calendar_sync
db.commit()
Return current_firm (FirmOut)

Import EmailCalendarSyncUpdate in app/schemas/settings.py imports.

---

STEP 8 — FRONTEND: My Integrations page

Create frontend/src/app/settings/my-integrations/page.tsx

This page is accessible to ALL staff (not just firm owners). It lives at /settings/my-integrations.

The page shows the current user's email integration status and lets them connect or disconnect.

On mount:
1. Fetch current user integrations: GET /api/v1/integrations/staff/me
2. Read URL params for ?connected=gmail, ?connected=outlook, ?error=gmail_failed, ?error=outlook_failed -- show toast accordingly
3. Read firm settings to check if email_sync_enabled and calendar_sync_enabled are true

Page layout:
- Heading: "My Integrations"
- Subtext: "Connect your email and calendar to JAMM PX. Your emails and calendar are private to you -- only you can see them."

Two integration cards: Gmail and Outlook. Each card shows:

IF firm has email_sync_enabled = false (from firm settings):
  Show gray "Email sync is disabled by your firm owner." message. No connect button.

IF connected (status = "connected"):
  - Green connected badge
  - Connected email address (from external_account_id)
  - "Disconnect" button: calls DELETE /api/v1/integrations/staff/{provider}, refreshes state

IF not connected:
  - "Connect Gmail" or "Connect Outlook" button
  - On click: GET /api/v1/integrations/staff/gmail/connect or /outlook/connect, then window.location.href = response.data.authorization_url

Style: same card pattern as other settings pages. Use the existing PortalBrandingTab or SendingDomainTab as the visual reference.

---

STEP 9 — FRONTEND: Firm owner email/calendar sync settings

Add a new section to the existing Firm tab in frontend/src/app/settings/page.tsx (or a new EmailSyncTab -- use a new tab called "Email & Calendar").

Create frontend/src/components/settings/EmailCalendarTab.tsx

This tab is firm_owner only.

It shows four toggle switches:

1. "Enable email sync" -- when on, staff can connect their Gmail/Outlook and see emails in JAMM PX. When off, the My Integrations page shows the disabled message.
   Key: email_sync_enabled (default: true)

2. "Enable calendar sync" -- when on, staff can sync their calendar events into JAMM PX.
   Key: calendar_sync_enabled (default: true)

3. "Allow staff to disable email sync" -- when on, individual staff members can opt out of email sync even when it's enabled firm-wide.
   Key: staff_can_disable_email_sync (default: true)

4. "Allow staff to disable calendar sync" -- same for calendar.
   Key: staff_can_disable_calendar_sync (default: true)

Each toggle calls PATCH /api/v1/settings/email-calendar-sync immediately on change (optimistic, revert on error).

Helper text under each toggle explaining what it does in plain English.

Wire into settings page: add { key: 'email_calendar', label: 'Email & Calendar' } to TABS after 'portal_domain'. firm_owner only. Render EmailCalendarTab.

---

STEP 10 — SIDEBAR: Add My Integrations link

In the sidebar navigation, add a link to /settings/my-integrations visible to all staff (not just firm owners). Place it in the Settings section or as a standalone item near the bottom of the sidebar, above Settings.

Find the sidebar component and add the link with a Plug or Link icon from lucide-react. Label: "My Integrations".

---

DO NOT forget the migration. This build requires alembic upgrade head on the droplet.

After completing confirm:
- Migration 0047 exists with user_id column, dropped old constraint, new constraint
- Integration model has user_id nullable FK
- Three new CRUD functions: get_user_integration, create_user_integration, get_integrations_for_user
- Gmail and Outlook scopes extended
- Both services updated to encode firm_id:user_id in state
- Six new endpoints in integrations.py (staff/gmail/connect, staff/gmail/callback, staff/outlook/connect, staff/outlook/callback, staff/me, staff/{provider} DELETE)
- EmailCalendarSyncUpdate schema and PATCH /settings/email-calendar-sync endpoint
- My Integrations page at /settings/my-integrations
- EmailCalendarTab.tsx with four toggles
- Settings page has Email & Calendar tab
- Sidebar has My Integrations link