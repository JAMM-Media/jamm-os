# STANDING RULES
- All file operations use the absolute path /home/corby/jamm-os/. Never use /mnt/c/Users paths. Never use Windows-style paths.
- Never use relative paths. Always use full absolute paths starting with /home/corby/jamm-os/.
- Never use the built-in file read tool to inspect file contents. Always use bash: cat, grep, sed. The file read tool caches stale content. Trust bash output only.
- Path comment at top of every file
- Never use && to chain commands
- Always use SQLAlchemy 2.0 Mapped[] syntax. Never use Column() style.
- Always scope every database query to firm_id. No exceptions.
- Never put business logic in routers. Logic goes in services/ or crud/.
- Always use get_current_firm from app.dependencies.tenant for auth. Never read firm_id from the request body.
- Background tasks need their own SessionLocal() in a try/finally block. Never pass the request db session into a background task.
- List endpoints return { items: [], total: N }. Never a plain array.
- Never use em dashes anywhere in any string, copy, or comment.
- Always use "engagements" not "projects". Always use "magic-link" not "portal link". Always use "automation presets" not "automation rules".

---

# VERIFY BEFORE ACT — MANDATORY FOR EVERY TASK
Before making any change to any file:
1. Run: pwd — confirm output is /home/corby/jamm-os. If it is not, run: cd /home/corby/jamm-os
2. Run grep using the full absolute path and paste the full bash output:
   grep -n "pattern" /home/corby/jamm-os/path/to/file
3. If the pattern is not found, run:
   cat /home/corby/jamm-os/path/to/file | grep -c "pattern"
   Paste that result too.
4. If both return zero, STOP and report exactly what bash returned. Do not proceed. Do not guess. Do not find the closest match. Do not trust the file read tool.
5. Only proceed when bash grep with the absolute path confirms the pattern exists on disk.

This rule cannot be skipped. If the task says "find this pattern" and bash grep cannot find it, the task description is wrong — not the file. Stop and wait for updated instructions.

---

# VERIFY AFTER ACT — MANDATORY FOR EVERY CHANGE
After every file change:
- Run grep -n for the exact new string using the full absolute path and paste the full output
- Never report a fix as working without showing the bash grep output
- Never report a file as created without running ls -la and showing the output
- If grep does not confirm the change, fix it before moving to the next step
- Trust bash output only — never the file read tool

---

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# Section 3 - The task

TASK 1 OF 6: Add briefing_sent_at to Firm model and run migration

VERIFY BEFORE ACT:
grep -n "briefing_sent_at" /home/corby/jamm-os/app/models/firm.py
grep -n "^from\|^import" /home/corby/jamm-os/app/models/firm.py | grep -i "datetime\|Optional"
Paste both before touching anything.

Add this column to the Firm model class in app/models/firm.py:
briefing_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

Place it near the other nullable timestamp columns. Confirm Optional and datetime are already imported. If not, add them to the existing imports.

VERIFY AFTER ACT:
grep -n "briefing_sent_at" /home/corby/jamm-os/app/models/firm.py
Confirm the line appears before proceeding.

Run migration (do not chain):
cd /home/corby/jamm-os
source .venv/bin/activate
alembic revision --autogenerate -m "add_briefing_sent_at_to_firms"

Read the generated migration file. Confirm it creates briefing_sent_at as a nullable TIMESTAMP WITH TIME ZONE on the firms table. Then:
alembic upgrade head

psql postgresql://postgres:postgres@localhost:5432/jammpx_dev -c "\d firms" | grep briefing_sent_at
Must show the column with timestamp with time zone type before stopping.


---

TASK 2 OF 6: Add upcoming_deadlines, overdue_document_requests, stale_engagements to context snapshot

VERIFY BEFORE ACT:
grep -n "upcoming_deadlines\|overdue_document_requests\|stale_engagements\|def _run_queries\|return {" /home/corby/jamm-os/app/api/concierge/context.py
Paste output before touching anything.

Add three new query functions to app/api/concierge/context.py and include their results in the _run_queries return dict.

Function 1 -- upcoming_deadlines:
Query engagements joined to clients. Where due_date is between now() and now() + 7 days, status not 'complete' and not 'cancelled'. Return list of dicts: name, client_name, due_date (as ISO string), status. Limit 10, order by due_date ascending.

Function 2 -- overdue_document_requests:
Query document_requests joined to clients. Where status is not 'complete' and created_at is more than 5 days ago. Return list of dicts: title, client_name. Limit 10, order by created_at ascending.

Function 3 -- stale_engagements:
Query engagements joined to clients. Where updated_at is more than 7 days ago, status not 'complete' and not 'cancelled'. Return list of dicts: name, client_name, status, updated_at (as ISO string). Limit 10, order by updated_at ascending.

Add all three to the return dict under keys: upcoming_deadlines, overdue_document_requests, stale_engagements.

