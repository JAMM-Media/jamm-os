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

TASK: Fix task count including completed and archived engagements, and fix Autopilot navigating to Settings instead of the real Staff page

USE: claude sonnet

VERIFY BEFORE ACT:
sed -n '897,935p' /home/corby/jamm-os/app/api/concierge/functions.py
grep -n "invite-staff" /home/corby/jamm-os/app/api/concierge/prompts.py

Confirm both match exactly what is described below before editing. These are two independent, unrelated fixes in different files, verify each on its own before touching either.

WHAT IS WRONG, PART ONE:

get_task_status counts incomplete tasks with no filter on the engagement's status at all, meaning a task belonging to a completed or archived engagement is still counted as an active outstanding task. This is the same category of bug already found and fixed once tonight between get_task_status and get_qc_checklist_status, where two tools counted the same underlying concept differently, this time affecting the raw task count itself against what a firm owner would expect to see as genuinely outstanding work. Confirmed as a real, live discrepancy during a deep audit comparing the reported task count against the real count on the actual Tasks page.

CHANGE INSTRUCTIONS, PART ONE:

Add a join to Engagement in the incomplete tasks query in get_task_status, if one is not already effectively present through the existing engagement_id relationship, and add a filter excluding tasks whose engagement status is completed or archived, matching the exact same status.notin_(["completed", "archived"]) pattern already used correctly elsewhere in this file, such as in get_qc_checklist_status.

WHAT IS WRONG, PART TWO:

Every existing CONCIERGE_ACTION example in the system prompt involving staff uses the route /settings with an invite-staff modal, since that was the only staff-related example ever written. There is no example showing simple navigation to view the real Staff page. Confirmed live: asking Autopilot to take me to the staff page navigated to Settings, opening the invite staff modal, instead of the real Staff page at /staff, since the model had no better example to follow.

CHANGE INSTRUCTIONS, PART TWO:

Add a new CONCIERGE_ACTION example directly alongside the existing staff-related one, showing plain navigation to view the staff page: CONCIERGE_ACTION: {"type":"navigate","route":"/staff"}, used when the firm owner wants to simply view or go to the staff roster, distinct from the existing invite-staff example, which should remain for when the firm owner specifically wants to invite a new staff member.

VERIFY AFTER ACT:

grep -n "status.notin_" /home/corby/jamm-os/app/api/concierge/functions.py

Confirm get_task_status now appears alongside the other tools already using this pattern.

grep -n "\"route\":\"/staff\"" /home/corby/jamm-os/app/api/concierge/prompts.py

Expected: present.

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import get_task_status
db = SessionLocal()
result = get_task_status('185314c9-e702-4eab-8600-249848022206', db)
print('incomplete_tasks:', result['incomplete_tasks'])
db.close()
"

Paste this real output and compare it manually against the real count shown on the actual Tasks page in the app.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. Ask what tasks are overdue right now, confirm the count now matches the real Tasks page count exactly.

Restart frontend. Turn on Autopilot, ask it to take you to the staff page, confirm it now navigates directly to the real /staff page, not Settings.

Report pass or fail for both, including the exact before and after counts for the task fix.

GIT:
git add -A
git commit -m "fix get_task_status counting tasks from completed and archived engagements as outstanding, matching the status exclusion pattern already used correctly elsewhere, and add a plain navigate-to-staff-page CONCIERGE_ACTION example so Autopilot stops defaulting to the invite-staff modal under Settings when the firm owner just wants to view the real Staff page"
git pull --rebase origin main
git push origin main