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
- Never use && to chain commands in PowerShell -- separate every command onto its own line
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

PHASE INSTRUCTIONS -- EMAIL AND CALENDAR INTELLIGENCE WIRING SESSION 4

No migrations. Backend only -- adding comprehensive behavioral event firing to the inbox API, calendar API, and signal extraction services. Also enhancing the Gmail and Outlook signal extraction to capture more granular metrics.

The goal: every meaningful email and calendar interaction fires a behavioral event with enough metadata that the intelligence layer can later answer: which clients are going cold, who takes too long to respond, which staff are most responsive, what communication patterns predict good vs bad client outcomes.

Never store email content or addresses in behavioral events. Only metadata.

---

STEP 1 -- INBOX API: app/api/inbox.py

Read the file. Currently none of the four endpoints fire any behavioral events. Add fire-and-forget behavioral event firing to each endpoint using threading.Thread with log_event.

Import log_event from app.services.behavioral_log at the top of the file.

-- GET /inbox/threads --

After successfully fetching threads, fire in a background thread:
  event_type: "email.inbox_viewed"
  firm_id: current_firm.id
  actor_type: "staff"
  actor_id: current_user.id
  metadata: {
    "provider": provider,
    "thread_count": len(result["threads"]),
    "client_matched_count": sum(1 for t in result["threads"] if t.get("client_id")),
    "unread_count": sum(1 for t in result["threads"] if t.get("unread")),
  }

-- GET /inbox/threads/{thread_id} --

After fetching the thread, check if any thread participants match a client. Fire two events:

Event 1:
  event_type: "email.thread_opened"
  firm_id: current_firm.id
  actor_type: "staff"
  actor_id: current_user.id
  entity_type: "client" if client_match else None
  entity_id: UUID(client_match["client_id"]) if client_match else None
  metadata: {
    "provider": provider,
    "thread_id": thread_id,
    "message_count": len(thread["messages"]),
    "client_matched": bool(client_match),
    "client_id": client_match["client_id"] if client_match else None,
  }

Event 2 (only if client matched -- this is the unanswered check):
  Look at the last message in the thread. If the last message sender is NOT the current user's email (integration.external_account_id), the client sent the last message and the firm has not yet replied.
  If last message is from the client side: fire event_type: "email.awaiting_firm_reply"
  metadata: {
    "provider": provider,
    "thread_id": thread_id,
    "client_id": client_match["client_id"],
    "last_client_message_date": thread["messages"][-1]["date"],
    "message_count": len(thread["messages"]),
  }

-- POST /inbox/reply --

After successfully sending a reply, fire:
  event_type: "email.reply_sent"
  firm_id: current_firm.id
  actor_type: "staff"
  actor_id: current_user.id
  metadata: {
    "provider": body.provider,
    "thread_id": body.thread_id,
    "to_address_domain": body.to.split("@")[-1] if "@" in body.to else None,
    -- note: never log the full to address, only the domain
  }

-- POST /inbox/compose --

After successfully sending, fire:
  event_type: "email.composed_sent"
  firm_id: current_firm.id
  actor_type: "staff"
  actor_id: current_user.id
  metadata: {
    "provider": body.provider,
    "to_address_domain": body.to.split("@")[-1] if "@" in body.to else None,
  }

All events use threading.Thread(target=log_event, kwargs={...}, daemon=True).start() pattern. Never block the response.

---

STEP 2 -- CALENDAR API: app/api/calendar.py

Read the file. Add behavioral event firing.

-- GET /calendar/external-events --

After fetching events, fire:
  event_type: "calendar.external_events_synced"
  firm_id: current_firm.id
  actor_type: "staff"
  actor_id: current_user.id
  metadata: {
    "provider": result["provider"],
    "event_count": len(result["events"]),
    "has_join_links": sum(1 for ev in result["events"] if any(
      p in (ev.get("description", "") + " " + ev.get("location", ""))
      for p in ["zoom.us", "meet.google.com", "teams.microsoft.com"]
    )),
  }

Import log_event and threading at the top of calendar.py.

---

STEP 3 -- GMAIL SIGNAL EXTRACTION: app/services/gmail_signals_service.py

Read the existing extract_gmail_signals function. It currently fires one event per client with: contact_frequency, avg_response_lag_hours, last_contact_date, thread_count.

Enhance to also compute and include in the metadata:

1. firm_initiated_count: number of threads where the firm sent the first message
2. client_initiated_count: number of threads where the client sent the first message
3. unanswered_count: number of threads where the last message is from the client (firm has not replied)
4. max_response_lag_hours: the single longest response lag observed across all threads (not just average)
5. min_response_lag_hours: the fastest response time observed
6. threads_with_no_response: threads where the firm never replied at all

Add these to the existing metadata dict in the log_event call. The computation requires looking at thread message order -- which is already being done when computing avg_response_lag_hours. Extend that logic to also track:

For each thread:
- first_sender_is_firm: bool -- whether firm_email appears as sender of the first message
- last_sender_is_client: bool -- whether the last message sender is NOT the firm email
- had_any_reply: bool -- whether there was at least one back-and-forth exchange

Add a second behavioral event per client for threads where last_sender_is_client is True:
  event_type: "email.unanswered_client_thread"
  firm_id: firm_id
  entity_type: "client"
  entity_id: client_id
  actor_type: "system"
  metadata: {
    "thread_count": number of unanswered threads for this client,
    "last_client_message_date": most recent date among unanswered threads,
    "provider": "gmail",
  }

