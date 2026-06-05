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

Windows / PowerShell:
- No && chaining — separate commands
- Quoted paths for directories with parentheses
- Separate git add commands for paths with special characters

---

PHASE-SPECIFIC INSTRUCTIONS — Timesheet timer + client-first engagement selection

Pure frontend build. No backend changes, no migration.

---

PART 1 — START/STOP TIMER on DailyTab

File: frontend/src/app/(dashboard)/timesheets/DailyTab.tsx

Add a live running timer to the Daily tab entry form. The timer persists across navigation using localStorage so staff can start a timer, leave JAMM PX to do their work, return later and stop it.

localStorage key: "jamm_active_timer"
localStorage value shape: { startedAt: ISO string, engagementId: string, activityType: string, customActivity: string, isBillable: boolean }

Timer state in component:
- Add a timerState: { startedAt: string, engagementId: string, activityType: string, customActivity: string, isBillable: boolean } | null state, initialized by reading localStorage on mount.
- Add elapsed: number state (seconds), updated every second via setInterval when timerState is not null.

On mount (useEffect with empty deps):
- Read localStorage key "jamm_active_timer". If present and valid JSON, set timerState and start the interval.

Start Timer button:
- Validate that engagementId and activityType are selected before starting. If not, show toast.error with appropriate message and do not start.
- Only one timer at a time. If timerState is not null when Start is pressed, show a toast.error: "Stop the current timer before starting a new one." Do not start.
- On start: write to localStorage, set timerState, pre-fill form.engagementId, form.activityType, form.isBillable from current form values.
- Show a pulsing red dot next to the elapsed time display to signal the timer is active.

Stop Timer button (shown when timer is running):
- Calculate start time string from timerState.startedAt (format HH:MM).
- Calculate end time string from now (format HH:MM).
- Call setForm with: engagementId from timerState, activityType from timerState, startTime from calculated start, endTime from calculated end, hours auto-calculated from the diff (use existing timeDiffHours function), hoursAutoFilled: true, isBillable from timerState.
- Also call setEngSearch with getEngLabel of the restored engagement so the search input shows the right label.
- Clear localStorage key "jamm_active_timer".
- Set timerState to null, clear interval.
- The form is now populated and ready for the staff member to review, add notes, and submit normally via the existing Add Entry flow. Do not auto-submit.

Elapsed display format: show HH:MM:SS while running. Sits between the engagement/activity fields and the start/end time fields in the form layout. Only visible when a timer is active.

Timer UI placement: add a "Start Timer" button to the right of the form's primary action area. When the timer is running, replace it with a "Stop Timer" button styled with a red background. The elapsed time display appears directly above the stop button.

---

PART 2 — CLIENT-FIRST ENGAGEMENT SELECTION on DailyTab

File: frontend/src/app/(dashboard)/timesheets/DailyTab.tsx

Add a client selector above the existing engagement dropdown in the entry form. The client selector narrows the engagement list to only that client's engagements.

Add clientFilter: string state (default '').

The clients state already exists as Record<string, string> (id → name). Derive a sorted client list from it for the dropdown:
const clientOptions = Object.entries(clients).sort((a, b) => a[1].localeCompare(b[1]))

Client selector UI: a standard select element above the engagement search input. Placeholder option "All clients". When a client is selected, set clientFilter to that client's id and clear the current engagementId and engSearch if the selected engagement doesn't belong to that client.

Update filteredEngagements() to filter by clientFilter when it is set:
- If clientFilter is not empty, only return engagements where eng.client_id === clientFilter.
- Then apply the existing engSearch text filter on top.

The assignedEngs() and otherEngs() grouping should continue to work correctly after this filter.

When clientFilter changes and the currently selected engagement no longer matches, clear form.engagementId and setEngSearch('').

---

PART 3 — CLIENT FILTER on timesheet page filter bar

File: frontend/src/app/(dashboard)/timesheets/page.tsx

Add a clientFilter: string state (default 'all') to the timesheets page.

Derive a sorted client list from the existing clientMap state:
const clientOptions = Object.entries(clientMap).sort((a, b) => a[1].localeCompare(b[1]))

Add a client filter select to the filter bar, before the engagement filter dropdown. Placeholder "All Clients". When a client is selected, also reset engagementFilter to 'all' since the previously selected engagement may not belong to the new client.

When clientFilter is not 'all', filter the engagement options shown in the engagement filter dropdown to only show engagements belonging to that client.

Pass clientFilter down to all tab components that accept engagementFilter — add it as an optional prop alongside engagementFilter. Each tab should additionally filter entries by client: since entries have engagement_id, derive the client from the engagements list and filter accordingly when clientFilter is set.

---

VERIFICATION

1. npx tsc --noEmit in frontend/ passes with no errors
2. Timer persists in localStorage — start a timer, navigate away to another page, return to Daily tab and confirm the clock is still running with correct elapsed time
3. Client selector in entry form correctly narrows engagement list
4. Stopping the timer correctly populates start time, end time, and hours in the form
5. Only one timer can run at a time — starting a second one shows the error toast