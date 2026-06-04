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

# POST-TASK — run after task completes
find /home/corby/jamm-os/app/api/concierge/ -name "*.py" | sort
ls /home/corby/jamm-os/migrations/versions/ | tail -5
python3 -c "from app.api.concierge.route import router; print('OK')"
find /home/corby/jamm-os/frontend/src/components/concierge/ -name "*.tsx" | sort

---

# Fix: Expand autopilot to full app navigation

Task: The current supported actions list is hardcoded to 7 actions. The frontend already
handles any route via router.push. Expand the prompt to allow the model to navigate to
any valid route in the app, not just the hardcoded list.

VERIFY BEFORE ACT:
sed -n '368,402p' /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

Make exactly two changes:

Change 1 -- replace the restrictive rule with one that allows full navigation:
OLD:
- Only emit when the firm's request clearly maps to one of the supported actions above.

NEW:
- Emit for any navigation or modal action the firm requests. The supported actions above are examples. You may also emit a plain navigate action to any valid route in the app. Valid routes are: /dashboard, /clients, /clients/[client-name-slug], /clients/[client-name-slug]?tab=engagements, /clients/[client-name-slug]?tab=irs-auth, /clients/[client-name-slug]?tab=billing, /clients/[client-name-slug]?tab=documents, /clients/[client-name-slug]?tab=portal, /clients/[client-name-slug]?tab=messages, /engagements, /engagements/[engagement-id], /engagements/templates, /billing, /documents, /tasks, /timesheets, /calendar, /settings, /settings/team, /settings/integrations, /settings/billing, /notifications. Use {"type":"navigate","route":"[route]"} for plain navigation with no modal.

Change 2 -- add two examples showing generic navigation:
Find this line:
Example response for "connect QuickBooks":
Does not exist -- find the last example block before the --- separator and add after it:

Find:
CONCIERGE_ACTION: {"type":"navigate-and-open","route":"/clients/patricia-nguyen","modal":"new-engagement","prefill":{"client":"Patricia Nguyen","engagementType":"tax_return"}}

Add immediately after it:
Example response for "go to Patricia Nguyen's IRS authorizations" with autopilot on:
Navigating to Patricia Nguyen's IRS Authorizations tab now.
CONCIERGE_ACTION: {"type":"navigate","route":"/clients/patricia-nguyen?tab=irs-auth"}

Example response for "take me to billing" with autopilot on:
Navigating to Billing now.
CONCIERGE_ACTION: {"type":"navigate","route":"/billing"}

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "any valid route\|irs-auth\|tab=engagements" /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm all three present.
2. Restart the backend.
3. Browser test with autopilot on -- say "take me to Patricia Nguyen's IRS authorizations".
   Confirm: Concierge navigates directly to her IRS Authorizations tab.
4. Browser test -- say "go to billing".
   Confirm: Concierge navigates to /billing.