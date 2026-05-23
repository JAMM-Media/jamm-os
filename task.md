== STANDING RULES — ENFORCE ALWAYS ==

Project: JAMM PX
Backend: FastAPI + PostgreSQL on DigitalOcean droplet, Uvicorn + Gunicorn
Frontend: Next.js 14+ App Router, TypeScript, Tailwind CSS, shadcn/ui
All backend files start with a path comment.
All frontend files start with a path comment.
Never use && to chain commands — run them sequentially.
Never modify the database schema without following the
migration procedure exactly.
Tenant isolation is absolute — every query scoped to firm_id.
Routers are thin — no business logic in routers ever.
Never use native_enum=True for enums — always use
sa.Enum(MyEnum, native_enum=False).

== MIGRATION PROCEDURE — FOLLOW EVERY TIME ==

1. alembic current
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full
4. If it contains tables beyond what was just added, delete
   it and write a clean manual migration
5. Do NOT run alembic upgrade head locally — Andrew runs
   this on the droplet

== TASK: Staff Timesheets — Full Feature Build ==

Build a complete timesheet system as a new first-class
sidebar tab. Staff see only their own entries. Managers and
firm owners see all staff with filter controls. Six view
tabs: Daily, Weekly, Biweekly, Monthly, Quarterly, Yearly.
Daily is the active entry surface. All other tabs are
read-and-edit with CSV export.

Read these files before writing any code:
- app/models/time_entry.py
- app/schemas/time_entry.py
- app/api/time_entries.py
- app/crud/time_entry.py
- app/services/time_entry_service.py
- app/core/enums.py (for NotificationType)
- app/crud/notification.py
- frontend/src/components/layout/Sidebar.tsx
- frontend/src/app/(dashboard)/billing/page.tsx
  (to understand existing time entry UI patterns)

Report what existing fields are on TimeEntry before writing
any code.

== PHASE 1 — BACKEND: EXTEND TIME ENTRY MODEL ==

Read the TimeEntry model first. Then add the following
fields via migration.

Fields to add to the TimeEntry model in
app/models/time_entry.py:

  start_time: Mapped[Optional[time]] = mapped_column(
      Time, nullable=True
  )
  end_time: Mapped[Optional[time]] = mapped_column(
      Time, nullable=True
  )
  activity_type: Mapped[Optional[str]] = mapped_column(
      String(100), nullable=True
  )
  is_submitted: Mapped[bool] = mapped_column(
      Boolean, default=False, nullable=False
  )
  submitted_at: Mapped[Optional[datetime]] = mapped_column(
      DateTime(timezone=True), nullable=True
  )
  is_approved: Mapped[bool] = mapped_column(
      Boolean, default=False, nullable=False
  )
  approved_at: Mapped[Optional[datetime]] = mapped_column(
      DateTime(timezone=True), nullable=True
  )
  approved_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
      ForeignKey("users.id", ondelete="SET NULL"),
      nullable=True
  )
  edited_after_submission: Mapped[bool] = mapped_column(
      Boolean, default=False, nullable=False
  )
  edit_note: Mapped[Optional[str]] = mapped_column(
      String(500), nullable=True
  )

Add the import for time at the top of the model file:
  from datetime import date, datetime, time, timezone

Add to app/schemas/time_entry.py:
- All new fields to TimeEntryOut
- start_time, end_time, activity_type to TimeEntryCreate
  and TimeEntryUpdate
- is_submitted, is_approved, edited_after_submission,
  edit_note to TimeEntryOut only — clients never set these
  directly

Write the migration file manually following the procedure.
The revision should chain from 0027. Do NOT run it locally.

== PHASE 2 — BACKEND: NEW TIMESHEET ENDPOINTS ==

File: app/api/time_entries.py

Add these endpoints after the existing ones. Read the
existing router before adding anything.

ENDPOINT 1 — Submit daily entries
POST /time-entries/submit-day
- Requires staff_or_above role
- Body: { date: date }
- Logic: Find all time entries for current_user.id and
  firm_id where entry.date == submitted date and
  is_submitted == False
- Mark each is_submitted = True, submitted_at = now
- If no entries found: return 400 "No unsubmitted entries
  for this date"
