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

TASK: Exempt set_firm_type from autopilot gate in prompts.py

Pre-task:
cd /home/corby/jamm-os
git add -A && git commit -m "checkpoint before set_firm_type autopilot exemption"

VERIFY BEFORE ACT:
sed -n '525,535p' /home/corby/jamm-os/app/api/concierge/prompts.py
Paste output before touching anything.

Change 1: prompts.py -- add exemption for set_firm_type before the autopilot gate rule

Find exactly:
- If autopilot is off, never emit CONCIERGE_ACTION. Instead give a full prose answer explaining what the user should do and where to go.

Replace with:
- Exception: always emit CONCIERGE_ACTION for set_firm_type actions, even when autopilot is off. This is a data write, not a navigation action.
- If autopilot is off, never emit CONCIERGE_ACTION for navigation or modal actions. Instead give a full prose answer explaining what the user should do and where to go.

Do not change anything else.

VERIFY AFTER ACT:
grep -n "Exception.*set_firm_type\|autopilot is off" /home/corby/jamm-os/app/api/concierge/prompts.py
Confirm both lines appear, exception line first.

No build needed. Restart the backend.

Database reset for browser test:
psql postgresql://postgres:postgres@localhost:5432/jammpx_dev -c "UPDATE firms SET firm_type = NULL WHERE id = '185314c9-e702-4eab-8600-249848022206';"

Browser test:
1. Hard refresh
2. Open panel -- intake appears instantly
3. Open DevTools console
4. Type "1" and send
5. Paste [CONCIERGE RAW] from console
6. Run immediately:
   psql postgresql://postgres:postgres@localhost:5432/jammpx_dev -c "SELECT firm_type FROM firms WHERE id = '185314c9-e702-4eab-8600-249848022206';"
   Confirm firm_type = tax_prep