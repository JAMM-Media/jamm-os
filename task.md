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

# Fix: Add few-shot example to PROACTIVE INTERRUPT block

Task: The two-sentence rule is being ignored because the model's training pulls it toward
educational responses on familiar topics. Add a concrete few-shot example showing the exact
response format for a notification click. Examples outperform rules for output pattern control.

VERIFY BEFORE ACT:
sed -n '137,148p' /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

Find this line inside the PROACTIVE INTERRUPT block:
Trigger message contains "IRS authorization records":
Offer: "Want me to walk you through adding an IRS authorization record for your first client now?"
Plan: Add IRS authorization. Steps: navigate to Clients, open the first client record, select
the IRS Authorizations tab, select New Authorization, fill in the form type and expiry date, save.

Add this example block immediately after it, before the closing --- of the PROACTIVE INTERRUPT section:

<proactive_interrupt_example>
  <user>None of your clients have IRS authorization records. If you handle any federal tax work, this is the gap most likely to create a problem. Want to add one now?</user>
  <assistant>No clients have IRS authorization records on file. Want me to walk you through adding one for your first tax client now?</assistant>
</proactive_interrupt_example>

<proactive_interrupt_example>
  <user>4 client(s) are missing email addresses. They won't receive portal invitations or document requests until this is fixed. Want a list of who they are?</user>
  <assistant>4 clients are missing email addresses and cannot receive portal invitations or document requests. Want me to walk you through adding them now?</assistant>
</proactive_interrupt_example>

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "proactive_interrupt_example" /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm two example blocks present.
2. Restart the backend.
3. Insert test notification and click it. Confirm response is two sentences only.