- Returns: { submitted_count: int, date: str }

ENDPOINT 2 — Get timesheet summary for a date range
GET /time-entries/summary
- Requires staff_or_above role
- Query params: start_date, end_date, user_id (optional,
  manager+ only)
- Staff: always scoped to their own user_id regardless of
  query param
- Manager+: can pass any user_id in the firm, or omit for
  all staff
- Returns list of summary rows grouped by user and date:
  [{ user_id, user_name, date, total_hours, billable_hours,
  billable_pct, entry_count, is_submitted, has_edits }]
- has_edits = any entry in that user+date group has
  edited_after_submission = True

ENDPOINT 3 — Edit submitted entry (with manager notification)
PATCH /time-entries/{entry_id}/submitted-edit
- Requires staff_or_above role
- Body: { hours, start_time, end_time, activity_type,
  description, edit_note } — all optional
- If entry.is_submitted == False: return 400 "Entry has
  not been submitted — use the regular edit endpoint"
- Staff can only edit their own entries
- Apply the changes, set edited_after_submission = True,
  set edit_note from body if provided
- Fire a notification to all managers and firm_owners in
  the firm:
  title: "Timesheet entry edited after submission"
  body: "{user.full_name} edited a submitted time entry
    for {entry.date}. {edit_note if provided}"
  notification_type: NotificationType.system
  related_entity_type: "time_entry"
  related_entity_id: entry.id
- Returns updated TimeEntryOut

ENDPOINT 4 — Approve a submitted entry
POST /time-entries/{entry_id}/approve
- Requires manager_or_above role
- Sets is_approved = True, approved_at = now,
  approved_by_id = current_user.id
- Returns updated TimeEntryOut

ENDPOINT 5 — Get CSV export
GET /time-entries/export
- Requires staff_or_above role
- Query params: start_date, end_date, user_id (optional,
  manager+ only), format="csv"
- Staff: scoped to own entries only
- Returns a CSV file response with headers:
  Date, Staff, Engagement, Activity Type, Description,
  Start Time, End Time, Hours, Billable, Rate, Value,
  Submitted, Approved
- Use fastapi.responses.StreamingResponse with
  media_type="text/csv"
- Set header:
  Content-Disposition: attachment;
  filename="timesheets_{start_date}_{end_date}.csv"

ENDPOINT 6 — Get firm settings for timesheets
This reads from the existing firm settings. Check if Firm
model has a timesheet_approval_required field. If not,
this endpoint just returns { approval_required: false }
as a placeholder — the settings toggle is built in Phase 4.

GET /time-entries/settings
- Requires manager_or_above role
- Returns { approval_required: bool }

== PHASE 3 — FRONTEND: SIDEBAR AND PAGE SHELL ==

SIDEBAR UPDATE
File: frontend/src/components/layout/Sidebar.tsx

Read this file first. Add Timesheets to navItems between
Tasks and Calendar:
  { href: '/timesheets', label: 'Timesheets',
    icon: Clock }

Import Clock from lucide-react — add to existing import.

PAGE SHELL
Create: frontend/src/app/(dashboard)/timesheets/page.tsx

This is the top-level page. It renders the tab bar and
the active tab content.

Tab bar: Daily | Weekly | Biweekly | Monthly | Quarterly
| Yearly

Active tab indicator: 2px border-bottom #1F3148 light /
#4A7FA5 dark. Inactive tabs: text-[#6B7280].

Page header:
- Left: "Timesheets" — 20px weight 500 #1F3148
- Right (manager+ only): Staff filter dropdown
  Default: "All Staff" for managers, hidden for staff
  Shows list of firm users from GET /users/?limit=100
  Selecting a user filters all tabs to that user

Tab content is rendered below the tab bar. Each tab is a
separate component imported from the timesheets components
directory.

Create the following empty component files that will be
filled in Phase 4:
- frontend/src/app/(dashboard)/timesheets/DailyTab.tsx
- frontend/src/app/(dashboard)/timesheets/WeeklyTab.tsx
- frontend/src/app/(dashboard)/timesheets/BiweeklyTab.tsx
- frontend/src/app/(dashboard)/timesheets/MonthlyTab.tsx
- frontend/src/app/(dashboard)/timesheets/QuarterlyTab.tsx
- frontend/src/app/(dashboard)/timesheets/YearlyTab.tsx

