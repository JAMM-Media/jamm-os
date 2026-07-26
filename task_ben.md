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

TASK: Stop the Concierge from claiming a send/create action is complete when a navigate-and-open CONCIERGE_ACTION only navigates and opens a modal

USE: claude sonnet

VERIFY BEFORE ACT:

sed -n '900,940p' /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm the CONCIERGE_ACTION rules section currently has no instruction governing what the required human-readable sentence (line 938's rule) is allowed to claim about the action's completion status, before editing.

WHAT THIS IS:

Confirmed live: with Autopilot on, asking the Concierge to send a client their portal link produced the response "Sending Robert & Carol Tanner their portal magic-link now." The actual navigate-and-open action for modal magic-link (being fixed separately, in a different task, to portal-magic-link) only switches tabs, highlights the send button for 3 seconds, and scrolls it into view. It never calls a send API. No CONCIERGE_ACTION type in this system performs a send, create, or any other business action directly, confirmed by reading every handled action.type case in the frontend. The required human-readable sentence before every CONCIERGE_ACTION (rule at line 938) has no constraint on what it may claim, so the model reasonably but incorrectly phrased a navigation action using send-completed language, because the trigger phrase itself was "send a magic-link." This is a systemic gap, not specific to the magic-link case, since the same rule applies to every navigate-and-open example in this section (new-client, new-engagement, invite-staff, new-template).

CHANGE INSTRUCTIONS:

In the "Rules for emitting CONCIERGE_ACTION" section, add one new rule stating plainly that the required human-readable sentence must describe what is about to happen (taking the user to the right place, opening the right modal or form) and must never claim that a send, creation, save, or any other business action has already completed, since navigate-and-open only navigates and opens, it never performs the underlying action itself. Do not rewrite any of the existing few-shot examples' CONCIERGE_ACTION JSON lines, this task only adds a new prose rule governing the sentence that precedes them. Do not change the set_firm_type exception rule already present at line 939.

VERIFY AFTER ACT:

grep -n "never claim\|already completed\|about to happen" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: the new rule is present and readable in context.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart the backend.

With Autopilot on, ask the Concierge to send a specific client their portal link.

Read the human-readable sentence before the action fires. Confirm it describes navigating to or opening the right place, not that a link has already been sent. Note: the ring highlight itself will still not fire yet, since that fix is separate and not yet applied — this check is only about the wording of the sentence.

Separately, ask the Concierge to create a new client, confirming the same corrected phrasing pattern holds for a second, different navigate-and-open example, not just the one that was directly tested.

Report the exact response text for both, pass or fail on whether either one overclaims completion.

GIT:

git add -A

git commit -m "add a rule governing the required human-readable sentence before every CONCIERGE_ACTION, so the Concierge stops claiming a send, create, or save action is already complete when the action itself only navigates and opens a modal, confirmed live tonight with the portal magic-link case claiming a link was sent when nothing was ever sent"

git pull --rebase origin main

git push origin main