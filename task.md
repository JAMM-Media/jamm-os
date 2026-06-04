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

# Prompt audit: Add Automation Presets workflow section

Task: Replace the thin AUTOMATION RULE data model entry with a full section covering
all 15 presets, which are enabled by default, and how to manage them.

VERIFY BEFORE ACT:
grep -n "AUTOMATION RULE\|15 presets\|automation_enabled" /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

OLD:
AUTOMATION RULE
A configurable automation preset. Each firm gets 15 seeded presets on signup. Presets are disabled by default and must be individually enabled.
Fields: id, firm_id, name, description, is_enabled, trigger_event, trigger_conditions (JSON), actions (JSON), default_actions (JSON), execution_count, last_executed_at.
The 15 presets cover: engagement status changes, task completions, document uploads, deadline proximity alerts, portal activity, and invoice events.

NEW:
AUTOMATION RULE
Each firm gets 15 automation presets seeded on signup. Each preset is either enabled or disabled. Enabled presets fire automatically when their trigger condition is met. Disabled presets do nothing until turned on.

How to manage automation presets:
Navigate to Settings and select Automation. Each preset is listed with its name, trigger, and an on/off toggle. Enable or disable presets individually. To reset a preset to its default actions, select Reset to Default.

Presets enabled by default (fire automatically from day one):
1. Document Request Reminder (3-day) -- sends a reminder email to the client 3 days after a document request is created if it is still pending
2. E-Signature Reminder (2-day) -- sends a reminder to the client 2 days after a signature envelope is sent if not yet signed
3. Overdue Task Alert to Staff -- notifies the assigned staff member when a task becomes overdue
4. New Client Welcome Email -- sends a welcome email to the client when they are first added
5. Invoice Overdue Reminder -- sends a payment reminder to the client when an invoice becomes overdue
6. Extension Filed Auto-Notify -- notifies the client of the extension and creates a deadline task
7. IRS Authorization Expiry Warning -- alerts staff and creates a renewal task when an IRS authorization is within 30 days of expiry
8. Invoice Overdue Escalating Sequence -- sends reminders on day 1 and day 7 after an invoice goes overdue, then notifies the firm owner on day 14
9. Engagement Deadline Approaching (14-day Alert) -- notifies assigned staff 14 days before an engagement deadline

Presets disabled by default (must be turned on manually):
10. Auto-Create Invoice on Engagement Completion -- creates a draft invoice when an engagement is marked complete
11. Notify Staff When Documents Are Complete -- notifies assigned staff when a client finishes uploading all requested documents
12. Recurring Engagement Kickoff Notification -- notifies staff when a new recurring engagement is automatically created
13. 1040 Season Kickoff -- sends a welcome email and creates intake tasks when a 1040 engagement is opened
14. Return Completed: Client Delivery Loop -- creates a delivery task, generates an invoice from time entries, emails the client, and creates a follow-up confirmation task when a return is marked complete
15. New Client Full Onboarding Sequence -- sends a welcome email, creates onboarding tasks, and sends an intake document request when a new client is added

Recommended presets to enable first:
For most firms, the highest-value presets to enable in the first week are: Notify Staff When Documents Are Complete (6), Auto-Create Invoice on Engagement Completion (10), and Return Completed: Client Delivery Loop (14). These three cover the most common manual follow-up tasks firms do after finishing work.

Common questions:
Q: Can I customize what a preset does?
A: Not yet. Presets run their default actions. Custom action editing is on the roadmap.

Q: Will presets fire for existing clients and engagements?
A: Presets only fire on new trigger events from the moment they are enabled. They do not retroactively process existing records.

Q: How do I know if a preset fired?
A: The execution count next to each preset in Settings shows how many times it has run. The last executed date shows when it last fired.

Q: Can I turn off a preset temporarily?
A: Yes. Toggle it off in Settings. It will not fire again until re-enabled.

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "AUTOMATION RULE\|Presets enabled by default\|Presets disabled by default" /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm all three present.
2. Restart the backend.
3. Browser test: ask "which automation presets should I turn on first".
   Confirm: response names specific presets with accurate descriptions, not generic advice.