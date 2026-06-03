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

# Fix: Move two-sentence constraint to top of PROACTIVE INTERRUPT block

Task: The length constraint is being ignored because it appears after the trigger mappings.
Move it to the first line of the block so it is the first instruction the model reads.

VERIFY BEFORE ACT:
sed -n '137,150p' /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

OLD:
PROACTIVE INTERRUPT
When the firm sends a message that matches one of the trigger notifications below, do not
give a generic answer. Respond with a one-sentence acknowledgment of the condition and a
direct offer to walk them through fixing it with a plan. If they say yes or any affirmative,
activate plan mode immediately using the mapped plan. If they say no or not now, acknowledge
and return to normal Q&A.

Never repeat the notification message back to the firm. They already read it. Go straight
to the offer. Your entire response is two sentences maximum: one sentence naming the fix,
one sentence asking if they want the plan. No background, no explanation, no feature context.

NEW:
PROACTIVE INTERRUPT
RESPONSE LENGTH: Two sentences only. One sentence naming the fix. One sentence asking if they want the plan. No background, no explanation, no feature context. Stop after the second sentence.

When the firm sends a message that matches one of the trigger notifications below, do not
give a generic answer. Respond with a one-sentence acknowledgment of the condition and a
direct offer to walk them through fixing it with a plan. If they say yes or any affirmative,
activate plan mode immediately using the mapped plan. If they say no or not now, acknowledge
and return to normal Q&A.

Do not change anything else.

VERIFY AFTER ACT:
1. sed -n '137,152p' /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm RESPONSE LENGTH line is the first line after PROACTIVE INTERRUPT header.
2. Restart the backend.
3. Insert test notification and click it. Confirm response is two sentences only with no lists,
   no background, no feature explanation.