Each empty component just renders a placeholder div for now:
  <div className="p-6 text-[13px] text-[#6B7280]">
    Loading...
  </div>

== PHASE 4 — FRONTEND: DAILY TAB ==

File: frontend/src/app/(dashboard)/timesheets/DailyTab.tsx

This is the primary entry surface. Props:
  interface DailyTabProps {
    selectedUserId: string | null  // null = current user
    currentUserId: string
    userRole: string
  }

LAYOUT:
Top section — Entry form (always visible)
Bottom section — Today's submitted and pending entries

ENTRY FORM:
Card surface bg #EDEEF0 dark:#383838, 8px radius,
padding 16px, margin-bottom 16px.

Form header: "Log time for {today's date formatted as
'Monday, May 22'}" — 13px weight 500

Form fields in a responsive grid (2-col on wide, 1-col
narrow):

1. Engagement — required
   Dropdown populated from GET /engagements/?limit=100
   Shows assigned engagements first (where
   assigned_staff_id == current user), then all others
   separated by a divider "— Other engagements —"
   Searchable — typing filters the list
   Display: "{engagement.name} — {client.name}"

2. Task — optional
   Dropdown populated from GET /tasks/?engagement_id=X
   after engagement is selected
   Shows tasks assigned to current user first
   Display: task.title

3. Activity Type — required
   Dropdown with preset options:
   Tax Preparation, Client Meeting, Document Review,
   Review & Sign-off, Client Communication, Research,
   Admin, Other
   Plus a free-text "Custom" option that shows a text
   input

4. Start Time — optional
   Time picker input, type="time"
   Default: current time rounded to nearest 15 minutes

5. End Time — optional
   Time picker input, type="time"
   Must be after Start Time — show inline error if not
   When both are set: auto-calculate and display duration
   below the end time field: "2h 30m"

6. Hours — required
   Number input, min 0.25, max 24, step 0.25
   Auto-populated from Start/End time difference if both
   are set, but remains editable
   If user manually edits hours after auto-fill, clear
   the auto-fill and keep manual value

7. Billable toggle — yes/no
   Default: yes for engagement-linked entries
   Pill toggle, brand blue when on

8. Notes — optional
   Textarea, 2 rows, max 500 chars
   Placeholder: "What did you work on?"

Below the form fields:
- "Add Entry" button — #1F3148 bg, white text, full width
  Validates required fields before adding
  On success: adds entry to today's pending list below,
  clears form fields (keep engagement and activity type
  selected for fast repeat entry)
  Shows soft duplicate warning if same engagement +
  activity type + overlapping time already exists today:
  "This looks similar to an entry you already logged
  today. Add anyway?"

TODAY'S ENTRIES:
Below the form, two sections:

PENDING ENTRIES (not yet submitted):
Section label: "Pending — not yet submitted"
11px uppercase letter-spacing muted color

Each entry row:
- Date chip (today) — muted
- Engagement name + client name — 12px weight 500
- Activity type — 12px muted
- Start–End time if set, else hours — 12px
- Billable indicator — small green dot if billable
- Edit icon — pencil, opens inline edit (same fields)
- Delete icon — trash, confirm before delete

Running total below pending entries:
"X entries · Y.Z hours · $N.NN billable value"

SUBMIT DAY BUTTON:
Below pending entries. Only shows if there are pending
entries.
"Submit Day" — full width, #1F3148 bg white text
On click: POST /time-entries/submit-day { date: today }
On success: move all pending entries to submitted section,
show success toast "Day submitted"

SUBMITTED ENTRIES:
Section label: "Submitted"
Same row layout as pending but:
- No edit/delete icons (edit triggers the submitted-edit
  flow)
- Show edit icon with a warning color if manager+ — on
  click show a warning modal: "Editing a submitted entry
  will notify all managers. Continue?" then open edit form
- Approved entries show a small green checkmark badge
- If approval mode is on (from settings): show "Pending
  approval" badge on unapproved submitted entries

EMPTY STATE:
If no entries at all today:
"Nothing logged yet today. Add your first entry above."

