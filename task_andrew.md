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

PHASE INSTRUCTIONS -- CALENDAR SESSION 3
Full calendar rebuild with color system, staff overlay, sidebar, and custom categories

---

STEP 1 -- MIGRATION

Current head: 0047_per_staff_integrations

Write a clean manual migration:
revision = '0048_user_calendar_settings'
down_revision = '0047_per_staff_integrations'

Add one column to the users table:
  calendar_settings: JSONB, nullable=True

This stores per-user calendar color preferences and custom categories.

Also add one column to the firms table:
  staff_calendar_colors: JSONB, nullable=True

This stores firm-owner-assigned colors per staff member (keyed by user_id string).

Run alembic upgrade head. Confirm at new head.

---

STEP 2 -- MODEL UPDATES

app/models/user.py -- add after the locked_until field:
    calendar_settings: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

app/models/firm.py -- add after the portal_domain_verification_token field:
    staff_calendar_colors: Mapped[Optional[dict]] = mapped_column(
        JSONB, nullable=True
    )

Import JSONB from sqlalchemy.dialects.postgresql in both files if not already imported.

---

STEP 3 -- BACKEND: Calendar endpoint updates in app/api/engagements.py

Read the existing GET /engagements/calendar endpoint. It returns CalendarResponse with CalendarEngagementItem items. Update it to also include the assigned staff member's user_id when available.

Update CalendarEngagementItem schema in app/schemas/engagement.py to add:
  assigned_to: Optional[UUID] = None

In the endpoint, when building each CalendarEngagementItem, include:
  assigned_to=eng.assigned_to if hasattr(eng, 'assigned_to') else None

---

STEP 4 -- BACKEND: New calendar support endpoints in app/api/calendar.py (new file)

Create app/api/calendar.py with these endpoints. Router prefix: /calendar. Tag: calendar.

-- GET /calendar/staff-colors --
Returns the firm's staff_calendar_colors dict. Requires get_current_firm.
Returns: { "colors": dict } where dict is keyed by user_id string, value is hex color string.
If staff_calendar_colors is None, return { "colors": {} }

