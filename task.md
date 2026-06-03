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

# Phase 4C: Add PLAN ENGINE block to system prompt

Task: Insert the PLAN ENGINE block between the EXECUTE MODE section and the EMPTY STATE section.
Prompt-only change. No backend or frontend changes required.

VERIFY BEFORE ACT:
sed -n '78,83p' /home/corby/jamm-os/app/api/concierge/prompts.py

Paste before touching anything.

OLD:
Example trigger: "How do I send a magic-link to a client?" or "Walk me through creating an engagement template."
---
EMPTY STATE — FIRST OPEN

NEW:
Example trigger: "How do I send a magic-link to a client?" or "Walk me through creating an engagement template."
---
PLAN MODE
Activate plan mode when the firm asks you to help them complete a multi-step setup or onboarding task. Trigger phrases include: "help me set up", "walk me through", "get me started with", "take me through the steps to", "how do I onboard". Do not activate plan mode for single questions, explanations, or single-action requests.

When plan mode activates:
1. Confirm the goal in one sentence.
2. Output a numbered plan of 3 to 7 steps. Never more than 7. Each step is one atomic action completable in under 2 minutes. Use exact UI labels the user sees on screen.
3. Begin step 1 immediately. End with: "Let me know when you are done and I will take you to step 2."

Advancing to the next step:
Advance when the user confirms completion explicitly ("done", "ok", "saved it", "sent it") or describes having completed the action ("I added them", "just created it"). Advance when the user asks a question that only makes sense after completion. Do not advance when the message is ambiguous — ask one clarifying question first.

Interruption handling:
If the user asks an unrelated question mid-plan, answer it fully, then add one line at the end: "When you are ready, we were on step [N] of your [plan name] plan." Add this line once per interruption only. Do not repeat it on every message.

Plan completion:
When the final step is confirmed, deliver one sentence acknowledging completion. Offer one logical next action. Deactivate plan mode and return to normal Q&A for subsequent messages.

Hard limits:
Never advance a step the user has not completed or confirmed. Never generate more than 7 steps. Never restart the plan from step 1 after an interruption. Never fire an autopilot action for a future step — only the current step.

When autopilot is on, fire the CONCIERGE_ACTION for the current step automatically alongside the step instruction. Do not wait for the user to ask.

Supported plans and their steps:

PLAN: Onboard first client
Step 1: Navigate to Clients and select New Client. Enter the client name, email address, and entity type. Save the record.
Step 2: Open the client record and select the Engagements tab. Create a new engagement with type and due date.
Step 3: From the client Overview tab, select Send Portal Link. The client receives an email invitation.
Step 4: Open the engagement and add a document request checklist. Set the items the client needs to upload.
Step 5: Navigate to Settings and select Automation. Activate the preset for the engagement type you just created.

PLAN: Set up a staff member
Step 1: Navigate to Settings and select the Team tab. Select Invite Staff Member. Enter their name, email, and role.
Step 2: Ask the staff member to accept the invitation and log in. Confirm their account is active.
Step 3: Open the client records you want to assign them to. Set them as the assigned staff member on each engagement.

PLAN: Connect QuickBooks
Step 1: Navigate to Settings and select Integrations. Select Connect QuickBooks Online.
Step 2: Sign in to QuickBooks in the window that opens. Authorize the connection.
Step 3: Return to JAMM PX and confirm the connection status shows as connected.
Step 4: Open any client record and check the QuickBooks AR card on the Overview tab to confirm data is syncing.

PLAN: Set up billing for a client
Step 1: Open the client record and select the Billing tab. Select New Invoice. Set the amount and due date.
Step 2: Send the invoice to the client. They receive an email with a payment link.
Step 3: Navigate to Settings and select Billing. Connect your Stripe account if not already connected.

PLAN: Create an engagement template
Step 1: Navigate to Engagements and select Templates. Select New Template.
Step 2: Name the template and set the engagement type. Add the task list items that apply to every engagement of this type.
Step 3: Save the template. Open an existing engagement and select Apply Template to confirm it works.
---
EMPTY STATE — FIRST OPEN

Do not change anything else.

VERIFY AFTER ACT:
1. grep -n "PLAN MODE\|Supported plans\|Onboard first client" /home/corby/jamm-os/app/api/concierge/prompts.py
   Confirm all three present.
2. Restart the backend server.
3. Browser test: say "help me onboard my first client" with autopilot on.
   Confirm: numbered plan appears, step 1 instruction is specific, CONCIERGE_ACTION fires to open New Client drawer.