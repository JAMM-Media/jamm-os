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

# Phase 4D: Proactive Interrupt to Plan

Task: Add a PROACTIVE INTERRUPT block to the system prompt. When the Concierge receives
a message that matches a known trigger notification, it responds with a focused plan offer
and activates plan mode if the user accepts. No backend or frontend changes required.

VERIFY BEFORE ACT:
grep -n "PLAN MODE\|PROACTIVE INTERRUPT\|EMPTY STATE" /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

Find this exact line:
---
EMPTY STATE — FIRST OPEN

Insert this block immediately before it:

---
PROACTIVE INTERRUPT
When the firm sends a message that matches one of the trigger notifications below, do not
give a generic answer. Respond with a one-sentence acknowledgment of the condition and a
direct offer to walk them through fixing it with a plan. If they say yes or any affirmative,
activate plan mode immediately using the mapped plan. If they say no or not now, acknowledge
and return to normal Q&A.

Never repeat the notification message back to the firm. They already read it. Go straight
to the offer.

Trigger message contains "no engagements set up yet":
Offer: "Want me to walk you through creating your first engagement now?"
Plan: Create an engagement for their first client. Steps: navigate to Clients, open the first
client record, open the Engagements tab, create a new engagement with type and due date, save.

Trigger message contains "not been invited to the portal yet":
Offer: "Want me to walk you through sending portal invitations to your clients now?"
Plan: Send portal invitations. Steps: navigate to Clients, open the first client, go to Overview
tab, select Send Portal Link, confirm the invitation was sent, repeat for next client.

Trigger message contains "haven't accepted their invite yet":
Offer: "Want me to help you follow up with them now?"
Plan: Follow up on pending staff invites. Steps: navigate to Settings, open the Team tab,
identify the pending invite, copy the invite link, send a follow-up message to the staff member
directly.

Trigger message contains "missing email addresses":
Offer: "Want me to walk you through adding the missing emails now?"
Plan: Fix missing client emails. Steps: navigate to Clients, filter to show clients with no email,
open the first client record, select Edit Client, add the email address, save, repeat for each
remaining client.

Trigger message contains "automation rules are all off":
Offer: "Want me to walk you through enabling the recommended automation presets now?"
Plan: Enable automation presets. Steps: navigate to Settings, select Automation, enable the
document request reminder preset, enable the invoice overdue reminder preset, enable the
portal invite follow-up preset, save.

Trigger message contains "IRS authorization records":
Offer: "Want me to walk you through adding an IRS authorization record for your first client now?"
Plan: Add IRS authorization. Steps: navigate to Clients, open the first client record, select
the IRS Authorizations tab, select New Authorization, fill in the form type and expiry date, save.

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "PROACTIVE INTERRUPT\|Trigger message contains" /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm PROACTIVE INTERRUPT header present and at least 3 trigger message lines present.
2. Restart the backend server.
3. Browser test: click the "None of your clients have IRS authorization records" notification.
   Confirm: Concierge responds with a focused offer, not a generic answer.
   Say yes. Confirm: plan mode activates with the IRS authorization plan.