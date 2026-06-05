STANDING RULES — ALWAYS FOLLOW THESE

Product name is JAMM PX. Never refer to it as JAMM OS.

Domain language — never substitute synonyms:
Firm = the accounting business. Client = the firm's customer. Engagement = unit of billable work, never "project". Task = discrete action item. Staff = firm employees. Firm Owner = admin-level user.

Tech stack — never deviate without explicit instruction:
Backend: FastAPI, PostgreSQL, SQLAlchemy ORM 2.0 (Mapped[] syntax only), Pydantic v2 (model_dump() and field_validator() only), Alembic, Uvicorn + Gunicorn, APScheduler, Argon2, JWT via python-jose, slowapi.
Frontend: Next.js 14+ App Router, TypeScript always, Tailwind CSS, shadcn/ui, Axios with JWT interceptor, TanStack Query.

Architecture rules — enforce always:
- Every model must have: UUID primary key, firm_id FK, created_at and updated_at (timezone-aware).
- Every module must have 4 Pydantic schemas: XBase, XCreate, XUpdate, XOut.
- Routers are thin — no business logic ever.
- All list endpoints paginated using PaginatedResponse[T].
- RBAC enforced at every endpoint.
- Tenant isolation is absolute — every query scoped to firm_id without exception.
- Signed URLs only for all file access — never public S3 URLs, 1 hour maximum expiry.
- Audit logging on every sensitive action.
- Always use string names in relationship() to avoid circular imports.
- Every generated file starts with a path comment.
- Background tasks that touch the database must create their own SessionLocal() session in a try/finally block — never pass the request's db session into a background task.
- Never use native_enum=True for enums whose values contain dots or special characters. Always use sa.Enum(MyEnum, native_enum=False).

Migration procedure — follow every time:
1. alembic current — verify starting state
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

Behavioral event log rules:
- Fire-and-forget writes only. A failed event log write never surfaces as an error to the user.
- Never block the main operation.
- Service layer only — never in routers, never in CRUD.
- Own session — the logging utility creates its own database session in a try/finally block, never inherits the request session.

Security checklist — every module:
Verify before marking complete: tenant isolation, RBAC, audit log, input validation, no sensitive data in logs, signed URLs, tests covering happy path and edge cases, tenant isolation test proving Firm A cannot access Firm B data.

Windows / PowerShell:
- No && chaining — separate commands
- Quoted paths for directories with parentheses
- Separate git add commands for paths with special characters

---

PHASE-SPECIFIC INSTRUCTIONS — Fee schedule complexity adders

Three parts: backend migration, settings UI extension, send letter modal update + engagement detail display.

---

PART 1 — BACKEND MIGRATION

Add one nullable JSONB column to the engagements table.

Step 1 — Add the field to app/models/engagement.py:

    from sqlalchemy.dialects.postgresql import JSONB

    complexity_flags: Mapped[dict | None] = mapped_column(
        JSONB,
        nullable=True,
        default=None,
        comment="Complexity flags selected at engagement letter send. Keys are flag names, values are selected tier label or True for fixed flags.",
    )

Step 2 — Add complexity_flags to EngagementBase in app/schemas/engagement.py:

    from typing import Optional, List, Any
    complexity_flags: Optional[dict] = None

Step 3 — Add a PATCH endpoint to app/api/engagements.py that allows updating complexity_flags on an existing engagement. Requires manager_or_above. Fires a behavioral event with event_type "engagement.complexity_flags_updated", metadata includes engagement_id, engagement_type, flags, and actor_id.

Step 4 — Run the migration:
    alembic revision --autogenerate -m "add_complexity_flags_to_engagements"
    Read the generated file in full. If it contains anything beyond adding the complexity_flags column, delete it and write a clean manual migration.
    alembic upgrade head
    alembic current

---

PART 2 — SETTINGS: EXTEND FeeScheduleTab

File: frontend/src/components/settings/FeeScheduleTab.tsx

The current component renders base fees per engagement type. Extend it to add a second section below the existing base rate section titled "Complexity Adders".

The complexity adder configuration is stored in firm.settings.fee_schedule under a key called "complexity_adders". It is a nested object. On load, read it from firmSettings?.fee_schedule?.complexity_adders. On save, merge it back into the fee_schedule object alongside the existing engagement type keys.

The ten fixed flags — each gets a simple dollar input, same style as the base rate inputs:
- rental_property: "Rental Property"
- foreign_accounts_fbar: "Foreign Accounts / FBAR"
- depreciation_schedules: "Depreciation Schedules"
- home_office: "Home Office Deduction"
- multiple_states: "Multiple States"
- trust_estate_involvement: "Trust or Estate Involvement"
- business_sale: "Business Sale or Disposition"
- equity_compensation: "Equity Compensation / ISO / RSU"

