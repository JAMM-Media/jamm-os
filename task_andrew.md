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

PHASE INSTRUCTIONS -- FIX INBOX BUILD ERROR + SIDEBAR VISIBILITY + PER-STAFF OPT-OUT

No migrations. No backend changes. Three frontend files.

---

FIX 1 -- Inbox page Suspense boundary (Vercel build error)

Read frontend/src/app/(dashboard)/inbox/page.tsx

The page uses useSearchParams() directly in the top-level component. Next.js App Router requires useSearchParams() to be wrapped in a Suspense boundary or it fails to build.

Fix: Extract the part of the component that uses useSearchParams() into a separate inner component called InboxContent. Wrap it in <Suspense fallback={<div />}> in the default export.

The default export should look like:

export default function InboxPage() {
  return (
    <Suspense fallback={<div />}>
      <InboxContent />
    </Suspense>
  )
}

Move all the existing page logic into InboxContent. Import Suspense from 'react'.

Same fix needed in frontend/src/app/settings/my-integrations/page.tsx if it also uses useSearchParams() directly -- read it and apply the same pattern if so.

Also check frontend/src/app/settings/page.tsx -- it now has a MyIntegrationsTabContent component that uses useSearchParams(). Wrap that component's useSearchParams call in a useEffect or wrap the component itself in Suspense where it is rendered. The simplest fix: in MyIntegrationsTabContent, replace the useSearchParams() usage with a useEffect that reads window.location.search directly, avoiding the need for Suspense entirely.

Specifically in MyIntegrationsTabContent:
- Remove the useSearchParams import if it is only used there
- Replace the searchParams effect with:

useEffect(() => {
  if (typeof window === 'undefined') return
  const params = new URLSearchParams(window.location.search)
  const connected = params.get('connected')
  const error = params.get('error')
  if (connected === 'gmail') toast.success('Gmail connected successfully.')
  if (connected === 'outlook') toast.success('Outlook connected successfully.')
  if (error === 'gmail_failed') toast.error('Gmail connection failed. Please try again.')
  if (error === 'outlook_failed') toast.error('Outlook connection failed. Please try again.')
}, [])

---

FIX 2 -- Sidebar inbox visibility based on firm setting AND per-staff opt-out

Read frontend/src/components/layout/Sidebar.tsx

The sidebar needs to hide the Inbox link when:
- Firm owner has email_sync_enabled = false (firm-wide disable), OR
- The current staff member has personally opted out (inbox_disabled stored in their user settings)

Add a useQuery for firm settings right after the existing notifications useQuery:

const { data: firmData } = useQuery({
  queryKey: ['firm-settings-sidebar'],
  queryFn: () => api.get('/api/v1/firms/me').then((r) => r.data),
  staleTime: 5 * 60 * 1000,
})

Derive visibility:
  const emailSyncEnabled = firmData?.settings?.email_sync_enabled !== false
  const userInboxDisabled = user?.settings?.inbox_disabled === true
  const showInbox = emailSyncEnabled && !userInboxDisabled

Update the visibleNavItems filter:
  if (item.href === '/inbox') return showInbox

Place this after the dashboard condition.

---

FIX 3 -- Per-staff inbox opt-out in My Integrations tab

The User model has a settings JSON field (check the model -- if it does not exist yet, store the opt-out in the Integration model's status field instead: set status to "disabled" to mean opted out by staff, "connected" to mean active).

Actually: use the Integration model. When a staff member opts out, set integration.status = "opted_out". When they opt back in, set it back to "connected" or create a new connection.

In the backend, add one new endpoint to app/api/integrations.py:

POST /integrations/staff/{provider}/disable
Requires get_current_user. Finds the user's integration for that provider. If not found, create one with status "opted_out". If found, set status = "opted_out". db.commit(). Return 200.

POST /integrations/staff/{provider}/enable  
Requires get_current_user. Finds the user's integration. Sets status = "connected" if previously opted_out. If no integration exists, redirect them to connect flow (return 400 "No integration connected. Connect first."). db.commit(). Return 200.

In frontend/src/app/settings/page.tsx, update MyIntegrationsTabContent:

The firm owner may allow or disallow staff from opting out, controlled by staff_can_disable_email_sync in firm settings.

For each provider card, when the staff member is connected (status = "connected"):
- If firmData.settings.staff_can_disable_email_sync is true (or missing): show a small "Pause inbox" link below the Disconnect button. Clicking it calls POST /api/v1/integrations/staff/{provider}/disable and refreshes state. When status is "opted_out", show "Resume inbox" link instead.
- If staff_can_disable_email_sync is false: do not show the pause/resume option.

When status is "opted_out":
- Show an amber badge "Paused" instead of the green "Connected" badge
- Show "Resume inbox" button that calls the enable endpoint

Update the sidebar FIX 2 to also check for opted_out status:
  const userInboxDisabled = integrations?.some(i => i.status === 'opted_out') ?? false

But the sidebar does not fetch integrations. Keep it simple: the sidebar hides Inbox only on the firm-level toggle. The per-staff opt-out is handled by the Inbox page itself showing an appropriate message when all integrations are opted_out.

So for FIX 2: only check emailSyncEnabled (firm level). The per-staff opted_out state is visible within the Inbox page and My Integrations tab, not the sidebar.

---

DO NOT run migrations. No schema changes.

After completing confirm:
- Inbox page wraps InboxContent in Suspense
- settings/page.tsx MyIntegrationsTabContent uses window.location.search instead of useSearchParams
- my-integrations/page.tsx wrapped in Suspense if it uses useSearchParams
- Sidebar hides Inbox when email_sync_enabled is false
- Two new endpoints: POST /integrations/staff/{provider}/disable and /enable
- MyIntegrationsTabContent shows Pause/Resume option when staff_can_disable_email_sync allows it