== PHASE 5 — FRONTEND: AGGREGATE TABS ==

Each aggregate tab (Weekly, Biweekly, Monthly, Quarterly,
Yearly) follows the same pattern with different date ranges.

Create a shared component:
frontend/src/app/(dashboard)/timesheets/AggregateTab.tsx

Props:
  interface AggregateTabProps {
    period: 'weekly' | 'biweekly' | 'monthly' |
            'quarterly' | 'yearly'
    selectedUserId: string | null
    currentUserId: string
    userRole: string
  }

DATE RANGE CALCULATION:
  weekly: current Mon–Sun
  biweekly: last two Mon–Sun periods
  monthly: first to last day of current month
  quarterly: first to last day of current quarter
  yearly: Jan 1 to Dec 31 of current year

NAVIGATION:
Left/right arrow buttons to go to previous/next period.
Center: period label e.g. "May 12 – May 18, 2026" or
"May 2026" or "Q2 2026"

MANAGER SUMMARY (manager+ only, shown above detail):
Summary row per staff member:
  Name | Total Hours | Billable Hours | Billable % |
  Entries | Status indicator

Status indicator:
  Green dot — all entries submitted and approved
  Amber dot — some submitted, some pending
  Red dot — entries exist but none submitted

Overtime flag: if total hours > 40 for weekly/biweekly
periods (normalized), show amber highlight on that row.
If > 50 hours show red highlight.

DETAIL TABLE:
Columns: Date | Staff (manager only) | Engagement |
Activity | Start | End | Hours | Billable | Notes |
Submitted | Approved | Actions

Actions column:
- Staff viewing own entries: edit icon only if not
  submitted, warning edit icon if submitted
- Manager viewing any entry: approve button if submitted
  but not approved, warning edit icon always

EDIT FLOW FOR SUBMITTED ENTRIES:
Show a modal with warning: "Editing this submitted entry
will notify all managers. Add a note explaining the
change (optional):" with a textarea for edit_note.
On confirm: PATCH /time-entries/{id}/submitted-edit

CSV EXPORT:
Top right of each aggregate tab: "Export CSV" button
On click: GET /time-entries/export with the current
period's date range and user filter
Triggers browser file download.

Update each of the six tab component files to import and
use the correct tab component:
- WeeklyTab, BiweeklyTab, MonthlyTab, QuarterlyTab,
  YearlyTab all import AggregateTab and pass the correct
  period prop
- DailyTab renders the full daily entry form

== PHASE 6 — SETTINGS: APPROVAL TOGGLE ==

Read the existing Settings page to understand the tab
structure.

File: frontend/src/components/settings/ (list files)

Add a new "Timesheets" section to the existing Firm
settings tab (not a new tab — add it as a new section
within the Firm tab below the existing firm settings).

The section has one toggle:
  Label: "Require manager approval for submitted
  timesheets"
  Helper text: "When on, submitted entries show as
  Pending Approval until a manager approves them."
  Default: off

This requires a new field on the Firm model:
  timesheet_approval_required: bool, default False

Add this field to:
- app/models/firm.py
- app/schemas/firm.py (FirmOut and FirmUpdate)

Write a migration for this field. Chain from 0028.

The toggle calls PATCH /firms/me with
{ timesheet_approval_required: bool }
The existing PATCH /firms/me endpoint should already
handle this if FirmUpdate includes the field.

== PHASE 7 — TYPESCRIPT, MIGRATION, AND GIT ==

Run: npx tsc --noEmit from the frontend directory.
Fix all TypeScript errors before proceeding.

Then confirm all migration files exist:
- 0028_add_timesheet_fields_to_time_entries.py
- 0029_add_timesheet_approval_to_firms.py

Then:
git add .
git commit -m "add timesheets — full feature build"
git push

== PHASE 8 — VERIFY ==

1. List every file created or modified
2. Confirm migration files exist and chain correctly
3. Confirm all six endpoints exist in the router
4. Confirm DailyTab renders the entry form and both
   entry sections
5. Confirm AggregateTab handles all five period types
6. Confirm the approval toggle exists in Firm settings
7. Confirm TypeScript passes clean
8. List exactly what Andrew needs to run on the droplet

Do not restart services — Andrew handles deployment.