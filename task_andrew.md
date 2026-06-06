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

PHASE INSTRUCTIONS — NPS TOGGLE + QBO DEEP LINK BUTTON

No new database models or migrations required. Two self-contained changes: one small backend schema update + one frontend-only change for the toggle, and one frontend-only change for the QBO button.

---

CHANGE 1 — NPS ENABLE/DISABLE TOGGLE

The review requests feature is gated on firm.feature_flags.review_requests_enabled. Currently the settings UI has a Google Review URL field but no way to turn the feature on or off. Add a toggle.

-- Backend: app/schemas/settings.py --

Find ReviewSettingsUpdate. It currently has one field: google_review_url. Add a second field:
  review_requests_enabled: bool | None = None

-- Backend: app/api/settings.py --

Find the update_review_settings endpoint (PATCH /review). It currently only handles google_review_url. Add handling for review_requests_enabled:

After the existing google_review_url merge logic, add:
  if body.review_requests_enabled is not None:
      existing_flags = current_firm.feature_flags or {}
      current_firm.feature_flags = {**existing_flags, "review_requests_enabled": body.review_requests_enabled}

The feature_flags field is a separate JSON column from settings. Do not merge it into the settings dict. Assign directly to current_firm.feature_flags.

-- Frontend: frontend/src/app/settings/page.tsx --

In the Review Requests card (inside the Firm tab, firm_owner only):

1. Add state for the toggle:
   const [reviewEnabled, setReviewEnabled] = useState(false)

2. In the existing useEffect that reads firmData.settings, also read the feature flag:
   setReviewEnabled(firmData?.feature_flags?.review_requests_enabled === true)

3. Include reviewEnabled in the handleSaveReviewSettings PATCH call:
   await api.patch('/settings/review', {
     google_review_url: googleReviewUrl || null,
     review_requests_enabled: reviewEnabled,
   })

4. Add the toggle UI inside the Review Requests card, above the Google Review Link field. Use the exact same toggle pattern as SecurityTab.tsx (the custom toggle switch with overflow-hidden, translate-x-[16px] on, translate-x-0 off, w-3.5 h-3.5 dot). Label: "Enable review requests". Helper text below toggle: "When enabled, clients who rate their experience 9 or 10 will be prompted to leave a Google review after an engagement is marked complete."

---

CHANGE 2 — QBO DEEP LINK BUTTON

The client profile page shows the QuickBooks Customer ID field. When a client has a quickbooksCustomerId set, add an "Open in QuickBooks" button next to it that calls the existing backend endpoint and opens the returned URL in a new tab.

-- Frontend: frontend/src/app/clients/[id]/page.tsx --

Find the QuickBooks Customer ID display section. It currently shows the ID value and a pencil edit button when not in edit mode.

In the non-edit-mode display row, after the existing pencil button, add an "Open in QuickBooks" button that:
- Only renders when client.quickbooksCustomerId is truthy (same condition as the existing pencil button)
- On click: calls GET /api/v1/integrations/quickbooks/deep-link/client/{client.id}
- On success: opens response.data.url in a new tab via window.open(url, '_blank')
- On error: shows toast.error('Could not open QuickBooks link.')
- Has its own loading state (small inline spinner while the request is in flight)
- Button style: same ghost style as other secondary actions on the page -- text-[12px] text-[#6B7280] hover:text-brand, with a small ExternalLink icon from lucide-react (h-3.5 w-3.5) to the left of the label "Open in QuickBooks"

Do not add a new useState import if one already exists -- just add the new state variable alongside existing ones.

---

DO NOT run migrations -- no schema changes to the database tables in this build. feature_flags is an existing JSON column, no migration needed.

After completing all steps confirm:
- ReviewSettingsUpdate schema has review_requests_enabled field
- PATCH /review endpoint handles review_requests_enabled and writes to current_firm.feature_flags
- Settings page has toggle wired to reviewEnabled state, included in save call
- Client profile has Open in QuickBooks button, only shown when quickbooksCustomerId exists, calls correct endpoint