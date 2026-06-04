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

# PRE-TASK
cd /home/corby/jamm-os
source .venv/bin/activate
python3 -c "from app.api.concierge.route import router; print('OK')"
If the import fails, stop and report. Do not proceed.
git add -A
git commit -m "checkpoint before [task name]"

---

TASK: Persist firm_type selection from intake and fix post-intake copy

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before firm_type persistence task"
python3 -c "from app.api.concierge.route import router; print('OK')"

VERIFY BEFORE ACT:
grep -n "ConciergeAction\|type.*navigate" /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts
grep -n "Welcome back" /home/corby/jamm-os/app/api/concierge/prompts.py
Paste both before touching anything.

---

Change 1: conciergeEvents.ts -- add set_firm_type action type

VERIFY BEFORE ACT:
cat /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts
Paste output.

Find:
  type: 'navigate' | 'open-modal' | 'navigate-and-open'

Replace with:
  type: 'navigate' | 'open-modal' | 'navigate-and-open' | 'set_firm_type'

Add one new optional field to the interface after the existing fields:
  firm_type?: string

VERIFY AFTER ACT:
cat /home/corby/jamm-os/frontend/src/lib/events/conciergeEvents.ts
Confirm set_firm_type appears in the type union and firm_type field is present.

---

Change 2: ConciergePanel.tsx -- handle set_firm_type action

VERIFY BEFORE ACT:
grep -n "executeAction\|set_firm_type\|PATCH\|firm_type" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Paste output.

Inside the executeAction function, add a handler for set_firm_type at the top of the
function before any existing logic:

Find the opening line of executeAction:
  async function executeAction(action: ConciergeAction) {

Add this block immediately after the opening line:

    if (action.type === 'set_firm_type' && action.firm_type) {
      try {
        await api.patch('/firms/me/concierge', { firm_type: action.firm_type })
        setStatusMessage('Practice type saved')
      } catch {
        // non-fatal — firm_type will be set on next reload
      }
      return
    }

Do not change anything else in this function.

VERIFY AFTER ACT:
grep -n "set_firm_type" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx
Confirm one result.

---

Change 3: prompts.py -- emit CONCIERGE_ACTION on firm type selection and fix copy

VERIFY BEFORE ACT:
sed -n '191,225p' /home/corby/jamm-os/app/api/concierge/prompts.py
Paste output.

Make exactly two changes to the EMPTY STATE block:

Change 3a -- add CONCIERGE_ACTION instruction after the firm type branching logic.
Find:
Do not add any other text. When the firm selects one, confirm their firm type and immediately recommend the three automation presets and one engagement template that match their practice type. Then proceed to the normal starter prompts for their type.

Replace with:
When the firm selects one (they will type "1", "2", "3", or the name of the practice type), append a CONCIERGE_ACTION line at the very end of your response, after all text:
CONCIERGE_ACTION:{"type":"set_firm_type","firm_type":"tax_prep"}
Use tax_prep for option 1, bookkeeping for option 2, advisory for option 3.
Then output the matching starter prompts for their type exactly as specified below.

Change 3b -- fix "Welcome back" in all three firm type blocks.
Find all three instances of:
"Welcome back. Here are three things to work on next:

Replace each with:
"Got it. Here are three things to work on first:

There are exactly three instances -- one for tax_prep, one for bookkeeping, one for advisory.
Replace all three. Do not change anything else.

VERIFY AFTER ACT:
grep -n "Welcome back" /home/corby/jamm-os/app/api/concierge/prompts.py
Confirm zero results.
grep -n "Got it" /home/corby/jamm-os/app/api/concierge/prompts.py
Confirm three results.
grep -n "set_firm_type" /home/corby/jamm-os/app/api/concierge/prompts.py
Confirm one result.

---

Post-task verification:
1. cd /home/corby/jamm-os/frontend
2. npm run build
   Zero TypeScript errors required before stopping.
3. find /home/corby/jamm-os/frontend/src/lib/events/ -name "*.ts" | sort
4. find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort
5. python3 -c "from app.api.concierge.route import router; print('OK')"

Database reset for browser test:
psql postgresql://postgres:postgres@localhost:5432/jammpx_dev -c "UPDATE firms SET firm_type = NULL WHERE id = '185314c9-e702-4eab-8600-249848022206';"

Browser test:
1. Hard refresh the app
2. Open the Concierge panel -- intake question must appear instantly
3. Type "1" and send
4. Confirm response says "Got it. Here are three things to work on first:"
5. Run this immediately after:
   psql postgresql://postgres:postgres@localhost:5432/jammpx_dev -c "SELECT firm_type FROM firms WHERE id = '185314c9-e702-4eab-8600-249848022206';"
   Confirm firm_type = tax_prep
6. Close and reopen the panel -- confirm tax_prep starters appear via API call