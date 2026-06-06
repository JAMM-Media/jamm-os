# STANDING RULES — PERMANENT, NEVER OVERWRITE THIS BLOCK
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

# MIGRATION PROCEDURE — FOLLOW EVERY TIME
1. alembic current — confirm starting revision before touching anything
2. alembic revision --autogenerate -m "description"
3. Read the generated file in full — if it contains tables beyond what you just added, delete it and write a clean manual migration
4. alembic upgrade head
5. alembic current — confirm now at head
All models must be imported in migrations/env.py or autogenerate silently misses them.

---

# PHASE INSTRUCTIONS — TIMER BEHAVIORAL EVENT TRACKING

## Context
The start/stop timer exists in the frontend at:
frontend/src/components/timesheets/DailyTab.tsx

It uses localStorage under the key 'jamm_active_timer'.
The startTimer() and stopTimer() functions already work correctly.
This build adds two backend endpoints that fire behavioral events only,
and wires two silent fire-and-forget API calls into those functions.

Zero visible changes to the UI. Zero changes to timer behavior.
If either API call fails, the timer continues working normally.
No migration. No new models. No database writes in the new endpoints.

---

## Pre-task checkpoint
git add -A
git commit -m "checkpoint before timer behavioral event tracking"

---

## VERIFY BEFORE STARTING
grep -n "def startTimer\|def stopTimer\|TIMER_KEY\|localStorage" frontend/src/components/timesheets/DailyTab.tsx | head -10
grep -n "time.entry\|time_entry" app/core/enums.py | head -10
Paste both outputs before touching anything.

---

## Change 1: Add two endpoints to the time entries router

Find the time entries router file.
grep -rn "router.*time" app/api/ to locate it if not obvious.

Add two new endpoints at the bottom of the router.
Both require staff_or_above auth.
Both fire behavioral events only — no database writes.

### POST /time-entries/timer/start

Accepts this request body:
    class TimerStartRequest(BaseModel):
        engagement_id: UUID
        activity_type: str
        is_billable: bool

Logic:
- Validate that the engagement exists and belongs to current_firm.id
- If not found: return 404
- Fire behavioral event:
    event_type: "time_entry.timer_started"
    entity_type: "engagement"
    entity_id: engagement_id
    actor_type: "staff"
    actor_id: current_user.id
    metadata:
        activity_type: activity_type
        is_billable: is_billable
        hour_of_day: datetime.now(timezone.utc).hour
        day_of_week: datetime.now(timezone.utc).weekday()
- Return: {"status": "ok"}

### POST /time-entries/timer/stop

Accepts this request body:
    class TimerStopRequest(BaseModel):
        engagement_id: UUID
        duration_seconds: int
        activity_type: str
        is_billable: bool

Logic:
- No engagement lookup needed on stop
- Fire behavioral event:
    event_type: "time_entry.timer_stopped"
    entity_type: "engagement"
    entity_id: engagement_id
    actor_type: "staff"
    actor_id: current_user.id
    metadata:
        duration_seconds: duration_seconds
        duration_minutes: round(duration_seconds / 60, 1)
        activity_type: activity_type
        is_billable: is_billable
        hour_of_day: datetime.now(timezone.utc).hour
        day_of_week: datetime.now(timezone.utc).weekday()
- Return: {"status": "ok"}

Both endpoints import log_event inside the function body
using the fire-and-forget pattern — never block the response.

---

## Change 2: Wire API calls into startTimer in DailyTab.tsx

Find the startTimer function in DailyTab.tsx.
It currently sets localStorage and updates state.

After the localStorage.setItem call, add a fire-and-forget API call:
    api.post('/time-entries/timer/start', {
      engagement_id: form.engagementId,
      activity_type: form.activityType || 'Other',
      is_billable: form.isBillable,
    }).catch(() => {})

The .catch(() => {}) is intentional and required.
If the call fails for any reason the timer continues working normally.
Never await this call. Never show an error to the user if it fails.

---

## Change 3: Wire API call into stopTimer in DailyTab.tsx

Find the stopTimer function in DailyTab.tsx.
It currently calculates startTime, endTime, hours from timestamps
and populates the form.

After the form population logic, add a fire-and-forget API call:
    const durationSeconds = Math.floor(
      (new Date().getTime() - new Date(timerState.startedAt).getTime()) / 1000
    )
    api.post('/time-entries/timer/stop', {
      engagement_id: timerState.engagementId,
      duration_seconds: durationSeconds,
      activity_type: timerState.activityType || 'Other',
      is_billable: timerState.isBillable,
    }).catch(() => {})

Same rules: never await, never surface errors, timer works regardless.

Then clear localStorage and reset timer state as it already does.

---

## Verify after all changes
grep -n "timer/start\|timer/stop\|timer_started\|timer_stopped" app/api/time_entries.py
grep -n "timer/start\|timer/stop" frontend/src/components/timesheets/DailyTab.tsx
python -m py_compile app/api/time_entries.py
All must pass before deploying.

cd frontend
npx tsc --noEmit
Zero TypeScript errors required.

---

## Deploy sequence
git add -A
git commit -m "timer behavioral event tracking"
git push origin main
Then on the droplet:
git pull origin main
alembic upgrade head
alembic current
systemctl restart jammpx.service
journalctl -u jammpx.service -n 20 --no-pager