VERIFY AFTER ACT:
grep -n "upcoming_deadlines\|overdue_document_requests\|stale_engagements" /home/corby/jamm-os/app/api/concierge/context.py
All three keys must appear in both the function definitions and the return dict.
python3 -c "from app.api.concierge.context import get_firm_context; print('OK')"
Must pass before stopping.
Restart the backend.

API test:
Log in as owner@riverside-demo.com / Demo2026x to get a token, then:
curl -s -H "Authorization: Bearer <token>" http://localhost:8000/concierge/context | python3 -m json.tool | grep -E "upcoming_deadlines|overdue_document_requests|stale_engagements"
All three keys must appear in the response.


---

TASK 3 OF 6: Add morning_briefing automation preset

VERIFY BEFORE ACT:
grep -rn "morning_briefing\|DEFAULT_PRESETS\|automation_presets\|default_enabled" /home/corby/jamm-os/app --include="*.py" | head -20
Paste output before touching anything. Identify which file and data structure contains the preset list.

Add the following preset to the existing preset list in that file. Match the exact format of the surrounding presets. Do not change any existing preset:
{
    "id": "morning_briefing",
    "name": "Morning Briefing",
    "description": "Get a daily summary of your firm's current engagement status, incomplete items, and upcoming due dates when you open the dashboard each morning.",
    "default_enabled": False,
    "category": "intelligence"
}

VERIFY AFTER ACT:
grep -n "morning_briefing" /home/corby/jamm-os/app --include="*.py" -r
Confirm the preset appears with default_enabled False.
python3 -c "from app.main import app; print('OK')"
Must pass before stopping.
Restart the backend.

API test:
curl -s -H "Authorization: Bearer <token>" http://localhost:8000/automation-rules | python3 -m json.tool | grep -A 5 "morning_briefing"
Must show the preset with enabled false.

Browser test:
Navigate to Settings > Automations.
Confirm Morning Briefing toggle appears.
Confirm it is off by default.
Toggle it on and off and confirm the state persists on page reload.


---

TASK 4 OF 6: Add POST /concierge/morning-briefing endpoint to route.py

VERIFY BEFORE ACT:
grep -n "morning.briefing\|briefing_sent_at\|/morning" /home/corby/jamm-os/app/api/concierge/route.py
grep -n "MORNING_BRIEFING_PROMPT\|from.*prompts import" /home/corby/jamm-os/app/api/concierge/route.py
grep -n "get_current_firm\|get_current_user\|get_firm_context\|anthropic\|haiku" /home/corby/jamm-os/app/api/concierge/route.py | head -15
Paste all three before touching anything. This tells you the exact import and call patterns already in use.

Add POST /concierge/morning-briefing to app/api/concierge/route.py. Place it after the existing /chat endpoint. Match the code style already in the file exactly.

Endpoint logic in order:
1. Require get_current_firm and get_current_user from the existing dependency pattern.
2. If user.role is "staff" or "client_portal_user": return JSONResponse({"detail": "Access denied"}, status_code=403).
3. Load the morning_briefing automation rule for this firm. If not found or enabled is False: return JSONResponse({"detail": "Morning briefing is not enabled"}, status_code=403).
4. Import datetime and timezone at the top if not already present. Check firm.briefing_sent_at. If it is not None and (datetime.now(timezone.utc) - firm.briefing_sent_at).total_seconds() < 64800: return Response(status_code=204).
5. Call get_firm_context(firm_id, db) -- already imported from context.py.
6. Call the Claude API using the existing Anthropic client pattern in the file. Model: claude-haiku-4-5-20251001. System: MORNING_BRIEFING_PROMPT (add to import from prompts now -- the constant will exist after Task 5). User message: str(context_data).
7. Extract briefing text from the response content blocks.
8. Set firm.briefing_sent_at = datetime.now(timezone.utc). db.commit().
9. Return JSONResponse({"briefing": briefing_text}).
10. Wrap the Claude API call and everything after step 5 in try/except Exception. On any exception: return Response(status_code=204).

VERIFY AFTER ACT:
grep -n "morning-briefing\|briefing_sent_at\|MORNING_BRIEFING_PROMPT" /home/corby/jamm-os/app/api/concierge/route.py
All three must appear.
python3 -c "from app.api.concierge.route import router; print('OK')"
Must pass before stopping.


---

TASK 5 OF 6: Add MORNING_BRIEFING_PROMPT to prompts.py

VERIFY BEFORE ACT:
grep -n "MORNING_BRIEFING_PROMPT" /home/corby/jamm-os/app/api/concierge/prompts.py
Paste output. If it already exists, stop -- Task 5 is already done.

Add MORNING_BRIEFING_PROMPT as a new constant at the end of app/api/concierge/prompts.py. This is separate from PHASE_1_SYSTEM_PROMPT and is only used by the morning briefing endpoint.

The prompt must contain the following sections in order:

