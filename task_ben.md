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

TASK: Fix get_stalled_engagements including completed and archived engagements as stalled

USE: claude sonnet

VERIFY BEFORE ACT:
grep -n "def get_stalled_engagements" -A 30 /home/corby/jamm-os/app/api/concierge/functions.py

Confirm the current query filters only on Engagement.updated_at with no status exclusion at all.

WHAT IS WRONG:

Confirmed live: engagements marked completed are appearing in the stalled engagements list, since the query only checks how long ago an engagement was last updated, with no exclusion for engagements that are already finished. This is conceptually different from an earlier decision made tonight about tasks remaining visible regardless of their parent engagement's status, that case involved individual real tasks still being genuinely incomplete. This case is different: stalled describes whether an engagement itself is failing to move forward, and a completed engagement is not supposed to be moving forward at all, there is nothing being neglected, so including it as stalled is simply incorrect, not a judgment call.

CHANGE INSTRUCTIONS:

Add a filter excluding engagements with status completed or archived, matching the exact status.notin_(["completed", "archived"]) pattern already used correctly elsewhere in this file, such as in get_qc_checklist_status.

VERIFY AFTER ACT:

python3 -c "
from app.db.session import SessionLocal
from app.api.concierge.functions import get_stalled_engagements
db = SessionLocal()
result = get_stalled_engagements('185314c9-e702-4eab-8600-249848022206', db)
for e in result['stalled']:
    print(e['client_name'], e['engagement_name'], e['status'], e['days_stalled'])
db.close()
"

Expected: no entry in this output has status completed or archived. Paste this real output.

python3 -c "from app.main import app; print('OK')"

MANUAL VERIFICATION:

Restart backend. Ask is there any stalled engagements, confirm every engagement listed now genuinely has an active, in_review, planning, or draft status, none marked completed or archived.

Report pass or fail.

GIT:
git add -A
git commit -m "fix get_stalled_engagements including completed and archived engagements, since stalled describes whether an engagement is failing to move forward and a finished engagement is not supposed to be moving forward at all, confirmed live via a real question returning several completed engagements incorrectly flagged as stalled"
git pull --rebase origin main
git push origin main