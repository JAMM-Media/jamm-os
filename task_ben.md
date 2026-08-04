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

TASK: Deterministically override the pre-action message for navigate-and-open actions, ending the model's discretion over claims of completion

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '685,724p' /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

grep -n "modalLabel\b" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

Confirm handleConciergeAction's final return path, reached when Autopilot is on and the action is not set_firm_type or show_briefing_again, currently returns beforeAction, the model's own generated prose, completely unmodified, as the actual displayed chat message. Confirm this is the exact code path responsible for messages like "Sending a magic-link to Robert & Carol Tanner now," confirmed live tonight by a browser audit to still occur roughly one in three times despite an existing prompt rule explicitly forbidding this phrasing. Confirm the existing modalLabel lookup pattern already used elsewhere in this file for status messages, to match its exact style for the new lookup table.

WHAT THIS IS:

This is the fourth attempt at this exact problem tonight, and the first three, all prompt wording changes, have now been proven insufficient by direct live evidence: a live browser audit found the model still claiming a send action was actively happening even after the existing rule was added earlier this session. This matches the core lesson proven repeatedly tonight, a natural language instruction cannot guarantee compliance for anything that must never fail. The fix is to stop trusting the model's own wording for this specific, narrow case entirely. The model continues to reliably decide what action to take and what modal to open, that part already works correctly, but the human-readable sentence describing a navigate-and-open action will now be deterministically substituted from a fixed, honest, pre-written lookup table, removing the model's discretion over the one part of its response that has repeatedly proven unreliable.

CHANGE INSTRUCTIONS:

Add a new constant near the top of this file or directly above handleConciergeAction, for example _NAVIGATE_OPEN_MESSAGES, a lookup table keyed by modal name, matching the exact object-literal style already used for modalLabel elsewhere in this file. Include real, honest, specific entries for every modal value already used in this codebase: new-client, new-engagement, invite-staff, new-template, and portal-magic-link, each describing only what is about to happen, navigating and opening the right place, never claiming a send, creation, or save has occurred. For portal-magic-link specifically, do not attempt to interpolate a client name into the sentence, keep it generic but honest, for example "Navigating to the client's page and opening the magic-link dialog." Include a safe, generic fallback string for any modal not present in the table, for example "Opening that for you now," never a claim of completion.

In handleConciergeAction's final return path, the one currently returning beforeAction unconditionally after autopilot is confirmed on, change this so that when action.type equals navigate-and-open and action.modal is present, the function returns the corresponding entry from the new lookup table instead of beforeAction, completely discarding the model's own generated text for this specific case. When action.type is navigate-and-open but action.modal is absent, meaning a plain navigation with no modal, or when action.type is anything else entirely, continue returning beforeAction exactly as today, this override applies only to the specific case that has proven unreliable. Do not change the set_firm_type or show_briefing_again branches, and do not change the autopilot-off branch, both are already correct and unaffected by this problem.

VERIFY AFTER ACT:

grep -n "_NAVIGATE_OPEN_MESSAGES" /home/corby/jamm-os/frontend/src/components/concierge/ConciergePanel.tsx

npx tsc --noEmit

MANUAL VERIFICATION:

Restart the frontend.

With Autopilot on, ask the Concierge to send a specific client's portal link three times in a row, the same repeated test used earlier tonight. Confirm all three responses now show the exact same deterministic sentence from the lookup table, word for word identical each time, never a claim that anything was sent, created, or saved.

Separately, ask it to create a new client, confirming a second, different navigate-and-open case also now shows its correct, fixed, honest sentence, not the model's own generated text.

Confirm the set_firm_type onboarding flow, the show_briefing_again flow, and any plain navigation with no modal, for example asking it to go to the Billing page, all still work and display exactly as they did before this change, confirming the override is correctly scoped only to the one failure case.

Report pass or fail for each of these checks individually, since this is meant to permanently close a problem that has already survived three prior attempts tonight, and deserves real confidence before being called done.

GIT:

git add -A

git commit -m "deterministically override the pre-action message for navigate-and-open actions, ending the model's discretion over the one part of its response proven unreliable three separate times tonight, claims that a send, creation, or save has already completed; a live browser audit tonight confirmed this still occurred roughly one in three times despite an existing prompt rule forbidding it, so the fixed, honest sentence is now pulled from a deterministic lookup table by modal name instead of ever trusting the model's own generated wording for this specific, narrow case, while the model continues to reliably control which action and modal actually fire"

git pull --rebase origin main

git push origin main