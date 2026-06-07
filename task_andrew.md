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

PHASE INSTRUCTIONS -- CALENDAR CLICKABLE EVENTS

No migrations. Two files: app/api/calendar.py (small update) and frontend/src/app/calendar/page.tsx (main work).

---

STEP 1 -- BACKEND: Add location to external events

Read app/api/calendar.py

Find the GET /calendar/external-events endpoint. It currently returns events with: id, title, start, end, description, type.

Update to also return location for each event:

For Gmail Calendar events:
- The Google Calendar API event object has a location field at the top level. Add location to the $fields or select param if used, otherwise just read event.get("location", "") from the response.
- Add "location": event.get("location", "") to each event dict in the response.

For Outlook events:
- Microsoft Graph returns a location object: location.displayName
- Add "location": msg.get("location", {}).get("displayName", "") to each event dict.

Update the return shape comment to include location: str.

---

STEP 2 -- FRONTEND: Clickable events and meeting popover

Read frontend/src/app/calendar/page.tsx in full before making changes.

-- CalEvent interface update --

Add two fields to the CalEvent interface:
  engagementId?: string | null
  location?: string | null

-- Event data mapping update --

When building allEvents from calendarItems (engagement deadlines/extensions):
- The item has engagementId available. Add it: engagementId: item.engagementId

When building allEvents from external events:
- Add location: ev.location ?? null to each external event

-- Click handler --

Add a new state variable:
  const [clickedEvent, setClickedEvent] = useState<CalEvent | null>(null)
  const [popoverPos, setPopoverPos] = useState<{ x: number; y: number }>({ x: 0, y: 0 })

Add a handleEventClick function:
  function handleEventClick(ev: CalEvent, e: React.MouseEvent) {
    e.stopPropagation()
    if (ev.type === 'deadline' || ev.type === 'extension') {
      if (ev.engagementId) {
        window.location.href = `/engagements/${ev.engagementId}`
      }
      return
    }
    if (ev.type === 'task') {
      if (ev.engagementId) {
        window.location.href = `/engagements/${ev.engagementId}`
      }
      return
    }
    if (ev.type === 'meeting') {
      const rect = (e.target as HTMLElement).getBoundingClientRect()
      setPopoverPos({ x: rect.left, y: rect.bottom + 8 })
      setClickedEvent(clickedEvent?.id === ev.id ? null : ev)
      return
    }
    // holidays: no action
  }

-- EventPill component update --

Add onClick prop to EventPill:
  onClick?: (e: React.MouseEvent) => void

In the EventPill div, add:
  onClick={onClick}
  cursor: 'pointer' in the style

-- renderPills update --

Pass the click handler to each EventPill:
  <EventPill
    key={ev.id}
    event={ev}
    borderColor={borderColor}
    fillColor={fillColor}
    isOwner={isFirmOwner}
    isPersonalView={justMe}
    onClick={(e) => handleEventClick(ev, e)}
  />

-- Meeting popover --

Add a MeetingPopover component inside the file:

function MeetingPopover({ event, pos, onClose }: { event: CalEvent; pos: { x: number; y: number }; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClick(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) onClose()
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [onClose])

  // Extract meeting join URL from description or location
  // Look for Zoom, Meet, Teams URLs
  const joinUrl = extractJoinUrl(event.description ?? '', event.location ?? '')

  return (
    <div
      ref={ref}
      className="fixed z-50 bg-surface-card border border-surface-border rounded-[10px] shadow-lg p-4 w-72"
      style={{ top: pos.y, left: Math.min(pos.x, window.innerWidth - 300) }}
    >
      <div className="flex items-start justify-between gap-2 mb-3">
        <p className="text-[13px] font-medium text-brand dark:text-[#EDEEF0] leading-snug">{event.title}</p>
        <button onClick={onClose} className="text-[#6B7280] hover:text-brand flex-shrink-0"><X size={14} /></button>
      </div>
      <p className="text-[12px] text-[#6B7280] mb-1">{formatDate(event.date)}</p>
      {event.location && (
        <p className="text-[12px] text-[#6B7280] mb-1">{event.location}</p>
      )}
      {event.description && !joinUrl && (
        <p className="text-[12px] text-[#6B7280] line-clamp-3 mb-2">{event.description}</p>
      )}
      {joinUrl && (
        
          href={joinUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 flex items-center gap-2 h-8 px-3 rounded-[6px] bg-brand text-white text-[12px] font-medium hover:bg-brand/90 transition-colors w-full justify-center"
        >
          Join Meeting
        </a>
      )}
    </div>
  )
}

Add extractJoinUrl helper function:

function extractJoinUrl(description: string, location: string): string | null {
  const combined = `${description} ${location}`
  const patterns = [
    /https?:\/\/[^\s]*zoom\.us\/[^\s]*/i,
    /https?:\/\/meet\.google\.com\/[^\s]*/i,
    /https?:\/\/teams\.microsoft\.com\/[^\s]*/i,
    /https?:\/\/[^\s]*webex\.com\/[^\s]*/i,
    /https?:\/\/[^\s]*gotomeeting\.com\/[^\s]*/i,
  ]
  for (const pattern of patterns) {
    const match = combined.match(pattern)
    if (match) return match[0].replace(/[.,;)>]+$/, '')
  }
  return null
}

-- Render the popover --

In the main return JSX, just before the closing </AppShell> tag, add:
  {clickedEvent && clickedEvent.type === 'meeting' && (
    <MeetingPopover
      event={clickedEvent}
      pos={popoverPos}
      onClose={() => setClickedEvent(null)}
    />
  )}

-- Close popover on calendar background click --

On the main calendar area div (the flex-1 overflow-hidden flex flex-col div), add:
  onClick={() => setClickedEvent(null)}

---

DO NOT run migrations. No schema changes.

After completing confirm:
- app/api/calendar.py returns location for Gmail and Outlook events
- CalEvent interface has engagementId and location fields
- Engagement and task events navigate to /engagements/{id} on click
- Meeting events open MeetingPopover on click
- MeetingPopover shows title, date, location, description, and Join Meeting button when URL detected
- extractJoinUrl handles Zoom, Meet, Teams, Webex, GoToMeeting
- Holidays have no click action
- Popover closes on outside click