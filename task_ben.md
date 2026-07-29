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
- Never trust file contents shown in VS Code opened against the Windows copy (C:\Users\corby\jamm-os) or Windows File Explorer. Verify all file state via the WSL terminal (cat, ls -la, wc -l) before assuming a file is stale, empty, or correct.
- Generated snapshot files (codebase_snapshot.txt, frontend/frontend_snapshot.txt) are gitignored. Never manually stage, commit, or resurrect them. Regenerate only via ./update_all_snapshots.sh.
- Before the first commit of any session, confirm git config user.email is ben@jammpx.com. Never assume git identity is correct without checking.
- Before writing or modifying anything touching the Concierge agent, read /home/corby/jamm-os/JAMM_PX_Perfect_Assistant_Build.md in full. Every Concierge task should be traceable to something described in that document.
- If a Concierge tool call fails inside the tool-use loop, the failure must surface as a diagnosable logged event, never as a generic deflection presented to the firm owner as if it were a real answer. Check backend logs for "Tool execution failed" before concluding a knowledge gap exists rather than a broken tool call.

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

# Section 3 - The task

TASK: Fix the duplicate invoice count on the Billing overdue banner, and make prefill-panel-input auto-send instead of waiting for a manual send click

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '148,157p' /home/corby/jamm-os/frontend/src/app/\(app\)/billing/page.tsx

sed -n '258,266p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "async function handleSend" -A 5 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm the Billing banner's message string currently begins with the same overdue_count number that ContextualBanner also renders separately as its own bold count element, producing a visible duplicate number. Confirm the prefill-panel-input handler currently calls setInput(action.prefillMessage), only filling the text box, and confirm handleSend already accepts an optional text argument and is already used this way elsewhere in this file, for example for notification drafts and starter prompts. Confirm both of these before editing, they are two separate, unrelated fixes bundled into one task only because both are small and low risk.

WHAT THIS IS:

Fix one, confirmed live tonight: the Billing overdue banner shows the invoice count twice, once as ContextualBanner's own bold count badge, and again as the leading number inside the message string itself, since the message was originally written to be a complete, standalone sentence before the count badge existed as a separate visual element.

Fix two, a direct product decision made tonight: clicking a card or banner that prefills a question into the Concierge's input, such as the Billing banner's Ask Concierge action, currently only fills the input and waits for a manual send. The decision was made to have this auto-send immediately instead, since clicking the button already represents clear, deliberate intent, and sending a question to the Concierge has no real-world consequence, unlike the irreversible actions the human-in-the-loop principle exists to guard against, such as emailing a client or posting an invoice. This distinction, asking a question versus taking a consequential action, means auto-sending here does not conflict with that existing principle.

CHANGE INSTRUCTIONS:

In billing/page.tsx, remove the leading overdue_count number and its following text from the start of the message string, so it no longer duplicates the count badge, while keeping the rest of the message grammatically correct and still stating the real total dollar amount clearly.

In ConciergePanel.tsx, change the prefill-panel-input handler to call handleSend(action.prefillMessage) instead of setInput(action.prefillMessage), so the message is sent immediately rather than only filling the input box. Do not change any other action type's handler, and do not change handleSend itself.

VERIFY AFTER ACT:

grep -n "overdue_count" /home/corby/jamm-os/frontend/src/app/\(app\)/billing/page.tsx

grep -n "prefill-panel-input" -A 2 /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Expected: the message string no longer starts with a raw count number, and the handler now calls handleSend instead of setInput.

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

Visit Billing with a real overdue invoice present. Confirm the banner's count badge shows the number once, and the message text no longer repeats it, while still clearly stating the real dollar total.

Click Ask Concierge on the banner. Confirm the panel opens and the question is sent immediately, with a real response appearing, rather than just sitting in the input box waiting for a manual send.

Report pass or fail for both checks individually.

GIT:

git add -A

git commit -m "fix the Billing overdue banner showing its invoice count twice, once as the bold count badge and again as the leading number in the message text, and change prefill-panel-input to auto-send immediately via the existing handleSend function instead of only filling the input box, a direct product decision made tonight since clicking a button that prefills a question already signals clear intent and asking the Concierge a question carries no real-world consequence, unlike the irreversible actions the human-in-the-loop principle is meant to guard against"

git pull --rebase origin main

git push origin main