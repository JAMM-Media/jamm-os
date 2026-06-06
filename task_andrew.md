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

PHASE INSTRUCTIONS -- CALENDAR UI FIXES

No migrations. No backend changes. One file only: frontend/src/app/calendar/page.tsx

Read the entire file before making any changes.

---

FIX 1 -- Move sidebar to the right

The current layout is: aside (left, 240px) | main area (flex-1)
Change to: main area (flex-1) | aside (right, 240px)

Move the aside element to appear AFTER the main area div in the JSX. Change border-r to border-l on the aside. Everything else about the aside stays identical.

---

FIX 2 -- Fix staff color mismatch

The bug: the staffList is fetched including the firm owner. The filter bar then does staffList.filter((s) => s.id !== user?.id) to exclude the firm owner. But staffIndexMap is built from the FULL staffList including the firm owner. So the index used to assign colors to staff members in the filter bar (which excludes the firm owner) is off by one compared to the index used to assign colors to events (which uses staffIndexMap built from the full list).

Fix: Build staffIndexMap from the FILTERED staff list (excluding the firm owner), not the full staffList. This ensures the color assigned to each person in the filter bar matches the color used to fill their events on the calendar.

Find where staffIndexMap is built:
  const staffIndexMap: Record<string, number> = {}
  staffList.forEach((s, i) => { staffIndexMap[s.id] = i })

Replace with:
  const filteredStaffList = staffList.filter((s) => s.id !== user?.id)
  const staffIndexMap: Record<string, number> = {}
  filteredStaffList.forEach((s, i) => { staffIndexMap[s.id] = i })

Then update the staff filter bar render to use filteredStaffList instead of staffList.filter((s) => s.id !== user?.id) -- they are now the same list, just reference filteredStaffList directly.

---

FIX 3 -- Replace horizontal staff filter bar with dropdown

Remove the entire horizontal staff filter bar (the div with flex items-center gap-2 px-4 py-1.5 border-b that contains "View:", "Just me" button, and the staff chip row).

Replace it with a compact dropdown in the TOOLBAR row (the div with flex items-center justify-between px-4 py-2 border-b). Add the staff dropdown between the navigation controls (left side) and the view toggle buttons (right side).

The dropdown:
- Trigger button: shows "Just me" when justMe is true, or "X staff selected" when staff are selected. Has a ChevronDown icon. Same style as the view toggle buttons.
- Dropdown panel: absolute positioned below the trigger, z-50, bg-surface-card border border-surface-border rounded shadow-lg, width 220px, max-height 300px overflow-y-auto
- Search input at top of panel: placeholder "Search staff...", filters the staff list by name or email
- Options list:
  - "Just me" row with a checkmark when justMe is true. Clicking sets justMe=true and clears selectedStaff.
  - "Select all" row. Clicking sets justMe=false and sets selectedStaff to all filteredStaffList ids.
  - Divider line
  - One row per staff member: color swatch (clickable to open inline ColorPicker) + name/email + checkbox. Clicking the row (not the swatch) toggles that staff member in selectedStaff and sets justMe=false.
- Clicking outside the dropdown closes it. Use a useRef + useEffect with mousedown listener, same pattern as the ColorPicker component already in the file.
- Add isDropdownOpen state (boolean) and staffSearch state (string) to control the dropdown.

Remove the separate staff filter bar div entirely. The dropdown now lives in the toolbar row.

---

FIX 4 -- Rename calls to meetings everywhere in the file

Find every occurrence of:
- 'call' as an EventType value -> change to 'meeting'
- 'call' in DEFAULT_COLORS -> change key to 'meeting'
- 'call' in TYPE_LABELS -> change key to 'meeting', value to 'Meetings'
- 'call' in allDefaultTypes array -> change to 'meeting'
- type: 'call' in the external events mapping -> change to 'meeting'
- Any string 'Calls' -> change to 'Meetings'
- EventType union type: replace 'call' with 'meeting'
- sidebarFilter default ['deadline'] stays the same -- no call reference there

Make sure every reference to 'call' as an event type key is updated to 'meeting'. Do a thorough search through the entire file.

---

DO NOT run migrations. No backend changes. One file only.

After completing confirm:
- Sidebar is on the right (border-l, appears after main area)
- staffIndexMap built from filteredStaffList
- Filter bar replaced with dropdown in toolbar row
- Dropdown has search, Just me, Select all, and per-staff rows with color swatches
- All 'call' event type references replaced with 'meeting'
- TYPE_LABELS shows 'Meetings' not 'Calls'