Fire this only if unanswered_count > 0 for that client.

---

STEP 4 -- OUTLOOK SIGNAL EXTRACTION: app/services/outlook_signals_service.py

Read the existing extract_outlook_signals function. Apply the exact same enhancements as Step 3 -- same six new metrics, same unanswered thread detection logic, same second behavioral event for unanswered threads.

The Outlook service uses Microsoft Graph message data with from.emailAddress.address for sender detection instead of raw headers. Adapt the logic accordingly.

---

STEP 5 -- FRONTEND: Client profile Emails tab behavioral events

Read frontend/src/app/clients/[id]/page.tsx

The Emails tab already exists. Add two fire-and-forget API calls:

1. When the emails tab becomes active (in the useEffect that fires when activeTab === 'emails'), after the data fetch completes, call:
   api.post('/api/v1/inbox/events', { event_type: 'client.emails_tab_viewed', client_id: clientId })
   Use .catch(() => {}) -- fire and forget, never block.

2. When a thread item is clicked (the <a> tag that navigates to /inbox?thread_id=...), add an onClick that fires:
   api.post('/api/v1/inbox/events', { event_type: 'client.email_thread_clicked', client_id: clientId, thread_id: thread.thread_id, provider: thread.provider })
   Use .catch(() => {}) -- fire and forget.

---

STEP 6 -- BACKEND: Simple client-side event receiver endpoint

Add to app/api/inbox.py:

POST /inbox/events
Requires get_current_user. Accepts any event dict from the frontend.
Body: { event_type: str, client_id: str | None, thread_id: str | None, provider: str | None }

Validates that event_type starts with "client." or "email." to prevent abuse.
Fires the event via log_event with firm_id from current_firm, actor_id from current_user.id.
Returns 200.

This lets the frontend fire behavioral events for UI interactions (tab views, clicks) without needing dedicated backend endpoints for each.

---

STEP 7 -- MORNING BRIEFING QUERY: app/services/morning_briefing_service.py (new file)

Create this service now even though the morning briefing UI is not yet built. The service reads from the behavioral_events table to produce the signals that will eventually power the morning briefing.

The service has one public function:

def get_morning_briefing_signals(firm_id: UUID, db: Session) -> dict:
    """
    Reads behavioral event history to produce actionable signals for the morning briefing.
    Returns a dict of signal categories, each with a list of items sorted by urgency.
    This function is read-only -- it never writes to the database.
    """

The function queries the behavioral_events table for events in the last 30 days for this firm.

Returns:
{
  "clients_going_cold": [
    -- clients where last_contact_date in gmail/outlook signals is 30+ days ago
    -- source: gmail.signals_extracted and outlook.signals_extracted events
    -- fields per item: client_id, client_name (join to clients table), last_contact_date, days_since_contact
    -- sorted by days_since_contact DESC (most neglected first)
    -- max 10 items
  ],
  "unanswered_client_messages": [
    -- clients with email.unanswered_client_thread events in last 7 days
    -- fields per item: client_id, client_name, unanswered_count, last_client_message_date
    -- sorted by last_client_message_date ASC (oldest unanswered first)
    -- max 10 items
  ],
  "slow_response_clients": [
    -- clients where avg_response_lag_hours > firm average across all clients
    -- source: gmail.signals_extracted metadata
    -- fields per item: client_id, client_name, avg_response_lag_hours, firm_average_hours
    -- sorted by avg_response_lag_hours DESC
    -- max 5 items
  ],
  "engagement_deadlines_today": [
    -- engagements with effective deadline = today
    -- query directly from Engagement table (not behavioral events)
    -- fields per item: engagement_id, engagement_name, client_name, deadline_type
  ],
  "engagement_deadlines_this_week": [
    -- engagements with effective deadline within next 7 days
    -- same source
    -- max 10 items
  ],
  "staff_email_activity": {
    -- aggregate email activity stats for the firm in last 7 days
    -- source: email.reply_sent and email.composed_sent events
    -- fields: total_replies_sent, total_composed_sent, active_staff_count (distinct actor_ids)
  }
}

Use SQLAlchemy 2.0 select() syntax throughout. Never use raw SQL strings.
All queries are scoped to firm_id.
Return empty lists/dicts for any category where no data exists -- never return None.

Add a GET /morning-briefing endpoint in a new file app/api/morning_briefing.py:
  Requires manager_or_above role.
  Calls get_morning_briefing_signals(current_firm.id, db).
  Returns the dict directly.
  Register in main.py with prefix="/api/v1".

---

DO NOT run migrations. No schema changes.

After completing confirm:
- app/api/inbox.py fires email.inbox_viewed, email.thread_opened, email.awaiting_firm_reply, email.reply_sent, email.composed_sent
- app/api/inbox.py has POST /inbox/events endpoint
- app/api/calendar.py fires calendar.external_events_synced
- gmail_signals_service.py fires enhanced metadata + email.unanswered_client_thread
- outlook_signals_service.py same enhancements
- frontend client profile fires client.emails_tab_viewed and client.email_thread_clicked
- app/services/morning_briefing_service.py exists with get_morning_briefing_signals
- app/api/morning_briefing.py exists with GET /morning-briefing endpoint registered in main.py