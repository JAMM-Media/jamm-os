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

# Fix: Add long-form punctuation example to tone_examples

Task: Add a fourth example to tone_examples showing correct punctuation in a longer
multi-sentence response with dependent clauses. The existing three examples only cover
short sentences, so the model drifts on longer prose.

VERIFY BEFORE ACT:
sed -n '33,50p' /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

OLD:
  <example>
    <user>add a new client named Acme Corp</user>
    <assistant>Opening the New Client drawer with Acme Corp filled in.</assistant>
  </example>
</tone_examples>

NEW:
  <example>
    <user>add a new client named Acme Corp</user>
    <assistant>Opening the New Client drawer with Acme Corp filled in.</assistant>
  </example>
  <example>
    <user>what engagements does Patricia Nguyen have</user>
    <assistant>Patricia Nguyen's engagements are listed under her client record. Navigate to Clients, open Patricia Nguyen, and select the Engagements tab. All engagements tied to her record are shown there with their status, type, and assigned staff member.</assistant>
  </example>
</tone_examples>

Do not change anything else.

VERIFY AFTER ACT:
1. sed -n '33,55p' /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm fourth example is present with correct punctuation throughout.
   Confirm no spaces before any comma or period in any example.
2. Restart the backend server.
3. Browser test: ask "what engagements does Patricia Nguyen have".
   Confirm no space before any comma or period in the response.