-- PATCH /calendar/staff-colors --
Requires firm_owner. Body: { "user_id": str, "color": str }
Validates color is a valid hex string (starts with #, 4 or 7 chars).
Merges into firm.staff_calendar_colors. db.commit().
Returns { "colors": dict }

-- GET /calendar/my-settings --
Returns current user's calendar_settings. Requires get_current_user.
Returns the full calendar_settings dict or defaults if null:
{
  "colors": {
    "deadline": "#EF4444",
    "extension": "#F97316",
    "task": "#3B82F6",
    "call": "#22C55E",
    "holiday": "#9CA3AF"
  },
  "custom_categories": []
}

-- PATCH /calendar/my-settings --
Requires get_current_user. Body: { "colors": dict | None, "custom_categories": list | None }
Merges changes into current_user.calendar_settings. db.commit().
Returns updated settings.

Register in app/main.py:
  from app.api.calendar import router as calendar_router
  app.include_router(calendar_router, prefix="/api/v1")

---

STEP 5 -- BACKEND: External calendar events endpoint

Add to app/api/calendar.py:

-- GET /calendar/external-events --
Requires get_current_user. Fetches calendar events from the user's connected Gmail or Outlook calendar (whichever is connected).

For Gmail: uses the Google Calendar API (not Gmail).
  - Build credentials using get_fresh_credentials from gmail_signals_service.py
  - Call Google Calendar API: GET https://www.googleapis.com/calendar/v3/calendars/primary/events
  - Params: timeMin=today ISO, timeMax=today+180days ISO, singleEvents=true, orderBy=startTime, maxResults=100
  - Each event returns: id, summary, start.dateTime or start.date, end.dateTime or end.date, description

For Outlook: uses Microsoft Graph calendar.
  - Use get_fresh_outlook_credentials from outlook_signals_service.py
  - GET https://graph.microsoft.com/v1.0/me/calendarView?startDateTime={today}&endDateTime={today+180days}&$select=id,subject,start,end,bodyPreview&$top=100
  - Each event returns: id, subject, start.dateTime, end.dateTime, bodyPreview

If no integration connected: return { "events": [], "provider": null }
If integration exists but Calendar scope not available (scopes don't include calendar.readonly or Calendars.Read): return { "events": [], "provider": null, "needs_reconnect": true }

Return shape:
{
  "events": [
    {
      "id": str,
      "title": str,
      "start": str,  -- ISO datetime or date string
      "end": str,
      "description": str,
      "type": "call"  -- all external events are type "call"
    }
  ],
  "provider": "gmail" | "outlook" | null
}

Wrap all API calls in try/except. If the calendar API call fails (token expired, scope missing), return empty events rather than 500.

---

STEP 6 -- FRONTEND: Full calendar page rebuild

Replace frontend/src/app/calendar/page.tsx entirely.

The new calendar has three zones:
- Left sidebar (240px): upcoming events list + color key at bottom
- Main calendar area (flex-1): month/week/agenda view with toolbar
- Firm owner only: staff filter bar above the calendar (horizontal checkboxes)

-- COLOR SYSTEM --

Default event type colors (border color):
  deadline: #EF4444 (red)
  extension: #F97316 (orange)
  task: #3B82F6 (blue)
  call: #22C55E (green)
  holiday: #9CA3AF (gray)

On mount: fetch GET /api/v1/calendar/my-settings to get user's custom colors. Merge with defaults (user overrides win). Store in state as eventColors.

Default staff colors (8 distinct colors that work as fill):
  ['#6366F1', '#EC4899', '#14B8A6', '#F59E0B', '#8B5CF6', '#06B6D4', '#F43F5E', '#84CC16']
  Assign sequentially by staff member index.

On mount (firm owner only): fetch GET /api/v1/calendar/staff-colors to get any custom-assigned staff colors.

-- EVENT RENDERING --

Each calendar event is rendered as a pill/block with:
- Border: 2px solid, color = eventColors[event.type]
- Fill: staff member's assigned color (aggregate view) OR white/surface color (personal view)
- 1px white/surface gap between border and fill (use box-shadow: inset 0 0 0 1px white or outline technique)
- Text: event title, truncated

In personal view (viewing only your own events):
- Border = event type color
- Fill = white (light mode) or dark-card (dark mode)
- This gives clean bordered events without color fill noise

In aggregate view (firm owner with staff selected):
- Border = event type color
- Fill = selected staff member's color
- Firm owner's own events: border = event type color, fill = white (no fill)

-- STAFF FILTER (firm owner only) --

Above the calendar, show a horizontal filter bar. Fetch staff list from GET /api/v1/users/ on mount (firm owner only).

Show: "View:" label, then "Just me" button + one checkbox-style toggle per staff member showing their name and a small color swatch of their assigned color.

Default state: "Just me" selected (firm owner sees only their own data).
Reset button: clicking "Just me" at any time resets to personal view.

Multi-select: clicking a staff member's name adds them to the view. Their events are overlaid with their fill color.

-- MAIN CALENDAR AREA --

View toggle: Month / Week / Agenda (same as current page, keep existing logic).

Month view: each day cell shows event pills. Truncate at 3 pills, show "+N more" link that opens a day popover.

Week view: 7-column grid, time-based positioning. Each day column shows events for that day.

Agenda view: list grouped by date, same as current ListView but with colored dots using eventColors.

Events to show:
1. Engagement deadlines and extensions: from GET /api/v1/engagements/calendar
2. Tasks due: from GET /api/v1/tasks/?limit=200 (filter to those with due_date in the 180-day window)
3. External calendar events (calls): from GET /api/v1/calendar/external-events
4. Holidays: hardcode US federal holidays for current year

When viewing a staff member's overlay (firm owner aggregate view), also fetch their engagement deadlines filtered by assigned_to = staff_member_id. The calendar endpoint already returns assigned_to -- filter client-side.

-- LEFT SIDEBAR --

Width: 240px. Background: surface-card. Border-right: 0.5px surface-border.

Top section -- Upcoming events list:
- Heading: "Upcoming" (13px weight 500)
- Filter: small multi-select pill row below heading. Default: "Deadlines" selected. Options: Deadlines, Extensions, Tasks, Calls. Each pill toggles on/off.
- List: events matching selected filter types, sorted by date, show as many as fit. Each item:
  - Colored dot (eventColors[type])
  - Event title (12px, truncated)
  - Date (11px muted)
- Scrollable within its section.

Bottom section -- Color key:
- Heading: "Color Key" (11px uppercase muted)
- One row per event type: colored swatch + label + edit icon
- Clicking edit icon (or the swatch itself) opens an inline color picker (use <input type="color"> positioned absolutely)
- Custom categories appear below the defaults with a small delete icon
- "+ Add category" button at bottom of key: opens inline form with name input + color picker, saves via PATCH /api/v1/calendar/my-settings
- Any change to colors calls PATCH /api/v1/calendar/my-settings immediately (optimistic update)

-- STAFF COLOR ASSIGNMENT (firm owner only) --

In the staff filter bar, clicking a staff member's color swatch opens an inline color picker. Saving calls PATCH /api/v1/calendar/staff-colors with { user_id, color }.

---

STEP 7 -- SIDEBAR NAV: Calendar visibility

The Calendar link is already in the sidebar navItems. No change needed.

---

DO NOT skip the migration. This build requires alembic upgrade head on the droplet.

After completing confirm:
- Migration 0048 exists with calendar_settings on users and staff_calendar_colors on firms
- Both model files updated
- CalendarEngagementItem schema has assigned_to field
- app/api/calendar.py with 5 endpoints registered in main.py
- frontend/src/app/calendar/page.tsx fully rebuilt with:
  - Left sidebar (upcoming list + color key with inline editing)
  - Staff filter bar (firm owner only)
  - Month/Week/Agenda views with bordered colored event pills
  - Border = event type color, fill = staff color or white
  - Color customization via color key
  - Custom category support