Section 1 -- Role and legal boundary:
You are a factual reporting assistant for a tax and accounting firm. Your only job is to report facts from the firm's data. You are not a licensed professional. You do not give professional advice, legal advice, tax advice, or accounting advice. You report what the data shows. The firm owner makes all professional decisions. If you are uncertain whether a statement crosses into advice, omit it and report a different fact instead.

Section 2 -- Factual reporting rules:
Report only facts that appear directly in the firm context data provided to you. Do not interpret what the facts mean. Do not prioritize items for the firm owner. Do not recommend professional actions. State what the data shows. Do not state what the firm owner should do about it. If a piece of data has no clear factual statement, omit it. Do not speculate.

Section 3 -- Prohibited language (hard rules):
Never use these words or phrases: urgent, immediate, critical, needs attention, at risk, must, should, need to, important, action required, falling behind, concerning, problematic.
Never say: "your highest priority is", "the most important item is", "first thing to address".
Never say: "you should send", "you should follow up", "consider reassigning", "we recommend".
Never say: "needs your attention", "requires action", "is at risk".

Section 4 -- Format rules:
4 to 6 sentences. Conversational prose. No bullet lists. No headers. No bold text. Begin with "Good morning." Cover engagements due this week with names and dates, clients with incomplete items by name, engagement status gaps, and one additional factual observation if available. End with the one additional factual observation as a plain fact with no interpretation. If no additional observation is available, do not add a filler sentence.

Section 5 -- Permitted and prohibited examples:
Permitted: "Three engagements have due dates this week: Patricia Nguyen's 1040 and Tom Callahan's 1040 are due Friday, and the Riverside Plumbing bookkeeping close is due Thursday."
Permitted: "Patricia's tax organizer has not been submitted."
Permitted: "Six clients have no portal access enabled."
Permitted: "Tom Callahan has had no engagement activity in 14 days."
Prohibited: "You should send Patricia her organizer today."
Prohibited: "Your highest priority is getting Riverside Plumbing closed before Thursday."
Prohibited: "This needs your immediate attention."

VERIFY AFTER ACT:
grep -n "MORNING_BRIEFING_PROMPT" /home/corby/jamm-os/app/api/concierge/prompts.py
python3 -c "from app.api.concierge.prompts import MORNING_BRIEFING_PROMPT; print(MORNING_BRIEFING_PROMPT[:120])"
Must print the first 120 characters without error.
python3 -c "from app.api.concierge.route import router; print('OK')"
Must pass before stopping.
Restart the backend.


---

TASK 6 OF 6: Wire morning briefing in ConciergePanel.tsx

VERIFY BEFORE ACT:
grep -n "morning.briefing\|hasInitialized\|__OPEN__\|firm_type\|usePathname\|useEffect" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx | head -40
Paste output before touching anything. Locate the useEffect that fires on first panel open where messages.length === 0.

Step 1 -- Check if usePathname is already imported:
grep -n "usePathname\|from 'next/navigation'" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
If usePathname is not imported, add it to the existing next/navigation import.

Step 2 -- In the useEffect that handles first panel open, add this block at the top before the firm_type check. The block only runs when pathname starts with /dashboard and messages.length === 0:
if (pathname.startsWith('/dashboard') && messages.length === 0) {
  try {
    const res = await api.post('/concierge/morning-briefing')
    if (res.status === 200 && res.data?.briefing) {
      setMessages([{ role: 'assistant', content: res.data.briefing }])
      hasInitialized.current = true
      return
    }
  } catch {
    // fall through to standard opening
  }
}

If the useEffect is not async, make it async or extract the call into an inner async function following the existing pattern in the file.

On 204 or any error the catch block does nothing and execution falls through to the existing firm_type check and standard opening. Do not change any of the existing firm_type or __OPEN__ logic below this block.

VERIFY AFTER ACT:
grep -n "morning-briefing\|usePathname\|pathname" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
All three must appear.

Build check:
cd /home/corby/jamm-os/frontend
/usr/bin/npm run build
Must complete with zero TypeScript errors before stopping.

Browser tests:
Test 1 -- Briefing fires:
Enable Morning Briefing in Settings > Automations for the Riverside test firm.
Navigate to /dashboard. Open Concierge panel.
Confirm briefing appears instantly. No Thinking delay.
Read every sentence. Flag any urgency language, priority statements, or action directives.
If any prohibited language appears, stop and tighten MORNING_BRIEFING_PROMPT then retest.

Test 2 -- 18-hour cooldown:
Close and reopen the panel while still on /dashboard.
Confirm the standard opening appears, not a second briefing.

Test 3 -- Page guard:
Navigate to /clients. Open the panel.
Confirm standard opening appears regardless of preset state.

Test 4 -- Preset off:
Disable Morning Briefing in Settings > Automations.
Navigate to /dashboard. Open the panel.
Confirm standard opening appears.

Git checkpoint after all tests pass:
cd /home/corby/jamm-os
git add -A
git commit -m "Phase 5A: Morning Briefing complete"
git pull --rebase origin main
git push