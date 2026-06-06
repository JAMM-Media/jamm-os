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

PHASE INSTRUCTIONS — MOVE MY INTEGRATIONS FROM SIDEBAR TO SETTINGS TAB

No migrations. No backend changes. Two frontend files only.

---

CHANGE 1 — Remove My Integrations from sidebar

Read frontend/src/components/layout/Sidebar.tsx

Find and remove:
- The myIntegrationsItem constant definition
- The My Integrations Link block in the JSX
- The Plug import from lucide-react (only remove it if Plug is not used anywhere else in the file)
- The pathname !== myIntegrationsItem.href condition that was added to the Settings link active state -- revert that back to just pathname.startsWith(settingsItem.href)

---

CHANGE 2 — Add My Integrations as a tab in Settings page

Read frontend/src/app/settings/page.tsx

The My Integrations page already exists at /settings/my-integrations/page.tsx. Rather than routing to that page, inline the content as a tab component. The tab should render the same content -- but since the page already exists as a standalone route, the simplest approach is to add a tab that renders an iframe or just redirects. Actually the cleanest approach is:

Import the MyIntegrationsPage content inline. But since it uses AppShell which would nest wrong, instead:

1. Add { key: 'my_integrations', label: 'My Integrations' } to the TABS constant. Place it FIRST in the tab list, before 'profile', so it's the first tab all staff see.

2. This tab is visible to ALL roles -- do NOT add it to the firm_owner-only filter. Add it to the filter function with: if (tab.key === 'my_integrations') return true

3. Create a new inline component MyIntegrationsTabContent directly in settings/page.tsx (or import from a new file). This component replicates the logic from /settings/my-integrations/page.tsx but WITHOUT the AppShell wrapper -- just the inner content.

The component should:
- On mount fetch GET /api/v1/integrations/staff/me to get the user's current integrations
- Read URL search params for ?connected=gmail, ?connected=outlook, ?error=gmail_failed, ?error=outlook_failed and show toast accordingly
- Read firm settings to check email_sync_enabled (from useFetch on firm details)
- Show two cards: Gmail and Outlook

Each card:
- If email_sync_enabled is false in firm settings: show muted "Email sync is disabled by your firm owner."
- If connected (status = "connected"): green badge, email address shown, Disconnect button calling DELETE /api/v1/integrations/staff/{provider}
- If not connected: Connect button calling GET /api/v1/integrations/staff/gmail/connect or /outlook/connect, then window.location.href = response.data.authorization_url

Heading: "My Integrations"
Subtext: "Connect your Gmail or Outlook to JAMM PX. Your emails and calendar events are private to you."

Style: match existing settings tab cards exactly.

4. Render: {activeTab === 'my_integrations' && <MyIntegrationsTabContent />}

---

DO NOT run migrations. No backend changes. Two files only: Sidebar.tsx and settings/page.tsx

After completing confirm:
- My Integrations link removed from Sidebar.tsx
- Plug import removed from Sidebar.tsx if unused
- Settings link active state reverted to original
- my_integrations tab added to TABS as first item
- Tab visible to all roles
- MyIntegrationsTabContent component renders Gmail and Outlook connection cards