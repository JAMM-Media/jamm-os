 STANDING RULES
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

# MIGRATION PROCEDURE
Before every migration: run alembic current first.
After autogenerate: read the generated file before running upgrade head. If it touches tables you did not intend, delete it and write a manual migration.
If alembic current shows a revision but no tables exist: run alembic stamp base, then alembic upgrade head.

---

# PRE-TASK — run before touching anything
git add -A
git commit -m "checkpoint before autopilot 3B fixes"
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.

---

# Standing verification rules — apply to every step in this task:
- Never report a file as created without running ls -la on it and including the output
- Never report a fix as working without running grep to confirm the change landed and including the output
- If any verification fails, fix it before moving to the next step
- After all steps, run: python3 -c "from app.api.concierge.route import router; print('OK')"
- Include all verification output in your final summary

---

# POST-TASK — run after task completes
find app/api/concierge/ -name "*.py" | sort
ls migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Section 3: Task to perform

Task: Add autopilot instructions to app/api/concierge/prompts.py

Read app/api/concierge/prompts.py in full before writing anything. Do not modify any existing content. Add only what is specified below.

---

Step 1 — Add autopilot block to PHASE_1_SYSTEM_PROMPT

Find the line: WHAT JAMM PX DOES NOT DO

Insert this entire block immediately before that section:

---

AUTOPILOT MODE

When the firm has autopilot enabled, you can navigate the application and open modals on their behalf. You signal an action by appending a CONCIERGE_ACTION: line at the very end of your response, after all human-readable text. The frontend detects this line, strips it from the displayed response, and executes the action.

CONCIERGE_ACTION format: a single line containing CONCIERGE_ACTION: followed by a JSON object with no line breaks.

Supported actions and when to use them:

"add a client" or "create a new client" or "new client":
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients","modal":"new-client"}

"add a client named [name]":
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients","modal":"new-client","prefill":{"name":"[name]"}}

"create an engagement for [client name]":
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients/[client-name-slug]","modal":"new-engagement","prefill":{"client":"[client name]"}}

"invite a staff member" or "add a staff member":
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/settings/team","modal":"invite-staff"}

"send a magic-link to [client name]":
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients/[client-name-slug]","modal":"magic-link"}

"create an engagement template":
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/engagements/templates","modal":"new-template"}

"connect QuickBooks":
CONCIERGE_ACTION: {"type":"navigate","route":"/settings/integrations"}

"connect Stripe":
CONCIERGE_ACTION: {"type":"navigate","route":"/settings/billing"}

Rules for emitting CONCIERGE_ACTION:
- Only emit when the firm's request clearly maps to one of the supported actions above.
- Always place CONCIERGE_ACTION: as the last line of the response with no text after it.
- The client name slug is the client name lowercased with spaces replaced by hyphens. Example: "Patricia Nguyen" becomes "patricia-nguyen".
- Never emit CONCIERGE_ACTION for questions, explanations, or anything that does not map to a supported action.
- If you are not sure whether autopilot is enabled, do not emit CONCIERGE_ACTION. The frontend handles the off state.

Example response for "add a client" with autopilot on:
Opening the New Client drawer for you.
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients","modal":"new-client"}

Example response for "create an engagement for Patricia Nguyen" with autopilot on:
Navigating to Patricia Nguyen and opening a new engagement.
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients/patricia-nguyen","modal":"new-engagement","prefill":{"client":"Patricia Nguyen"}}

---

After adding the block:
1. grep -n "CONCIERGE_ACTION\|autopilot\|Autopilot" app/api/concierge/prompts.py
2. python3 -c "from app.api.concierge.route import router; print('OK')"
3. Print lines surrounding the insertion point to confirm placement:
   grep -n "WHAT JAMM PX DOES NOT DO\|AUTOPILOT MODE" app/api/concierge/prompts.py
4. Report exact line numbers where the block was inserted