The two tiered flags — K-1s and crypto get a tier builder instead of a single dollar input:
- k1_involvement: "K-1 Involvement"
- crypto: "Cryptocurrency Transactions"

Tier builder UI for each tiered flag:
- Shows a list of tiers the firm has defined. Each tier row has: a text input for the tier label (e.g. "1-3 K-1s", "Simple exchange") and a dollar input for the amount.
- An "+ Add Tier" button below the list adds a new empty tier row.
- A small X button on each row removes that tier.
- Minimum 0 tiers (firm may leave it empty). No maximum.
- Tiers are stored as an array of objects: [{ label: string, amount: string }]

Store the full complexity_adders structure as:
{
  rental_property: "150",
  foreign_accounts_fbar: "200",
  ...other fixed flags...,
  k1_involvement: [{ label: "1-3 K-1s", amount: "100" }, { label: "4+ K-1s", amount: "250" }],
  crypto: [{ label: "Simple exchange", amount: "75" }, { label: "Multiple wallets", amount: "200" }]
}

The Save Fee Schedule button at the bottom saves everything — base rates and complexity adders together — in a single PATCH to /users/firm/settings with the full fee_schedule object.

---

PART 3 — SEND ENGAGEMENT LETTER MODAL

File: frontend/src/components/engagements/SendEngagementLetterModal.tsx

The modal already fetches firm settings and auto-populates feeAmount from fee_schedule[engagementType]. Extend it to add a complexity flags section in the template mode flow, between the fee amount field and the bottom helper text paragraph.

Add a complexityAdders state that reads from the fetched firm settings: the complexity_adders object from fee_schedule. Add a selectedFlags state: Record<string, string | true> — keys are flag names, values are either true (fixed flag checked) or the tier label string (tiered flag with tier selected).

Complexity flags section layout:
- Section label: "Complexity" — 11px uppercase muted, same style as the auto-populated preview label
- A checklist of all ten flags. Each row: a checkbox on the left, the flag label on the right.
- When a fixed flag is checked, add its dollar amount to the running fee total.
- When k1_involvement or crypto is checked, a second inline dropdown appears immediately below that row showing the firm's configured tiers for that flag. Selecting a tier adds that tier's dollar amount to the total. If no tiers are configured for that flag, checking it shows a small muted note: "No tiers configured — set them in Settings → Fee Schedule."
- Only show the complexity section if complexity_adders has at least one key with a value.

Fee recalculation: the feeAmount field is editable by the firm, but it should recalculate automatically as flags are checked and unchecked. The calculation is: base rate from fee_schedule[engagementType] (strip $ if present, parse as number) plus all checked fixed flag adders plus selected tier amounts. Format the result as "$X,XXX" with no decimals. If the firm manually edits the fee field after auto-calculation, preserve their override — do not recalculate on top of a manual edit. Add a small "Reset to calculated" link next to the fee field that re-runs the calculation if they want to undo a manual edit.

On send (handleSend, template mode): after the letter is sent successfully, fire a PATCH to /engagements/{engagementId}/complexity_flags with the selectedFlags object. Fire this as a background call — do not await it before calling onSent(). A failed flags write should not block the success toast or the modal close.

---

PART 4 — ENGAGEMENT DETAIL PAGE: COMPLEXITY FLAGS DISPLAY

File: frontend/src/app/engagements/[id]/page.tsx

In the Overview tab, inside the existing info card grid, add a new full-width row at the bottom of the grid that shows complexity flags. Only render this row if engagement.complexity_flags exists and has at least one key.

Display: label "Complexity Flags" in the standard labelClass style. Value: a horizontal flex-wrap row of pill badges — one per flag. Each pill shows the flag's human-readable label plus the tier label if applicable (e.g. "K-1 Involvement — 4+ K-1s"). Pill style: bg-surface-page dark:bg-dark-page, border border-surface-border dark:border-dark-border, text-[12px] text-brand dark:text-[#EDEEF0], rounded-full px-2.5 py-0.5.

The human-readable label map to use:
rental_property → "Rental Property"
k1_involvement → "K-1 Involvement"
foreign_accounts_fbar → "Foreign Accounts / FBAR"
depreciation_schedules → "Depreciation Schedules"
home_office → "Home Office Deduction"
multiple_states → "Multiple States"
trust_estate_involvement → "Trust or Estate Involvement"
business_sale → "Business Sale or Disposition"
equity_compensation → "Equity Compensation / ISO / RSU"
crypto → "Cryptocurrency"

---

VERIFICATION

1. alembic current confirms at head
2. npx tsc --noEmit in frontend/ passes with no errors
3. Confirm complexity_adders saves and reloads correctly in Settings → Fee Schedule
4. Confirm fee auto-populates and recalculates as flags are checked in the send letter modal
5. Confirm complexity flags appear on the engagement detail page after a letter is sent